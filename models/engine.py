"""
Motor de Predicción – Núcleo del Sistema
==========================================
Implementa:
  1. Modelo de Distribución de Poisson con corrección Dixon-Coles
  2. Regresión Logística (resultado G/E/P)
  3. Calibración de probabilidades (Platt Scaling)
  4. Detector de Value Bets (edge = P_modelo - P_implícita)
  5. Criterio de Kelly Fraccionado (sizing de apuesta)
"""

import math
import warnings
import numpy as np
import pandas as pd
from scipy.stats import poisson
from scipy.optimize import minimize
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import cross_val_score
from sklearn.metrics import accuracy_score, log_loss
import pickle
from pathlib import Path

warnings.filterwarnings("ignore")
MODELS_DIR = Path(__file__).parent.parent / "models"
MODELS_DIR.mkdir(exist_ok=True)

from data.fetcher import TEAMS_DB
from data.team_names import canon_team

# ───────────────────────────────────────────────────────────────
# Elo de selecciones nacionales (Mundial 2026)
# ───────────────────────────────────────────────────────────────
# El modelo Poisson/LogReg esta entrenado con ligas de CLUBES, no selecciones.
# Para el Mundial usamos el Elo de cada seleccion (World Football Elo, eloratings.net)
# para derivar los lambdas. Top-20 anclado a datos enero 2026; el resto, estimaciones
# por nivel conocido. Cualquier seleccion no listada cae a un Elo neutro-bajo (1550).
WORLD_CUP_ELO = {
    # Top tier (Elo confirmado ene-2026)
    "Spain": 2171, "Argentina": 2113, "France": 2063, "England": 2042,
    "Colombia": 1998, "Brazil": 1979, "Portugal": 1976, "Netherlands": 1959,
    "Croatia": 1933, "Ecuador": 1933, "Norway": 1922, "Germany": 1910,
    "Switzerland": 1897, "Uruguay": 1890, "Japan": 1879, "Senegal": 1869,
    "Denmark": 1864, "Belgium": 1849,
    # Tier medio-alto (estimaciones)
    "Morocco": 1845, "Serbia": 1800, "South Korea": 1800, "Korea Republic": 1800,
    "Austria": 1795, "Mexico": 1790, "Poland": 1775, "Iran": 1760, "USA": 1760,
    "United States": 1760, "Scotland": 1755, "Algeria": 1750, "Paraguay": 1745,
    "Nigeria": 1740, "Ivory Coast": 1730, "Canada": 1730, "Australia": 1725,
    "Peru": 1720, "Egypt": 1715, "Cameroon": 1705, "Venezuela": 1700,
    # Tier medio (estimaciones)
    "Ghana": 1695, "Tunisia": 1690, "Panama": 1670, "Qatar": 1660, "Mali": 1660,
    "Costa Rica": 1655, "South Africa": 1655, "Saudi Arabia": 1640,
    "Cape Verde": 1635, "Uzbekistan": 1620, "DR Congo": 1620, "Honduras": 1565,
    "Iraq": 1560, "Jamaica": 1585, "Jordan": 1550,
    # Tier bajo (estimaciones)
    "Curacao": 1505, "Curaçao": 1505, "New Zealand": 1500, "Haiti": 1500,
    "Bolivia": 1500,
}
WC_GOALS_TOTAL = 2.60    # goles totales esperados por partido (controla Over/Under, estable)
WC_ELO_KS      = 0.0050  # supremacia (lambda_h - lambda_a) por cada punto de diferencia de Elo
WC_SUP_MAX     = 2.40    # tope de supremacia (evita lambdas extremos)
WC_LAMBDA_MIN  = 0.18    # piso de lambda

# Cobertura minima: partidos de entrenamiento que necesita CADA equipo para que
# el modelo emita alertas. Por debajo, los parametros son poco fiables -> edge = ruido.
MIN_TEAM_MATCHES = 20
WC_ELO_DEFAULT = 1550    # Elo para selecciones no listadas


def wc_elo_lookup(team: str) -> int:
    """Devuelve el Elo de una seleccion (match exacto, luego case-insensitive, luego default)."""
    key = (team or "").strip()
    if key in WORLD_CUP_ELO:
        return WORLD_CUP_ELO[key]
    low = key.lower()
    for k, v in WORLD_CUP_ELO.items():
        if k.lower() == low:
            return v
    return WC_ELO_DEFAULT


def dixon_coles_tau(x: int, y: int, lambda_h: float, lambda_a: float, rho: float) -> float:
    """
    Factor de corrección Dixon-Coles (τ) para resultados de pocos goles.
    Corrige la independencia entre goles locales y visitantes para:
      0-0, 1-0, 0-1, 1-1
    Para el resto de resultados τ = 1 (sin corrección).
    rho < 0 → correlación negativa (resultados bajos más frecuentes de lo que Poisson predice)
    rho típico: entre -0.1 y -0.2
    """
    if x == 0 and y == 0:
        return 1 - lambda_h * lambda_a * rho
    elif x == 1 and y == 0:
        return 1 + lambda_a * rho
    elif x == 0 and y == 1:
        return 1 + lambda_h * rho
    elif x == 1 and y == 1:
        return 1 - rho
    else:
        return 1.0


class PoissonModel:
    """
    Modelo de Dixon-Coles completo.
    Estima parámetros de ataque y defensa por equipo usando MLE iterativo,
    y aplica la corrección Dixon-Coles (factor τ con parámetro ρ) para
    corregir la sobreestimación de resultados bajos (0-0, 1-0, 0-1, 1-1).

    Variables adicionales integradas:
      - Forma reciente (últimos N partidos): ajusta lambdas según rendimiento reciente
      - H2H (historial directo): sesgo basado en victorias históricas entre los dos equipos
    """

    def __init__(self):
        self.attack_params  = {}
        self.defense_params = {}
        self.home_advantage = 0.0
        self.league_avg     = {}
        self.rho            = -0.13
        self.is_fitted      = False
        self.team_n         = {}   # partidos de entrenamiento por equipo
        self.team_league    = {}   # liga de entrenamiento mas reciente de cada equipo
        # Historial completo para forma reciente y H2H
        self._df_history: pd.DataFrame | None = None

    def _expected_goals(self, home: str, away: str, league: str) -> tuple[float, float]:
        avg = self.league_avg.get(league, 1.35)
        att_h = self.attack_params.get(home, 1.0)
        def_h = self.defense_params.get(home, 1.0)
        att_a = self.attack_params.get(away, 1.0)
        def_a = self.defense_params.get(away, 1.0)
        lambda_h = att_h * def_a * avg * math.exp(self.home_advantage)
        lambda_a = att_a * def_h * avg
        return lambda_h, lambda_a

    def _estimate_rho(self, df: pd.DataFrame) -> float:
        """
        Estima el parámetro ρ (rho) de Dixon-Coles maximizando la log-verosimilitud
        de los 4 resultados bajos con los lambdas ya estimados.
        """
        if not self.is_fitted or len(df) < 50:
            return -0.13

        low = df[(df["home_goals"] <= 1) & (df["away_goals"] <= 1)]
        if len(low) == 0:
            return -0.13
        lams = np.array([self._expected_goals(r["home_team"], r["away_team"], r["league"])
                         for _, r in low.iterrows()])
        lh, la = lams[:, 0], lams[:, 1]
        x = low["home_goals"].to_numpy()
        y = low["away_goals"].to_numpy()
        base = np.log(poisson.pmf(x, lh)) + np.log(poisson.pmf(y, la))

        def neg_log_likelihood(rho_val):
            r = rho_val[0]
            tau = np.where((x == 0) & (y == 0), 1 - lh * la * r,
                  np.where((x == 0) & (y == 1), 1 + lh * r,
                  np.where((x == 1) & (y == 0), 1 + la * r, 1 - r)))
            if np.any(tau <= 0):
                return 1e10
            return -float(np.sum(base + np.log(tau)))

        result = minimize(neg_log_likelihood, x0=[-0.13],
                         bounds=[(-0.4, 0.0)], method="L-BFGS-B")
        rho_estimated = float(result.x[0])
        print(f"[Dixon-Coles] ρ estimado: {rho_estimated:.4f}")
        return rho_estimated

    def fit(self, df: pd.DataFrame):
        print("[Poisson] Estimando parámetros por equipo (iterativo)...")

        for league, grp in df.groupby("league"):
            self.league_avg[league] = (grp["home_goals"].mean() + grp["away_goals"].mean()) / 2

        teams = sorted(set(df["home_team"]) | set(df["away_team"]))
        self.team_n = {
            str(k): int(v) for k, v in
            pd.concat([df["home_team"], df["away_team"]]).value_counts().items()
        }
        # Liga mas reciente de cada equipo (df viene ordenado por fecha)
        self.team_league = {}
        for _, r in df[["home_team", "away_team", "league"]].iterrows():
            self.team_league[r["home_team"]] = r["league"]
            self.team_league[r["away_team"]] = r["league"]

        home_avg = df["home_goals"].mean()
        away_avg = df["away_goals"].mean()
        self.home_advantage = math.log(home_avg / away_avg) / 2 if away_avg > 0 else 0.1

        # ── Ajuste iterativo vectorizado (misma formula que antes, mucho mas rapido) ──
        idx = {t: i for i, t in enumerate(teams)}
        hi  = df["home_team"].map(idx).to_numpy()
        ai  = df["away_team"].map(idx).to_numpy()
        hg  = df["home_goals"].to_numpy(dtype=float)
        ag  = df["away_goals"].to_numpy(dtype=float)
        lav = df["league"].map(lambda l: self.league_avg.get(l, 1.35)).to_numpy(dtype=float)
        eh  = math.exp(self.home_advantage)
        nt  = len(teams)
        scored   = np.bincount(hi, hg, nt) + np.bincount(ai, ag, nt)
        conceded = np.bincount(hi, ag, nt) + np.bincount(ai, hg, nt)
        att  = np.ones(nt)
        deff = np.ones(nt)

        for iteration in range(50):
            # goles esperados a favor (sin el att propio) y en contra (sin la def propia)
            exp_for = (np.bincount(hi, deff[ai] * lav * eh, nt) +
                       np.bincount(ai, deff[hi] * lav, nt))
            exp_ag  = (np.bincount(hi, att[ai] * lav, nt) +
                       np.bincount(ai, att[hi] * lav * eh, nt))
            new_att  = scored   / (exp_for + 1e-6)
            new_deff = conceded / (exp_ag  + 1e-6)
            new_att  /= new_att.mean()
            new_deff /= new_deff.mean()
            delta = max(np.abs(new_att - att).max(), np.abs(new_deff - deff).max())
            att, deff = new_att, new_deff
            if iteration > 5 and delta < 1e-5:
                break

        att  = {t: float(att[i])  for t, i in idx.items()}
        deff = {t: float(deff[i]) for t, i in idx.items()}

        self.attack_params  = att
        self.defense_params = deff
        self.is_fitted      = True
        # Guardar historial para forma reciente y H2H
        self._df_history    = df.copy()
        self._build_history_index()
        print(f"[Poisson] OK en {iteration+1} iteraciones. Home advantage: {self.home_advantage:.3f}")

        self.rho = self._estimate_rho(df)

    def _build_history_index(self):
        """Indices por equipo y por cruce sobre el historial, para que forma y H2H
        no filtren el DataFrame completo en cada prediccion."""
        df = self._df_history.reset_index(drop=True)
        self._df_history = df
        self._hg = df["home_goals"].to_numpy()
        self._ag = df["away_goals"].to_numpy()
        self._idx_home = {k: v for k, v in df.groupby("home_team").indices.items()}
        self._idx_away = {k: v for k, v in df.groupby("away_team").indices.items()}
        self._idx_pair = {k: v for k, v in df.groupby(["home_team", "away_team"]).indices.items()}
        self._global_scored_avg = (df["home_goals"].mean() + df["away_goals"].mean()) / 2 or 1.3

    def _ensure_index(self):
        if not hasattr(self, "_idx_home") and self._df_history is not None:
            self._build_history_index()

    def get_recent_form(self, team: str, n: int = 5) -> dict:
        """
        Calcula la forma reciente de un equipo en los últimos N partidos.
        Retorna:
          - goals_scored_avg:   promedio de goles marcados
          - goals_conceded_avg: promedio de goles encajados
          - win_rate:           % de victorias
          - form_factor_att:    multiplicador de ataque (>1 = mejor forma, <1 = peor)
          - form_factor_def:    multiplicador de defensa (>1 = peor defensa, <1 = mejor)
          - n_matches:          partidos encontrados
        """
        if self._df_history is None or len(self._df_history) == 0:
            return {"form_factor_att": 1.0, "form_factor_def": 1.0, "n_matches": 0}

        self._ensure_index()
        hi = self._idx_home.get(team, np.array([], dtype=int))[-n:]   # ultimos n como local
        ai = self._idx_away.get(team, np.array([], dtype=int))[-n:]   # ultimos n como visitante
        scored   = list(self._hg[hi]) + list(self._ag[ai])
        conceded = list(self._ag[hi]) + list(self._hg[ai])
        wins = int((self._hg[hi] > self._ag[hi]).sum() + (self._ag[ai] > self._hg[ai]).sum())

        total = len(scored)
        if total == 0:
            return {"form_factor_att": 1.0, "form_factor_def": 1.0, "n_matches": 0}

        scored_avg   = np.mean(scored)
        conceded_avg = np.mean(conceded)
        win_rate     = wins / total

        # Forma relativa a la media global del historial
        global_scored_avg = self._global_scored_avg

        # Factor de ataque: cuánto mejor/peor convierte respecto a la media
        form_factor_att = np.clip(scored_avg / global_scored_avg, 0.7, 1.4)
        # Factor de defensa: cuánto más/menos encaja (invertido: menos goles = mejor)
        form_factor_def = np.clip(global_scored_avg / (conceded_avg + 0.1), 0.7, 1.4)

        return {
            "goals_scored_avg":   round(float(scored_avg), 2),
            "goals_conceded_avg": round(float(conceded_avg), 2),
            "win_rate":           round(float(win_rate), 3),
            "form_factor_att":    round(float(form_factor_att), 4),
            "form_factor_def":    round(float(form_factor_def), 4),
            "n_matches":          total,
        }

    def get_h2h_factor(self, home: str, away: str, n: int = 10) -> dict:
        """
        Calcula el factor H2H (historial directo) entre dos equipos.
        Considera los últimos N enfrentamientos (en cualquier condición).
        Retorna:
          - home_win_rate:    % que ganó el equipo local en estos H2H
          - away_win_rate:    % que ganó el equipo visitante en estos H2H
          - draw_rate:        % de empates
          - avg_goals_home:   promedio de goles del equipo local en H2H
          - avg_goals_away:   promedio de goles del equipo visitante en H2H
          - h2h_bias_home:    factor multiplicador para lambda_home (>1 favorece local)
          - h2h_bias_away:    factor multiplicador para lambda_away (>1 favorece visitante)
          - n_matches:        partidos H2H encontrados
        """
        if self._df_history is None or len(self._df_history) == 0:
            return {"h2h_bias_home": 1.0, "h2h_bias_away": 1.0, "n_matches": 0}

        self._ensure_index()
        empty = np.array([], dtype=int)
        di = self._idx_pair.get((home, away), empty)[-n:]   # directos
        ri = self._idx_pair.get((away, home), empty)[-n:]   # inversos ("home" fue visitante)
        goals_home = list(self._hg[di]) + list(self._ag[ri])
        goals_away = list(self._ag[di]) + list(self._hg[ri])
        gh, ga = np.array(goals_home), np.array(goals_away)
        home_wins = int((gh > ga).sum())
        away_wins = int((gh < ga).sum())
        draws     = int((gh == ga).sum())

        total = len(goals_home)
        if total == 0:
            return {"h2h_bias_home": 1.0, "h2h_bias_away": 1.0, "n_matches": 0}

        home_wr = home_wins / total
        away_wr = away_wins / total
        draw_r  = draws / total

        avg_gh = np.mean(goals_home)
        avg_ga = np.mean(goals_away)

        # Bias: si el equipo local domina el H2H, sus lambdas suben levemente
        # Escala suave: máx ±15%
        h2h_bias_home = np.clip(1.0 + (home_wr - away_wr) * 0.3, 0.85, 1.15)
        h2h_bias_away = np.clip(1.0 + (away_wr - home_wr) * 0.3, 0.85, 1.15)

        return {
            "home_win_rate":  round(float(home_wr), 3),
            "away_win_rate":  round(float(away_wr), 3),
            "draw_rate":      round(float(draw_r), 3),
            "avg_goals_home": round(float(avg_gh), 2),
            "avg_goals_away": round(float(avg_ga), 2),
            "h2h_bias_home":  round(float(h2h_bias_home), 4),
            "h2h_bias_away":  round(float(h2h_bias_away), 4),
            "n_matches":      total,
        }

    def _elo_expected_goals(self, home: str, away: str) -> tuple[float, float]:
        """
        Lambdas para selecciones nacionales (Mundial) a partir del Elo de AMBOS equipos.
        Sin ventaja de local (sede neutral): solo cuenta la diferencia de fuerza.
        Modelo aditivo: total de goles fijo (Over/Under estable) y supremacia desde el Elo
        (controla quien gana). Asi una diferencia de Elo grande NO infla los goles totales.
        """
        elo_h = wc_elo_lookup(home)
        elo_a = wc_elo_lookup(away)
        s = (elo_h - elo_a) * WC_ELO_KS
        s = float(np.clip(s, -WC_SUP_MAX, WC_SUP_MAX))
        lambda_h = max(WC_LAMBDA_MIN, WC_GOALS_TOTAL / 2 + s / 2)
        lambda_a = max(WC_LAMBDA_MIN, WC_GOALS_TOTAL / 2 - s / 2)
        return round(lambda_h, 3), round(lambda_a, 3)

    def predict_proba(self, home: str, away: str, league: str,
                       max_goals: int = 8,
                       use_form: bool = True,
                       use_h2h: bool = True,
                       form_weight: float = 0.25,
                       h2h_weight: float = 0.15) -> dict:
        # Nombres de The Odds API -> nombres de football-data (los del entrenamiento)
        home, away = canon_team(home), canon_team(away)
        # Si ambos equipos entrenaron en la misma liga, usamos esa liga para el promedio
        # de goles (cubre copas como Libertadores/Champions entre equipos de la misma liga)
        lg_h = getattr(self, "team_league", {}).get(home)
        lg_a = getattr(self, "team_league", {}).get(away)
        same_league = lg_h is not None and lg_h == lg_a
        model_league = lg_h if same_league else league

        if league == "Mundial 2026":
            # Seleccion nacional: lambdas desde el Elo de ambos equipos (sede neutral, sin ventaja de local)
            lambda_h, lambda_a = self._elo_expected_goals(home, away)
        else:
            # Equipo no entrenado -> parametros neutros (1.0) solo para ese equipo;
            # el rival conserva sus parametros reales. model_coverage marca el caso.
            lambda_h, lambda_a = self._expected_goals(home, away, model_league)

        # ── Forma reciente ──────────────────────────────────────────────────
        form_home = {"form_factor_att": 1.0, "form_factor_def": 1.0, "n_matches": 0}
        form_away = {"form_factor_att": 1.0, "form_factor_def": 1.0, "n_matches": 0}
        if use_form:
            form_home = self.get_recent_form(home, n=5)
            form_away = self.get_recent_form(away, n=5)

            # Ajuste: forma afecta lambdas con peso form_weight
            # lambda_home sube si el local ataca bien Y el visitante defiende mal
            form_mult_h = (
                1.0 * (1 - form_weight) +
                form_home["form_factor_att"] * form_away["form_factor_def"] * form_weight
            )
            form_mult_a = (
                1.0 * (1 - form_weight) +
                form_away["form_factor_att"] * form_home["form_factor_def"] * form_weight
            )
            lambda_h *= form_mult_h
            lambda_a *= form_mult_a

        # ── H2H ────────────────────────────────────────────────────────────
        h2h = {"h2h_bias_home": 1.0, "h2h_bias_away": 1.0, "n_matches": 0}
        if use_h2h:
            h2h = self.get_h2h_factor(home, away, n=10)

            # Ajuste: H2H sesga lambdas con peso h2h_weight (solo si hay suficientes partidos)
            if h2h["n_matches"] >= 3:
                lambda_h *= (1.0 * (1 - h2h_weight) + h2h["h2h_bias_home"] * h2h_weight)
                lambda_a *= (1.0 * (1 - h2h_weight) + h2h["h2h_bias_away"] * h2h_weight)

        # ── Clima ───────────────────────────────────────────────────────────
        weather_data = {"available": False}
        weather_factor = 1.0
        try:
            from data.weather import get_weather_for_league, weather_lambda_factor
            weather_data   = get_weather_for_league(league)
            weather_factor = weather_lambda_factor(weather_data)
            if weather_factor != 1.0:
                lambda_h *= weather_factor
                lambda_a *= weather_factor
        except Exception:
            pass  # Si falla el clima, continua sin ajuste

        # ── Score matrix (Dixon-Coles) ──────────────────────────────────────
        goals = np.arange(max_goals + 1)
        score_matrix = np.outer(poisson.pmf(goals, lambda_h), poisson.pmf(goals, lambda_a))
        for i in (0, 1):
            for j in (0, 1):
                score_matrix[i, j] *= dixon_coles_tau(i, j, lambda_h, lambda_a, self.rho)

        total = score_matrix.sum()
        if total > 0:
            score_matrix /= total

        p_home = float(np.sum(np.tril(score_matrix, -1)))
        p_draw = float(np.sum(np.diag(score_matrix)))
        p_away = float(np.sum(np.triu(score_matrix, 1)))

        p_over25 = float(score_matrix[np.add.outer(goals, goals) > 2].sum())
        p_under25 = 1.0 - p_over25

        team_n = getattr(self, "team_n", {}) or {}
        n_h = int(team_n.get(home, 0))
        n_a = int(team_n.get(away, 0))
        model_coverage = {
            "home_n":       n_h,
            "away_n":       n_a,
            "min_required": MIN_TEAM_MATCHES,
            "same_league":  same_league,
            "model_league": model_league if same_league else None,
            "ok":           (n_h >= MIN_TEAM_MATCHES and n_a >= MIN_TEAM_MATCHES
                             and same_league),
        }

        total_1x2 = p_home + p_draw + p_away
        return {
            "model_coverage": model_coverage,
            "p_home":      round(p_home / total_1x2, 4),
            "p_draw":      round(p_draw / total_1x2, 4),
            "p_away":      round(p_away / total_1x2, 4),
            "p_over25":    round(p_over25, 4),
            "p_under25":   round(p_under25, 4),
            "lambda_home": round(lambda_h, 3),
            "lambda_away": round(lambda_a, 3),
            "rho":         round(self.rho, 4),
            # Variables adicionales (para UI y debugging)
            "form_home":     form_home,
            "form_away":     form_away,
            "h2h":           h2h,
            "weather":       weather_data,
            "weather_factor": round(weather_factor, 4),
        }

    def save(self):
        with open(MODELS_DIR / "poisson_model.pkl", "wb") as f:
            pickle.dump(self, f)

    @classmethod
    def load(cls):
        path = MODELS_DIR / "poisson_model.pkl"
        if path.exists():
            with open(path, "rb") as f:
                return pickle.load(f)
        return cls()


class LogisticModel:
    """
    Regresión Logística multi-clase (H/D/A) con features contextuales.
    Complementa al modelo Poisson capturando factores no reflejados en goles.
    """

    def __init__(self):
        self.model   = LogisticRegression(max_iter=1000, C=0.8, solver="lbfgs")
        self.scaler  = StandardScaler()
        self.is_fitted = False

    def _build_features(self, df: pd.DataFrame) -> np.ndarray:
        features = []
        for _, row in df.iterrows():
            elo_diff = row.get("home_elo", 1700) - row.get("away_elo", 1700)
            home_td  = TEAMS_DB.get(row["home_team"], {"att": 1.2, "def": 1.1})
            away_td  = TEAMS_DB.get(row["away_team"], {"att": 1.2, "def": 1.1})
            features.append([
                elo_diff / 400,
                row.get("lambda_home", home_td["att"]),
                row.get("lambda_away", away_td["att"]),
                home_td["att"] - away_td["att"],
                home_td["def"] - away_td["def"],
                home_td["att"] * away_td["def"],
                # Variables adicionales: forma reciente y H2H (si están presentes)
                float(row.get("form_att_home", 1.0)),
                float(row.get("form_att_away", 1.0)),
                float(row.get("h2h_home_wr", 0.33)),
                float(row.get("h2h_away_wr", 0.33)),
            ])
        return np.array(features)

    def fit(self, df: pd.DataFrame):
        print("[LogReg] Entrenando con {} partidos...".format(len(df)))
        X = self._build_features(df)
        y = df["result"].values
        X_scaled = self.scaler.fit_transform(X)
        y = np.array(y)
        cv_scores = cross_val_score(self.model, X_scaled, y, cv=5, scoring="accuracy")
        self.model.fit(X_scaled, y)
        self.is_fitted = True
        print(f"[LogReg] CV Accuracy: {cv_scores.mean():.3f} ± {cv_scores.std():.3f}")

    def predict_proba(self, home: str, away: str,
                       lambda_home: float, lambda_away: float,
                       form_att_home: float = 1.0, form_att_away: float = 1.0,
                       h2h_home_wr: float = 0.33, h2h_away_wr: float = 0.33) -> dict:
        if not self.is_fitted:
            return {}
        home_td = TEAMS_DB.get(home, {"att": 1.2, "def": 1.1, "elo": 1700})
        away_td = TEAMS_DB.get(away, {"att": 1.2, "def": 1.1, "elo": 1700})
        elo_diff = home_td.get("elo", 1700) - away_td.get("elo", 1700)
        X = np.array([[
            elo_diff / 400,
            lambda_home,
            lambda_away,
            home_td["att"] - away_td["att"],
            home_td["def"] - away_td["def"],
            home_td["att"] * away_td["def"],
            form_att_home,
            form_att_away,
            h2h_home_wr,
            h2h_away_wr,
        ]])
        X_scaled = self.scaler.transform(X)
        proba = self.model.predict_proba(X_scaled)[0]
        classes = list(self.model.classes_)
        return {
            "lr_p_home": round(proba[classes.index("H")] if "H" in classes else 0.33, 4),
            "lr_p_draw": round(proba[classes.index("D")] if "D" in classes else 0.33, 4),
            "lr_p_away": round(proba[classes.index("A")] if "A" in classes else 0.34, 4),
        }

    def save(self):
        with open(MODELS_DIR / "logistic_model.pkl", "wb") as f:
            pickle.dump(self, f)


class ProbabilityCalibrator:
    """
    Calibración de probabilidades usando Platt Scaling.
    Entrena una regresión logística encima de las probabilidades
    crudas del modelo para que reflejen frecuencias reales.

    Ejemplo: si el modelo dice 70% pero históricamente gana 58%,
    la calibración corrige ese gap.
    """

    def __init__(self):
        self.calibrators = {}
        self.is_fitted   = False

    def fit(self, proba_list: list[dict], results: list[str]):
        """
        proba_list: lista de dicts con p_home, p_draw, p_away (salida de PoissonModel)
        results:    lista de resultados reales ('H', 'D', 'A')
        """
        if len(proba_list) < 30:
            print("[Calibrator] Pocos datos, se usarán probabilidades sin calibrar.")
            return

        markets = {
            "H": ("p_home",  [1 if r == "H" else 0 for r in results]),
            "D": ("p_draw",  [1 if r == "D" else 0 for r in results]),
            "A": ("p_away",  [1 if r == "A" else 0 for r in results]),
        }

        for key, (prob_key, y) in markets.items():
            X = np.array([[p[prob_key]] for p in proba_list])
            y = np.array(y)
            if len(set(y)) < 2:
                continue
            cal = LogisticRegression(C=1.0, solver="lbfgs")
            cal.fit(X, y)
            self.calibrators[key] = (cal, prob_key)

        self.is_fitted = True
        print(f"[Calibrator] Calibrado con {len(proba_list)} partidos.")

    def calibrate(self, prediction: dict) -> dict:
        """
        Ajusta p_home, p_draw, p_away de una predicción.
        Normaliza para que sumen 1.
        """
        if not self.is_fitted or not self.calibrators:
            return prediction

        result = prediction.copy()
        raw = {}
        for key, (cal, prob_key) in self.calibrators.items():
            X = np.array([[prediction[prob_key]]])
            raw[key] = cal.predict_proba(X)[0][1]

        total = sum(raw.values()) or 1.0
        if "H" in raw:
            result["p_home"] = round(raw["H"] / total, 4)
        if "D" in raw:
            result["p_draw"] = round(raw["D"] / total, 4)
        if "A" in raw:
            result["p_away"] = round(raw["A"] / total, 4)

        result["calibrated"] = True
        return result

    def save(self):
        with open(MODELS_DIR / "calibrator.pkl", "wb") as f:
            pickle.dump(self, f)

    @classmethod
    def load(cls):
        path = MODELS_DIR / "calibrator.pkl"
        if path.exists():
            with open(path, "rb") as f:
                return pickle.load(f)
        return cls()


class ValueBetDetector:
    """
    Compara las probabilidades del modelo contra las cuotas del bookmaker
    para identificar apuestas con valor esperado positivo.
    """

    MIN_EDGE = 0.03
    MIN_ODD  = 1.50
    # Tope de cordura: un edge > 15% contra el mercado casi siempre es un error del
    # modelo (dato faltante, lesion, rotacion), no una oportunidad real.
    MAX_EDGE = 0.15

    def detect(self, prediction: dict, odds: dict, match: dict,
               closing_odds: dict = None) -> list[dict]:
        alerts = []
        markets = [
            ("1X2_H",    prediction["p_home"],   odds["odd_home"],    "Local gana",       "odd_home"),
            ("1X2_D",    prediction["p_draw"],   odds["odd_draw"],    "Empate",           "odd_draw"),
            ("1X2_A",    prediction["p_away"],   odds["odd_away"],    "Visitante gana",   "odd_away"),
            ("OVER25",   prediction["p_over25"], odds["odd_over25"],  "Over 2.5 goles",   "odd_over25"),
            ("UNDER25",  prediction["p_under25"],odds["odd_under25"], "Under 2.5 goles",  "odd_under25"),
        ]

        for market_id, p_model, odd, label, odd_key in markets:
            if odd < self.MIN_ODD:
                continue
            p_implied = 1 / odd
            edge      = p_model - p_implied

            if self.MIN_EDGE <= edge <= self.MAX_EDGE:
                kelly      = self._kelly(p_model, odd)
                ev         = round(p_model * (odd - 1) - (1 - p_model), 4)
                confidence = self._confidence_score(edge, p_model)

                # Closing Line Value
                clv_pct = None
                odd_closing = None
                if closing_odds and odd_key in closing_odds:
                    odd_closing = closing_odds[odd_key]
                    if odd_closing and odd_closing > 1.0:
                        clv_pct = round((odd / odd_closing - 1) * 100, 2)

                alerts.append({
                    "match_id":     match["match_id"],
                    "league":       match["league"],
                    "home_team":    match["home_team"],
                    "away_team":    match["away_team"],
                    "kickoff":      match.get("kickoff", "N/A"),
                    "market":       market_id,
                    "market_label": label,
                    "bookmaker":    odds["bookmaker"],
                    "bookmaker_name": odds.get("bookmaker_name", odds["bookmaker"]),
                    "bookmaker_url":  odds.get("bookmaker_url", ""),
                    "odd":          odd,
                    "odd_closing":  odd_closing,
                    "clv_pct":      clv_pct,
                    "p_model":      round(p_model, 4),
                    "p_implied":    round(p_implied, 4),
                    "edge_pct":     round(edge * 100, 2),
                    "ev":           ev,
                    "kelly_frac":   kelly,
                    "confidence":   confidence,
                    "lambda_home":  prediction.get("lambda_home", 0),
                    "lambda_away":  prediction.get("lambda_away", 0),
                    "rho":          prediction.get("rho", -0.13),
                    "calibrated":   prediction.get("calibrated", False),
                    # Variables adicionales para UI
                    "form_home":    match.get("form_home", {}),
                    "form_away":    match.get("form_away", {}),
                    "h2h":          match.get("h2h", {}),
                    "weather":      prediction.get("weather", {"available": False}),
                    "weather_factor": prediction.get("weather_factor", 1.0),
                })

        return sorted(alerts, key=lambda x: x["edge_pct"], reverse=True)

    def _kelly(self, p: float, odd: float, fraction: float = 0.5) -> float:
        b = odd - 1
        q = 1 - p
        f_full = (b * p - q) / b
        f_half = f_full * fraction
        return round(min(max(f_half, 0.0), 0.05), 4)

    def _confidence_score(self, edge: float, p_model: float) -> str:
        score = edge * 100 + p_model * 20
        if score >= 12:
            return "ALTA"
        elif score >= 7:
            return "MEDIA"
        else:
            return "BAJA"


class ArbitrageDetector:
    """
    Detecta oportunidades de arbitraje entre bookmakers.
    Existe arb cuando Σ(1/odd_i) < 1 entre distintas casas.
    """

    def detect_arb(self, odds_list: list[dict]) -> dict | None:
        if len(odds_list) < 2:
            return None

        best_home = max(odds_list, key=lambda x: x["odd_home"])
        best_draw = max(odds_list, key=lambda x: x["odd_draw"])
        best_away = max(odds_list, key=lambda x: x["odd_away"])

        margin = (1/best_home["odd_home"] + 1/best_draw["odd_draw"] + 1/best_away["odd_away"])

        if margin < 1.0:
            profit_pct = round((1 / margin - 1) * 100, 3)
            return {
                "type":       "ARBITRAGE",
                "margin":     round(margin, 4),
                "profit_pct": profit_pct,
                "bets": [
                    {"market": "Home", "bookmaker": best_home["bookmaker"],
                     "odd": best_home["odd_home"],
                     "stake_pct": round(100 / (margin * best_home["odd_home"]), 2)},
                    {"market": "Draw", "bookmaker": best_draw["bookmaker"],
                     "odd": best_draw["odd_draw"],
                     "stake_pct": round(100 / (margin * best_draw["odd_draw"]), 2)},
                    {"market": "Away", "bookmaker": best_away["bookmaker"],
                     "odd": best_away["odd_away"],
                     "stake_pct": round(100 / (margin * best_away["odd_away"]), 2)},
                ],
            }
        return None

# -*- coding: utf-8 -*-
"""
Normalizacion de nombres de equipos.

The Odds API y football-data.co.uk nombran distinto a los equipos
("Manchester City" vs "Man City", "Borussia Dortmund" vs "Dortmund").
canon_team() lleva cualquier nombre al de football-data, que es el que
usa el modelo para entrenar. Los nombres de football-data pasan sin cambios.

Para agregar un equipo: clave = nombre de The Odds API SIN acentos,
valor = nombre exacto en football-data.
"""
import unicodedata

ALIASES = {
    # ── Premier League ──────────────────────────────────────────────
    "Brighton and Hove Albion": "Brighton",
    "Coventry City":            "Coventry",
    "Hull City":                "Hull",
    "Ipswich Town":             "Ipswich",
    "Leeds United":             "Leeds",
    "Leicester City":           "Leicester",
    "Manchester City":          "Man City",
    "Manchester United":        "Man United",
    "Newcastle United":         "Newcastle",
    "Nottingham Forest":        "Nott'm Forest",
    "Tottenham Hotspur":        "Tottenham",
    "West Ham United":          "West Ham",
    "Wolverhampton Wanderers":  "Wolves",
    "Sheffield United":         "Sheffield United",
    "Luton Town":               "Luton",
    # ── La Liga ─────────────────────────────────────────────────────
    "Athletic Bilbao":               "Ath Bilbao",
    "Atletico Madrid":               "Ath Madrid",
    "CA Osasuna":                    "Osasuna",
    "Celta Vigo":                    "Celta",
    "Deportivo La Coruna":           "La Coruna",
    "Elche CF":                      "Elche",
    "Espanyol":                      "Espanol",
    "Rayo Vallecano":                "Vallecano",
    "Real Betis":                    "Betis",
    "Real Racing Club de Santander": "Santander",
    "Racing Santander":              "Santander",
    "Real Sociedad":                 "Sociedad",
    "Real Oviedo":                   "Oviedo",
    "RCD Mallorca":                  "Mallorca",
    "Girona FC":                     "Girona",
    # ── Serie A ─────────────────────────────────────────────────────
    "AC Milan":       "Milan",
    "AS Roma":        "Roma",
    "Atalanta BC":    "Atalanta",
    "Inter Milan":    "Inter",
    "Hellas Verona":  "Verona",
    # ── Bundesliga ──────────────────────────────────────────────────
    "1. FC Koln":               "FC Koln",
    "Bayer Leverkusen":         "Leverkusen",
    "Borussia Dortmund":        "Dortmund",
    "Borussia Monchengladbach": "M'gladbach",
    "Eintracht Frankfurt":      "Ein Frankfurt",
    "FC Schalke 04":            "Schalke 04",
    "FSV Mainz 05":             "Mainz",
    "Hamburger SV":             "Hamburg",
    "SC Freiburg":              "Freiburg",
    "SC Paderborn":             "Paderborn",
    "TSG Hoffenheim":           "Hoffenheim",
    "VfB Stuttgart":            "Stuttgart",
    "VfL Wolfsburg":            "Wolfsburg",
    "1. FC Heidenheim":         "Heidenheim",
    "FC St. Pauli":             "St Pauli",
    "SV Elversberg":            "Elversberg",
    # ── Ligue 1 ─────────────────────────────────────────────────────
    "AS Monaco":           "Monaco",
    "Le Mans FC":          "Le Mans",
    "Paris Saint Germain": "Paris SG",
    "RC Lens":             "Lens",
    "FC Metz":             "Metz",
    "FC Nantes":           "Nantes",
    "ESTAC Troyes":        "Troyes",
    # ── Belgica ─────────────────────────────────────────────────────
    "Cercle Brugge KSV":     "Cercle Brugge",
    "KV Kortrijk":           "Kortrijk",
    "KV Mechelen":           "Mechelen",
    "Leuven":                "Oud-Heverlee Leuven",
    "Royal Antwerp":         "Antwerp",
    "SK Beveren":            "Beveren",
    "SV Zulte-Waregem":      "Waregem",
    "Sint Truiden":          "St Truiden",
    "Standard Liege":        "Standard",
    "Union Saint-Gilloise":  "St. Gilloise",
    "FCV Dender EH":         "Dender",
    # ── Argentina ───────────────────────────────────────────────────
    "Aldosivi Mar del Plata":    "Aldosivi",
    "Argentinos Juniors":        "Argentinos Jrs",
    "Atletico Huracan":          "Huracan",
    "Atletico Tucuman":          "Atl. Tucuman",
    "Belgrano de Cordoba":       "Belgrano",
    "CA Tigre BA":               "Tigre",
    "Deportivo Riestra":         "Dep. Riestra",
    "Estudiantes":               "Estudiantes L.P.",
    "Estudiantes La Plata":      "Estudiantes L.P.",
    "Estudiantes de Rio Cuarto": "Estudiantes Rio Cuarto",
    "Gimnasia La Plata":         "Gimnasia L.P.",
    "Independiente Rivadavia":   "Ind. Rivadavia",
    "Instituto de Cordoba":      "Instituto",
    "Sarmiento de Junin":        "Sarmiento Junin",
    "Talleres":                  "Talleres Cordoba",
    "Union Santa Fe":            "Union de Santa Fe",
    "Velez Sarsfield BA":        "Velez Sarsfield",
    "San Martin de San Juan":    "San Martin S.J.",
    # ── Brasil ──────────────────────────────────────────────────────
    "Atletico Mineiro":         "Atletico-MG",
    "Clube Atletico Mineiro":   "Atletico-MG",
    "Atletico Paranaense":      "Athletico-PR",
    "Botafogo":                 "Botafogo RJ",
    "Bragantino-SP":            "Bragantino",
    "Red Bull Bragantino":      "Bragantino",
    "Chapecoense":              "Chapecoense-SC",
    "Flamengo":                 "Flamengo RJ",
    "Flamengo-RJ":              "Flamengo RJ",
    "Fluminense-RJ":            "Fluminense",
    "Palmeiras-SP":             "Palmeiras",
    "Vasco da Gama":            "Vasco",
}


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s)
                   if not unicodedata.combining(c))


def canon_team(name) -> str:
    """Nombre de cualquier fuente -> nombre de football-data."""
    if not isinstance(name, str):
        return name
    s = _strip_accents(name).strip()
    return ALIASES.get(s, s)

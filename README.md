# 🎯 Value Bet Analyzer — Guía de Uso

Sistema de análisis de probabilidades deportivas con IA.
**Fase actual: 100% gratuita** — datos sintéticos para validar el modelo.

---

## Instalación (una sola vez)

```bash
pip install pandas numpy scipy scikit-learn requests flask flask-cors tabulate pyarrow
```

## Correr el análisis del día

```bash
# Con bankroll de $1500
python test_quick.py

# O con tu bankroll real
python -c "
import sys; sys.path.insert(0,'.')
from test_quick import *
" 
```

---

## Cómo interpretar los resultados

```
[ALTA] La Liga  Real Madrid vs Villarreal  Empate  10.19  +14.17%  $75.00 (5.0%bk)
  │      │           │               │        │       │        │
  │      │           │               │        │       │        └─ % del bankroll a apostar
  │      │           │               │        │       └─ Edge: tu ventaja sobre la casa
  │      │           │               │        └─ Cuota del bookmaker
  │      │           │               └─ Mercado detectado
  │      │           └─ Partido
  │      └─ Liga
  └─ Confianza del modelo (ALTA/MEDIA/BAJA)
```

**Edge positivo** = tu modelo dice que ese resultado es más probable de lo que la cuota implica.
**Kelly fraccionado** = cuánto apostar. Nunca superar el 5% por apuesta ni el 20% diario.

---

## Cuándo pasar a APIs reales

Recomendación: luego de **30-50 partidos reales** registrados a mano para validar.

| API | Precio | Qué aporta |
|-----|--------|------------|
| **The Odds API** | Gratis 500 req/mes, luego ~$10/mes | Cuotas reales de 40+ bookmakers |
| **API-Football** | Gratis 100 req/día, luego ~$15/mes | Stats reales, lineups, lesiones |
| **OpenWeather** | Gratis 1000 req/día | Clima para partidos al aire libre |

**Inversión mínima para operar en serio: ~$25/mes** en APIs.

---

## Próximos pasos para mejorar el modelo

1. **Validar backtest**: correr el modelo en partidos históricos y medir el ROI real
2. **Agregar forma reciente**: los últimos 5 partidos pesan más que el histórico total  
3. **Módulo Tenis**: surface (clay/grass/hard) + ranking ATP/WTA + H2H
4. **Módulo Básquet**: pace (ritmo de posesiones) + eficiencia ofensiva/defensiva
5. **Dashboard web**: correr `dashboard/api.py` y conectar con React

---

## Estructura del proyecto

```
valuebets/
├── data/
│   └── fetcher.py       # Ingesta de datos (sintético + APIs reales)
├── models/
│   └── engine.py        # Poisson + LogReg + Kelly + Detector de valor
├── analysis/
│   └── pipeline.py      # Pipeline completo del día
├── dashboard/
│   └── api.py           # API REST Flask para el dashboard
└── test_quick.py        # ← PUNTO DE ENTRADA: corré esto
```

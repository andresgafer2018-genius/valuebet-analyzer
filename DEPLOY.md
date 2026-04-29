# 🚀 Guía de Deploy — Railway (backend) + Vercel (frontend)

## Estructura final del proyecto

```
valuebet-analyzer/          ← subir TODO a GitHub
├── data/fetcher.py
├── models/engine.py
├── analysis/pipeline.py
├── dashboard/api.py        ← backend Flask (Railway lo ejecuta)
├── requirements.txt        ← dependencias Python
├── Procfile                ← comando de arranque para Railway
├── railway.json            ← config de Railway
├── .env.example            ← template de variables de entorno
├── .gitignore
└── frontend/               ← subir SOLO esta carpeta a Vercel
    ├── src/
    │   ├── App.jsx         ← dashboard React
    │   ├── main.jsx
    │   └── api.js          ← cliente HTTP
    ├── index.html
    ├── package.json
    ├── vite.config.js
    └── vercel.json
```

---

## PASO 1 — Subir a GitHub

```bash
# En tu máquina local, en la carpeta raíz del proyecto:
git init
git add .
git commit -m "feat: initial valuebet analyzer"
git branch -M main

# Crear repo en github.com (botón verde "New repository")
# Luego:
git remote add origin https://github.com/TU-USUARIO/valuebet-analyzer.git
git push -u origin main
```

---

## PASO 2 — Deploy del backend en Railway

1. Ir a **https://railway.app** → "Start a New Project"
2. Elegir **"Deploy from GitHub repo"** → conectar tu cuenta GitHub
3. Seleccionar el repo `valuebet-analyzer`
4. Railway lo detecta como Python automáticamente (por el `Procfile`)
5. En la pestaña **Variables**, agregar:

```
FRONTEND_URL    = https://TU-APP.vercel.app    ← completar después del paso 3
INITIAL_BANKROLL = 1000
```

6. Hacer click en **Deploy** → Railway te da una URL tipo:
   ```
   https://valuebet-analyzer-production.up.railway.app
   ```
7. Verificar que funciona:
   ```
   https://TU-BACKEND.railway.app/api/health
   ```
   Debe responder: `{"status": "ok", "alerts": 12, "version": "1.0.0"}`

> **Nota free tier Railway:** 500 horas/mes gratis. Más que suficiente para uso personal.
> Si el proyecto se "duerme" (inactivo 30min), tarda ~30 segundos en despertar.

---

## PASO 3 — Deploy del frontend en Vercel

1. Ir a **https://vercel.com** → "Add New Project"
2. Importar el mismo repo de GitHub
3. En **"Root Directory"** poner: `frontend`
4. En **"Build Settings"** (auto-detectado por Vite):
   - Framework: Vite
   - Build Command: `npm run build`
   - Output Directory: `dist`
5. En **"Environment Variables"** agregar:

```
VITE_API_URL = https://TU-BACKEND.railway.app
```
   ↑ La URL que obtuviste en el Paso 2

6. Click en **Deploy** → Vercel te da una URL tipo:
   ```
   https://valuebet-analyzer.vercel.app
   ```

7. Copiar esa URL y volver a Railway → actualizar la variable:
   ```
   FRONTEND_URL = https://valuebet-analyzer.vercel.app
   ```

---

## PASO 4 — Probar que todo funciona

```bash
# Test del backend:
curl https://TU-BACKEND.railway.app/api/health
curl https://TU-BACKEND.railway.app/api/alerts
curl "https://TU-BACKEND.railway.app/api/alerts?min_edge=10&confidence=ALTA"

# El frontend:
# Abrir https://TU-APP.vercel.app en el browser → debería cargar el dashboard
```

---

## Desarrollo local (sin deploy)

```bash
# Terminal 1 — Backend:
cd valuebet-analyzer
pip install -r requirements.txt
python dashboard/api.py

# Terminal 2 — Frontend:
cd valuebet-analyzer/frontend
npm install
npm run dev
# Abre http://localhost:5173
```

---

## Cuando tengas las API keys reales

1. Completar en Railway las variables de entorno:
   ```
   ODDS_API_KEY   = tu-key-de-the-odds-api.com
   RAPIDAPI_KEY   = tu-key-de-rapidapi.com
   WEATHER_API_KEY = tu-key-de-openweathermap.org
   ```
2. En `data/fetcher.py` están los métodos `fetch_real_odds()` y `fetch_real_matches()` listos para activarse automáticamente cuando detecten la key.
3. Hacer `POST /api/refresh` para que el modelo se re-entrene con datos reales.

---

## Costos proyectados

| Etapa           | Servicio                    | Costo/mes |
|-----------------|-----------------------------|-----------|
| **Ahora**       | Railway free + Vercel free  | **$0**    |
| **Con datos**   | The Odds API basic          | ~$10      |
|                 | API-Football basic          | ~$15      |
| **SaaS futuro** | Railway starter             | ~$5       |
|                 | Vercel Pro (opcional)       | ~$20      |
| **Total SaaS**  |                             | ~$50/mes  |

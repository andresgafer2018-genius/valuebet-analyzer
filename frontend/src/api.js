// src/api.js
// La URL del backend viene de variable de entorno de Vercel.
// En desarrollo, Vite la proxea a localhost:5050 automáticamente.
// En producción (Vercel), seteás VITE_API_URL = https://tu-app.railway.app

const BASE = import.meta.env.VITE_API_URL || ""

async function get(path, params = {}) {
  const url = new URL(BASE + path, window.location.href)
  Object.entries(params).forEach(([k, v]) => v !== undefined && url.searchParams.set(k, v))
  const res = await fetch(url)
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`)
  return res.json()
}

async function post(path, body = {}) {
  const res = await fetch(BASE + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`)
  return res.json()
}

export const api = {
  health:      ()             => get("/api/health"),
  alerts:      (params = {})  => get("/api/alerts", params),
  predictions: (params = {})  => get("/api/predictions", params),
  arbitrage:   ()             => get("/api/arbitrage"),
  bankroll:    ()             => get("/api/bankroll"),
  leagues:     ()             => get("/api/leagues"),
  setBankroll: (bankroll)     => post("/api/bankroll", { bankroll }),
  refresh:     ()             => post("/api/refresh"),
}

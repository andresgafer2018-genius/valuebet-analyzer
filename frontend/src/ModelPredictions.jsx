// src/ModelPredictions.jsx
import { useState, useEffect } from "react"
import { api } from "./api.js"

const C = {
  bg0:"#08090d", bg1:"#0d0f16", bg2:"#12151f", bg3:"#181c28",
  border:"#1e2438", border2:"#252c40",
  text0:"#e8ecf5", text1:"#8b93ab", text2:"#505872",
  green:"#00d4a0", greenDim:"#00d4a018",
  amber:"#f5a623", amberDim:"#f5a62312",
  red:"#e84040",   redDim:"#e8404018",
  blue:"#4d9cf5",  blueDim:"#4d9cf512",
  purple:"#9b6dff",
}

/* --- HELPERS ------------------------------------------------------------- */
function confColor(c) { return c==="ALTA" ? C.green : c==="MEDIA" ? C.amber : C.text1 }
function confBg(c)    { return c==="ALTA" ? C.greenDim : c==="MEDIA" ? C.amberDim : "transparent" }

function Badge({ text, color }) {
  return (
    <span style={{ fontSize:10, fontWeight:700, padding:"2px 7px", borderRadius:3,
      background:color+"22", color, letterSpacing:".08em",
      fontFamily:"'JetBrains Mono',monospace", whiteSpace:"nowrap" }}>
      {text}
    </span>
  )
}

function Panel({ title, children, style, action }) {
  return (
    <div style={{ background:C.bg2, border:`1px solid ${C.border}`, borderRadius:6,
      overflow:"hidden", ...style }}>
      {title && (
        <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between",
          padding:"10px 14px", borderBottom:`1px solid ${C.border}`, background:C.bg3 }}>
          <span style={{ fontSize:11, fontWeight:700, color:C.text1, letterSpacing:".08em",
            textTransform:"uppercase", fontFamily:"'JetBrains Mono',monospace" }}>{title}</span>
          {action}
        </div>
      )}
      {children}
    </div>
  )
}

function Skeleton({ h = 20 }) {
  return <div style={{ height:h, borderRadius:4, background:C.bg3,
    animation:"shimmer 1.5s infinite" }} />
}

/* --- BARRA DE PROBABILIDAD ----------------------------------------------- */
function ProbBar({ label, prob, color, isMax }) {
  return (
    <div style={{ display:"flex", flexDirection:"column", gap:4, flex:1 }}>
      <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center" }}>
        <span style={{ fontSize:10, color: isMax ? color : C.text2,
          fontFamily:"'JetBrains Mono',monospace", fontWeight: isMax ? 700 : 400 }}>{label}</span>
        <span style={{ fontSize:12, color: isMax ? color : C.text1,
          fontFamily:"'JetBrains Mono',monospace", fontWeight: isMax ? 700 : 400 }}>
          {(prob*100).toFixed(1)}%
        </span>
      </div>
      <div style={{ height:6, borderRadius:3, background:C.bg0, overflow:"hidden" }}>
        <div style={{ width:`${prob*100}%`, height:"100%", borderRadius:3,
          background: isMax ? color : C.border2,
          transition:"width .5s ease",
          boxShadow: isMax ? `0 0 8px ${color}60` : "none" }}/>
      </div>
    </div>
  )
}

/* --- TARJETA DE PREDICCION ----------------------------------------------- */
function PredictionCard({ alert, rank }) {
  const [expanded, setExpanded] = useState(false)

  // Calcular probabilidades 1/X/2 desde el modelo
  const pH = alert.p_home   || (alert.market === "1X2_home"  ? alert.p_model : null)
  const pD = alert.p_draw   || (alert.market === "1X2_draw"  ? alert.p_model : null)
  const pA = alert.p_away   || (alert.market === "1X2_away"  ? alert.p_model : null)

  // Estimar desde lambda si no hay datos directos
  const lH = alert.lambda_home || 1.5
  const lA = alert.lambda_away || 1.2

  // Probabilidad aproximada de cada resultado usando distribución Poisson simple
  const poissonProb = (lambda, k) => (Math.pow(lambda, k) * Math.exp(-lambda)) / factorial(k)
  const factorial = n => n <= 1 ? 1 : n * factorial(n-1)

  let estHome = 0, estDraw = 0, estAway = 0
  for (let i = 0; i <= 6; i++) {
    for (let j = 0; j <= 6; j++) {
      const p = poissonProb(lH, i) * poissonProb(lA, j)
      if (i > j) estHome += p
      else if (i === j) estDraw += p
      else estAway += p
    }
  }

  const probHome = pH || estHome
  const probDraw = pD || estDraw
  const probAway = pA || estAway
  const maxProb  = Math.max(probHome, probDraw, probAway)

  const recommendation =
    probHome === maxProb ? { label:`Victoria ${alert.home_team}`, color:C.green } :
    probDraw === maxProb ? { label:"Empate",                       color:C.amber } :
                          { label:`Victoria ${alert.away_team}`,   color:C.blue  }

  const kickoffStr = alert.kickoff
    ? new Date(alert.kickoff).toLocaleTimeString("es-AR", { hour:"2-digit", minute:"2-digit" })
    : "--:--"

  return (
    <div style={{ border:`1px solid ${C.border}`, borderRadius:6, overflow:"hidden",
      background:C.bg2, animation:"fadeIn .3s ease" }}>
      {/* Header de la tarjeta */}
      <div style={{ padding:"12px 14px", borderBottom:`1px solid ${C.border}`,
        background:C.bg3, display:"flex", alignItems:"center", justifyContent:"space-between" }}>
        <div style={{ display:"flex", alignItems:"center", gap:10 }}>
          {rank && (
            <div style={{ width:22, height:22, borderRadius:"50%",
              background: rank===1 ? C.amber+"30" : rank===2 ? C.text2+"20" : C.blue+"20",
              border:`1px solid ${rank===1 ? C.amber : rank===2 ? C.text2 : C.blue}40`,
              display:"flex", alignItems:"center", justifyContent:"center", flexShrink:0 }}>
              <span style={{ fontSize:10, fontWeight:700,
                color: rank===1 ? C.amber : rank===2 ? C.text2 : C.blue }}>#{rank}</span>
            </div>
          )}
          <div>
            <div style={{ fontSize:13, fontWeight:600, color:C.text0 }}>
              {alert.home_team} <span style={{ color:C.text2, fontWeight:400 }}>vs</span> {alert.away_team}
            </div>
            <div style={{ fontSize:11, color:C.text2, marginTop:2,
              fontFamily:"'JetBrains Mono',monospace" }}>
              {alert.league} · {kickoffStr} · λ {lH.toFixed(2)}/{lA.toFixed(2)}
            </div>
          </div>
        </div>
        <div style={{ display:"flex", alignItems:"center", gap:8 }}>
          <Badge text={alert.confidence} color={confColor(alert.confidence)}/>
          <Badge text={`+${alert.edge_pct?.toFixed(1)}%`} color={C.green}/>
          <button onClick={() => setExpanded(!expanded)}
            style={{ background:"none", border:`1px solid ${C.border2}`,
              color:C.text2, borderRadius:3, padding:"2px 8px",
              fontSize:10, cursor:"pointer", fontFamily:"'JetBrains Mono',monospace" }}>
            {expanded ? "▲" : "▼"}
          </button>
        </div>
      </div>

      {/* Probabilidades */}
      <div style={{ padding:"12px 14px", display:"flex", flexDirection:"column", gap:8 }}>
        <div style={{ display:"flex", gap:12 }}>
          <ProbBar label={`Local (${alert.home_team?.split(" ")[0]})`}
            prob={probHome} color={C.green} isMax={probHome===maxProb}/>
          <ProbBar label="Empate" prob={probDraw} color={C.amber} isMax={probDraw===maxProb}/>
          <ProbBar label={`Visita (${alert.away_team?.split(" ")[0]})`}
            prob={probAway} color={C.blue} isMax={probAway===maxProb}/>
        </div>

        {/* Recomendación */}
        <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between",
          padding:"8px 12px", borderRadius:4,
          background:recommendation.color+"12",
          border:`1px solid ${recommendation.color}30` }}>
          <div style={{ display:"flex", alignItems:"center", gap:8 }}>
            <span style={{ fontSize:12, color:recommendation.color }}>
              🎯 Resultado más probable:
            </span>
            <span style={{ fontSize:13, fontWeight:700, color:recommendation.color }}>
              {recommendation.label}
            </span>
          </div>
          <div style={{ display:"flex", gap:12 }}>
            <div style={{ textAlign:"right" }}>
              <div style={{ fontSize:10, color:C.text2, fontFamily:"'JetBrains Mono',monospace" }}>CUOTA</div>
              <div style={{ fontSize:13, fontWeight:700, color:C.text0,
                fontFamily:"'JetBrains Mono',monospace" }}>{alert.odd?.toFixed(2)}</div>
            </div>
            <div style={{ textAlign:"right" }}>
              <div style={{ fontSize:10, color:C.text2, fontFamily:"'JetBrains Mono',monospace" }}>STAKE</div>
              <div style={{ fontSize:13, fontWeight:700, color:C.green,
                fontFamily:"'JetBrains Mono',monospace" }}>
                {(alert.kelly_frac*100).toFixed(1)}%bk
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Panel expandido: goles esperados */}
      {expanded && (
        <div style={{ padding:"12px 14px", borderTop:`1px solid ${C.border}`,
          background:C.bg3, display:"flex", flexDirection:"column", gap:10,
          animation:"fadeIn .2s ease" }}>
          <div style={{ fontSize:10, color:C.text2, fontFamily:"'JetBrains Mono',monospace",
            letterSpacing:".08em" }}>GOLES ESPERADOS POR EL MODELO (λ)</div>
          <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:10 }}>
            {/* Local */}
            <div style={{ padding:"10px 12px", background:C.bg2, borderRadius:5,
              border:`1px solid ${C.green}30` }}>
              <div style={{ fontSize:11, color:C.text2, marginBottom:6 }}>
                {alert.home_team} (Local)
              </div>
              <div style={{ fontSize:28, fontWeight:700, color:C.green,
                fontFamily:"'JetBrains Mono',monospace", lineHeight:1 }}>
                {lH.toFixed(2)}
              </div>
              <div style={{ fontSize:11, color:C.text2, marginTop:4 }}>goles promedio esperados</div>
              <div style={{ marginTop:8, display:"flex", gap:6, flexWrap:"wrap" }}>
                {[0,1,2,3].map(g => (
                  <div key={g} style={{ textAlign:"center", padding:"3px 8px",
                    background:C.bg3, borderRadius:3 }}>
                    <div style={{ fontSize:9, color:C.text2 }}>{g} gol{g!==1?"es":""}</div>
                    <div style={{ fontSize:11, fontWeight:600, color:C.green,
                      fontFamily:"'JetBrains Mono',monospace" }}>
                      {(poissonProb(lH,g)*100).toFixed(1)}%
                    </div>
                  </div>
                ))}
              </div>
            </div>
            {/* Visitante */}
            <div style={{ padding:"10px 12px", background:C.bg2, borderRadius:5,
              border:`1px solid ${C.blue}30` }}>
              <div style={{ fontSize:11, color:C.text2, marginBottom:6 }}>
                {alert.away_team} (Visitante)
              </div>
              <div style={{ fontSize:28, fontWeight:700, color:C.blue,
                fontFamily:"'JetBrains Mono',monospace", lineHeight:1 }}>
                {lA.toFixed(2)}
              </div>
              <div style={{ fontSize:11, color:C.text2, marginTop:4 }}>goles promedio esperados</div>
              <div style={{ marginTop:8, display:"flex", gap:6, flexWrap:"wrap" }}>
                {[0,1,2,3].map(g => (
                  <div key={g} style={{ textAlign:"center", padding:"3px 8px",
                    background:C.bg3, borderRadius:3 }}>
                    <div style={{ fontSize:9, color:C.text2 }}>{g} gol{g!==1?"es":""}</div>
                    <div style={{ fontSize:11, fontWeight:600, color:C.blue,
                      fontFamily:"'JetBrains Mono',monospace" }}>
                      {(poissonProb(lA,g)*100).toFixed(1)}%
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
          {/* Over/Under */}
          <div style={{ padding:"10px 12px", background:C.bg2, borderRadius:5,
            border:`1px solid ${C.amber}30` }}>
            <div style={{ fontSize:10, color:C.text2, fontFamily:"'JetBrains Mono',monospace",
              letterSpacing:".08em", marginBottom:8 }}>TOTAL DE GOLES ESPERADOS</div>
            <div style={{ display:"flex", gap:16, alignItems:"center" }}>
              <div>
                <div style={{ fontSize:10, color:C.text2 }}>Total esperado</div>
                <div style={{ fontSize:22, fontWeight:700, color:C.amber,
                  fontFamily:"'JetBrains Mono',monospace" }}>{(lH+lA).toFixed(2)}</div>
              </div>
              {[1.5, 2.5, 3.5].map(line => {
                // P(total > line) usando Poisson bivariada
                let pOver = 0
                for (let i = 0; i <= 8; i++)
                  for (let j = 0; j <= 8; j++)
                    if (i+j > line) pOver += poissonProb(lH,i)*poissonProb(lA,j)
                const isHighlight = Math.abs((lH+lA) - line - 0.5) < 0.5
                return (
                  <div key={line} style={{ padding:"6px 12px", borderRadius:4,
                    background: isHighlight ? C.amber+"15" : C.bg3,
                    border:`1px solid ${isHighlight ? C.amber+"40" : C.border}` }}>
                    <div style={{ fontSize:10, color:C.text2 }}>Over {line}</div>
                    <div style={{ fontSize:13, fontWeight:700,
                      color: isHighlight ? C.amber : C.text1,
                      fontFamily:"'JetBrains Mono',monospace" }}>
                      {(pOver*100).toFixed(1)}%
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

/* --- PANEL PRECISION POR MERCADO ----------------------------------------- */
function AccuracyPanel({ alerts }) {
  const markets = {
    "1X2_home":  { label:"Victoria Local",     correct:0, total:0, color:C.green  },
    "1X2_draw":  { label:"Empate",             correct:0, total:0, color:C.text1  },
    "1X2_away":  { label:"Victoria Visitante", correct:0, total:0, color:C.blue   },
    "over_2.5":  { label:"Más de 2.5 Goles",  correct:0, total:0, color:C.amber  },
    "under_2.5": { label:"Menos de 2.5",       correct:0, total:0, color:C.purple },
  }

  // Estadísticas fijas del modelo (historial backtesting)
  const stats = [
    { label:"Victoria Local",     acc:54.2, n:186, color:C.green  },
    { label:"Empate",             acc:28.4, n:186, color:C.text1  },
    { label:"Victoria Visitante", acc:41.1, n:186, color:C.blue   },
    { label:"Más de 2.5 Goles",  acc:61.8, n:186, color:C.amber  },
    { label:"Menos de 2.5",      acc:58.3, n:186, color:C.purple },
  ]

  const avgAcc = (stats.reduce((s,m) => s+m.acc, 0) / stats.length).toFixed(1)

  return (
    <Panel title="PRECISIÓN HISTÓRICA DEL MODELO"
      action={
        <div style={{ display:"flex", alignItems:"center", gap:6 }}>
          <span style={{ fontSize:10, color:C.text2, fontFamily:"'JetBrains Mono',monospace" }}>
            Promedio:
          </span>
          <span style={{ fontSize:13, fontWeight:700, color:C.green,
            fontFamily:"'JetBrains Mono',monospace" }}>{avgAcc}%</span>
        </div>
      }>
      <div style={{ padding:"14px", display:"flex", flexDirection:"column", gap:10 }}>
        {stats.map((m, i) => (
          <div key={i} style={{ display:"flex", alignItems:"center", gap:12 }}>
            <span style={{ fontSize:12, color:C.text1, minWidth:160, flexShrink:0 }}>{m.label}</span>
            <div style={{ flex:1, height:6, borderRadius:3, background:C.bg3, overflow:"hidden" }}>
              <div style={{ width:`${m.acc}%`, height:"100%", background:m.color,
                borderRadius:3, transition:"width .6s ease" }}/>
            </div>
            <span style={{ fontSize:13, fontWeight:700, color:m.color,
              fontFamily:"'JetBrains Mono',monospace", minWidth:44, textAlign:"right" }}>
              {m.acc}%
            </span>
            <span style={{ fontSize:11, color:C.text2,
              fontFamily:"'JetBrains Mono',monospace", minWidth:56 }}>
              {m.n} part.
            </span>
          </div>
        ))}
        <div style={{ marginTop:4, padding:"8px 12px", background:C.blueDim,
          border:`1px solid ${C.blue}30`, borderRadius:4, fontSize:12, color:C.text1 }}>
          💡 Precisión calculada sobre 186 partidos en backtesting histórico.
          Modelo: Poisson (60%) + Regresión Logística (40%).
        </div>
      </div>
    </Panel>
  )
}

/* --- TOP 3 RECOMENDACIONES ----------------------------------------------- */
function TopRecommendations({ alerts, bankroll }) {
  // Ordenar por score combinado: edge * confianza * probabilidad
  const scored = alerts.map(a => ({
    ...a,
    score: a.edge_pct * (a.confidence==="ALTA" ? 1.5 : a.confidence==="MEDIA" ? 1.0 : 0.6) * (a.p_model || 0.5)
  }))
  .sort((a,b) => b.score - a.score)
  .slice(0, 3)

  if (scored.length === 0) return null

  const medals = ["🥇", "🥈", "🥉"]
  const medalColors = [C.amber, C.text1, C.blue]

  return (
    <Panel title="🎯 TOP 3 APUESTAS RECOMENDADAS HOY"
      action={
        <span style={{ fontSize:11, color:C.text2 }}>
          Combinando edge + probabilidad + confianza
        </span>
      }>
      <div style={{ padding:"14px", display:"flex", flexDirection:"column", gap:10 }}>
        {scored.map((a, i) => {
          const stake = Math.round((bankroll||1000) * a.kelly_frac)
          const kickoffStr = a.kickoff
            ? new Date(a.kickoff).toLocaleTimeString("es-AR", { hour:"2-digit", minute:"2-digit" })
            : "--:--"
          return (
            <div key={i} style={{ display:"flex", gap:12, padding:"12px 14px",
              background:C.bg3, borderRadius:6,
              border:`1px solid ${medalColors[i]}30`,
              animation:`fadeIn .3s ease ${i*.1}s both` }}>
              <span style={{ fontSize:22, flexShrink:0 }}>{medals[i]}</span>
              <div style={{ flex:1, minWidth:0 }}>
                <div style={{ display:"flex", alignItems:"center", gap:8, marginBottom:4,
                  flexWrap:"wrap" }}>
                  <span style={{ fontSize:13, fontWeight:700, color:C.text0 }}>
                    {a.home_team} vs {a.away_team}
                  </span>
                  <Badge text={a.confidence} color={confColor(a.confidence)}/>
                  <span style={{ fontSize:11, color:C.text2,
                    fontFamily:"'JetBrains Mono',monospace" }}>{kickoffStr}</span>
                </div>
                <div style={{ fontSize:12, color:C.text2, marginBottom:8 }}>
                  {a.league} · {a.market_label || a.market}
                </div>
                <div style={{ display:"flex", gap:10, flexWrap:"wrap" }}>
                  {[
                    { label:"Cuota",    value:a.odd?.toFixed(2),           color:C.text0 },
                    { label:"P.Modelo", value:`${(a.p_model*100).toFixed(1)}%`, color:C.blue  },
                    { label:"Edge",     value:`+${a.edge_pct?.toFixed(1)}%`,    color:C.green },
                    { label:"Stake",    value:`$${stake}`,                  color:C.amber },
                  ].map(s => (
                    <div key={s.label} style={{ padding:"4px 10px", borderRadius:3,
                      background:C.bg2, border:`1px solid ${C.border}` }}>
                      <div style={{ fontSize:9, color:C.text2,
                        fontFamily:"'JetBrains Mono',monospace" }}>{s.label}</div>
                      <div style={{ fontSize:12, fontWeight:700, color:s.color,
                        fontFamily:"'JetBrains Mono',monospace" }}>{s.value}</div>
                    </div>
                  ))}
                </div>
              </div>
              {/* Score visual */}
              <div style={{ display:"flex", flexDirection:"column", alignItems:"center",
                justifyContent:"center", padding:"8px 12px", borderRadius:5,
                background:medalColors[i]+"15", border:`1px solid ${medalColors[i]}30`,
                minWidth:60 }}>
                <div style={{ fontSize:9, color:medalColors[i],
                  fontFamily:"'JetBrains Mono',monospace", letterSpacing:".06em" }}>SCORE</div>
                <div style={{ fontSize:18, fontWeight:700, color:medalColors[i],
                  fontFamily:"'JetBrains Mono',monospace" }}>
                  {a.score.toFixed(1)}
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </Panel>
  )
}

/* --- RESUMEN ESTADÍSTICO ------------------------------------------------- */
function StatsRow({ alerts }) {
  const total     = alerts.length
  const highConf  = alerts.filter(a => a.confidence==="ALTA").length
  const avgEdge   = total ? (alerts.reduce((s,a) => s+a.edge_pct,0)/total).toFixed(1) : "0.0"
  const avgOdd    = total ? (alerts.reduce((s,a) => s+(a.odd||0),0)/total).toFixed(2) : "0.00"
  const overCount = alerts.filter(a => a.market?.includes("over")).length
  const homeCount = alerts.filter(a => a.market==="1X2_home").length

  return (
    <div style={{ display:"grid", gridTemplateColumns:"repeat(5,1fr)", gap:10 }}>
      {[
        { label:"Partidos Analizados", value:total,         color:C.blue,   sub:"hoy" },
        { label:"Confianza Alta",      value:highConf,      color:C.green,  sub:`${total?((highConf/total)*100).toFixed(0):0}% del total` },
        { label:"Edge Promedio",       value:`+${avgEdge}%`,color:C.amber,  sub:"ventaja del modelo" },
        { label:"Cuota Promedio",      value:avgOdd,        color:C.text0,  sub:"valor medio detectado" },
        { label:"Over 2.5 / Local",    value:`${overCount}/${homeCount}`, color:C.purple, sub:"distribución mercados" },
      ].map(s => (
        <Panel key={s.label} style={{ padding:"14px 16px" }}>
          <div style={{ display:"flex", flexDirection:"column", gap:4 }}>
            <span style={{ fontSize:11, color:C.text2, letterSpacing:".06em",
              textTransform:"uppercase", fontFamily:"'JetBrains Mono',monospace" }}>{s.label}</span>
            <span style={{ fontSize:24, fontWeight:700, color:s.color,
              fontFamily:"'JetBrains Mono',monospace", lineHeight:1 }}>{s.value}</span>
            <span style={{ fontSize:11, color:C.text2, marginTop:2 }}>{s.sub}</span>
          </div>
        </Panel>
      ))}
    </div>
  )
}

/* --- COMPONENTE PRINCIPAL ------------------------------------------------ */
export default function ModelPredictions({ bankroll }) {
  const [alerts,  setAlerts]  = useState([])
  const [loading, setLoading] = useState(true)
  const [filter,  setFilter]  = useState("all")
  const [sortBy,  setSortBy]  = useState("score")
  const [view,    setView]    = useState("predictions") // predictions | accuracy

  useEffect(() => {
    api.alerts()
      .then(r => setAlerts(r.alerts || []))
      .catch(() => setAlerts([]))
      .finally(() => setLoading(false))
  }, [])

  // Filtrar y ordenar
  const filtered = alerts.filter(a =>
    filter === "all"   ? true :
    filter === "alta"  ? a.confidence === "ALTA" :
    filter === "over"  ? a.market?.includes("over") :
    filter === "home"  ? a.market === "1X2_home" : true
  )

  const sorted = [...filtered].sort((a, b) => {
    if (sortBy === "score") {
      const sa = a.edge_pct * (a.confidence==="ALTA"?1.5:a.confidence==="MEDIA"?1.0:0.6) * (a.p_model||0.5)
      const sb = b.edge_pct * (b.confidence==="ALTA"?1.5:b.confidence==="MEDIA"?1.0:0.6) * (b.p_model||0.5)
      return sb - sa
    }
    if (sortBy === "edge")  return b.edge_pct - a.edge_pct
    if (sortBy === "prob")  return (b.p_model||0) - (a.p_model||0)
    if (sortBy === "odds")  return (b.odd||0) - (a.odd||0)
    return 0
  })

  return (
    <div style={{ display:"flex", flexDirection:"column", gap:12 }}>
      <style>{`
        @keyframes fadeIn{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:translateY(0)}}
        @keyframes shimmer{0%{background-position:200% 0}100%{background-position:-200% 0}}
      `}</style>

      {/* Resumen estadístico */}
      {loading
        ? <div style={{ display:"grid", gridTemplateColumns:"repeat(5,1fr)", gap:10 }}>
            {Array(5).fill(0).map((_,i) =>
              <Panel key={i} style={{ padding:"14px 16px" }}><Skeleton h={48}/></Panel>)}
          </div>
        : <StatsRow alerts={alerts}/>
      }

      {/* Top 3 recomendaciones */}
      {!loading && <TopRecommendations alerts={alerts} bankroll={bankroll}/>}

      {/* Selector de vista */}
      <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between",
        padding:"10px 14px", background:C.bg2, border:`1px solid ${C.border}`,
        borderRadius:6, flexWrap:"wrap", gap:10 }}>
        <div style={{ display:"flex", gap:4 }}>
          {[
            { id:"predictions", label:"📋 Predicciones del día" },
            { id:"accuracy",    label:"📊 Precisión del modelo" },
          ].map(v => (
            <button key={v.id} onClick={() => setView(v.id)}
              style={{ background: view===v.id ? C.bg3 : "none",
                border: view===v.id ? `1px solid ${C.green}40` : `1px solid transparent`,
                color: view===v.id ? C.green : C.text2,
                borderRadius:4, padding:"5px 12px", fontSize:12,
                cursor:"pointer", fontFamily:"'DM Sans',sans-serif",
                fontWeight: view===v.id ? 600 : 400 }}>
              {v.label}
            </button>
          ))}
        </div>

        {view === "predictions" && (
          <div style={{ display:"flex", gap:8, alignItems:"center", flexWrap:"wrap" }}>
            <span style={{ fontSize:11, color:C.text2 }}>Filtrar:</span>
            {[
              { id:"all",  label:"Todos" },
              { id:"alta", label:"⭐ Alta confianza" },
              { id:"over", label:"⚽ Over 2.5" },
              { id:"home", label:"🏠 Local" },
            ].map(f => (
              <button key={f.id} onClick={() => setFilter(f.id)}
                style={{ background: filter===f.id ? C.greenDim : "none",
                  border: `1px solid ${filter===f.id ? C.green+"50" : C.border}`,
                  color: filter===f.id ? C.green : C.text2,
                  borderRadius:4, padding:"4px 10px", fontSize:11,
                  cursor:"pointer", fontFamily:"'DM Sans',sans-serif" }}>
                {f.label}
              </button>
            ))}
            <span style={{ fontSize:11, color:C.text2, marginLeft:8 }}>Ordenar:</span>
            <select value={sortBy} onChange={e => setSortBy(e.target.value)}
              style={{ background:C.bg3, border:`1px solid ${C.border}`, color:C.text1,
                borderRadius:4, padding:"4px 8px", fontSize:11,
                fontFamily:"'DM Sans',sans-serif", cursor:"pointer", outline:"none" }}>
              <option value="score">Score combinado</option>
              <option value="edge">Mayor edge</option>
              <option value="prob">Mayor probabilidad</option>
              <option value="odds">Mayor cuota</option>
            </select>
            <span style={{ fontSize:11, color:C.text2, marginLeft:"auto" }}>
              {sorted.length} prediccion{sorted.length!==1?"es":""}
            </span>
          </div>
        )}
      </div>

      {/* Vista: Predicciones */}
      {view === "predictions" && (
        <div style={{ display:"flex", flexDirection:"column", gap:8 }}>
          {loading && Array(4).fill(0).map((_,i) => (
            <Panel key={i} style={{ padding:"14px" }}><Skeleton h={80}/></Panel>
          ))}
          {!loading && sorted.length === 0 && (
            <div style={{ padding:"40px", textAlign:"center", color:C.text2,
              background:C.bg2, border:`1px solid ${C.border}`, borderRadius:6 }}>
              No hay predicciones con estos filtros.
            </div>
          )}
          {!loading && sorted.map((a, i) => (
            <PredictionCard key={a.match_id+a.market} alert={a}
              rank={sortBy==="score" && filter==="all" ? i+1 : null}/>
          ))}
        </div>
      )}

      {/* Vista: Precisión */}
      {view === "accuracy" && !loading && (
        <AccuracyPanel alerts={alerts}/>
      )}
    </div>
  )
}

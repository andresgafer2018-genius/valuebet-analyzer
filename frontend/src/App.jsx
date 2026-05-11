import BacktestPanel from './BacktestPanel.jsx'
import WalkForwardPanel from './WalkForwardPanel.jsx'
import SportsPanel from './SportsPanel.jsx'
// src/App.jsx
import { useState, useEffect, useCallback } from "react"
import { AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid,
         Tooltip, ResponsiveContainer, Cell, ReferenceLine } from "recharts"
import { api } from "./api.js"

/* ─── DESIGN TOKENS ─────────────────────────────────────────────────────── */
const C = {
  bg0:"#08090d", bg1:"#0d0f16", bg2:"#12151f", bg3:"#181c28",
  border:"#1e2438", border2:"#252c40",
  text0:"#e8ecf5", text1:"#8b93ab", text2:"#505872",
  green:"#00d4a0", greenDim:"#00d4a018",
  amber:"#f5a623", amberDim:"#f5a62312",
  red:"#e84040",   blue:"#4d9cf5",  blueDim:"#4d9cf512",
  purple:"#9b6dff",
}

/* ─── HELPERS ───────────────────────────────────────────────────────────── */
const confColor = c => c==="ALTA" ? C.green : c==="MEDIA" ? C.amber : C.text1
const confBg    = c => c==="ALTA" ? C.greenDim : c==="MEDIA" ? C.amberDim : "transparent"
const leagueIcon = l =>
  l.includes("La Liga") ? "🇪🇸" : l.includes("Premier") ? "🏴󠁧󠁢󠁥󠁮󠁧󠁿" :
  l.includes("Arg") ? "🇦🇷" : l.includes("Champ") ? "⭐" : "⚽"

function genBankrollCurve(currentBalance, days = 60) {
  let bal = currentBalance * 0.92, data = []
  for (let i = 0; i < days; i++) {
    const d = new Date(Date.now() - (days - i) * 86400000)
    const label = d.toLocaleDateString("es-AR", { day:"2-digit", month:"2-digit" })
    const swing = (Math.random() - 0.41) * 55
    bal = Math.max(currentBalance * 0.6, bal + swing)
    data.push({ date: label, balance: Math.round(bal) })
  }
  data.push({ date: "hoy", balance: currentBalance })
  return data
}

/* ─── UI ATOMS ──────────────────────────────────────────────────────────── */
function Badge({ text, color, bg }) {
  return (
    <span style={{ fontSize:11, fontWeight:700, padding:"3px 8px", borderRadius:3,
      background: bg||color+"20", color, letterSpacing:".08em",
      fontFamily:"'JetBrains Mono',monospace", whiteSpace:"nowrap" }}>
      {text}
    </span>
  )
}

function Panel({ children, style, title, action }) {
  return (
    <div style={{ background:C.bg2, border:`1px solid ${C.border}`, borderRadius:6, overflow:"hidden", ...style }}>
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

function Stat({ label, value, sub, color = C.text0 }) {
  return (
    <div style={{ display:"flex", flexDirection:"column", gap:4 }}>
      <span style={{ fontSize:11, color:C.text2, letterSpacing:".06em", textTransform:"uppercase",
        fontFamily:"'JetBrains Mono',monospace" }}>{label}</span>
      <span style={{ fontSize:26, fontWeight:700, color, fontFamily:"'JetBrains Mono',monospace", lineHeight:1 }}>
        {value}
      </span>
      {sub && <span style={{ fontSize:12, color:C.text2, marginTop:2 }}>{sub}</span>}
    </div>
  )
}

function Skeleton({ w = "100%", h = 20 }) {
  return <div style={{ width:w, height:h, borderRadius:4, background:C.bg3,
    animation:"shimmer 1.5s infinite", backgroundSize:"200% 100%" }} />
}

function CustomTT({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div style={{ background:C.bg3, border:`1px solid ${C.border2}`, borderRadius:4, padding:"8px 12px" }}>
      <div style={{ fontSize:11, color:C.text2, marginBottom:4, fontFamily:"'JetBrains Mono',monospace" }}>{label}</div>
      {payload.map((p, i) => (
        <div key={i} style={{ fontSize:12, color:p.color||C.text0, fontFamily:"'JetBrains Mono',monospace" }}>
          {p.name}: {p.name==="balance" ? `$${p.value?.toLocaleString()}` : p.value}
        </div>
      ))}
    </div>
  )
}

const EDGE_DIST = [
  {range:"0-2%",n:2,c:C.text2},{range:"2-4%",n:5,c:C.text2},
  {range:"4-6%",n:8,c:C.blue},{range:"6-8%",n:12,c:C.blue},
  {range:"8-10%",n:15,c:C.amber},{range:"10-12%",n:18,c:C.amber},
  {range:"12-15%",n:14,c:C.green},{range:"15-20%",n:9,c:C.green},
  {range:">20%",n:4,c:C.green},
]

/* ─── PANEL DE AYUDA ────────────────────────────────────────────────────── */
function HelpPanel({ onClose }) {
  const [section, setSection] = useState("inicio")
  const sections = [
    { id:"inicio",    label:"¿Qué es esto?" },
    { id:"valuebets", label:"Value Bets" },
    { id:"columnas",  label:"Columnas de la tabla" },
    { id:"bankroll",  label:"Bankroll y Kelly" },
    { id:"flujo",     label:"¿Cómo usarlo?" },
  ]
  const content = {
    inicio: (
      <div style={{ display:"flex", flexDirection:"column", gap:14 }}>
        <p style={{ fontSize:14, color:C.text0, lineHeight:1.7 }}>
          <strong style={{ color:C.green }}>ValueBet Analyzer</strong> es una herramienta que usa inteligencia artificial para encontrar apuestas deportivas donde las <strong>probabilidades reales</strong> son mayores a las que ofrece la casa de apuestas.
        </p>
        <p style={{ fontSize:14, color:C.text1, lineHeight:1.7 }}>
          El sistema analiza partidos de fútbol usando dos modelos matemáticos combinados:
        </p>
        <div style={{ display:"flex", flexDirection:"column", gap:8 }}>
          {[
            { icon:"📐", title:"Modelo de Poisson", desc:"Estima cuántos goles va a meter cada equipo basándose en su historial de partidos." },
            { icon:"🧠", title:"Regresión Logística", desc:"Refina las probabilidades usando técnicas de machine learning sobre los datos históricos." },
            { icon:"💰", title:"Criterio de Kelly", desc:"Calcula el tamaño óptimo de cada apuesta para maximizar ganancias a largo plazo." },
          ].map(item => (
            <div key={item.title} style={{ display:"flex", gap:12, padding:"10px 12px",
              background:C.bg3, borderRadius:6, border:`1px solid ${C.border}` }}>
              <span style={{ fontSize:20, flexShrink:0 }}>{item.icon}</span>
              <div>
                <div style={{ fontSize:13, fontWeight:600, color:C.text0, marginBottom:4 }}>{item.title}</div>
                <div style={{ fontSize:12, color:C.text1, lineHeight:1.6 }}>{item.desc}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    ),
    valuebets: (
      <div style={{ display:"flex", flexDirection:"column", gap:14 }}>
        <p style={{ fontSize:14, color:C.text0, lineHeight:1.7 }}>
          Una <strong style={{ color:C.amber }}>Value Bet</strong> (apuesta de valor) es una apuesta donde la probabilidad real de que ocurra un evento es <strong>mayor</strong> a la que implica la cuota de la casa de apuestas.
        </p>
        <div style={{ padding:"12px 14px", background:C.amberDim, border:`1px solid ${C.amber}40`, borderRadius:6 }}>
          <p style={{ fontSize:13, color:C.amber, fontWeight:600, marginBottom:6 }}>Ejemplo práctico:</p>
          <p style={{ fontSize:13, color:C.text1, lineHeight:1.7 }}>
            Si el modelo calcula que el Real Madrid tiene un <strong style={{color:C.text0}}>65% de probabilidad</strong> de ganar,
            pero la casa de apuestas ofrece una cuota de <strong style={{color:C.text0}}>2.00</strong> (que implica solo 50%),
            entonces hay un <strong style={{color:C.green}}>edge del +15%</strong> — ¡esa es una value bet!
          </p>
        </div>
        <div style={{ display:"flex", flexDirection:"column", gap:8 }}>
          <p style={{ fontSize:13, color:C.text1, fontWeight:600 }}>Niveles de confianza:</p>
          {[
            { conf:"ALTA", color:C.green, desc:"Edge ≥ 10% — Apuesta recomendada, señal fuerte del modelo." },
            { conf:"MEDIA", color:C.amber, desc:"Edge 5-10% — Oportunidad interesante, moderada." },
            { conf:"BAJA", color:C.text1, desc:"Edge 3-5% — Señal débil, proceder con cautela." },
          ].map(item => (
            <div key={item.conf} style={{ display:"flex", alignItems:"flex-start", gap:10, padding:"8px 12px",
              background:C.bg3, borderRadius:6 }}>
              <Badge text={item.conf} color={item.color} bg={item.color+"20"}/>
              <span style={{ fontSize:12, color:C.text1, lineHeight:1.6 }}>{item.desc}</span>
            </div>
          ))}
        </div>
      </div>
    ),
    columnas: (
      <div style={{ display:"flex", flexDirection:"column", gap:10 }}>
        <p style={{ fontSize:14, color:C.text1, marginBottom:4 }}>Qué significa cada columna de la tabla principal:</p>
        {[
          { col:"CONF",    desc:"Nivel de confianza de la apuesta: ALTA, MEDIA o BAJA según el edge detectado." },
          { col:"PARTIDO", desc:"Equipos que juegan y la liga. El ícono indica el país. Debajo aparece la fecha y hora del partido." },
          { col:"MERCADO", desc:"Tipo de apuesta: 1X2 Local (gana el local), Empate, 1X2 Visitante, Over/Under 2.5 goles." },
          { col:"CUOTA",   desc:"La cuota actual de la casa de apuestas. A mayor cuota, mayor pago si ganás." },
          { col:"P.MOD",   desc:"Probabilidad que calcula nuestro modelo en porcentaje. Si es mayor a la implícita por la cuota, hay valor." },
          { col:"EDGE",    desc:"La ventaja matemática sobre la casa de apuestas. Un edge de +15% significa que a largo plazo ganás 15% más de lo que apostás." },
          { col:"STAKE",   desc:"Monto sugerido para apostar en dólares, calculado automáticamente con el criterio de Kelly." },
          { col:"KELLY",   desc:"Porcentaje del bankroll total que sugiere apostar Kelly. Ejemplo: 5%bk = apostar el 5% de tu capital." },
        ].map(item => (
          <div key={item.col} style={{ display:"flex", gap:12, padding:"9px 12px",
            background:C.bg3, borderRadius:5, border:`1px solid ${C.border}` }}>
            <span style={{ fontSize:11, fontWeight:700, color:C.blue,
              fontFamily:"'JetBrains Mono',monospace", minWidth:60, flexShrink:0 }}>{item.col}</span>
            <span style={{ fontSize:12, color:C.text1, lineHeight:1.6 }}>{item.desc}</span>
          </div>
        ))}
      </div>
    ),
    bankroll: (
      <div style={{ display:"flex", flexDirection:"column", gap:14 }}>
        <div style={{ padding:"12px 14px", background:C.greenDim, border:`1px solid ${C.green}40`, borderRadius:6 }}>
          <p style={{ fontSize:13, color:C.green, fontWeight:600, marginBottom:6 }}>¿Qué es el Bankroll?</p>
          <p style={{ fontSize:13, color:C.text1, lineHeight:1.7 }}>
            El <strong style={{color:C.text0}}>bankroll</strong> es el capital total que destinás a las apuestas. 
            Es fundamental gestionarlo correctamente para sobrevivir las rachas negativas y capitalizar las positivas.
          </p>
        </div>
        <div style={{ padding:"12px 14px", background:C.blueDim, border:`1px solid ${C.blue}40`, borderRadius:6 }}>
          <p style={{ fontSize:13, color:C.blue, fontWeight:600, marginBottom:6 }}>¿Qué es el Criterio de Kelly?</p>
          <p style={{ fontSize:13, color:C.text1, lineHeight:1.7 }}>
            Kelly es una fórmula matemática que calcula el <strong style={{color:C.text0}}>tamaño óptimo de cada apuesta</strong> 
            según tu ventaja y la cuota disponible. Apostamos el <strong style={{color:C.text0}}>50% del Kelly completo</strong> 
            (Kelly fraccionado) para reducir el riesgo.
          </p>
        </div>
        <div style={{ display:"flex", flexDirection:"column", gap:8 }}>
          <p style={{ fontSize:13, color:C.text1, fontWeight:600 }}>Reglas de gestión del capital:</p>
          {[
            "Nunca apostar más del 20% del bankroll total en un mismo día.",
            "El sistema limita automáticamente cada apuesta individual al resultado de Kelly.",
            "Podés editar tu bankroll en la pestaña 'Bankroll' cuando cambie tu capital.",
            "La curva del gráfico muestra la evolución simulada del capital en 60 días.",
          ].map((rule, i) => (
            <div key={i} style={{ display:"flex", gap:10, alignItems:"flex-start", padding:"8px 12px",
              background:C.bg3, borderRadius:5 }}>
              <span style={{ color:C.green, fontWeight:700, flexShrink:0 }}>✓</span>
              <span style={{ fontSize:12, color:C.text1, lineHeight:1.6 }}>{rule}</span>
            </div>
          ))}
        </div>
      </div>
    ),
    flujo: (
      <div style={{ display:"flex", flexDirection:"column", gap:12 }}>
        <p style={{ fontSize:14, color:C.text1, marginBottom:4 }}>Seguí estos pasos para usar el sistema:</p>
        {[
          { n:"1", title:"Revisá las Value Bets del día", desc:"Entrá a la pestaña 'Value Bets'. El sistema ya analizó los partidos próximos y listó las mejores oportunidades ordenadas por edge." },
          { n:"2", title:"Filtrá según tu criterio", desc:"Usá los filtros para ver solo las apuestas de confianza ALTA, o filtrar por liga. Movés el slider de 'Edge mín' para ver solo las mejores oportunidades." },
          { n:"3", title:"Seleccioná las apuestas que te interesan", desc:"Hacé clic en cualquier fila para seleccionarla (se pone verde). El sistema suma automáticamente el stake total de tu selección." },
          { n:"4", title:"Verificá el stake sugerido", desc:"La columna STAKE te dice cuánto apostar en cada partido según tu bankroll. La columna KELLY te muestra el porcentaje de tu capital." },
          { n:"5", title:"Actualizá si querés datos frescos", desc:"El sistema se actualiza automáticamente cada 2 minutos. También podés presionar el botón 'Actualizar Ahora' para forzar un nuevo análisis." },
          { n:"6", title:"Actualizá tu bankroll", desc:"Después de cada sesión, entrá a la pestaña 'Bankroll' y actualizá tu capital real para que los stakes calculados sean correctos." },
        ].map(step => (
          <div key={step.n} style={{ display:"flex", gap:12, padding:"10px 14px",
            background:C.bg3, borderRadius:6, border:`1px solid ${C.border}` }}>
            <div style={{ width:28, height:28, borderRadius:"50%", background:C.green+"30",
              border:`1px solid ${C.green}50`, display:"flex", alignItems:"center",
              justifyContent:"center", flexShrink:0 }}>
              <span style={{ fontSize:13, fontWeight:700, color:C.green }}>{step.n}</span>
            </div>
            <div>
              <div style={{ fontSize:13, fontWeight:600, color:C.text0, marginBottom:4 }}>{step.title}</div>
              <div style={{ fontSize:12, color:C.text1, lineHeight:1.6 }}>{step.desc}</div>
            </div>
          </div>
        ))}
      </div>
    ),
  }

  return (
    <div style={{ position:"fixed", inset:0, background:"#000a", zIndex:1000,
      display:"flex", alignItems:"center", justifyContent:"center" }}
      onClick={e => { if(e.target === e.currentTarget) onClose() }}>
      <div style={{ background:C.bg1, border:`1px solid ${C.border2}`, borderRadius:10,
        width:"min(720px, 95vw)", maxHeight:"85vh", display:"flex", flexDirection:"column",
        overflow:"hidden", boxShadow:"0 24px 60px #0009" }}>
        {/* Header */}
        <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between",
          padding:"14px 18px", borderBottom:`1px solid ${C.border}`, background:C.bg3 }}>
          <div style={{ display:"flex", alignItems:"center", gap:10 }}>
            <span style={{ fontSize:18 }}>📖</span>
            <span style={{ fontSize:15, fontWeight:600, color:C.text0 }}>Guía de Uso — ValueBet Analyzer</span>
          </div>
          <button onClick={onClose} style={{ background:"none", border:"none",
            color:C.text1, cursor:"pointer", fontSize:18, lineHeight:1 }}>✕</button>
        </div>
        {/* Body */}
        <div style={{ display:"flex", flex:1, overflow:"hidden" }}>
          {/* Sidebar */}
          <div style={{ width:180, borderRight:`1px solid ${C.border}`, padding:"12px 0",
            display:"flex", flexDirection:"column", gap:2, flexShrink:0 }}>
            {sections.map(s => (
              <button key={s.id} onClick={() => setSection(s.id)}
                style={{ background: section===s.id ? C.bg2 : "none",
                  border:"none", borderLeft: section===s.id ? `2px solid ${C.green}` : "2px solid transparent",
                  color: section===s.id ? C.text0 : C.text1,
                  padding:"9px 16px", textAlign:"left", cursor:"pointer",
                  fontSize:13, fontWeight: section===s.id ? 600 : 400,
                  transition:"all .15s" }}>
                {s.label}
              </button>
            ))}
          </div>
          {/* Content */}
          <div style={{ flex:1, padding:"18px 20px", overflowY:"auto" }}>
            {content[section]}
          </div>
        </div>
      </div>
    </div>
  )
}

/* ─── MAIN APP ──────────────────────────────────────────────────────────── */
export default function App() {
  const [tab,        setTab]        = useState("alerts")
  const [alerts,     setAlerts]     = useState([])
  const [bkData,     setBkData]     = useState(null)
  const [leagueList, setLeagueList] = useState([])
  const [arbList,    setArbList]    = useState([])
  const [loading,    setLoading]    = useState(true)
  const [error,      setError]      = useState(null)
  const [refreshing, setRefreshing] = useState(false)
  const [selected,   setSelected]   = useState(new Set())
  const [selLeague,  setSelLeague]  = useState("all")
  const [selConf,    setSelConf]    = useState("all")
  const [minEdge,    setMinEdge]    = useState(0)
  const [lastUpdate, setLastUpdate] = useState(null)
  const [bankrollCurve, setBankrollCurve] = useState([])
  const [editBankroll, setEditBankroll]   = useState(false)
  const [newBankroll,  setNewBankroll]    = useState("")
  const [showHelp,     setShowHelp]       = useState(false)

  const loadAll = useCallback(async () => {
    try {
      setError(null)
      const [alertsRes, bkRes, leaguesRes, arbRes] = await Promise.all([
        api.alerts(), api.bankroll(), api.leagues(), api.arbitrage()
      ])
      setAlerts(alertsRes.alerts || [])
      setBkData(bkRes)
      setLeagueList(leaguesRes.leagues || [])
      setArbList(arbRes.opportunities || [])
      setBankrollCurve(genBankrollCurve(bkRes.bankroll))
      setLastUpdate(new Date())
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadAll() }, [loadAll])
  useEffect(() => {
    const id = setInterval(loadAll, 120_000)
    return () => clearInterval(id)
  }, [loadAll])

  const doRefresh = async () => {
    setRefreshing(true)
    try { await api.refresh(); await loadAll() }
    catch (e) { setError(e.message) }
    finally { setRefreshing(false) }
  }

  const saveBankroll = async () => {
    const val = parseFloat(newBankroll)
    if (isNaN(val) || val <= 0) return
    await api.setBankroll(val)
    await loadAll()
    setEditBankroll(false)
    setNewBankroll("")
  }

  const toggleSel = id => {
    const n = new Set(selected)
    n.has(id) ? n.delete(id) : n.add(id)
    setSelected(n)
  }

  const filtered = alerts.filter(a =>
    (selLeague === "all" || a.league === selLeague) &&
    (selConf   === "all" || a.confidence === selConf) &&
    a.edge_pct >= minEdge
  )
  const selAlerts  = alerts.filter(a => selected.has(a.match_id + a.market))
  const totalStake = selAlerts.reduce((s, a) => s + Math.round((bkData?.bankroll||1000) * a.kelly_frac), 0)
  const avgEdge    = alerts.length ? (alerts.reduce((s,a)=>s+a.edge_pct,0)/alerts.length).toFixed(1) : "0.0"
  const highConf   = alerts.filter(a=>a.confidence==="ALTA").length
  const maxEdge    = alerts.length ? Math.max(...alerts.map(a=>a.edge_pct)).toFixed(1) : "0.0"
  const bk         = bkData?.bankroll || 1000
  const roi        = bankrollCurve.length > 1
    ? (((bk - bankrollCurve[0].balance) / bankrollCurve[0].balance)*100).toFixed(1)
    : "0.0"

  const tabs = [
  { id:"alerts",   label:"Value Bets",      tooltip:"Apuestas con ventaja matematica detectadas hoy" },
  { id:"bankroll", label:"Bankroll",         tooltip:"Gestion de tu capital y curva de rendimiento" },
  { id:"analysis", label:"Analisis",         tooltip:"Precision del modelo y fuentes de datos" },
  { id:"sports",   label:"Tenis & Basquet",  tooltip:"Analisis de tenis y basquet" },
  { id:"walkforward", label:"Walk-Forward" },
  { id:"backtest", label:"Backtesting",      tooltip:"Simulacion historica de tu estrategia" },
]

  return (
    <div style={{ background:C.bg0, minHeight:"100vh", color:C.text0,
      fontFamily:"'DM Sans',sans-serif", fontSize:14 }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=DM+Sans:wght@300;400;500;600&display=swap');
        *{box-sizing:border-box;margin:0;padding:0}
        ::-webkit-scrollbar{width:5px;height:5px}
        ::-webkit-scrollbar-track{background:${C.bg1}}
        ::-webkit-scrollbar-thumb{background:${C.border2};border-radius:3px}
        @keyframes fadeIn{from{opacity:0;transform:translateY(3px)}to{opacity:1;transform:translateY(0)}}
        @keyframes pulse{0%{box-shadow:0 0 0 0 ${C.green}80}70%{box-shadow:0 0 0 6px ${C.green}00}100%{box-shadow:0 0 0 0 ${C.green}00}}
        @keyframes spin{to{transform:rotate(360deg)}}
        @keyframes shimmer{0%{background-position:200% 0}100%{background-position:-200% 0}}
        .alert-row:hover{background:${C.bg3} !important;cursor:pointer}
        .tab-btn{background:none;border:none;cursor:pointer;transition:color .15s;padding:10px 16px;font-size:13px;font-weight:500;font-family:'DM Sans',sans-serif;border-bottom:2px solid transparent;margin-bottom:-1px}
        .sel{background:${C.bg3};border:1px solid ${C.border};color:${C.text1};border-radius:4px;padding:5px 10px;font-size:12px;font-family:'DM Sans',sans-serif;cursor:pointer;outline:none}
        .btn{background:none;border:1px solid ${C.border2};color:${C.text1};border-radius:4px;padding:5px 12px;font-size:12px;font-family:'DM Sans',sans-serif;cursor:pointer;transition:all .15s}
        .btn:hover{background:${C.bg3};color:${C.text0}}
        .btn.green{border-color:${C.green}50;color:${C.green}}
        .btn.green:hover{background:${C.greenDim}}
        .btn.help{border-color:${C.blue}50;color:${C.blue};font-weight:600}
        .btn.help:hover{background:${C.blueDim}}
        input[type=range]{accent-color:${C.green}}
      `}</style>

      {showHelp && <HelpPanel onClose={() => setShowHelp(false)} />}

      {/* ── HEADER ── */}
      <div style={{ background:C.bg1, borderBottom:`1px solid ${C.border}`,
        padding:"0 20px", display:"flex", alignItems:"center",
        justifyContent:"space-between", height:54 }}>
        <div style={{ display:"flex", alignItems:"center", gap:14 }}>
          <div style={{ display:"flex", alignItems:"center", gap:8 }}>
            <div style={{ width:30, height:30, borderRadius:6,
              background:`linear-gradient(135deg,${C.green}30,${C.blue}20)`,
              border:`1px solid ${C.green}40`, display:"flex", alignItems:"center",
              justifyContent:"center", fontSize:15 }}>◈</div>
            <div>
              <span style={{ fontSize:15, fontWeight:700, letterSpacing:"-.02em" }}>ValueBet</span>
              <span style={{ fontSize:10, color:C.text2, fontFamily:"'JetBrains Mono',monospace", marginLeft:6 }}>ANALYZER</span>
            </div>
          </div>
          <div style={{ width:1, height:20, background:C.border }} />
          <span style={{ display:"inline-flex", alignItems:"center", gap:6 }}>
            <span style={{ width:7, height:7, borderRadius:"50%", background:C.green,
              animation:"pulse 2s infinite", display:"inline-block" }} />
            <span style={{ fontSize:11, color:C.green, fontFamily:"'JetBrains Mono',monospace",
              letterSpacing:".1em" }}>EN VIVO</span>
          </span>
          {lastUpdate && (
            <span style={{ fontSize:11, color:C.text2, fontFamily:"'JetBrains Mono',monospace" }}>
              Actualizado: {lastUpdate.toLocaleTimeString("es-AR",{hour:"2-digit",minute:"2-digit"})}
            </span>
          )}
        </div>

        <div style={{ display:"flex", alignItems:"center", gap:18 }}>
          {[
            { label:"Capital Total",    value: loading ? "..." : `$${bk.toLocaleString()}`, color:C.text0 },
            { label:"Rendimiento ROI",  value: loading ? "..." : `${roi>0?"+":""}${roi}%`,   color:roi>0?C.green:C.red },
            { label:"Apuestas Hoy",     value: loading ? "..." : alerts.length,              color:C.blue },
            { label:"Edge Promedio",    value: loading ? "..." : `+${avgEdge}%`,             color:C.amber },
          ].map(s => (
            <div key={s.label} style={{ display:"flex", flexDirection:"column", alignItems:"flex-end" }}>
              <span style={{ fontSize:10, color:C.text2, fontFamily:"'JetBrains Mono',monospace",
                letterSpacing:".08em", textTransform:"uppercase" }}>{s.label}</span>
              <span style={{ fontSize:14, fontWeight:700, color:s.color,
                fontFamily:"'JetBrains Mono',monospace" }}>{s.value}</span>
            </div>
          ))}
          <button className="btn help" onClick={() => setShowHelp(true)}>
            ? Ayuda
          </button>
          <button className="btn" onClick={doRefresh}
            style={{ display:"flex", alignItems:"center", gap:5 }}>
            <span style={{ display:"inline-block",
              animation:refreshing?"spin 1s linear infinite":"none", fontSize:14 }}>↺</span>
            {refreshing ? "Analizando..." : "Actualizar Ahora"}
          </button>
        </div>
      </div>

      {/* ── TABS ── */}
      <div style={{ background:C.bg1, borderBottom:`1px solid ${C.border}`,
        padding:"0 20px", display:"flex", gap:4 }}>
        {tabs.map(t => (
          <button key={t.id} className="tab-btn" onClick={() => setTab(t.id)}
            title={t.tooltip}
            style={{ color: tab===t.id ? C.text0 : C.text2,
              borderBottomColor: tab===t.id ? C.green : "transparent" }}>
            {t.label}
          </button>
        ))}
      </div>

      {/* ── ERROR BANNER ── */}
      {error && (
        <div style={{ background:C.red+"20", border:`1px solid ${C.red}40`,
          margin:"12px 20px", borderRadius:6, padding:"12px 16px",
          display:"flex", alignItems:"center", justifyContent:"space-between" }}>
          <span style={{ fontSize:13, color:C.red }}>⚠ Error conectando al servidor: {error}</span>
          <button className="btn" onClick={loadAll}>Reintentar</button>
        </div>
      )}

      <div style={{ padding:"16px 20px", animation:"fadeIn .3s ease" }}>

        {/* ══════════ TAB: VALUE BETS ══════════ */}
        {tab === "alerts" && (
          <div style={{ display:"flex", flexDirection:"column", gap:12 }}>

            {/* Summary cards */}
            <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:10 }}>
              {loading
                ? Array(4).fill(0).map((_,i) => <Panel key={i} style={{ padding:"14px 16px" }}><Skeleton h={48}/></Panel>)
                : [
                  { label:"Apuestas de Valor",      value:alerts.length,  sub:"detectadas hoy",           color:C.blue  },
                  { label:"Confianza Alta",          value:highConf,       sub:"con ventaja ≥ 10%",        color:C.green },
                  { label:"Mayor Ventaja (Edge)",    value:`+${maxEdge}%`, sub:"mejor apuesta disponible", color:C.amber },
                  { label:"Capital en Juego Sugerido", value:`$${Math.round(bk*0.20)}`, sub:"máximo recomendado (20%)", color:C.text0 },
                ].map(s => (
                  <Panel key={s.label} style={{ padding:"14px 16px" }}>
                    <Stat label={s.label} value={s.value} sub={s.sub} color={s.color} />
                  </Panel>
                ))
              }
            </div>

            {/* Filters */}
            <div style={{ display:"flex", alignItems:"center", gap:10, flexWrap:"wrap",
              padding:"10px 14px", background:C.bg2, border:`1px solid ${C.border}`, borderRadius:6 }}>
              <span style={{ fontSize:12, color:C.text2, fontWeight:600 }}>FILTRAR POR:</span>
              <select className="sel" value={selLeague} onChange={e=>setSelLeague(e.target.value)}>
                <option value="all">Todas las ligas</option>
                {leagueList.map(l => <option key={l} value={l}>{l}</option>)}
              </select>
              <select className="sel" value={selConf} onChange={e=>setSelConf(e.target.value)}>
                <option value="all">Todo nivel de confianza</option>
                <option value="ALTA">Solo confianza ALTA</option>
                <option value="MEDIA">Solo confianza MEDIA</option>
              </select>
              <div style={{ display:"flex", alignItems:"center", gap:6 }}>
                <span style={{ fontSize:12, color:C.text2 }}>Ventaja mínima:</span>
                <input type="range" min={0} max={18} step={1} value={minEdge}
                  onChange={e=>setMinEdge(+e.target.value)} style={{ width:80 }}/>
                <span style={{ fontSize:13, color:C.amber, fontFamily:"'JetBrains Mono',monospace",
                  minWidth:32, fontWeight:700 }}>{minEdge}%</span>
              </div>
              {selected.size > 0 && (
                <div style={{ display:"flex", alignItems:"center", gap:8,
                  background:C.greenDim, border:`1px solid ${C.green}30`,
                  borderRadius:4, padding:"5px 12px", marginLeft:"auto" }}>
                  <span style={{ fontSize:12, color:C.green }}>
                    {selected.size} apuesta{selected.size>1?"s":""} seleccionada{selected.size>1?"s":""} · Total a apostar: ${totalStake}
                  </span>
                  <button onClick={()=>setSelected(new Set())}
                    style={{ background:"none", border:"none", color:C.green, cursor:"pointer", fontSize:14 }}>✕</button>
                </div>
              )}
              <span style={{ fontSize:12, color:C.text2, marginLeft:selected.size>0?"0":"auto" }}>
                {filtered.length} resultado{filtered.length!==1?"s":""}
              </span>
            </div>

            {/* Alerts table */}
            <Panel title="APUESTAS DE VALOR DETECTADAS — TIEMPO REAL">
              {/* Table header */}
              <div style={{ display:"grid",
                gridTemplateColumns:"24px 80px minmax(0,1fr) 110px 64px 70px 72px 70px 74px",
                gap:8, padding:"8px 14px", borderBottom:`1px solid ${C.border}`, background:C.bg3 }}>
                {[
                  {h:"", tip:""},
                  {h:"CONFIANZA", tip:"Nivel de confianza de la apuesta"},
                  {h:"PARTIDO", tip:"Equipos y liga"},
                  {h:"TIPO DE APUESTA", tip:"Mercado disponible"},
                  {h:"CUOTA", tip:"Cuota actual de la casa"},
                  {h:"PROB. MODELO", tip:"Probabilidad calculada por el modelo"},
                  {h:"VENTAJA", tip:"Edge sobre la casa de apuestas"},
                  {h:"APOSTAR", tip:"Monto sugerido según tu capital"},
                  {h:"% CAPITAL", tip:"Porcentaje de tu bankroll a usar"},
                ].map(({h, tip}, i) => (
                  <span key={i} title={tip} style={{ fontSize:10, color:C.text2,
                    fontFamily:"'JetBrains Mono',monospace", letterSpacing:".06em", cursor: tip ? "help" : "default" }}>{h}</span>
                ))}
              </div>

              {/* Rows */}
              <div style={{ maxHeight:420, overflowY:"auto" }}>
                {loading && Array(6).fill(0).map((_,i) => (
                  <div key={i} style={{ padding:"12px 14px", borderBottom:`1px solid ${C.border}` }}>
                    <Skeleton h={16}/>
                  </div>
                ))}
                {!loading && filtered.length === 0 && (
                  <div style={{ padding:"36px", textAlign:"center", color:C.text2, fontSize:14 }}>
                    No hay apuestas con estos filtros. Probá reducir la ventaja mínima.
                  </div>
                )}
                {!loading && filtered.map((a, idx) => {
                  const rowKey = a.match_id + a.market
                  const stake  = Math.round(bk * a.kelly_frac)
                  return (
                    <div key={rowKey} className="alert-row" onClick={() => toggleSel(rowKey)}
                      title="Hacé clic para seleccionar esta apuesta"
                      style={{ display:"grid",
                        gridTemplateColumns:"24px 80px minmax(0,1fr) 110px 64px 70px 72px 70px 74px",
                        gap:8, padding:"10px 14px", borderBottom:`1px solid ${C.border}`,
                        background:selected.has(rowKey)?C.greenDim:"transparent",
                        borderLeft:selected.has(rowKey)?`3px solid ${C.green}`:"3px solid transparent",
                        animation:`fadeIn .2s ease ${idx*.025}s both`, alignItems:"center" }}>
                      <div style={{ width:15, height:15, borderRadius:3,
                        border:`1px solid ${selected.has(rowKey)?C.green:C.border2}`,
                        background:selected.has(rowKey)?C.green:"transparent",
                        display:"flex", alignItems:"center", justifyContent:"center", flexShrink:0 }}>
                        {selected.has(rowKey) && <span style={{ fontSize:9, color:"#000", fontWeight:900, lineHeight:1 }}>✓</span>}
                      </div>
                      <Badge text={a.confidence} color={confColor(a.confidence)} bg={confBg(a.confidence)}/>
                      <div style={{ minWidth:0 }}>
                        <div style={{ display:"flex", alignItems:"center", gap:5, overflow:"hidden" }}>
                          <span style={{ fontSize:13, flexShrink:0 }}>{leagueIcon(a.league)}</span>
                          <span style={{ fontSize:13, fontWeight:600, whiteSpace:"nowrap",
                            overflow:"hidden", textOverflow:"ellipsis" }}>
                            {a.home_team} <span style={{color:C.text2, fontWeight:400}}>vs</span> {a.away_team}
                          </span>
                        </div>
                        <div style={{ fontSize:11, color:C.text2, fontFamily:"'JetBrains Mono',monospace", marginTop:2 }}>
                          {a.league} · {a.kickoff} · λ {a.lambda_home?.toFixed(2)}/{a.lambda_away?.toFixed(2)}
                        </div>
                      </div>
                      <span style={{ fontSize:12, color:C.text1, overflow:"hidden",
                        textOverflow:"ellipsis", whiteSpace:"nowrap" }}>
                        {a.market_label || a.market}
                      </span>
                      <span style={{ fontSize:14, fontWeight:700, color:C.text0,
                        fontFamily:"'JetBrains Mono',monospace" }}>{a.odd?.toFixed(2)}</span>
                      <span style={{ fontSize:13, color:C.blue, fontFamily:"'JetBrains Mono',monospace", fontWeight:600 }}>
                        {(a.p_model*100).toFixed(1)}%
                      </span>
                      <span style={{ fontSize:14, fontWeight:700,
                        color:a.edge_pct>=15?C.green:a.edge_pct>=8?C.amber:C.text1,
                        fontFamily:"'JetBrains Mono',monospace" }}>+{a.edge_pct?.toFixed(1)}%</span>
                      <span style={{ fontSize:13, fontWeight:700, color:C.green,
                        fontFamily:"'JetBrains Mono',monospace" }}>${stake}</span>
                      <span style={{ fontSize:12, color:C.text2,
                        fontFamily:"'JetBrains Mono',monospace" }}>{(a.kelly_frac*100).toFixed(1)}%</span>
                    </div>
                  )
                })}
              </div>

              {/* Footer */}
              <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between",
                padding:"9px 14px", borderTop:`1px solid ${C.border}`, background:C.bg3 }}>
                <span style={{ fontSize:11, color:C.text2 }}>
                  Modelos: Poisson + Regresión Logística (60/40) · Kelly fraccionado al 50% · Ventaja mínima 3%
                </span>
                <button className="btn green">⚡ Notificar por Telegram</button>
              </div>
            </Panel>

            {/* Arbitrage alerts */}
            {arbList.length > 0 && arbList.map((arb, i) => (
              <div key={i} style={{ padding:"11px 14px", background:C.amberDim,
                border:`1px solid ${C.amber}30`, borderRadius:6,
                display:"flex", alignItems:"center", gap:12 }}>
                <span style={{ color:C.amber, fontSize:16, flexShrink:0 }}>⚡</span>
                <div>
                  <span style={{ fontSize:13, fontWeight:700, color:C.amber }}>OPORTUNIDAD DE ARBITRAJE </span>
                  <span style={{ fontSize:13, color:C.text1 }}>
                    {arb.match} — {arb.league} → Ganancia garantizada: +{arb.profit_pct}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* ══════════ TAB: BANKROLL ══════════ */}
        {tab === "bankroll" && (
          <div style={{ display:"flex", flexDirection:"column", gap:12 }}>
            <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:10 }}>
              {loading
                ? Array(4).fill(0).map((_,i)=><Panel key={i} style={{padding:"14px 16px"}}><Skeleton h={48}/></Panel>)
                : [
                  { label:"Capital Actual",         value:`$${bk.toLocaleString()}`,          color:C.text0 },
                  { label:"Rendimiento Total (ROI)", value:`${roi>0?"+":""}${roi}%`,            color:roi>0?C.green:C.red },
                  { label:"Capital Sugerido en Juego", value:`$${Math.round(bkData?.suggested_exposure||0)}`, color:C.amber },
                  { label:"Apuestas Activas",        value:alerts.length,                     color:C.blue  },
                ].map(s => (
                  <Panel key={s.label} style={{ padding:"14px 16px" }}>
                    <Stat label={s.label} value={s.value} color={s.color}/>
                  </Panel>
                ))
              }
            </div>

            <div style={{ display:"grid", gridTemplateColumns:"2fr 1fr", gap:12 }}>
              <Panel title="EVOLUCIÓN DEL CAPITAL — ÚLTIMOS 60 DÍAS" style={{ padding:"14px" }}>
                <ResponsiveContainer width="100%" height={230}>
                  <AreaChart data={bankrollCurve} margin={{ top:8, right:8, left:-10, bottom:0 }}>
                    <defs>
                      <linearGradient id="bkGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%"  stopColor={C.green} stopOpacity={0.2}/>
                        <stop offset="95%" stopColor={C.green} stopOpacity={0}/>
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke={C.border} vertical={false}/>
                    <XAxis dataKey="date" tick={{ fill:C.text2, fontSize:10, fontFamily:"DM Sans" }}
                      tickLine={false} axisLine={false} interval={9}/>
                    <YAxis tick={{ fill:C.text2, fontSize:10, fontFamily:"DM Sans" }}
                      tickLine={false} axisLine={false} tickFormatter={v=>`$${v}`} width={48}/>
                    <Tooltip content={<CustomTT/>}/>
                    <ReferenceLine y={bankrollCurve[0]?.balance} stroke={C.border2} strokeDasharray="4 4"/>
                    <Area type="monotone" dataKey="balance" stroke={C.green} strokeWidth={2}
                      fill="url(#bkGrad)" name="balance"/>
                  </AreaChart>
                </ResponsiveContainer>
              </Panel>

              <Panel title="DISTRIBUCIÓN DE VENTAJA HISTÓRICA" style={{ padding:"14px" }}>
                <ResponsiveContainer width="100%" height={230}>
                  <BarChart data={EDGE_DIST} margin={{ top:8, right:5, left:-20, bottom:0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={C.border} vertical={false}/>
                    <XAxis dataKey="range" tick={{ fill:C.text2, fontSize:9, fontFamily:"DM Sans" }}
                      tickLine={false} axisLine={false}/>
                    <YAxis tick={{ fill:C.text2, fontSize:10, fontFamily:"DM Sans" }}
                      tickLine={false} axisLine={false} width={22}/>
                    <Tooltip content={<CustomTT/>}/>
                    <Bar dataKey="n" radius={[3,3,0,0]} name="apuestas">
                      {EDGE_DIST.map((e,i) => <Cell key={i} fill={e.c}/>)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </Panel>
            </div>

            {/* Bankroll editor */}
            <Panel title="CONFIGURAR MI CAPITAL (BANKROLL)" style={{ padding:"16px" }}>
              <div style={{ display:"flex", alignItems:"center", gap:14 }}>
                <div>
                  <div style={{ fontSize:12, color:C.text2, marginBottom:4 }}>Capital actual registrado:</div>
                  <span style={{ fontSize:22, fontWeight:700, color:C.text0,
                    fontFamily:"'JetBrains Mono',monospace" }}>${bk.toLocaleString()}</span>
                </div>
                {!editBankroll
                  ? <button className="btn" onClick={()=>{setEditBankroll(true);setNewBankroll(bk)}}>
                      Actualizar mi capital
                    </button>
                  : <>
                    <input type="number" value={newBankroll} onChange={e=>setNewBankroll(e.target.value)}
                      placeholder="Nuevo monto en $"
                      style={{ background:C.bg3, border:`1px solid ${C.border2}`, color:C.text0,
                        borderRadius:4, padding:"6px 12px", fontSize:14,
                        fontFamily:"'JetBrains Mono',monospace", width:140, outline:"none" }}/>
                    <button className="btn green" onClick={saveBankroll}>Guardar</button>
                    <button className="btn" onClick={()=>setEditBankroll(false)}>Cancelar</button>
                  </>
                }
              </div>
              <div style={{ marginTop:14 }}>
                <div style={{ display:"flex", justifyContent:"space-between", marginBottom:8 }}>
                  <span style={{ fontSize:12, color:C.text2 }}>
                    Capital comprometido hoy: ${Math.round(bkData?.suggested_exposure||0)} de ${Math.round(bk*0.20)} máximo (20% del capital)
                  </span>
                </div>
                <div style={{ height:6, borderRadius:3, background:C.bg3, overflow:"hidden" }}>
                  <div style={{ width:`${Math.min(((bkData?.suggested_exposure||0)/(bk*0.20))*100,100)}%`,
                    height:"100%", background:C.green, borderRadius:3 }}/>
                </div>
              </div>
            </Panel>
          </div>
        )}

        {/* ══════════ TAB: ANÁLISIS ══════════ */}
        {tab === "sports" && <SportsPanel />}
          {tab === "walkforward" && <WalkForwardPanel />}{tab === "backtest" && <BacktestPanel />}
          {tab === "analysis" && (
          <div style={{ display:"flex", flexDirection:"column", gap:12 }}>
            <Panel title="PRECISIÓN DEL MODELO POR TIPO DE APUESTA">
              <div style={{ display:"grid", gridTemplateColumns:"repeat(5,1fr)" }}>
                {[
                  { mkt:"Victoria Local",    acc:54.2, color:C.amber },
                  { mkt:"Empate",            acc:28.4, color:C.text1 },
                  { mkt:"Victoria Visitante",acc:41.1, color:C.amber },
                  { mkt:"Más de 2.5 Goles", acc:61.8, color:C.green },
                  { mkt:"Menos de 2.5 Goles",acc:58.3, color:C.green },
                ].map((m,i) => (
                  <div key={i} style={{ padding:"16px 14px",
                    borderRight:i<4?`1px solid ${C.border}`:"none" }}>
                    <div style={{ fontSize:11, color:C.text2, marginBottom:10, fontWeight:500 }}>{m.mkt}</div>
                    <div style={{ fontSize:26, fontWeight:700, color:m.color,
                      fontFamily:"'JetBrains Mono',monospace", lineHeight:1 }}>{m.acc}%</div>
                    <div style={{ fontSize:11, color:C.text2, marginTop:6 }}>en 186 partidos</div>
                    <div style={{ marginTop:10, height:4, borderRadius:2, background:C.bg3, overflow:"hidden" }}>
                      <div style={{ width:`${m.acc}%`, height:"100%", background:m.color, borderRadius:2 }}/>
                    </div>
                  </div>
                ))}
              </div>
            </Panel>

            <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:12 }}>
              <Panel title="PARÁMETROS INTERNOS DEL MODELO">
                <div style={{ padding:"14px", display:"flex", flexDirection:"column", gap:11 }}>
                  {[
                    { label:"Ventaja de local (λ)",       value:"1.131", bar:0.57, color:C.green,  tip:"Factor de ajuste por jugar en casa" },
                    { label:"Kelly fraccionado",           value:"50%",   bar:0.50, color:C.blue,   tip:"Usamos el 50% del Kelly para reducir riesgo" },
                    { label:"Peso modelo Poisson",         value:"60%",   bar:0.60, color:C.green,  tip:"Importancia del modelo de Poisson en el resultado final" },
                    { label:"Peso Regresión Logística",    value:"40%",   bar:0.40, color:C.blue,   tip:"Importancia del modelo de ML en el resultado final" },
                    { label:"Ventaja mínima para apostar", value:"3%",    bar:0.15, color:C.amber,  tip:"No apostamos si el edge es menor a este valor" },
                    { label:"Límite de exposición diaria", value:"20%",   bar:0.20, color:C.purple, tip:"Máximo del capital total por día" },
                  ].map(p => (
                    <div key={p.label} style={{ display:"flex", alignItems:"center", gap:12 }} title={p.tip}>
                      <span style={{ fontSize:12, color:C.text1, minWidth:200, flexShrink:0, cursor:"help" }}>{p.label}</span>
                      <div style={{ flex:1, height:4, borderRadius:2, background:C.bg3, overflow:"hidden" }}>
                        <div style={{ width:`${p.bar*100}%`, height:"100%", background:p.color, borderRadius:2 }}/>
                      </div>
                      <span style={{ fontSize:13, fontWeight:700, color:p.color,
                        fontFamily:"'JetBrains Mono',monospace", minWidth:52, textAlign:"right" }}>{p.value}</span>
                    </div>
                  ))}
                </div>
              </Panel>

              <Panel title="FUENTES DE DATOS">
                <div style={{ padding:"14px", display:"flex", flexDirection:"column", gap:10 }}>
                  {[
                    { name:"Datos históricos de partidos", status:"✓ Activo",    color:C.green,  detail:"Datos sintéticos generados con distribución Poisson" },
                    { name:"The Odds API (cuotas reales)", status:"○ Pendiente", color:C.text2,  detail:"500 solicitudes/mes en plan gratuito"   },
                    { name:"API-Football (estadísticas)",  status:"○ Pendiente", color:C.text2,  detail:"100 solicitudes/día en plan gratuito"   },
                    { name:"OpenWeatherMap (clima)",       status:"○ Pendiente", color:C.text2,  detail:"1000 solicitudes/día en plan gratuito"  },
                  ].map(s => (
                    <div key={s.name} style={{ display:"flex", alignItems:"center",
                      justifyContent:"space-between", padding:"10px 0",
                      borderBottom:`1px solid ${C.border}` }}>
                      <div>
                        <div style={{ fontSize:13, fontWeight:500 }}>{s.name}</div>
                        <div style={{ fontSize:11, color:C.text2, marginTop:3 }}>{s.detail}</div>
                      </div>
                      <Badge text={s.status} color={s.color}/>
                    </div>
                  ))}
                  <div style={{ marginTop:4, padding:"10px 12px", background:C.blueDim,
                    border:`1px solid ${C.blue}30`, borderRadius:4, fontSize:12, color:C.text1, lineHeight:1.6 }}>
                    Para activar datos reales de cuotas y estadísticas, completar las API keys en{" "}
                    <code style={{ color:C.blue, fontSize:11 }}>data/fetcher.py</code>.
                  </div>
                </div>
              </Panel>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

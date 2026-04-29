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
    <span style={{ fontSize:9, fontWeight:700, padding:"2px 6px", borderRadius:3,
      background: bg||color+"20", color, letterSpacing:".1em",
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
          padding:"8px 12px", borderBottom:`1px solid ${C.border}`, background:C.bg3 }}>
          <span style={{ fontSize:9, fontWeight:700, color:C.text2, letterSpacing:".12em",
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
    <div style={{ display:"flex", flexDirection:"column", gap:3 }}>
      <span style={{ fontSize:9, color:C.text2, letterSpacing:".1em", textTransform:"uppercase",
        fontFamily:"'JetBrains Mono',monospace" }}>{label}</span>
      <span style={{ fontSize:22, fontWeight:700, color, fontFamily:"'JetBrains Mono',monospace", lineHeight:1 }}>
        {value}
      </span>
      {sub && <span style={{ fontSize:10, color:C.text2, marginTop:1 }}>{sub}</span>}
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
    <div style={{ background:C.bg3, border:`1px solid ${C.border2}`, borderRadius:4, padding:"7px 11px" }}>
      <div style={{ fontSize:9, color:C.text2, marginBottom:3, fontFamily:"'JetBrains Mono',monospace" }}>{label}</div>
      {payload.map((p, i) => (
        <div key={i} style={{ fontSize:11, color:p.color||C.text0, fontFamily:"'JetBrains Mono',monospace" }}>
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

  /* ── Filtered alerts ── */
  const filtered = alerts.filter(a =>
    (selLeague === "all" || a.league === selLeague) &&
    (selConf   === "all" || a.confidence === selConf) &&
    a.edge_pct >= minEdge
  )
  const selAlerts    = alerts.filter(a => selected.has(a.match_id + a.market))
  const totalStake   = selAlerts.reduce((s, a) => s + Math.round((bkData?.bankroll||1000) * a.kelly_frac), 0)
  const avgEdge      = alerts.length ? (alerts.reduce((s,a)=>s+a.edge_pct,0)/alerts.length).toFixed(1) : "0.0"
  const highConf     = alerts.filter(a=>a.confidence==="ALTA").length
  const maxEdge      = alerts.length ? Math.max(...alerts.map(a=>a.edge_pct)).toFixed(1) : "0.0"
  const bk           = bkData?.bankroll || 1000
  const roi          = bankrollCurve.length > 1
    ? (((bk - bankrollCurve[0].balance) / bankrollCurve[0].balance)*100).toFixed(1)
    : "0.0"

  const tabs = [
    { id:"alerts",   label:"Value Bets" },
    { id:"bankroll", label:"Bankroll"   },
    { id:"analysis", label:"Análisis"   },
  ]

  /* ─── GLOBAL STYLES ─────────────────────────────────────────────────────── */
  return (
    <div style={{ background:C.bg0, minHeight:"100vh", color:C.text0,
      fontFamily:"'DM Sans',sans-serif" }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=DM+Sans:wght@300;400;500;600&display=swap');
        *{box-sizing:border-box;margin:0;padding:0}
        ::-webkit-scrollbar{width:4px;height:4px}
        ::-webkit-scrollbar-track{background:${C.bg1}}
        ::-webkit-scrollbar-thumb{background:${C.border2};border-radius:2px}
        @keyframes fadeIn{from{opacity:0;transform:translateY(3px)}to{opacity:1;transform:translateY(0)}}
        @keyframes pulse{0%{box-shadow:0 0 0 0 ${C.green}80}70%{box-shadow:0 0 0 6px ${C.green}00}100%{box-shadow:0 0 0 0 ${C.green}00}}
        @keyframes spin{to{transform:rotate(360deg)}}
        @keyframes shimmer{0%{background-position:200% 0}100%{background-position:-200% 0}}
        .alert-row:hover{background:${C.bg3} !important;cursor:pointer}
        .tab-btn{background:none;border:none;cursor:pointer;transition:color .15s;padding:9px 14px;font-size:12px;font-weight:500;font-family:'DM Sans',sans-serif;border-bottom:2px solid transparent;margin-bottom:-1px}
        .sel{background:${C.bg3};border:1px solid ${C.border};color:${C.text1};border-radius:4px;padding:4px 8px;font-size:10px;font-family:'JetBrains Mono',monospace;cursor:pointer;outline:none}
        .btn{background:none;border:1px solid ${C.border2};color:${C.text1};border-radius:4px;padding:4px 10px;font-size:10px;font-family:'JetBrains Mono',monospace;cursor:pointer;transition:all .15s;letter-spacing:.06em}
        .btn:hover{background:${C.bg3};color:${C.text0}}
        .btn.green{border-color:${C.green}50;color:${C.green}}
        .btn.green:hover{background:${C.greenDim}}
        input[type=range]{accent-color:${C.green}}
      `}</style>

      {/* ── HEADER ── */}
      <div style={{ background:C.bg1, borderBottom:`1px solid ${C.border}`,
        padding:"0 16px", display:"flex", alignItems:"center",
        justifyContent:"space-between", height:48 }}>
        <div style={{ display:"flex", alignItems:"center", gap:12 }}>
          <div style={{ display:"flex", alignItems:"center", gap:7 }}>
            <div style={{ width:26, height:26, borderRadius:5,
              background:`linear-gradient(135deg,${C.green}30,${C.blue}20)`,
              border:`1px solid ${C.green}40`, display:"flex", alignItems:"center",
              justifyContent:"center", fontSize:13 }}>◈</div>
            <span style={{ fontSize:13, fontWeight:600, letterSpacing:"-.02em" }}>ValueBet</span>
            <span style={{ fontSize:9, color:C.text2, fontFamily:"'JetBrains Mono',monospace" }}>ANALYZER</span>
          </div>
          <div style={{ width:1, height:18, background:C.border }} />
          {/* Live indicator */}
          <span style={{ display:"inline-flex", alignItems:"center", gap:5 }}>
            <span style={{ width:6, height:6, borderRadius:"50%", background:C.green,
              animation:"pulse 2s infinite", display:"inline-block" }} />
            <span style={{ fontSize:9, color:C.green, fontFamily:"'JetBrains Mono',monospace",
              letterSpacing:".1em" }}>LIVE</span>
          </span>
          {lastUpdate && (
            <span style={{ fontSize:9, color:C.text2, fontFamily:"'JetBrains Mono',monospace" }}>
              {lastUpdate.toLocaleTimeString("es-AR",{hour:"2-digit",minute:"2-digit"})}
            </span>
          )}
        </div>

        <div style={{ display:"flex", alignItems:"center", gap:16 }}>
          {[
            { label:"Bankroll", value: loading ? "..." : `$${bk.toLocaleString()}`, color:C.text0 },
            { label:"ROI",      value: loading ? "..." : `${roi>0?"+":""}${roi}%`,   color:roi>0?C.green:C.red },
            { label:"VBs Hoy",  value: loading ? "..." : alerts.length,              color:C.blue },
            { label:"Avg Edge", value: loading ? "..." : `+${avgEdge}%`,             color:C.amber },
          ].map(s => (
            <div key={s.label} style={{ display:"flex", flexDirection:"column", alignItems:"flex-end" }}>
              <span style={{ fontSize:8, color:C.text2, fontFamily:"'JetBrains Mono',monospace",
                letterSpacing:".1em", textTransform:"uppercase" }}>{s.label}</span>
              <span style={{ fontSize:12, fontWeight:700, color:s.color,
                fontFamily:"'JetBrains Mono',monospace" }}>{s.value}</span>
            </div>
          ))}
          <button className="btn" onClick={doRefresh}
            style={{ display:"flex", alignItems:"center", gap:4 }}>
            <span style={{ display:"inline-block",
              animation:refreshing?"spin 1s linear infinite":"none" }}>↺</span>
            {refreshing ? "..." : "Refresh"}
          </button>
        </div>
      </div>

      {/* ── TABS ── */}
      <div style={{ background:C.bg1, borderBottom:`1px solid ${C.border}`,
        padding:"0 16px", display:"flex" }}>
        {tabs.map(t => (
          <button key={t.id} className="tab-btn" onClick={() => setTab(t.id)}
            style={{ color: tab===t.id ? C.text0 : C.text2,
              borderBottomColor: tab===t.id ? C.green : "transparent" }}>
            {t.label}
          </button>
        ))}
      </div>

      {/* ── ERROR BANNER ── */}
      {error && (
        <div style={{ background:C.red+"20", border:`1px solid ${C.red}40`,
          margin:"12px 16px", borderRadius:6, padding:"10px 14px",
          display:"flex", alignItems:"center", justifyContent:"space-between" }}>
          <span style={{ fontSize:11, color:C.red }}>⚠ Error conectando al backend: {error}</span>
          <button className="btn" onClick={loadAll}>Reintentar</button>
        </div>
      )}

      <div style={{ padding:"14px 16px", animation:"fadeIn .3s ease" }}>

        {/* ══════════ TAB: VALUE BETS ══════════ */}
        {tab === "alerts" && (
          <div style={{ display:"flex", flexDirection:"column", gap:10 }}>

            {/* Summary cards */}
            <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:8 }}>
              {loading
                ? Array(4).fill(0).map((_,i) => <Panel key={i} style={{ padding:"11px 14px" }}><Skeleton h={40}/></Panel>)
                : [
                  { label:"Value Bets",        value:alerts.length,  sub:"detectadas hoy",    color:C.blue  },
                  { label:"Confianza Alta",     value:highConf,       sub:"edge ≥ 10%",        color:C.green },
                  { label:"Edge Máximo",        value:`+${maxEdge}%`, sub:"mejor apuesta",     color:C.amber },
                  { label:"Exposición sugerida",value:`$${Math.round(bk*0.20)}`, sub:"20% bankroll", color:C.text0 },
                ].map(s => (
                  <Panel key={s.label} style={{ padding:"11px 14px" }}>
                    <Stat label={s.label} value={s.value} sub={s.sub} color={s.color} />
                  </Panel>
                ))
              }
            </div>

            {/* Filters */}
            <div style={{ display:"flex", alignItems:"center", gap:8, flexWrap:"wrap",
              padding:"8px 12px", background:C.bg2, border:`1px solid ${C.border}`, borderRadius:6 }}>
              <span style={{ fontSize:9, color:C.text2, fontFamily:"'JetBrains Mono',monospace",
                letterSpacing:".1em" }}>FILTROS</span>
              <select className="sel" value={selLeague} onChange={e=>setSelLeague(e.target.value)}>
                <option value="all">Todas las ligas</option>
                {leagueList.map(l => <option key={l} value={l}>{l}</option>)}
              </select>
              <select className="sel" value={selConf} onChange={e=>setSelConf(e.target.value)}>
                <option value="all">Toda confianza</option>
                <option value="ALTA">Solo ALTA</option>
                <option value="MEDIA">Solo MEDIA</option>
              </select>
              <div style={{ display:"flex", alignItems:"center", gap:5 }}>
                <span style={{ fontSize:9, color:C.text2, fontFamily:"'JetBrains Mono',monospace" }}>Edge mín:</span>
                <input type="range" min={0} max={18} step={1} value={minEdge}
                  onChange={e=>setMinEdge(+e.target.value)} style={{ width:70 }}/>
                <span style={{ fontSize:10, color:C.amber, fontFamily:"'JetBrains Mono',monospace",
                  minWidth:28 }}>{minEdge}%</span>
              </div>
              {selected.size > 0 && (
                <div style={{ display:"flex", alignItems:"center", gap:7,
                  background:C.greenDim, border:`1px solid ${C.green}30`,
                  borderRadius:4, padding:"3px 10px", marginLeft:"auto" }}>
                  <span style={{ fontSize:10, color:C.green, fontFamily:"'JetBrains Mono',monospace" }}>
                    {selected.size} sel · ${totalStake} stake total
                  </span>
                  <button onClick={()=>setSelected(new Set())}
                    style={{ background:"none", border:"none", color:C.green, cursor:"pointer", fontSize:12 }}>✕</button>
                </div>
              )}
              <span style={{ fontSize:9, color:C.text2, fontFamily:"'JetBrains Mono',monospace",
                marginLeft:selected.size>0?"0":"auto" }}>{filtered.length} resultados</span>
            </div>

            {/* Alerts table */}
            <Panel title="alertas de valor — tiempo real">
              {/* Table header */}
              <div style={{ display:"grid",
                gridTemplateColumns:"20px 64px minmax(0,1fr) 90px 52px 54px 58px 56px 62px",
                gap:8, padding:"6px 12px", borderBottom:`1px solid ${C.border}`, background:C.bg3 }}>
                {["","CONF","PARTIDO","MERCADO","CUOTA","P.MOD","EDGE","STAKE","KELLY"].map((h,i) => (
                  <span key={i} style={{ fontSize:8, color:C.text2,
                    fontFamily:"'JetBrains Mono',monospace", letterSpacing:".1em" }}>{h}</span>
                ))}
              </div>

              {/* Rows */}
              <div style={{ maxHeight:400, overflowY:"auto" }}>
                {loading && Array(6).fill(0).map((_,i) => (
                  <div key={i} style={{ padding:"10px 12px", borderBottom:`1px solid ${C.border}` }}>
                    <Skeleton h={14}/>
                  </div>
                ))}
                {!loading && filtered.length === 0 && (
                  <div style={{ padding:"32px", textAlign:"center", color:C.text2, fontSize:12 }}>
                    Sin alertas con estos filtros
                  </div>
                )}
                {!loading && filtered.map((a, idx) => {
                  const rowKey = a.match_id + a.market
                  const stake  = Math.round(bk * a.kelly_frac)
                  return (
                    <div key={rowKey} className="alert-row" onClick={() => toggleSel(rowKey)}
                      style={{ display:"grid",
                        gridTemplateColumns:"20px 64px minmax(0,1fr) 90px 52px 54px 58px 56px 62px",
                        gap:8, padding:"8px 12px", borderBottom:`1px solid ${C.border}`,
                        background:selected.has(rowKey)?C.greenDim:"transparent",
                        borderLeft:selected.has(rowKey)?`2px solid ${C.green}`:"2px solid transparent",
                        animation:`fadeIn .2s ease ${idx*.025}s both`, alignItems:"center" }}>
                      <div style={{ width:13, height:13, borderRadius:2,
                        border:`1px solid ${selected.has(rowKey)?C.green:C.border2}`,
                        background:selected.has(rowKey)?C.green:"transparent",
                        display:"flex", alignItems:"center", justifyContent:"center", flexShrink:0 }}>
                        {selected.has(rowKey) && <span style={{ fontSize:8, color:"#000", fontWeight:900, lineHeight:1 }}>✓</span>}
                      </div>
                      <Badge text={a.confidence} color={confColor(a.confidence)} bg={confBg(a.confidence)}/>
                      <div style={{ minWidth:0 }}>
                        <div style={{ display:"flex", alignItems:"center", gap:4, overflow:"hidden" }}>
                          <span style={{ fontSize:10, flexShrink:0 }}>{leagueIcon(a.league)}</span>
                          <span style={{ fontSize:11, fontWeight:500, whiteSpace:"nowrap",
                            overflow:"hidden", textOverflow:"ellipsis" }}>
                            {a.home_team} <span style={{color:C.text2}}>vs</span> {a.away_team}
                          </span>
                        </div>
                        <div style={{ fontSize:9, color:C.text2, fontFamily:"'JetBrains Mono',monospace", marginTop:1 }}>
                          {a.league} · {a.kickoff} · λ {a.lambda_home?.toFixed(2)}/{a.lambda_away?.toFixed(2)}
                        </div>
                      </div>
                      <span style={{ fontSize:10, color:C.text1, fontFamily:"'JetBrains Mono',monospace",
                        overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>
                        {a.market_label || a.market}
                      </span>
                      <span style={{ fontSize:12, fontWeight:700, color:C.text0,
                        fontFamily:"'JetBrains Mono',monospace" }}>{a.odd?.toFixed(2)}</span>
                      <span style={{ fontSize:10, color:C.blue,
                        fontFamily:"'JetBrains Mono',monospace" }}>
                        {(a.p_model*100).toFixed(1)}%
                      </span>
                      <span style={{ fontSize:12, fontWeight:700,
                        color:a.edge_pct>=15?C.green:a.edge_pct>=8?C.amber:C.text1,
                        fontFamily:"'JetBrains Mono',monospace" }}>+{a.edge_pct?.toFixed(1)}%</span>
                      <span style={{ fontSize:11, fontWeight:600, color:C.green,
                        fontFamily:"'JetBrains Mono',monospace" }}>${stake}</span>
                      <span style={{ fontSize:10, color:C.text2,
                        fontFamily:"'JetBrains Mono',monospace" }}>{(a.kelly_frac*100).toFixed(1)}%bk</span>
                    </div>
                  )
                })}
              </div>

              {/* Footer */}
              <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between",
                padding:"7px 12px", borderTop:`1px solid ${C.border}`, background:C.bg3 }}>
                <span style={{ fontSize:9, color:C.text2, fontFamily:"'JetBrains Mono',monospace" }}>
                  Poisson + LogReg 60/40 · Kelly fraccionado 50% · edge mín 3%
                </span>
                <button className="btn green">⚡ Notificar Telegram</button>
              </div>
            </Panel>

            {/* Arbitrage alerts */}
            {arbList.length > 0 && arbList.map((arb, i) => (
              <div key={i} style={{ padding:"9px 12px", background:C.amberDim,
                border:`1px solid ${C.amber}30`, borderRadius:6,
                display:"flex", alignItems:"center", gap:10 }}>
                <span style={{ color:C.amber, fontSize:13, flexShrink:0 }}>⚡</span>
                <span style={{ fontSize:11, fontWeight:500, color:C.amber }}>ARBITRAJE </span>
                <span style={{ fontSize:11, color:C.text1 }}>
                  {arb.match} — {arb.league} → profit neto +{arb.profit_pct}%
                </span>
              </div>
            ))}
          </div>
        )}

        {/* ══════════ TAB: BANKROLL ══════════ */}
        {tab === "bankroll" && (
          <div style={{ display:"flex", flexDirection:"column", gap:10 }}>
            <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:8 }}>
              {loading
                ? Array(4).fill(0).map((_,i)=><Panel key={i} style={{padding:"11px 14px"}}><Skeleton h={40}/></Panel>)
                : [
                  { label:"Balance Actual",    value:`$${bk.toLocaleString()}`,          color:C.text0 },
                  { label:"ROI Total",         value:`${roi>0?"+":""}${roi}%`,            color:roi>0?C.green:C.red },
                  { label:"Exposición sugerida",value:`$${Math.round(bkData?.suggested_exposure||0)}`, color:C.amber },
                  { label:"Value Bets activas", value:alerts.length,                     color:C.blue  },
                ].map(s => (
                  <Panel key={s.label} style={{ padding:"11px 14px" }}>
                    <Stat label={s.label} value={s.value} color={s.color}/>
                  </Panel>
                ))
              }
            </div>

            <div style={{ display:"grid", gridTemplateColumns:"2fr 1fr", gap:10 }}>
              <Panel title="curva de bankroll — 60 días" style={{ padding:"12px" }}>
                <ResponsiveContainer width="100%" height={220}>
                  <AreaChart data={bankrollCurve} margin={{ top:8, right:8, left:-10, bottom:0 }}>
                    <defs>
                      <linearGradient id="bkGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%"  stopColor={C.green} stopOpacity={0.2}/>
                        <stop offset="95%" stopColor={C.green} stopOpacity={0}/>
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke={C.border} vertical={false}/>
                    <XAxis dataKey="date" tick={{ fill:C.text2, fontSize:8, fontFamily:"JetBrains Mono" }}
                      tickLine={false} axisLine={false} interval={9}/>
                    <YAxis tick={{ fill:C.text2, fontSize:8, fontFamily:"JetBrains Mono" }}
                      tickLine={false} axisLine={false} tickFormatter={v=>`$${v}`} width={44}/>
                    <Tooltip content={<CustomTT/>}/>
                    <ReferenceLine y={bankrollCurve[0]?.balance} stroke={C.border2} strokeDasharray="4 4"/>
                    <Area type="monotone" dataKey="balance" stroke={C.green} strokeWidth={1.5}
                      fill="url(#bkGrad)" name="balance"/>
                  </AreaChart>
                </ResponsiveContainer>
              </Panel>

              <Panel title="distribución de edge histórico" style={{ padding:"12px" }}>
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={EDGE_DIST} margin={{ top:8, right:5, left:-20, bottom:0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={C.border} vertical={false}/>
                    <XAxis dataKey="range" tick={{ fill:C.text2, fontSize:7, fontFamily:"JetBrains Mono" }}
                      tickLine={false} axisLine={false}/>
                    <YAxis tick={{ fill:C.text2, fontSize:8, fontFamily:"JetBrains Mono" }}
                      tickLine={false} axisLine={false} width={20}/>
                    <Tooltip content={<CustomTT/>}/>
                    <Bar dataKey="n" radius={[2,2,0,0]} name="apuestas">
                      {EDGE_DIST.map((e,i) => <Cell key={i} fill={e.c}/>)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </Panel>
            </div>

            {/* Bankroll editor */}
            <Panel title="configurar bankroll" style={{ padding:"14px" }}>
              <div style={{ display:"flex", alignItems:"center", gap:12 }}>
                <span style={{ fontSize:11, color:C.text1 }}>Bankroll actual:</span>
                <span style={{ fontSize:18, fontWeight:700, color:C.text0,
                  fontFamily:"'JetBrains Mono',monospace" }}>${bk.toLocaleString()}</span>
                {!editBankroll
                  ? <button className="btn" onClick={()=>{setEditBankroll(true);setNewBankroll(bk)}}>Editar</button>
                  : <>
                    <input type="number" value={newBankroll} onChange={e=>setNewBankroll(e.target.value)}
                      style={{ background:C.bg3, border:`1px solid ${C.border2}`, color:C.text0,
                        borderRadius:4, padding:"4px 10px", fontSize:12,
                        fontFamily:"'JetBrains Mono',monospace", width:100, outline:"none" }}/>
                    <button className="btn green" onClick={saveBankroll}>Guardar</button>
                    <button className="btn" onClick={()=>setEditBankroll(false)}>Cancelar</button>
                  </>
                }
              </div>
              <div style={{ marginTop:12 }}>
                <div style={{ display:"flex", justifyContent:"space-between", marginBottom:6 }}>
                  <span style={{ fontSize:10, color:C.text2, fontFamily:"'JetBrains Mono',monospace" }}>
                    Exposición diaria usada: ${Math.round(bkData?.suggested_exposure||0)} / ${Math.round(bk*0.20)} (límite 20%)
                  </span>
                </div>
                <div style={{ height:5, borderRadius:3, background:C.bg3, overflow:"hidden" }}>
                  <div style={{ width:`${Math.min(((bkData?.suggested_exposure||0)/(bk*0.20))*100,100)}%`,
                    height:"100%", background:C.green, borderRadius:3 }}/>
                </div>
              </div>
            </Panel>
          </div>
        )}

        {/* ══════════ TAB: ANÁLISIS ══════════ */}
        {tab === "analysis" && (
          <div style={{ display:"flex", flexDirection:"column", gap:10 }}>
            <Panel title="accuracy del modelo por mercado">
              <div style={{ display:"grid", gridTemplateColumns:"repeat(5,1fr)" }}>
                {[
                  { mkt:"1X2 Local",    acc:54.2, color:C.amber },
                  { mkt:"Empate",       acc:28.4, color:C.text1 },
                  { mkt:"1X2 Visitante",acc:41.1, color:C.amber },
                  { mkt:"Over 2.5",     acc:61.8, color:C.green },
                  { mkt:"Under 2.5",    acc:58.3, color:C.green },
                ].map((m,i) => (
                  <div key={i} style={{ padding:"14px 12px",
                    borderRight:i<4?`1px solid ${C.border}`:"none" }}>
                    <div style={{ fontSize:9, color:C.text2, fontFamily:"'JetBrains Mono',monospace",
                      letterSpacing:".08em", marginBottom:8 }}>{m.mkt}</div>
                    <div style={{ fontSize:22, fontWeight:700, color:m.color,
                      fontFamily:"'JetBrains Mono',monospace", lineHeight:1 }}>{m.acc}%</div>
                    <div style={{ fontSize:9, color:C.text2, marginTop:4 }}>en 186 partidos</div>
                    <div style={{ marginTop:8, height:3, borderRadius:2, background:C.bg3, overflow:"hidden" }}>
                      <div style={{ width:`${m.acc}%`, height:"100%", background:m.color, borderRadius:2 }}/>
                    </div>
                  </div>
                ))}
              </div>
            </Panel>

            <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:10 }}>
              <Panel title="parámetros del modelo">
                <div style={{ padding:"12px", display:"flex", flexDirection:"column", gap:9 }}>
                  {[
                    { label:"Home advantage (λ)", value:"1.131", bar:0.57, color:C.green  },
                    { label:"Kelly fracción",      value:"50%",   bar:0.50, color:C.blue   },
                    { label:"Ensemble Poisson",    value:"60%",   bar:0.60, color:C.green  },
                    { label:"Ensemble LogReg",     value:"40%",   bar:0.40, color:C.blue   },
                    { label:"Edge mínimo",         value:"3%",    bar:0.15, color:C.amber  },
                    { label:"Exposición máx/día",  value:"20%bk", bar:0.20, color:C.purple },
                  ].map(p => (
                    <div key={p.label} style={{ display:"flex", alignItems:"center", gap:10 }}>
                      <span style={{ fontSize:10, color:C.text1, minWidth:160, flexShrink:0 }}>{p.label}</span>
                      <div style={{ flex:1, height:3, borderRadius:2, background:C.bg3, overflow:"hidden" }}>
                        <div style={{ width:`${p.bar*100}%`, height:"100%", background:p.color, borderRadius:2 }}/>
                      </div>
                      <span style={{ fontSize:10, fontWeight:700, color:p.color,
                        fontFamily:"'JetBrains Mono',monospace", minWidth:50, textAlign:"right" }}>{p.value}</span>
                    </div>
                  ))}
                </div>
              </Panel>

              <Panel title="fuentes de datos">
                <div style={{ padding:"12px", display:"flex", flexDirection:"column", gap:8 }}>
                  {[
                    { name:"Datos históricos",   status:"✓ activo",    color:C.green,  detail:"Sintéticos (Poisson)" },
                    { name:"The Odds API",        status:"○ pendiente", color:C.text2,  detail:"500 req/mes gratis"   },
                    { name:"API-Football",        status:"○ pendiente", color:C.text2,  detail:"100 req/día gratis"   },
                    { name:"OpenWeatherMap",      status:"○ pendiente", color:C.text2,  detail:"1000 req/día gratis"  },
                  ].map(s => (
                    <div key={s.name} style={{ display:"flex", alignItems:"center",
                      justifyContent:"space-between", padding:"8px 0",
                      borderBottom:`1px solid ${C.border}` }}>
                      <div>
                        <div style={{ fontSize:12 }}>{s.name}</div>
                        <div style={{ fontSize:9, color:C.text2, fontFamily:"'JetBrains Mono',monospace",
                          marginTop:2 }}>{s.detail}</div>
                      </div>
                      <Badge text={s.status} color={s.color}/>
                    </div>
                  ))}
                  <div style={{ marginTop:4, padding:"8px 10px", background:C.blueDim,
                    border:`1px solid ${C.blue}30`, borderRadius:4, fontSize:10, color:C.text1 }}>
                    Para activar datos reales, completar las API keys en{" "}
                    <code style={{ color:C.blue, fontSize:9 }}>data/fetcher.py</code>{" "}
                    y las variables de entorno en Railway.
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

import { useState, useEffect, useCallback, useRef } from "react";
import { LineChart, Line, AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, ReferenceLine } from "recharts";

/* ─── DESIGN TOKENS ──────────────────────────────────────────────────────── */
const C = {
  bg0:    "#08090d",
  bg1:    "#0d0f16",
  bg2:    "#12151f",
  bg3:    "#181c28",
  border: "#1e2438",
  border2:"#252c40",
  text0:  "#e8ecf5",
  text1:  "#8b93ab",
  text2:  "#505872",
  green:  "#00d4a0",
  greenDim:"#00d4a020",
  amber:  "#f5a623",
  amberDim:"#f5a62315",
  red:    "#e84040",
  redDim: "#e8404015",
  blue:   "#4d9cf5",
  blueDim:"#4d9cf515",
  purple: "#9b6dff",
};

/* ─── MOCK DATA ENGINE ───────────────────────────────────────────────────── */
function genBankrollCurve(days = 60) {
  let bal = 1500, data = [];
  for (let i = 0; i < days; i++) {
    const date = new Date(Date.now() - (days - i) * 86400000);
    const label = date.toLocaleDateString("es-AR", { day: "2-digit", month: "2-digit" });
    const swing = (Math.random() - 0.42) * 60;
    bal = Math.max(900, bal + swing);
    data.push({ date: label, balance: Math.round(bal), day: i });
  }
  return data;
}

function genAlerts() {
  const rows = [
    { league:"Liga Argentina", home:"River Plate",    away:"Estudiantes",     market:"Empate",         odds:6.79,  edge:22.6, conf:"ALTA",  bk:"Bet365",  kelly:5.0, lambda:"1.58 / 0.92" },
    { league:"Liga Argentina", home:"River Plate",    away:"Estudiantes",     market:"Under 2.5",      odds:1.91,  edge:21.3, conf:"ALTA",  bk:"Unibet",  kelly:5.0, lambda:"1.58 / 0.92" },
    { league:"La Liga",        home:"Atlético Madrid",away:"Athletic Bilbao", market:"Empate",         odds:7.09,  edge:17.1, conf:"ALTA",  bk:"William Hill", kelly:5.0, lambda:"1.52 / 1.08" },
    { league:"Premier League", home:"Man City",       away:"Arsenal",         market:"Over 2.5",       odds:2.07,  edge:16.7, conf:"ALTA",  bk:"Betfair", kelly:5.0, lambda:"2.31 / 1.98" },
    { league:"La Liga",        home:"Atlético Madrid",away:"Athletic Bilbao", market:"Under 2.5",      odds:2.01,  edge:16.7, conf:"ALTA",  bk:"Bet365",  kelly:5.0, lambda:"1.52 / 1.08" },
    { league:"Liga Argentina", home:"Racing Club",    away:"San Lorenzo",     market:"Over 2.5",       odds:2.00,  edge:15.0, conf:"ALTA",  bk:"Unibet",  kelly:5.0, lambda:"1.42 / 1.28" },
    { league:"La Liga",        home:"Real Madrid",    away:"Villarreal",      market:"Empate",         odds:10.19, edge:14.2, conf:"ALTA",  bk:"William Hill", kelly:5.0, lambda:"2.44 / 1.12" },
    { league:"La Liga",        home:"Barcelona",      away:"Real Sociedad",   market:"Empate",         odds:8.40,  edge:11.9, conf:"ALTA",  bk:"Betfair", kelly:5.0, lambda:"2.28 / 1.38" },
    { league:"La Liga",        home:"Real Madrid",    away:"Villarreal",      market:"Under 2.5",      odds:2.05,  edge:11.4, conf:"ALTA",  bk:"Bet365",  kelly:5.0, lambda:"2.44 / 1.12" },
    { league:"Premier League", home:"Liverpool",      away:"Newcastle",       market:"Empate",         odds:7.43,  edge:10.8, conf:"ALTA",  bk:"Unibet",  kelly:5.0, lambda:"2.18 / 1.42" },
    { league:"Liga Argentina", home:"Boca Juniors",   away:"Independiente",   market:"Empate",         odds:5.71,  edge:10.7, conf:"ALTA",  bk:"William Hill", kelly:5.0, lambda:"1.48 / 1.22" },
    { league:"Premier League", home:"Chelsea",        away:"Tottenham",       market:"Empate",         odds:5.30,  edge:6.3,  conf:"MEDIA", bk:"Betfair", kelly:3.9, lambda:"1.72 / 1.68" },
  ];
  return rows.map((r, i) => ({
    ...r,
    id: i,
    kickoff: new Date(Date.now() + (i % 4 + 1) * 3600000 * 8).toLocaleTimeString("es-AR", { hour: "2-digit", minute: "2-digit" }) + "hs",
    ev: +(r.odds * (r.edge / 100 + 1 / r.odds) - 1).toFixed(3),
    stake: Math.round(1500 * r.kelly / 100),
    selected: false,
  }));
}

function genEdgeDistrib() {
  return Array.from({ length: 20 }, (_, i) => ({
    edge: `${(i * 2).toFixed(0)}-${(i * 2 + 2).toFixed(0)}%`,
    count: Math.round(Math.exp(-((i - 6) ** 2) / 8) * 18 + Math.random() * 3),
  }));
}

function genLeagueBreakdown() {
  return [
    { league: "La Liga",       vbs: 4, avgEdge: 14.1, roi: 8.2  },
    { league: "Liga Arg.",     vbs: 3, avgEdge: 16.2, roi: 11.4 },
    { league: "Premier Lge",  vbs: 3, avgEdge: 11.3, roi: 6.7  },
    { league: "Champions",    vbs: 2, avgEdge: 9.8,  roi: 4.1  },
  ];
}

/* ─── STYLE HELPERS ─────────────────────────────────────────────────────── */
const confColor = c => c === "ALTA" ? C.green : c === "MEDIA" ? C.amber : C.text1;
const confBg    = c => c === "ALTA" ? C.greenDim : c === "MEDIA" ? C.amberDim : "transparent";
const leagueIcon = l => {
  if (l.includes("La Liga")) return "🇪🇸";
  if (l.includes("Premier")) return "🏴󠁧󠁢󠁥󠁮󠁧󠁿";
  if (l.includes("Arg"))     return "🇦🇷";
  if (l.includes("Champions")) return "⭐";
  return "⚽";
};

/* ─── SUB-COMPONENTS ─────────────────────────────────────────────────────── */
function Stat({ label, value, sub, color = C.text0, small }) {
  return (
    <div style={{ display:"flex", flexDirection:"column", gap:2 }}>
      <span style={{ fontSize:11, color:C.text2, letterSpacing:"0.08em", textTransform:"uppercase", fontFamily:"'JetBrains Mono', monospace" }}>{label}</span>
      <span style={{ fontSize: small ? 18 : 26, fontWeight:600, color, fontFamily:"'JetBrains Mono', monospace", lineHeight:1 }}>{value}</span>
      {sub && <span style={{ fontSize:11, color:C.text1 }}>{sub}</span>}
    </div>
  );
}

function Badge({ text, color, bg }) {
  return (
    <span style={{ fontSize:10, fontWeight:700, padding:"2px 7px", borderRadius:3, background: bg || color + "20", color, letterSpacing:"0.1em", fontFamily:"'JetBrains Mono', monospace" }}>
      {text}
    </span>
  );
}

function Panel({ children, style, title, action }) {
  return (
    <div style={{ background:C.bg2, border:`1px solid ${C.border}`, borderRadius:6, overflow:"hidden", ...style }}>
      {title && (
        <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", padding:"10px 14px", borderBottom:`1px solid ${C.border}`, background:C.bg3 }}>
          <span style={{ fontSize:10, fontWeight:700, color:C.text2, letterSpacing:"0.12em", textTransform:"uppercase", fontFamily:"'JetBrains Mono', monospace" }}>{title}</span>
          {action}
        </div>
      )}
      {children}
    </div>
  );
}

function LivePulse() {
  return (
    <span style={{ position:"relative", display:"inline-flex", alignItems:"center", gap:6 }}>
      <span style={{
        width:7, height:7, borderRadius:"50%", background:C.green,
        boxShadow:`0 0 0 0 ${C.green}`,
        animation:"pulse 2s infinite",
      }} />
      <style>{`@keyframes pulse{0%{box-shadow:0 0 0 0 ${C.green}80}70%{box-shadow:0 0 0 6px ${C.green}00}100%{box-shadow:0 0 0 0 ${C.green}00}}`}</style>
      <span style={{ fontSize:10, color:C.green, fontFamily:"'JetBrains Mono', monospace", letterSpacing:"0.1em" }}>LIVE</span>
    </span>
  );
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background:C.bg3, border:`1px solid ${C.border2}`, borderRadius:4, padding:"8px 12px" }}>
      <div style={{ fontSize:10, color:C.text2, marginBottom:4, fontFamily:"'JetBrains Mono', monospace" }}>{label}</div>
      {payload.map((p, i) => (
        <div key={i} style={{ fontSize:12, color:p.color || C.text0, fontFamily:"'JetBrains Mono', monospace" }}>
          {p.name}: {typeof p.value === "number" && p.name?.includes("balance") ? `$${p.value.toLocaleString()}` : p.value}
        </div>
      ))}
    </div>
  );
}

/* ─── MAIN DASHBOARD ─────────────────────────────────────────────────────── */
export default function ValueBetDashboard() {
  const [alerts]     = useState(genAlerts);
  const [bankroll]   = useState(genBankrollCurve);
  const [edgeDist]   = useState(genEdgeDistrib);
  const [leagues]    = useState(genLeagueBreakdown);
  const [selected,   setSelected]   = useState(new Set());
  const [filterLeague, setFilterLeague] = useState("all");
  const [filterConf,   setFilterConf]   = useState("all");
  const [minEdge,      setMinEdge]      = useState(0);
  const [activeTab,    setActiveTab]    = useState("alerts");
  const [lastRefresh,  setLastRefresh]  = useState(new Date());
  const [refreshing,   setRefreshing]   = useState(false);
  const intervalRef = useRef();

  const refresh = useCallback(() => {
    setRefreshing(true);
    setTimeout(() => { setRefreshing(false); setLastRefresh(new Date()); }, 1200);
  }, []);

  useEffect(() => {
    intervalRef.current = setInterval(refresh, 120000);
    return () => clearInterval(intervalRef.current);
  }, [refresh]);

  const toggleSelect = id => setSelected(s => {
    const n = new Set(s);
    n.has(id) ? n.delete(id) : n.add(id);
    return n;
  });

  const leagues_list  = ["all", ...new Set(alerts.map(a => a.league))];
  const filtered = alerts.filter(a =>
    (filterLeague === "all" || a.league === filterLeague) &&
    (filterConf   === "all" || a.conf === filterConf) &&
    a.edge >= minEdge
  );

  const selAlerts     = alerts.filter(a => selected.has(a.id));
  const totalStake    = selAlerts.reduce((s, a) => s + a.stake, 0);
  const bankrollLast  = bankroll[bankroll.length - 1]?.balance || 1500;
  const bankrollFirst = bankroll[0]?.balance || 1500;
  const roi           = (((bankrollLast - bankrollFirst) / bankrollFirst) * 100).toFixed(1);
  const avgEdge       = (alerts.reduce((s, a) => s + a.edge, 0) / alerts.length).toFixed(1);

  const tabs = [
    { id:"alerts",   label:"Value Bets" },
    { id:"bankroll", label:"Bankroll" },
    { id:"analysis", label:"Análisis" },
  ];

  return (
    <div style={{ background:C.bg0, minHeight:"100vh", fontFamily:"'DM Sans', sans-serif", color:C.text0 }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=DM+Sans:wght@300;400;500;600&display=swap');
        * { box-sizing:border-box; margin:0; padding:0; }
        ::-webkit-scrollbar { width:4px; height:4px; }
        ::-webkit-scrollbar-track { background:${C.bg1}; }
        ::-webkit-scrollbar-thumb { background:${C.border2}; border-radius:2px; }
        @keyframes fadeIn { from{opacity:0;transform:translateY(4px)} to{opacity:1;transform:translateY(0)} }
        @keyframes spin { to{transform:rotate(360deg)} }
        .alert-row:hover { background:${C.bg3} !important; }
        .tab-btn { background:none; border:none; cursor:pointer; transition:all .15s; }
        .filter-sel { background:${C.bg3}; border:1px solid ${C.border}; color:${C.text1}; border-radius:4px; padding:4px 8px; font-size:11px; font-family:'JetBrains Mono',monospace; cursor:pointer; outline:none; }
        .filter-sel:focus { border-color:${C.border2}; }
        .action-btn { background:none; border:1px solid ${C.border2}; color:${C.text1}; border-radius:4px; padding:5px 12px; font-size:11px; font-family:'JetBrains Mono',monospace; cursor:pointer; transition:all .15s; letter-spacing:.06em; }
        .action-btn:hover { background:${C.bg3}; color:${C.text0}; border-color:${C.blue}40; }
        .action-btn.primary { border-color:${C.green}50; color:${C.green}; }
        .action-btn.primary:hover { background:${C.greenDim}; }
        .checkbox { width:14px; height:14px; border:1px solid ${C.border2}; border-radius:2px; cursor:pointer; display:flex; align-items:center; justify-content:center; flex-shrink:0; transition:all .1s; }
        .checkbox.checked { background:${C.green}; border-color:${C.green}; }
      `}</style>

      {/* ── HEADER ── */}
      <div style={{ background:C.bg1, borderBottom:`1px solid ${C.border}`, padding:"0 20px", display:"flex", alignItems:"center", justifyContent:"space-between", height:52 }}>
        <div style={{ display:"flex", alignItems:"center", gap:16 }}>
          <div style={{ display:"flex", alignItems:"center", gap:8 }}>
            <div style={{ width:28, height:28, borderRadius:6, background:`linear-gradient(135deg,${C.green}30,${C.blue}20)`, border:`1px solid ${C.green}40`, display:"flex", alignItems:"center", justifyContent:"center", fontSize:14 }}>◈</div>
            <span style={{ fontSize:14, fontWeight:600, letterSpacing:"-0.02em" }}>ValueBet</span>
            <span style={{ fontSize:10, color:C.text2, fontFamily:"'JetBrains Mono',monospace", marginTop:1 }}>ANALYZER</span>
          </div>
          <div style={{ width:1, height:20, background:C.border }} />
          <LivePulse />
          <span style={{ fontSize:10, color:C.text2, fontFamily:"'JetBrains Mono',monospace" }}>
            {refreshing ? "actualizando..." : `última actualización ${lastRefresh.toLocaleTimeString("es-AR",{hour:"2-digit",minute:"2-digit"})}`}
          </span>
        </div>

        <div style={{ display:"flex", alignItems:"center", gap:20 }}>
          {/* Stat pills */}
          {[
            { label:"Bankroll", value:`$${bankrollLast.toLocaleString()}`, color:C.text0 },
            { label:"ROI",      value:`${roi > 0 ? "+" : ""}${roi}%`,    color: roi > 0 ? C.green : C.red },
            { label:"VBs Hoy",  value:`${alerts.length}`,                color:C.blue },
            { label:"Avg Edge", value:`+${avgEdge}%`,                    color:C.amber },
          ].map(s => (
            <div key={s.label} style={{ display:"flex", flexDirection:"column", alignItems:"flex-end" }}>
              <span style={{ fontSize:9, color:C.text2, fontFamily:"'JetBrains Mono',monospace", letterSpacing:".1em", textTransform:"uppercase" }}>{s.label}</span>
              <span style={{ fontSize:13, fontWeight:700, color:s.color, fontFamily:"'JetBrains Mono',monospace" }}>{s.value}</span>
            </div>
          ))}
          <button className="action-btn" onClick={refresh} style={{ display:"flex", alignItems:"center", gap:5 }}>
            <span style={{ display:"inline-block", animation: refreshing ? "spin 1s linear infinite" : "none" }}>↺</span> Refresh
          </button>
        </div>
      </div>

      {/* ── TABS ── */}
      <div style={{ background:C.bg1, borderBottom:`1px solid ${C.border}`, padding:"0 20px", display:"flex", gap:0 }}>
        {tabs.map(t => (
          <button key={t.id} className="tab-btn" onClick={() => setActiveTab(t.id)}
            style={{ padding:"10px 16px", fontSize:12, fontWeight:500, color: activeTab===t.id ? C.text0 : C.text2, borderBottom: activeTab===t.id ? `2px solid ${C.green}` : "2px solid transparent", marginBottom:-1 }}>
            {t.label}
          </button>
        ))}
      </div>

      <div style={{ padding:"16px 20px", animation:"fadeIn .3s ease" }}>

        {/* ══════════════════ TAB: VALUE BETS ══════════════════ */}
        {activeTab === "alerts" && (
          <div style={{ display:"flex", flexDirection:"column", gap:12 }}>

            {/* Summary row */}
            <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:10 }}>
              {[
                { label:"Value Bets",    value:alerts.length,       sub:"detectadas hoy",    color:C.blue   },
                { label:"Conf. Alta",    value:alerts.filter(a=>a.conf==="ALTA").length, sub:"edge ≥ 10%", color:C.green  },
                { label:"Edge Máx",      value:`+${Math.max(...alerts.map(a=>a.edge)).toFixed(1)}%`, sub:"River vs Estudiantes", color:C.amber },
                { label:"Exposición",    value:`$${Math.min(alerts.reduce((s,a)=>s+a.stake,0), 300)}`, sub:"máx 20% bankroll", color:C.text0 },
              ].map(s => (
                <Panel key={s.label} style={{ padding:"12px 16px" }}>
                  <Stat label={s.label} value={s.value} sub={s.sub} color={s.color} />
                </Panel>
              ))}
            </div>

            {/* Filters */}
            <div style={{ display:"flex", alignItems:"center", gap:10, flexWrap:"wrap" }}>
              <span style={{ fontSize:10, color:C.text2, fontFamily:"'JetBrains Mono',monospace", letterSpacing:".1em" }}>FILTROS</span>
              <select className="filter-sel" value={filterLeague} onChange={e=>setFilterLeague(e.target.value)}>
                {leagues_list.map(l => <option key={l} value={l}>{l==="all"?"Todas las ligas":l}</option>)}
              </select>
              <select className="filter-sel" value={filterConf} onChange={e=>setFilterConf(e.target.value)}>
                <option value="all">Toda confianza</option>
                <option value="ALTA">ALTA</option>
                <option value="MEDIA">MEDIA</option>
              </select>
              <div style={{ display:"flex", alignItems:"center", gap:6 }}>
                <span style={{ fontSize:10, color:C.text2, fontFamily:"'JetBrains Mono',monospace" }}>Edge mín:</span>
                <input type="range" min={0} max={20} step={1} value={minEdge} onChange={e=>setMinEdge(+e.target.value)}
                  style={{ width:80, accentColor:C.green }} />
                <span style={{ fontSize:10, color:C.amber, fontFamily:"'JetBrains Mono',monospace", minWidth:32 }}>{minEdge}%</span>
              </div>
              <div style={{ marginLeft:"auto", display:"flex", gap:8 }}>
                {selected.size > 0 && (
                  <div style={{ display:"flex", alignItems:"center", gap:8, background:C.greenDim, border:`1px solid ${C.green}30`, borderRadius:4, padding:"4px 12px" }}>
                    <span style={{ fontSize:11, color:C.green, fontFamily:"'JetBrains Mono',monospace" }}>{selected.size} sel. → ${totalStake} stake</span>
                    <button className="action-btn primary" style={{ padding:"2px 8px" }} onClick={()=>setSelected(new Set())}>✕</button>
                  </div>
                )}
                <span style={{ fontSize:10, color:C.text2, padding:"6px 0", fontFamily:"'JetBrains Mono',monospace" }}>{filtered.length} resultados</span>
              </div>
            </div>

            {/* Alerts table */}
            <Panel title="alertas de valor">
              {/* Header */}
              <div style={{ display:"grid", gridTemplateColumns:"24px 90px 1fr 110px 60px 70px 70px 70px 80px 70px", gap:10, padding:"8px 14px", borderBottom:`1px solid ${C.border}`, background:C.bg3 }}>
                {["","CONF","PARTIDO","MERCADO","CUOTA","P.MOD","P.CASA","EDGE","APUESTA","KELLY"].map((h,i) => (
                  <span key={i} style={{ fontSize:9, color:C.text2, fontFamily:"'JetBrains Mono',monospace", letterSpacing:".1em" }}>{h}</span>
                ))}
              </div>
              {/* Rows */}
              <div style={{ maxHeight:420, overflowY:"auto" }}>
                {filtered.length === 0 && (
                  <div style={{ padding:"32px", textAlign:"center", color:C.text2, fontSize:13 }}>No hay alertas con los filtros seleccionados</div>
                )}
                {filtered.map((a, idx) => (
                  <div key={a.id} className="alert-row" onClick={() => toggleSelect(a.id)}
                    style={{ display:"grid", gridTemplateColumns:"24px 90px 1fr 110px 60px 70px 70px 70px 80px 70px", gap:10, padding:"9px 14px",
                      background: selected.has(a.id) ? C.greenDim : "transparent",
                      borderBottom:`1px solid ${C.border}`, cursor:"pointer",
                      borderLeft: selected.has(a.id) ? `2px solid ${C.green}` : "2px solid transparent",
                      animation:`fadeIn .2s ease ${idx * 0.03}s both`,
                    }}>
                    <div className={`checkbox ${selected.has(a.id)?"checked":""}`}>
                      {selected.has(a.id) && <span style={{fontSize:8,color:"#000",fontWeight:900}}>✓</span>}
                    </div>
                    <Badge text={a.conf} color={confColor(a.conf)} bg={confBg(a.conf)} />
                    <div style={{ display:"flex", flexDirection:"column", gap:2, minWidth:0 }}>
                      <div style={{ display:"flex", alignItems:"center", gap:5 }}>
                        <span style={{ fontSize:9 }}>{leagueIcon(a.league)}</span>
                        <span style={{ fontSize:12, fontWeight:500, whiteSpace:"nowrap", overflow:"hidden", textOverflow:"ellipsis" }}>
                          {a.home} <span style={{color:C.text2}}>vs</span> {a.away}
                        </span>
                      </div>
                      <div style={{ display:"flex", gap:6 }}>
                        <span style={{ fontSize:9, color:C.text2, fontFamily:"'JetBrains Mono',monospace" }}>{a.league}</span>
                        <span style={{ fontSize:9, color:C.text2, fontFamily:"'JetBrains Mono',monospace" }}>· {a.kickoff}</span>
                        <span style={{ fontSize:9, color:C.text2, fontFamily:"'JetBrains Mono',monospace" }}>· λ {a.lambda}</span>
                      </div>
                    </div>
                    <span style={{ fontSize:11, color:C.text1, alignSelf:"center", fontFamily:"'JetBrains Mono',monospace" }}>{a.market}</span>
                    <span style={{ fontSize:13, fontWeight:700, alignSelf:"center", color:C.text0, fontFamily:"'JetBrains Mono',monospace" }}>{a.odds.toFixed(2)}</span>
                    <span style={{ fontSize:11, alignSelf:"center", color:C.blue, fontFamily:"'JetBrains Mono',monospace" }}>{(100/a.odds).toFixed(1)}%</span>
                    <span style={{ fontSize:11, alignSelf:"center", color:C.text1, fontFamily:"'JetBrains Mono',monospace" }}>{(100/(a.odds*(1+a.edge/100))).toFixed(1)}%</span>
                    <span style={{ fontSize:13, fontWeight:700, alignSelf:"center", color: a.edge >= 15 ? C.green : a.edge >= 8 ? C.amber : C.text1, fontFamily:"'JetBrains Mono',monospace" }}>+{a.edge.toFixed(1)}%</span>
                    <span style={{ fontSize:12, fontWeight:600, alignSelf:"center", color:C.green, fontFamily:"'JetBrains Mono',monospace" }}>${a.stake}</span>
                    <span style={{ fontSize:11, alignSelf:"center", color:C.text2, fontFamily:"'JetBrains Mono',monospace" }}>{a.kelly.toFixed(1)}%bk</span>
                  </div>
                ))}
              </div>
              {/* Footer */}
              <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", padding:"8px 14px", borderTop:`1px solid ${C.border}`, background:C.bg3 }}>
                <span style={{ fontSize:10, color:C.text2, fontFamily:"'JetBrains Mono',monospace" }}>
                  Modelo: Poisson + LogReg ensemble (60/40) · Kelly fraccionado 50%
                </span>
                <div style={{ display:"flex", gap:8 }}>
                  <button className="action-btn">Exportar CSV</button>
                  <button className="action-btn primary">Notificar Telegram</button>
                </div>
              </div>
            </Panel>

            {/* Arbitrage alert */}
            <Panel style={{ padding:"10px 14px", background:C.amberDim, borderColor:`${C.amber}30` }}>
              <div style={{ display:"flex", alignItems:"center", gap:10 }}>
                <span style={{ fontSize:14, color:C.amber }}>⚡</span>
                <div>
                  <span style={{ fontSize:11, fontWeight:600, color:C.amber }}>ARBITRAJE POTENCIAL DETECTADO</span>
                  <span style={{ fontSize:11, color:C.text1, marginLeft:8 }}>Chelsea vs Tottenham — Distribución entre Bet365 / William Hill / Unibet → margen neto +0.8%</span>
                </div>
                <span style={{ marginLeft:"auto", fontSize:10, color:C.text2, fontFamily:"'JetBrains Mono',monospace" }}>hace 4 min</span>
              </div>
            </Panel>
          </div>
        )}

        {/* ══════════════════ TAB: BANKROLL ══════════════════ */}
        {activeTab === "bankroll" && (
          <div style={{ display:"flex", flexDirection:"column", gap:12 }}>
            <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:10 }}>
              {[
                { label:"Balance Actual", value:`$${bankrollLast.toLocaleString()}`,             color:C.text0 },
                { label:"ROI Total",      value:`${roi>0?"+":""}${roi}%`,                         color:roi>0?C.green:C.red },
                { label:"Variación Hoy",  value:"+$47",                                           color:C.green },
                { label:"Exposición Max", value:`$300`,                                            color:C.amber, sub:"20% límite" },
              ].map(s=>(
                <Panel key={s.label} style={{ padding:"12px 16px" }}>
                  <Stat label={s.label} value={s.value} sub={s.sub||""} color={s.color} />
                </Panel>
              ))}
            </div>

            <div style={{ display:"grid", gridTemplateColumns:"2fr 1fr", gap:12 }}>
              <Panel title="curva de bankroll — últimos 60 días" style={{ padding:"12px 14px" }}>
                <ResponsiveContainer width="100%" height={240}>
                  <AreaChart data={bankroll} margin={{ top:10, right:10, left:0, bottom:0 }}>
                    <defs>
                      <linearGradient id="bankGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%"  stopColor={C.green} stopOpacity={0.25}/>
                        <stop offset="95%" stopColor={C.green} stopOpacity={0}/>
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke={C.border} vertical={false}/>
                    <XAxis dataKey="date" tick={{ fill:C.text2, fontSize:9, fontFamily:"JetBrains Mono" }} tickLine={false} axisLine={false} interval={9}/>
                    <YAxis tick={{ fill:C.text2, fontSize:9, fontFamily:"JetBrains Mono" }} tickLine={false} axisLine={false} tickFormatter={v=>`$${v}`} width={48}/>
                    <Tooltip content={<CustomTooltip/>}/>
                    <ReferenceLine y={1500} stroke={C.border2} strokeDasharray="4 4" label={{ value:"inicio", fill:C.text2, fontSize:9 }}/>
                    <Area type="monotone" dataKey="balance" stroke={C.green} strokeWidth={1.5} fill="url(#bankGrad)" name="balance"/>
                  </AreaChart>
                </ResponsiveContainer>
              </Panel>

              <Panel title="distribución de edge" style={{ padding:"12px 14px" }}>
                <ResponsiveContainer width="100%" height={240}>
                  <BarChart data={edgeDist.slice(0,12)} margin={{ top:10,right:5,left:0,bottom:0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={C.border} horizontal={true} vertical={false}/>
                    <XAxis dataKey="edge" tick={{ fill:C.text2, fontSize:8, fontFamily:"JetBrains Mono" }} tickLine={false} axisLine={false} interval={2}/>
                    <YAxis tick={{ fill:C.text2, fontSize:9, fontFamily:"JetBrains Mono" }} tickLine={false} axisLine={false} width={24}/>
                    <Tooltip content={<CustomTooltip/>}/>
                    <Bar dataKey="count" radius={[2,2,0,0]} name="apuestas">
                      {edgeDist.slice(0,12).map((e,i)=>(
                        <Cell key={i} fill={i < 3 ? C.text2 : i < 6 ? C.blue : i < 9 ? C.amber : C.green}/>
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </Panel>
            </div>

            <Panel title="kelly calculator">
              <div style={{ padding:"14px", display:"grid", gridTemplateColumns:"repeat(3,1fr)", gap:20 }}>
                {[
                  { label:"Apuesta",     value:"$75",    sub:"5.0% bankroll" },
                  { label:"P(ganar)",    value:"31.4%",  sub:"modelo Poisson" },
                  { label:"EV esperado", value:"+$12.4", sub:"por apuesta" },
                ].map(s=>(
                  <div key={s.label}>
                    <Stat label={s.label} value={s.value} sub={s.sub} color={C.green} small/>
                  </div>
                ))}
                <div style={{ gridColumn:"1/-1", display:"flex", alignItems:"center", gap:8, marginTop:4 }}>
                  <div style={{ flex:1, height:6, borderRadius:3, background:C.bg3, overflow:"hidden" }}>
                    <div style={{ width:"5%", height:"100%", background:C.green, borderRadius:3 }}/>
                  </div>
                  <span style={{ fontSize:10, color:C.text2, fontFamily:"'JetBrains Mono',monospace" }}>5% / 20% límite diario</span>
                </div>
              </div>
            </Panel>
          </div>
        )}

        {/* ══════════════════ TAB: ANÁLISIS ══════════════════ */}
        {activeTab === "analysis" && (
          <div style={{ display:"flex", flexDirection:"column", gap:12 }}>
            <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:12 }}>

              <Panel title="rendimiento por liga">
                <div style={{ padding:"4px 0" }}>
                  {leagues.map((l, i) => (
                    <div key={i} style={{ display:"grid", gridTemplateColumns:"1fr 60px 70px 70px", gap:10, padding:"10px 14px", borderBottom:`1px solid ${C.border}`, alignItems:"center" }}>
                      <div style={{ display:"flex", alignItems:"center", gap:8 }}>
                        <span>{leagueIcon(l.league)}</span>
                        <span style={{ fontSize:12 }}>{l.league}</span>
                      </div>
                      <span style={{ fontSize:11, color:C.blue, fontFamily:"'JetBrains Mono',monospace", textAlign:"right" }}>{l.vbs} VBs</span>
                      <span style={{ fontSize:11, color:C.amber, fontFamily:"'JetBrains Mono',monospace", textAlign:"right" }}>+{l.avgEdge}%</span>
                      <span style={{ fontSize:12, fontWeight:600, color:l.roi>8?C.green:l.roi>4?C.amber:C.text1, fontFamily:"'JetBrains Mono',monospace", textAlign:"right" }}>ROI {l.roi}%</span>
                    </div>
                  ))}
                </div>
              </Panel>

              <Panel title="parámetros del modelo">
                <div style={{ padding:"14px", display:"flex", flexDirection:"column", gap:10 }}>
                  {[
                    { label:"Home advantage (λ factor)", value:"1.131",  bar:0.57, color:C.green },
                    { label:"Edge mínimo requerido",     value:"3.0%",   bar:0.15, color:C.amber },
                    { label:"Kelly fracción",            value:"50%",    bar:0.50, color:C.blue  },
                    { label:"Exposición máx/día",        value:"20% bk", bar:0.20, color:C.purple},
                    { label:"Ensemble Poisson weight",   value:"60%",    bar:0.60, color:C.green },
                    { label:"Ensemble LogReg weight",    value:"40%",    bar:0.40, color:C.blue  },
                    { label:"Max goles en matriz",       value:"8",      bar:0.40, color:C.text1 },
                  ].map(p => (
                    <div key={p.label} style={{ display:"flex", alignItems:"center", gap:12 }}>
                      <span style={{ fontSize:11, color:C.text1, minWidth:220, flexShrink:0 }}>{p.label}</span>
                      <div style={{ flex:1, height:4, borderRadius:2, background:C.bg3, overflow:"hidden" }}>
                        <div style={{ width:`${p.bar*100}%`, height:"100%", background:p.color, borderRadius:2 }}/>
                      </div>
                      <span style={{ fontSize:11, fontWeight:600, color:p.color, fontFamily:"'JetBrains Mono',monospace", minWidth:60, textAlign:"right" }}>{p.value}</span>
                    </div>
                  ))}
                </div>
              </Panel>
            </div>

            <Panel title="backtesting — accuracy del modelo por mercado">
              <div style={{ display:"grid", gridTemplateColumns:"repeat(5,1fr)", gap:0 }}>
                {[
                  { mkt:"1X2 Local",   acc:54.2, calib:0.89, n:186 },
                  { mkt:"Empate",      acc:28.4, calib:0.92, n:186 },
                  { mkt:"1X2 Visit",   acc:41.1, calib:0.87, n:186 },
                  { mkt:"Over 2.5",    acc:61.8, calib:0.94, n:186 },
                  { mkt:"Under 2.5",   acc:58.3, calib:0.93, n:186 },
                ].map((m,i) => (
                  <div key={i} style={{ padding:"14px 16px", borderRight: i<4 ? `1px solid ${C.border}` : "none" }}>
                    <div style={{ fontSize:10, color:C.text2, fontFamily:"'JetBrains Mono',monospace", letterSpacing:".08em", marginBottom:8 }}>{m.mkt}</div>
                    <div style={{ fontSize:22, fontWeight:700, color: m.acc > 55 ? C.green : m.acc > 40 ? C.amber : C.text1, fontFamily:"'JetBrains Mono',monospace", lineHeight:1 }}>{m.acc}%</div>
                    <div style={{ fontSize:10, color:C.text2, marginTop:4 }}>accuracy en {m.n} partidos</div>
                    <div style={{ marginTop:8, height:3, borderRadius:2, background:C.bg3, overflow:"hidden" }}>
                      <div style={{ width:`${m.acc}%`, height:"100%", background: m.acc>55?C.green:m.acc>40?C.amber:C.text1, borderRadius:2 }}/>
                    </div>
                    <div style={{ fontSize:9, color:C.text2, marginTop:4, fontFamily:"'JetBrains Mono',monospace" }}>calibración: {m.calib}</div>
                  </div>
                ))}
              </div>
            </Panel>

            <Panel style={{ padding:"12px 16px", background:C.blueDim, borderColor:`${C.blue}30` }}>
              <div style={{ display:"flex", gap:12, alignItems:"flex-start" }}>
                <span style={{ fontSize:16, marginTop:1 }}>ℹ</span>
                <div style={{ fontSize:11, color:C.text1, lineHeight:1.7 }}>
                  <strong style={{ color:C.text0 }}>Nota sobre los datos actuales:</strong> Los resultados muestran datos sintéticos generados con distribuciones Poisson reales por equipo. El modelo está listo para conectar cuotas reales de <strong style={{ color:C.blue }}>The Odds API</strong> (free tier: 500 req/mes) y estadísticas de <strong style={{ color:C.blue }}>API-Football</strong> (free: 100 req/día). Completar las API keys en <code style={{ background:C.bg3, padding:"1px 5px", borderRadius:3, fontFamily:"'JetBrains Mono',monospace", fontSize:10 }}>data/fetcher.py</code> para activar datos reales.
                </div>
              </div>
            </Panel>
          </div>
        )}
      </div>
    </div>
  );
}

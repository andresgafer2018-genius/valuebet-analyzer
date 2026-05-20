// BetsTracker.jsx
import { useState, useEffect, useCallback } from "react";

const API = import.meta.env.VITE_API_URL || "http://localhost:5050";

const C = {
  bg0: "#08090d", bg1: "#0d0f16", bg2: "#12151f", bg3: "#181c28",
  border: "#1e2438", border2: "#252c40",
  text0: "#e8ecf5", text1: "#8b93ab", text2: "#505872",
  green: "#00d4a0", greenDim: "#00d4a018",
  amber: "#f5a623", amberDim: "#f5a62312",
  red: "#e84040", redDim: "#e8404018",
  blue: "#4d9cf5", blueDim: "#4d9cf512",
};

const fmt = (n, dec = 2) => n == null ? "-" : Number(n).toFixed(dec);

const fmtDate = (iso) => {
  if (!iso) return "-";
  return new Date(iso).toLocaleDateString("es-AR", { day: "2-digit", month: "short", year: "2-digit" });
};

const Badge = ({ result }) => {
  const cfg = {
    pending: { label: "Pendiente", color: C.amber,  bg: C.amberDim },
    win:     { label: "Ganada",    color: C.green,  bg: C.greenDim },
    loss:    { label: "Perdida",   color: C.red,    bg: C.redDim   },
    void:    { label: "Anulada",   color: C.text2,  bg: "#ffffff08" },
  }[result] || { label: "Pendiente", color: C.amber, bg: C.amberDim };
  return (
    <span style={{ display:"inline-flex", alignItems:"center", padding:"2px 8px", borderRadius:4,
      fontSize:11, fontWeight:600, color:cfg.color, background:cfg.bg, border:`1px solid ${cfg.color}22` }}>
      {cfg.label}
    </span>
  );
};

const StatCard = ({ label, value, sub, color = C.text0 }) => (
  <div style={{ background:C.bg2, border:`1px solid ${C.border}`, borderRadius:8, padding:"14px 18px", flex:1, minWidth:100 }}>
    <div style={{ fontSize:10, color:C.text2, letterSpacing:"0.08em", marginBottom:4 }}>{label}</div>
    <div style={{ fontSize:22, fontWeight:700, color, fontFamily:"'JetBrains Mono',monospace" }}>{value}</div>
    {sub && <div style={{ fontSize:10, color:C.text2, marginTop:2 }}>{sub}</div>}
  </div>
);

export default function BetsTracker() {
  const [bets, setBets] = useState([]);
  const [stats, setStats] = useState({});
  const [bankroll, setBankroll] = useState(1000);
  const [newBankroll, setNewBankroll] = useState("");
  const [editingBankroll, setEditingBankroll] = useState(false);
  const [filter, setFilter] = useState("all");
  const [loading, setLoading] = useState(false);
  const [editingResult, setEditingResult] = useState(null);
  const [msg, setMsg] = useState(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [betsRes, statsRes, brRes] = await Promise.all([
        fetch(`${API}/api/bets?limit=200`),
        fetch(`${API}/api/stats`),
        fetch(`${API}/api/bankroll`),
      ]);
      const betsData  = await betsRes.json();
      const statsData = await statsRes.json();
      const brData    = await brRes.json();
      setBets(Array.isArray(betsData) ? betsData : (betsData.bets || []));
      setStats(statsData);
      setBankroll(brData.amount ?? brData.bankroll ?? 1000);
      setNewBankroll(brData.amount ?? brData.bankroll ?? 1000);
    } catch (e) {
      showMsg("Error cargando datos", "error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const showMsg = (text, type = "ok") => {
    setMsg({ text, type });
    setTimeout(() => setMsg(null), 3000);
  };

  const handleUpdateResult = async (bet_id, result) => {
    try {
      const profit = result === "win" ? 10 : result === "loss" ? -10 : 0;
      const res = await fetch(`${API}/api/bets/${bet_id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ result, profit }),
      });
      if (res.ok) { showMsg("Resultado actualizado"); setEditingResult(null); loadData(); }
    } catch (e) { showMsg("Error", "error"); }
  };

  const handleDelete = async (bet_id) => {
    if (!confirm("Eliminar esta apuesta?")) return;
    await fetch(`${API}/api/bets/${bet_id}`, { method: "DELETE" });
    showMsg("Eliminada"); loadData();
  };

  const handleUpdateBankroll = async () => {
    const amount = parseFloat(newBankroll);
    if (isNaN(amount) || amount <= 0) return showMsg("Monto invalido", "error");
    try {
      await fetch(`${API}/api/bankroll`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ amount }),
      });
      setBankroll(amount); setEditingBankroll(false); showMsg("Bankroll actualizado");
    } catch (e) { showMsg("Error", "error"); }
  };

  const filteredBets = filter === "all" ? bets : bets.filter(b => b.result === filter);
  const profitColor = (stats?.total_profit ?? 0) >= 0 ? C.green : C.red;

  return (
    <div style={{ padding:"20px 24px", minHeight:"100vh", background:C.bg0, color:C.text0 }}>

      {msg && (
        <div style={{ position:"fixed", top:20, right:20, zIndex:9999,
          background: msg.type==="error" ? C.redDim : C.greenDim,
          border:`1px solid ${msg.type==="error" ? C.red : C.green}`,
          color: msg.type==="error" ? C.red : C.green,
          padding:"10px 16px", borderRadius:8, fontSize:13 }}>
          {msg.text}
          <button onClick={() => setMsg(null)} style={{ marginLeft:10, background:"none", border:"none", color:"inherit", cursor:"pointer" }}>x</button>
        </div>
      )}

      <div style={{ display:"flex", justifyContent:"space-between", alignItems:"flex-start", marginBottom:20 }}>
        <div>
          <h2 style={{ margin:0, fontSize:22, fontWeight:700, color:C.green }}>Historial de Apuestas</h2>
          <p style={{ margin:"4px 0 0", fontSize:13, color:C.text1 }}>Registra y segui el resultado de tus apuestas en tiempo real</p>
        </div>
        <div style={{ background:C.bg2, border:`1px solid ${C.border}`, borderRadius:10, padding:"10px 16px", minWidth:140 }}>
          <div style={{ fontSize:10, color:C.text2, letterSpacing:"0.08em", marginBottom:4 }}>BANKROLL</div>
          {editingBankroll ? (
            <div style={{ display:"flex", gap:6, alignItems:"center" }}>
              <input type="number" value={newBankroll} onChange={e => setNewBankroll(e.target.value)}
                style={{ width:80, background:C.bg3, border:`1px solid ${C.border2}`, borderRadius:4, padding:"2px 6px", color:C.text0, fontSize:14 }} />
              <button onClick={handleUpdateBankroll} style={{ background:C.green, border:"none", borderRadius:4, padding:"2px 8px", color:"#000", cursor:"pointer", fontSize:12 }}>OK</button>
              <button onClick={() => setEditingBankroll(false)} style={{ background:"none", border:"none", color:C.text2, cursor:"pointer" }}>x</button>
            </div>
          ) : (
            <div style={{ display:"flex", alignItems:"center", gap:8 }}>
              <span style={{ fontSize:18, fontWeight:700, fontFamily:"'JetBrains Mono',monospace" }}>
                ${bankroll != null ? Number(bankroll).toLocaleString("es-AR") : "-"}
              </span>
              <button onClick={() => setEditingBankroll(true)}
                style={{ background:"none", border:"none", color:C.text2, cursor:"pointer", fontSize:12 }}>[e]</button>
            </div>
          )}
        </div>
      </div>

      <div style={{ display:"flex", gap:12, flexWrap:"wrap", marginBottom:20 }}>
        <StatCard label="TOTAL APUESTAS" value={stats.total ?? 0} />
        <StatCard label="GANADAS" value={stats.won ?? stats.wins ?? 0}
          sub={`Win rate: ${stats.win_rate != null ? fmt(stats.win_rate,1) : "-"}%`} color={C.green} />
        <StatCard label="PERDIDAS" value={stats.lost ?? stats.losses ?? 0} color={C.red} />
        <StatCard label="PENDIENTES" value={stats.pending ?? 0} color={C.amber} />
        <StatCard label="PROFIT TOTAL"
          value={`${(stats.total_profit??0)>=0?"+":""}$${fmt(stats.total_profit??0)}`}
          sub={`Stakeado: $${fmt(stats.total_staked??0)}`} color={profitColor} />
        <StatCard label="ROI REAL"
          value={`${stats.roi!=null?fmt(stats.roi,1):"-"}%`}
          sub={`Edge medio: ${fmt(stats.avg_edge??0,1)}%`}
          color={(stats.roi??0)>=0?C.green:C.red} />
      </div>

      <div style={{ display:"flex", gap:8, marginBottom:16, alignItems:"center" }}>
        {[
          { key:"all",     label:"Todas" },
          { key:"pending", label:`Pendientes (${stats.pending??0})` },
          { key:"win",     label:`Ganadas (${stats.won??stats.wins??0})` },
          { key:"loss",    label:`Perdidas (${stats.lost??stats.losses??0})` },
        ].map(f => (
          <button key={f.key} onClick={() => setFilter(f.key)} style={{
            padding:"5px 14px", borderRadius:20, fontSize:12, cursor:"pointer",
            background: filter===f.key ? C.green : "transparent",
            color: filter===f.key ? "#000" : C.text1,
            border:`1px solid ${filter===f.key ? C.green : C.border}`,
            fontWeight: filter===f.key ? 700 : 400,
          }}>{f.label}</button>
        ))}
        <button onClick={loadData} style={{ marginLeft:"auto", padding:"5px 12px", borderRadius:6,
          background:"transparent", border:`1px solid ${C.border}`, color:C.text1, fontSize:12, cursor:"pointer" }}>
          Actualizar
        </button>
      </div>

      {loading ? (
        <div style={{ textAlign:"center", color:C.text2, padding:40 }}>Cargando...</div>
      ) : filteredBets.length === 0 ? (
        <div style={{ textAlign:"center", padding:50, border:`1px dashed ${C.border}`, borderRadius:10 }}>
          <div style={{ fontSize:14, marginBottom:8 }}>No hay apuestas registradas</div>
          <div style={{ fontSize:12, color:C.text2 }}>
            Las apuestas se guardan automaticamente cuando usas el boton guardar en el panel principal
          </div>
        </div>
      ) : (
        <div style={{ overflowX:"auto" }}>
          <table style={{ width:"100%", borderCollapse:"collapse", fontSize:13 }}>
            <thead>
              <tr style={{ borderBottom:`1px solid ${C.border}` }}>
                {["PARTIDO","LIGA","TIPO","CUOTA","EDGE","MONTO","PROFIT","FECHA","ESTADO",""].map(h => (
                  <th key={h} style={{ padding:"8px 12px", textAlign:"left", fontSize:10, color:C.text2, letterSpacing:"0.08em", fontWeight:600 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filteredBets.map(bet => (
                <tr key={bet.id} style={{ borderBottom:`1px solid ${C.border}22` }}>
                  <td style={{ padding:"10px 12px" }}>
                    <div style={{ fontWeight:600 }}>{bet.home_team}</div>
                    <div style={{ fontSize:11, color:C.text2 }}>vs {bet.away_team}</div>
                  </td>
                  <td style={{ padding:"10px 12px", color:C.text1, fontSize:12 }}>{bet.league}</td>
                  <td style={{ padding:"10px 12px" }}>
                    <span style={{ background:C.blueDim, color:C.blue, padding:"2px 8px", borderRadius:4, fontSize:11, fontWeight:600 }}>
                      {(bet.bet_type||"").toUpperCase()}
                    </span>
                  </td>
                  <td style={{ padding:"10px 12px", fontFamily:"'JetBrains Mono',monospace" }}>{fmt(bet.odds)}</td>
                  <td style={{ padding:"10px 12px", color:C.green, fontWeight:600 }}>+{fmt((bet.edge??0)*100,1)}%</td>
                  <td style={{ padding:"10px 12px", fontFamily:"'JetBrains Mono',monospace" }}>${fmt(bet.amount_bet)}</td>
                  <td style={{ padding:"10px 12px", fontFamily:"'JetBrains Mono',monospace", color:profitColor }}>
                    {bet.result==="pending" ? "-" : `${(bet.profit??0)>=0?"+":""}$${fmt(bet.profit)}`}
                  </td>
                  <td style={{ padding:"10px 12px", color:C.text2, fontSize:12 }}>{fmtDate(bet.created_at)}</td>
                  <td style={{ padding:"10px 12px" }}>
                    {editingResult === bet.id ? (
                      <div style={{ display:"flex", gap:4, flexWrap:"wrap" }}>
                        {["win","loss","void"].map(r => (
                          <button key={r} onClick={() => handleUpdateResult(bet.id, r)} style={{
                            padding:"2px 8px", borderRadius:4, fontSize:11, cursor:"pointer",
                            background: r==="win"?C.greenDim : r==="loss"?C.redDim : "#ffffff08",
                            color: r==="win"?C.green : r==="loss"?C.red : C.text2,
                            border:`1px solid ${r==="win"?C.green : r==="loss"?C.red : C.border}`,
                          }}>{r==="win"?"Gano":r==="loss"?"Perdio":"Anular"}</button>
                        ))}
                        <button onClick={() => setEditingResult(null)} style={{ padding:"2px 6px", borderRadius:4, fontSize:11, cursor:"pointer", background:"none", border:`1px solid ${C.border}`, color:C.text2 }}>x</button>
                      </div>
                    ) : <Badge result={bet.result} />}
                  </td>
                  <td style={{ padding:"10px 12px" }}>
                    <div style={{ display:"flex", gap:6 }}>
                      {bet.result === "pending" && (
                        <button onClick={() => setEditingResult(bet.id)} style={{ padding:"3px 8px", borderRadius:4, fontSize:11, cursor:"pointer", background:C.amberDim, color:C.amber, border:`1px solid ${C.amber}44` }}>resultado</button>
                      )}
                      <button onClick={() => handleDelete(bet.id)} style={{ padding:"3px 8px", borderRadius:4, fontSize:11, cursor:"pointer", background:C.redDim, color:C.red, border:`1px solid ${C.red}44` }}>eliminar</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
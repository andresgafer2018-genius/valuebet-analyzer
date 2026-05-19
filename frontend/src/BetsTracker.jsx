// BetsTracker.jsx
// Pegar en: C:\valuebet-source\frontend\src\BetsTracker.jsx

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
  purple: "#9b6dff",
};

const fmt = (n, dec = 2) =>
  n == null ? "—" : Number(n).toFixed(dec);

const fmtDate = (iso) => {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleDateString("es-AR", { day: "2-digit", month: "short", year: "2-digit" });
};

const RESULT_CONFIG = {
  pending: { label: "Pendiente", color: C.amber,   bg: C.amberDim, icon: "⏳" },
  win:     { label: "Ganada",    color: C.green,   bg: C.greenDim, icon: "✓"  },
  loss:    { label: "Perdida",   color: C.red,     bg: C.redDim,   icon: "✗"  },
  void:    { label: "Anulada",   color: C.text2,   bg: "#ffffff08", icon: "○"  },
};

const Badge = ({ result }) => {
  const cfg = RESULT_CONFIG[result] || RESULT_CONFIG.pending;
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 4,
      padding: "2px 8px", borderRadius: 4,
      fontSize: 11, fontWeight: 600, letterSpacing: "0.05em",
      color: cfg.color, background: cfg.bg,
      border: `1px solid ${cfg.color}22`,
    }}>
      {cfg.icon} {cfg.label}
    </span>
  );
};

const StatCard = ({ label, value, sub, color = C.text0 }) => (
  <div style={{
    background: C.bg2, border: `1px solid ${C.border}`,
    borderRadius: 10, padding: "14px 18px", flex: 1, minWidth: 120,
  }}>
    <div style={{ fontSize: 11, color: C.text2, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 6 }}>
      {label}
    </div>
    <div style={{ fontSize: 22, fontWeight: 700, color, lineHeight: 1 }}>{value}</div>
    {sub && <div style={{ fontSize: 11, color: C.text2, marginTop: 4 }}>{sub}</div>}
  </div>
);

export default function BetsTracker() {
  const [bets, setBets] = useState([]);
  const [stats, setStats] = useState(null);
  const [bankroll, setBankroll] = useState(null);
  const [filter, setFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [editingResult, setEditingResult] = useState(null); // bet_id siendo editado
  const [newBankroll, setNewBankroll] = useState("");
  const [editingBankroll, setEditingBankroll] = useState(false);
  const [msg, setMsg] = useState(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [betsRes, statsRes, brRes] = await Promise.all([
        fetch(`${API}/api/bets?limit=200`),
        fetch(`${API}/api/bets/stats`),
        fetch(`${API}/api/bankroll`),
      ]);
      const betsData  = await betsRes.json();
      const statsData = await statsRes.json();
      const brData    = await brRes.json();
      setBets(Array.isArray(betsData) ? betsData : []);
      setStats(statsData);
      setBankroll(brData.amount ?? 1000);
      setNewBankroll(brData.amount ?? 1000);
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
      const res = await fetch(`${API}/api/bets/${bet_id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ result }),
      });
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      showMsg(`Apuesta marcada como ${RESULT_CONFIG[result]?.label}`);
      setEditingResult(null);
      loadData();
    } catch (e) {
      showMsg("Error actualizando resultado", "error");
    }
  };

  const handleDelete = async (bet_id) => {
    if (!confirm("¿Eliminar esta apuesta?")) return;
    try {
      await fetch(`${API}/api/bets/${bet_id}`, { method: "DELETE" });
      showMsg("Apuesta eliminada");
      loadData();
    } catch (e) {
      showMsg("Error eliminando apuesta", "error");
    }
  };

  const handleUpdateBankroll = async () => {
    const amount = parseFloat(newBankroll);
    if (isNaN(amount) || amount <= 0) return showMsg("Monto inválido", "error");
    try {
      await fetch(`${API}/api/bankroll`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ amount }),
      });
      setBankroll(amount);
      setEditingBankroll(false);
      showMsg("Bankroll actualizado");
    } catch (e) {
      showMsg("Error actualizando bankroll", "error");
    }
  };

  const filteredBets = filter === "all"
    ? bets
    : bets.filter(b => b.result === filter);

  const roiColor = stats?.roi > 0 ? C.green : stats?.roi < 0 ? C.red : C.text1;
  const profitColor = stats?.total_profit > 0 ? C.green : stats?.total_profit < 0 ? C.red : C.text1;

  return (
    <div style={{ padding: "24px 0", fontFamily: "'Inter', sans-serif" }}>
      {/* Mensaje toast */}
      {msg && (
        <div style={{
          position: "fixed", top: 20, right: 20, zIndex: 9999,
          padding: "10px 18px", borderRadius: 8,
          background: msg.type === "error" ? C.redDim : C.greenDim,
          border: `1px solid ${msg.type === "error" ? C.red : C.green}44`,
          color: msg.type === "error" ? C.red : C.green,
          fontSize: 13, fontWeight: 500,
          animation: "fadeIn 0.2s ease",
        }}>
          {msg.text}
        </div>
      )}

      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: C.green, display: "flex", alignItems: "center", gap: 8 }}>
            📋 Historial de Apuestas
          </h2>
          <p style={{ margin: "4px 0 0", fontSize: 13, color: C.text2 }}>
            Registrá y seguí el resultado de tus apuestas en tiempo real
          </p>
        </div>

        {/* Bankroll */}
        <div style={{
          background: C.bg2, border: `1px solid ${C.border}`,
          borderRadius: 10, padding: "10px 16px",
          display: "flex", alignItems: "center", gap: 10,
        }}>
          <div>
            <div style={{ fontSize: 10, color: C.text2, textTransform: "uppercase", letterSpacing: "0.08em" }}>Bankroll</div>
            {editingBankroll ? (
              <div style={{ display: "flex", gap: 6, marginTop: 4 }}>
                <input
                  type="number"
                  value={newBankroll}
                  onChange={e => setNewBankroll(e.target.value)}
                  style={{
                    width: 90, padding: "3px 8px", borderRadius: 5,
                    background: C.bg3, border: `1px solid ${C.border2}`,
                    color: C.text0, fontSize: 13,
                  }}
                />
                <button onClick={handleUpdateBankroll} style={{
                  padding: "3px 10px", borderRadius: 5, border: "none",
                  background: C.green, color: "#000", fontSize: 12, fontWeight: 600, cursor: "pointer",
                }}>OK</button>
                <button onClick={() => setEditingBankroll(false)} style={{
                  padding: "3px 8px", borderRadius: 5, border: `1px solid ${C.border2}`,
                  background: "transparent", color: C.text1, fontSize: 12, cursor: "pointer",
                }}>✕</button>
              </div>
            ) : (
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ fontSize: 18, fontWeight: 700, color: C.text0 }}>
                  ${bankroll != null ? bankroll.toLocaleString("es-AR") : "—"}
                </span>
                <button onClick={() => setEditingBankroll(true)} style={{
                  background: "transparent", border: "none", color: C.text2,
                  cursor: "pointer", fontSize: 13, padding: 0,
                }} title="Editar bankroll">✏️</button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Stats cards */}
      {stats && (
        <div style={{ display: "flex", gap: 10, marginBottom: 20, flexWrap: "wrap" }}>
          <StatCard label="Total apuestas" value={stats.total_bets ?? 0} />
          <StatCard label="Ganadas" value={stats.wins ?? 0}
            sub={`Win rate: ${fmt(stats.win_rate, 1)}%`} color={C.green} />
          <StatCard label="Perdidas" value={stats.losses ?? 0} color={C.red} />
          <StatCard label="Pendientes" value={stats.pending ?? 0} color={C.amber} />
          <StatCard label="Profit total"
            value={`${stats.total_profit >= 0 ? "+" : ""}$${fmt(stats.total_profit)}`}
            sub={`Stakeado: $${fmt(stats.total_staked)}`}
            color={profitColor} />
          <StatCard label="ROI real"
            value={`${stats.roi >= 0 ? "+" : ""}${fmt(stats.roi)}%`}
            sub={`Edge medio: ${fmt(stats.avg_edge * 100, 1)}%`}
            color={roiColor} />
        </div>
      )}

      {/* Filtros */}
      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        {[
          { key: "all",     label: "Todas" },
          { key: "pending", label: "Pendientes" },
          { key: "win",     label: "Ganadas" },
          { key: "loss",    label: "Perdidas" },
        ].map(f => (
          <button key={f.key} onClick={() => setFilter(f.key)} style={{
            padding: "5px 14px", borderRadius: 6, fontSize: 12, fontWeight: 600,
            cursor: "pointer", transition: "all 0.15s",
            background: filter === f.key ? C.green : "transparent",
            color: filter === f.key ? "#000" : C.text1,
            border: `1px solid ${filter === f.key ? C.green : C.border}`,
          }}>
            {f.label}
            {f.key !== "all" && stats && (
              <span style={{ marginLeft: 5, opacity: 0.7 }}>
                ({stats[f.key === "win" ? "wins" : f.key === "loss" ? "losses" : "pending"] ?? 0})
              </span>
            )}
          </button>
        ))}
        <button onClick={loadData} style={{
          marginLeft: "auto", padding: "5px 12px", borderRadius: 6,
          background: "transparent", border: `1px solid ${C.border}`,
          color: C.text1, fontSize: 12, cursor: "pointer",
        }}>
          ↻ Actualizar
        </button>
      </div>

      {/* Tabla */}
      {loading ? (
        <div style={{ textAlign: "center", color: C.text2, padding: 40 }}>Cargando...</div>
      ) : filteredBets.length === 0 ? (
        <div style={{
          textAlign: "center", color: C.text2, padding: 50,
          border: `1px dashed ${C.border}`, borderRadius: 10,
        }}>
          <div style={{ fontSize: 32, marginBottom: 10 }}>📭</div>
          <div style={{ fontSize: 14 }}>No hay apuestas registradas</div>
          <div style={{ fontSize: 12, marginTop: 4 }}>
            Las apuestas se guardan automáticamente cuando usás el botón "Registrar apuesta" en el panel principal
          </div>
        </div>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: `1px solid ${C.border}` }}>
                {["Partido", "Liga", "Tipo", "Cuota", "Edge", "Monto", "Profit", "Fecha", "Estado", ""].map(h => (
                  <th key={h} style={{
                    padding: "8px 10px", textAlign: "left",
                    color: C.text2, fontWeight: 600,
                    fontSize: 11, textTransform: "uppercase", letterSpacing: "0.06em",
                    whiteSpace: "nowrap",
                  }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filteredBets.map(bet => (
                <tr key={bet.id} style={{
                  borderBottom: `1px solid ${C.border}22`,
                  transition: "background 0.1s",
                }}
                  onMouseEnter={e => e.currentTarget.style.background = C.bg2}
                  onMouseLeave={e => e.currentTarget.style.background = "transparent"}
                >
                  <td style={{ padding: "10px 10px", color: C.text0, fontWeight: 500 }}>
                    <div style={{ fontSize: 13 }}>{bet.home_team}</div>
                    <div style={{ fontSize: 11, color: C.text2 }}>vs {bet.away_team}</div>
                  </td>
                  <td style={{ padding: "10px 10px", color: C.text1, fontSize: 12 }}>{bet.league}</td>
                  <td style={{ padding: "10px 10px" }}>
                    <span style={{
                      padding: "2px 7px", borderRadius: 4,
                      background: C.blueDim, color: C.blue,
                      fontSize: 11, fontWeight: 600,
                    }}>{bet.bet_type}</span>
                  </td>
                  <td style={{ padding: "10px 10px", color: C.text0, fontWeight: 600 }}>{fmt(bet.odds)}</td>
                  <td style={{ padding: "10px 10px", color: C.green, fontWeight: 600 }}>
                    +{fmt(bet.edge * 100, 1)}%
                  </td>
                  <td style={{ padding: "10px 10px", color: C.text0 }}>${fmt(bet.amount_bet)}</td>
                  <td style={{ padding: "10px 10px", fontWeight: 600,
                    color: bet.profit > 0 ? C.green : bet.profit < 0 ? C.red : C.text2
                  }}>
                    {bet.result === "pending" ? "—" : `${bet.profit >= 0 ? "+" : ""}$${fmt(bet.profit)}`}
                  </td>
                  <td style={{ padding: "10px 10px", color: C.text2, fontSize: 12 }}>{fmtDate(bet.created_at)}</td>
                  <td style={{ padding: "10px 10px" }}>
                    {editingResult === bet.id ? (
                      <div style={{ display: "flex", gap: 4 }}>
                        {["win", "loss", "void"].map(r => (
                          <button key={r} onClick={() => handleUpdateResult(bet.id, r)} style={{
                            padding: "3px 8px", borderRadius: 4, border: "none",
                            background: r === "win" ? C.green : r === "loss" ? C.red : C.border2,
                            color: r === "void" ? C.text1 : "#000",
                            fontSize: 11, fontWeight: 600, cursor: "pointer",
                          }}>
                            {RESULT_CONFIG[r].icon}
                          </button>
                        ))}
                        <button onClick={() => setEditingResult(null)} style={{
                          padding: "3px 6px", borderRadius: 4,
                          background: "transparent", border: `1px solid ${C.border}`,
                          color: C.text2, fontSize: 11, cursor: "pointer",
                        }}>✕</button>
                      </div>
                    ) : (
                      <Badge result={bet.result} />
                    )}
                  </td>
                  <td style={{ padding: "10px 6px" }}>
                    <div style={{ display: "flex", gap: 4 }}>
                      {bet.result === "pending" && (
                        <button onClick={() => setEditingResult(bet.id)} style={{
                          padding: "4px 8px", borderRadius: 5,
                          background: C.amberDim, border: `1px solid ${C.amber}33`,
                          color: C.amber, fontSize: 11, cursor: "pointer",
                        }} title="Marcar resultado">✎</button>
                      )}
                      <button onClick={() => handleDelete(bet.id)} style={{
                        padding: "4px 8px", borderRadius: 5,
                        background: C.redDim, border: `1px solid ${C.red}33`,
                        color: C.red, fontSize: 11, cursor: "pointer",
                      }} title="Eliminar">🗑</button>
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

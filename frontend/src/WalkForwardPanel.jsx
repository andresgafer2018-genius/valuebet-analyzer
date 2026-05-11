import { useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, ReferenceLine
} from "recharts";

const API = import.meta.env.VITE_API_URL || "http://localhost:5000";

const LEAGUES = [
  "Premier League", "La Liga", "Serie A", "Bundesliga",
  "Ligue 1", "Liga Argentina", "Champions League"
];

export default function WalkForwardPanel() {
  const [league, setLeague]             = useState("Premier League");
  const [windowMonths, setWindowMonths] = useState(3);
  const [stepMonths, setStepMonths]     = useState(1);
  const [minEdge, setMinEdge]           = useState(0.05);
  const [loading, setLoading]           = useState(false);
  const [result, setResult]             = useState(null);
  const [error, setError]               = useState(null);

  async function runWFV() {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const params = new URLSearchParams({
        league,
        window_months: windowMonths,
        step_months: stepMonths,
        min_edge: minEdge,
        bankroll: 1000,
      });
      const res  = await fetch(`${API}/api/backtest/walk-forward?${params}`);
      const data = await res.json();
      if (data.error) setError(data.error);
      else setResult(data);
    } catch (e) {
      setError("Error conectando con el servidor");
    }
    setLoading(false);
  }

  const chartData = result?.windows?.map((w) => ({
    name      : w.period,
    "ROI Kelly": w.roi_kelly,
    "ROI Flat" : w.roi_flat,
  })) || [];

  return (
    <div style={{ padding: "24px", color: "#e2e8f0", fontFamily: "Inter, sans-serif" }}>
      <h2 style={{ color: "#4ade80", marginBottom: 4, fontSize: 22 }}>
        📊 Walk-Forward Validation
      </h2>
      <p style={{ color: "#94a3b8", marginBottom: 24, fontSize: 13 }}>
        Simula el modelo ventana por ventana en el tiempo — más realista que el backtesting estático.
      </p>

      {/* Config */}
      <div style={{
        display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px,1fr))",
        gap: 16, background: "#1e293b", padding: 20, borderRadius: 12, marginBottom: 24
      }}>
        <div>
          <label style={labelStyle}>Liga</label>
          <select value={league} onChange={e => setLeague(e.target.value)} style={selectStyle}>
            {LEAGUES.map(l => <option key={l}>{l}</option>)}
          </select>
        </div>
        <div>
          <label style={labelStyle}>Ventana entrenamiento (meses)</label>
          <input type="number" min={1} max={12} value={windowMonths}
            onChange={e => setWindowMonths(+e.target.value)} style={inputStyle} />
        </div>
        <div>
          <label style={labelStyle}>Paso (meses)</label>
          <input type="number" min={1} max={3} value={stepMonths}
            onChange={e => setStepMonths(+e.target.value)} style={inputStyle} />
        </div>
        <div>
          <label style={labelStyle}>Edge mínimo</label>
          <input type="number" min={0.01} max={0.3} step={0.01} value={minEdge}
            onChange={e => setMinEdge(+e.target.value)} style={inputStyle} />
        </div>
      </div>

      <button onClick={runWFV} disabled={loading} style={{
        background: loading ? "#374151" : "#16a34a",
        color: "#fff", border: "none", borderRadius: 8,
        padding: "12px 32px", fontSize: 15, cursor: loading ? "not-allowed" : "pointer",
        marginBottom: 28, fontWeight: 600
      }}>
        {loading ? "⏳ Calculando..." : "▶ Ejecutar WFV"}
      </button>

      {error && (
        <div style={{ background: "#7f1d1d", color: "#fca5a5", padding: 16,
          borderRadius: 8, marginBottom: 20 }}>
          ⚠️ {error}
        </div>
      )}

      {result && (
        <>
          {/* KPIs */}
          <div style={{
            display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px,1fr))",
            gap: 12, marginBottom: 28
          }}>
            {[
              { label: "Ventanas totales",   value: result.total_windows },
              { label: "Ventanas rentables", value: `${result.profitable_windows} (${result.pct_profitable}%)`,
                color: result.pct_profitable >= 50 ? "#4ade80" : "#f87171" },
              { label: "ROI medio Kelly",    value: `${result.avg_roi_kelly}%`,
                color: result.avg_roi_kelly > 0 ? "#4ade80" : "#f87171" },
              { label: "ROI medio Flat",     value: `${result.avg_roi_flat}%`,
                color: result.avg_roi_flat > 0 ? "#4ade80" : "#f87171" },
              { label: "Mejor ROI",          value: `${result.best_roi_kelly}%`, color: "#4ade80" },
              { label: "Peor ROI",           value: `${result.worst_roi_kelly}%`, color: "#f87171" },
              { label: "Desv. estándar ROI", value: `±${result.std_roi_kelly}%`, color: "#fbbf24" },
            ].map(kpi => (
              <div key={kpi.label} style={{
                background: "#1e293b", borderRadius: 10, padding: "14px 16px",
                borderLeft: `3px solid ${kpi.color || "#64748b"}`
              }}>
                <div style={{ fontSize: 11, color: "#94a3b8", marginBottom: 4 }}>{kpi.label}</div>
                <div style={{ fontSize: 20, fontWeight: 700, color: kpi.color || "#e2e8f0" }}>
                  {kpi.value}
                </div>
              </div>
            ))}
          </div>

          {/* Gráfico ROI por ventana */}
          <div style={{ background: "#1e293b", borderRadius: 12, padding: 20, marginBottom: 24 }}>
            <h3 style={{ color: "#94a3b8", fontSize: 14, marginBottom: 16 }}>
              ROI por ventana temporal
            </h3>
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 11 }} />
                <YAxis tick={{ fill: "#94a3b8", fontSize: 11 }} unit="%" />
                <Tooltip
                  contentStyle={{ background: "#0f172a", border: "1px solid #334155", borderRadius: 8 }}
                  labelStyle={{ color: "#94a3b8" }}
                  formatter={(v) => [`${v}%`]}
                />
                <Legend wrapperStyle={{ color: "#94a3b8", fontSize: 12 }} />
                <ReferenceLine y={0} stroke="#475569" strokeDasharray="4 4" />
                <Line type="monotone" dataKey="ROI Kelly" stroke="#4ade80" strokeWidth={2}
                  dot={{ r: 4, fill: "#4ade80" }} activeDot={{ r: 6 }} />
                <Line type="monotone" dataKey="ROI Flat" stroke="#60a5fa" strokeWidth={2}
                  dot={{ r: 4, fill: "#60a5fa" }} activeDot={{ r: 6 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Tabla detalle */}
          <div style={{ background: "#1e293b", borderRadius: 12, padding: 20, overflowX: "auto" }}>
            <h3 style={{ color: "#94a3b8", fontSize: 14, marginBottom: 14 }}>
              Detalle por ventana
            </h3>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: "1px solid #334155" }}>
                  {["Período","Entreno","Test","Apuestas","Win%","ROI Kelly","ROI Flat"].map(h => (
                    <th key={h} style={{ padding: "8px 12px", textAlign: "left",
                      color: "#64748b", fontWeight: 600 }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {result.windows.map((w, i) => (
                  <tr key={i} style={{ borderBottom: "1px solid #1e293b",
                    background: i % 2 === 0 ? "#0f172a" : "transparent" }}>
                    <td style={tdStyle}>{w.period}</td>
                    <td style={tdStyle}>{w.train_size}</td>
                    <td style={tdStyle}>{w.test_size}</td>
                    <td style={tdStyle}>{w.bets}</td>
                    <td style={tdStyle}>{w.win_rate}%</td>
                    <td style={{ ...tdStyle, color: w.roi_kelly >= 0 ? "#4ade80" : "#f87171",
                      fontWeight: 600 }}>{w.roi_kelly}%</td>
                    <td style={{ ...tdStyle, color: w.roi_flat >= 0 ? "#60a5fa" : "#f87171",
                      fontWeight: 600 }}>{w.roi_flat}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

const labelStyle = { display: "block", fontSize: 11, color: "#64748b",
  marginBottom: 6, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em" };
const inputStyle = { width: "100%", background: "#0f172a", border: "1px solid #334155",
  borderRadius: 6, padding: "8px 10px", color: "#e2e8f0", fontSize: 14, boxSizing: "border-box" };
const selectStyle = { ...inputStyle };
const tdStyle = { padding: "9px 12px", color: "#cbd5e1" };

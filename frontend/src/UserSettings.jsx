// src/UserSettings.jsx
import { useState, useEffect } from "react"

const API = import.meta.env.VITE_API_URL || 'http://localhost:5050'

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

const DEFAULTS = {
  // Perfil
  username:    "",
  currency:    "USD",
  timezone:    "America/Argentina/Buenos_Aires",
  // Apuestas
  min_stake:   10,
  max_stake:   500,
  max_daily_pct: 20,
  min_edge:    3,
  fav_leagues: [],
  fav_markets: [],
  // Notificaciones
  notif_telegram:  false,
  telegram_token:  "",
  telegram_chat:   "",
  notif_email:     false,
  email_address:   "",
  notif_min_conf:  "ALTA",
  notif_min_edge:  8,
  // Modelo
  kelly_fraction:  50,
  poisson_weight:  60,
  logistic_weight: 40,
  min_confidence:  "BAJA",
  home_advantage:  1.131,
}

const ALL_LEAGUES = [
  "Premier League", "La Liga", "Serie A", "Bundesliga", "Ligue 1",
  "Champions League", "Liga Argentina", "MLS", "Brasileirao", "Liga MX",
]
const ALL_MARKETS = [
  { id:"1X2_home",  label:"Victoria Local" },
  { id:"1X2_draw",  label:"Empate" },
  { id:"1X2_away",  label:"Victoria Visitante" },
  { id:"over_2.5",  label:"Más de 2.5 Goles" },
  { id:"under_2.5", label:"Menos de 2.5 Goles" },
]

/* --- UI ATOMS ------------------------------------------------------------ */
function Panel({ title, icon, children, style }) {
  return (
    <div style={{ background:C.bg2, border:`1px solid ${C.border}`,
      borderRadius:6, overflow:"hidden", ...style }}>
      <div style={{ padding:"12px 16px", borderBottom:`1px solid ${C.border}`,
        background:C.bg3, display:"flex", alignItems:"center", gap:8 }}>
        <span style={{ fontSize:16 }}>{icon}</span>
        <span style={{ fontSize:12, fontWeight:700, color:C.text1,
          letterSpacing:".08em", textTransform:"uppercase",
          fontFamily:"'JetBrains Mono',monospace" }}>{title}</span>
      </div>
      <div style={{ padding:"16px" }}>{children}</div>
    </div>
  )
}

function Field({ label, hint, children }) {
  return (
    <div style={{ display:"flex", flexDirection:"column", gap:6 }}>
      <label style={{ fontSize:12, fontWeight:600, color:C.text1 }}>{label}</label>
      {children}
      {hint && <span style={{ fontSize:11, color:C.text2 }}>{hint}</span>}
    </div>
  )
}

function Input({ value, onChange, type="text", placeholder, min, max, step, disabled }) {
  return (
    <input type={type} value={value} onChange={onChange}
      placeholder={placeholder} min={min} max={max} step={step}
      disabled={disabled}
      style={{ background:C.bg3, border:`1px solid ${C.border2}`, color: disabled ? C.text2 : C.text0,
        borderRadius:4, padding:"8px 12px", fontSize:13,
        fontFamily: type==="number" ? "'JetBrains Mono',monospace" : "'DM Sans',sans-serif",
        width:"100%", outline:"none", cursor: disabled ? "not-allowed" : "text",
        transition:"border .15s" }}
      onFocus={e => { if(!disabled) e.target.style.borderColor = C.green+"60" }}
      onBlur={e => e.target.style.borderColor = C.border2}
    />
  )
}

function Select({ value, onChange, options }) {
  return (
    <select value={value} onChange={onChange}
      style={{ background:C.bg3, border:`1px solid ${C.border2}`, color:C.text0,
        borderRadius:4, padding:"8px 12px", fontSize:13,
        fontFamily:"'DM Sans',sans-serif", width:"100%",
        outline:"none", cursor:"pointer" }}>
      {options.map(o => (
        <option key={o.value} value={o.value}>{o.label}</option>
      ))}
    </select>
  )
}

function Toggle({ value, onChange, label }) {
  return (
    <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between",
      padding:"10px 14px", background:C.bg3, borderRadius:5,
      border:`1px solid ${value ? C.green+"40" : C.border}` }}>
      <span style={{ fontSize:13, color: value ? C.text0 : C.text1 }}>{label}</span>
      <div onClick={() => onChange(!value)}
        style={{ width:40, height:22, borderRadius:11, cursor:"pointer",
          background: value ? C.green : C.border2, position:"relative",
          transition:"background .2s" }}>
        <div style={{ position:"absolute", top:3,
          left: value ? 21 : 3, width:16, height:16,
          borderRadius:"50%", background:"#fff",
          transition:"left .2s", boxShadow:"0 1px 3px #0004" }}/>
      </div>
    </div>
  )
}

function SliderField({ label, value, onChange, min, max, step=1, unit="", color=C.green, hint }) {
  return (
    <Field label={label} hint={hint}>
      <div style={{ display:"flex", alignItems:"center", gap:12 }}>
        <input type="range" min={min} max={max} step={step} value={value}
          onChange={onChange}
          style={{ flex:1, accentColor:color, cursor:"pointer" }}/>
        <span style={{ fontSize:14, fontWeight:700, color,
          fontFamily:"'JetBrains Mono',monospace", minWidth:52, textAlign:"right" }}>
          {value}{unit}
        </span>
      </div>
    </Field>
  )
}

function MultiSelect({ options, selected, onChange, color=C.green }) {
  const toggle = id => {
    const next = selected.includes(id)
      ? selected.filter(x => x !== id)
      : [...selected, id]
    onChange(next)
  }
  return (
    <div style={{ display:"flex", flexWrap:"wrap", gap:6 }}>
      {options.map(o => {
        const active = selected.includes(o.id || o)
        return (
          <button key={o.id||o} onClick={() => toggle(o.id||o)}
            style={{ background: active ? color+"20" : "none",
              border:`1px solid ${active ? color+"50" : C.border2}`,
              color: active ? color : C.text2,
              borderRadius:4, padding:"5px 12px", fontSize:12,
              cursor:"pointer", fontFamily:"'DM Sans',sans-serif",
              transition:"all .15s", fontWeight: active ? 600 : 400 }}>
            {o.label || o}
          </button>
        )
      })}
    </div>
  )
}

function SaveBar({ onSave, onReset, saving, saved }) {
  return (
    <div style={{ position:"sticky", bottom:0, background:C.bg1,
      borderTop:`1px solid ${C.border}`, padding:"12px 0",
      display:"flex", alignItems:"center", justifyContent:"space-between",
      marginTop:16 }}>
      <button onClick={onReset}
        style={{ background:"none", border:`1px solid ${C.border2}`,
          color:C.text2, borderRadius:4, padding:"7px 16px",
          fontSize:12, cursor:"pointer", fontFamily:"'DM Sans',sans-serif" }}>
        Restablecer valores por defecto
      </button>
      <div style={{ display:"flex", alignItems:"center", gap:10 }}>
        {saved && (
          <span style={{ fontSize:12, color:C.green,
            fontFamily:"'JetBrains Mono',monospace" }}>
            ✓ Configuración guardada
          </span>
        )}
        <button onClick={onSave} disabled={saving}
          style={{ background: saving ? C.bg3 : C.green+"20",
            border:`1px solid ${C.green}50`, color:C.green,
            borderRadius:4, padding:"7px 20px", fontSize:13,
            fontWeight:600, cursor: saving ? "wait" : "pointer",
            fontFamily:"'DM Sans',sans-serif", transition:"all .15s" }}>
          {saving ? "Guardando..." : "💾 Guardar configuración"}
        </button>
      </div>
    </div>
  )
}

/* --- SECCIONES ----------------------------------------------------------- */
function PerfilSection({ s, set }) {
  return (
    <Panel title="Perfil de Usuario" icon="👤">
      <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr 1fr", gap:14 }}>
        <Field label="Nombre de usuario"
          hint="Cómo querés que te llame el sistema">
          <Input value={s.username} placeholder="Tu nombre"
            onChange={e => set("username", e.target.value)}/>
        </Field>
        <Field label="Moneda preferida">
          <Select value={s.currency} onChange={e => set("currency", e.target.value)}
            options={[
              { value:"USD", label:"USD — Dólar americano" },
              { value:"ARS", label:"ARS — Peso argentino" },
              { value:"EUR", label:"EUR — Euro" },
              { value:"GBP", label:"GBP — Libra esterlina" },
              { value:"BRL", label:"BRL — Real brasileño" },
            ]}/>
        </Field>
        <Field label="Zona horaria">
          <Select value={s.timezone} onChange={e => set("timezone", e.target.value)}
            options={[
              { value:"America/Argentina/Buenos_Aires", label:"Buenos Aires (GMT-3)" },
              { value:"America/New_York",               label:"New York (GMT-5)" },
              { value:"Europe/London",                  label:"Londres (GMT+0)" },
              { value:"Europe/Madrid",                  label:"Madrid (GMT+1)" },
              { value:"America/Sao_Paulo",              label:"São Paulo (GMT-3)" },
            ]}/>
        </Field>
      </div>
    </Panel>
  )
}

function ApuestasSection({ s, set }) {
  return (
    <Panel title="Preferencias de Apuestas" icon="⚽">
      <div style={{ display:"flex", flexDirection:"column", gap:16 }}>
        <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:14 }}>
          <Field label="Stake mínimo por apuesta"
            hint="No se sugerirán apuestas por debajo de este monto">
            <Input type="number" value={s.min_stake} min={1} max={s.max_stake}
              onChange={e => set("min_stake", +e.target.value)}/>
          </Field>
          <Field label="Stake máximo por apuesta"
            hint="Límite superior por apuesta individual">
            <Input type="number" value={s.max_stake} min={s.min_stake} max={100000}
              onChange={e => set("max_stake", +e.target.value)}/>
          </Field>
        </div>

        <SliderField label="Máximo capital diario en juego"
          value={s.max_daily_pct} onChange={e => set("max_daily_pct", +e.target.value)}
          min={5} max={50} unit="%" color={C.amber}
          hint="Porcentaje máximo del bankroll que podés comprometer por día"/>

        <SliderField label="Edge mínimo para mostrar apuestas"
          value={s.min_edge} onChange={e => set("min_edge", +e.target.value)}
          min={1} max={20} unit="%" color={C.green}
          hint="Solo se muestran apuestas con ventaja mayor a este porcentaje"/>

        <Field label="Ligas favoritas"
          hint="Solo se analizarán estas ligas (vacío = todas)">
          <MultiSelect
            options={ALL_LEAGUES}
            selected={s.fav_leagues}
            onChange={v => set("fav_leagues", v)}
            color={C.blue}/>
        </Field>

        <Field label="Mercados preferidos"
          hint="Tipos de apuesta que querés ver (vacío = todos)">
          <MultiSelect
            options={ALL_MARKETS}
            selected={s.fav_markets}
            onChange={v => set("fav_markets", v)}
            color={C.green}/>
        </Field>
      </div>
    </Panel>
  )
}

function NotificacionesSection({ s, set }) {
  return (
    <Panel title="Notificaciones" icon="🔔">
      <div style={{ display:"flex", flexDirection:"column", gap:14 }}>

        {/* Telegram */}
        <Toggle value={s.notif_telegram}
          onChange={v => set("notif_telegram", v)}
          label="Notificaciones por Telegram"/>

        {s.notif_telegram && (
          <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:12,
            padding:"12px", background:C.bg3, borderRadius:5,
            border:`1px solid ${C.green}30`, animation:"fadeIn .2s ease" }}>
            <Field label="Token del Bot de Telegram"
              hint="Obtené uno con @BotFather en Telegram">
              <Input value={s.telegram_token} placeholder="123456789:ABCdef..."
                onChange={e => set("telegram_token", e.target.value)}/>
            </Field>
            <Field label="Chat ID"
              hint="Tu ID de chat (usá @userinfobot para obtenerlo)">
              <Input value={s.telegram_chat} placeholder="-100123456789"
                onChange={e => set("telegram_chat", e.target.value)}/>
            </Field>
          </div>
        )}

        {/* Email */}
        <Toggle value={s.notif_email}
          onChange={v => set("notif_email", v)}
          label="Notificaciones por Email"/>

        {s.notif_email && (
          <div style={{ padding:"12px", background:C.bg3, borderRadius:5,
            border:`1px solid ${C.blue}30`, animation:"fadeIn .2s ease" }}>
            <Field label="Dirección de email">
              <Input type="email" value={s.email_address}
                placeholder="tu@email.com"
                onChange={e => set("email_address", e.target.value)}/>
            </Field>
          </div>
        )}

        {/* Umbrales */}
        {(s.notif_telegram || s.notif_email) && (
          <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:12,
            padding:"12px", background:C.bg3, borderRadius:5,
            border:`1px solid ${C.border}` }}>
            <Field label="Notificar solo desde confianza">
              <Select value={s.notif_min_conf}
                onChange={e => set("notif_min_conf", e.target.value)}
                options={[
                  { value:"BAJA",  label:"BAJA — Todas las apuestas" },
                  { value:"MEDIA", label:"MEDIA — Confianza media o alta" },
                  { value:"ALTA",  label:"ALTA — Solo las mejores" },
                ]}/>
            </Field>
            <SliderField label="Edge mínimo para notificar"
              value={s.notif_min_edge}
              onChange={e => set("notif_min_edge", +e.target.value)}
              min={1} max={20} unit="%" color={C.amber}/>
          </div>
        )}

        {!s.notif_telegram && !s.notif_email && (
          <div style={{ padding:"12px 14px", background:C.amberDim,
            border:`1px solid ${C.amber}30`, borderRadius:5 }}>
            <span style={{ fontSize:12, color:C.amber }}>
              💡 Activá al menos un canal para recibir alertas cuando aparezcan value bets.
            </span>
          </div>
        )}
      </div>
    </Panel>
  )
}

function ModeloSection({ s, set }) {
  const total = s.poisson_weight + s.logistic_weight

  const handlePoisson = (v) => {
    set("poisson_weight", v)
    set("logistic_weight", 100 - v)
  }

  return (
    <Panel title="Configuración del Modelo" icon="🧠">
      <div style={{ display:"flex", flexDirection:"column", gap:16 }}>

        <SliderField label="Kelly fraccionado"
          value={s.kelly_fraction}
          onChange={e => set("kelly_fraction", +e.target.value)}
          min={10} max={100} unit="%"
          color={C.blue}
          hint="50% = conservador (recomendado). 100% = Kelly completo, mayor riesgo."/>

        <div style={{ padding:"12px 14px", background:C.bg3, borderRadius:5,
          border:`1px solid ${C.border}`, display:"flex", flexDirection:"column", gap:10 }}>
          <div style={{ fontSize:12, fontWeight:600, color:C.text1, marginBottom:2 }}>
            Peso de cada modelo en el ensemble
          </div>
          <SliderField label="Modelo de Poisson"
            value={s.poisson_weight}
            onChange={e => handlePoisson(+e.target.value)}
            min={10} max={90} unit="%"
            color={C.green}
            hint="Estima goles esperados por equipo"/>
          <SliderField label="Regresión Logística"
            value={s.logistic_weight}
            onChange={() => {}}
            min={10} max={90} unit="%"
            color={C.purple}
            hint="Calculado automáticamente: 100% - Poisson"/>
          {total !== 100 && (
            <span style={{ fontSize:11, color:C.red }}>⚠ Los pesos deben sumar 100%</span>
          )}
        </div>

        <Field label="Confianza mínima para mostrar apuestas">
          <Select value={s.min_confidence}
            onChange={e => set("min_confidence", e.target.value)}
            options={[
              { value:"BAJA",  label:"BAJA — Mostrar todas (edge >= 3%)" },
              { value:"MEDIA", label:"MEDIA — Solo media y alta (edge >= 5%)" },
              { value:"ALTA",  label:"ALTA — Solo las mejores (edge >= 10%)" },
            ]}/>
        </Field>

        <Field label="Factor de ventaja local (λ)"
          hint="Multiplicador para el equipo local. Por defecto 1.131 (11.3% de ventaja)">
          <div style={{ display:"flex", alignItems:"center", gap:12 }}>
            <input type="range" min={0.9} max={1.5} step={0.001}
              value={s.home_advantage}
              onChange={e => set("home_advantage", +parseFloat(e.target.value).toFixed(3))}
              style={{ flex:1, accentColor:C.amber, cursor:"pointer" }}/>
            <span style={{ fontSize:14, fontWeight:700, color:C.amber,
              fontFamily:"'JetBrains Mono',monospace", minWidth:52, textAlign:"right" }}>
              {s.home_advantage.toFixed(3)}
            </span>
          </div>
          <div style={{ display:"flex", justifyContent:"space-between",
            fontSize:10, color:C.text2, fontFamily:"'JetBrains Mono',monospace" }}>
            <span>0.900 (sin ventaja)</span>
            <span style={{ color:C.amber }}>1.131 (por defecto)</span>
            <span>1.500 (máxima)</span>
          </div>
        </Field>

        <div style={{ padding:"10px 14px", background:C.blueDim,
          border:`1px solid ${C.blue}30`, borderRadius:5 }}>
          <span style={{ fontSize:12, color:C.text1 }}>
            💡 Los cambios en el modelo se aplican en el próximo re-entrenamiento.
            Podés forzarlo desde el panel de <strong style={{color:C.blue}}>Backtesting</strong>.
          </span>
        </div>
      </div>
    </Panel>
  )
}

/* --- COMPONENTE PRINCIPAL ------------------------------------------------ */
export default function UserSettings() {
  const [settings, setSettings] = useState(DEFAULTS)
  const [loading,  setLoading]  = useState(true)
  const [saving,   setSaving]   = useState(false)
  const [saved,    setSaved]    = useState(false)
  const [activeTab, setActiveTab] = useState("perfil")

  useEffect(() => {
    fetch(`${API}/api/settings`)
      .then(r => r.json())
      .then(d => setSettings({ ...DEFAULTS, ...d }))
      .catch(() => setSettings(DEFAULTS))
      .finally(() => setLoading(false))
  }, [])

  const set = (key, val) => {
    setSettings(prev => ({ ...prev, [key]: val }))
    setSaved(false)
  }

  const save = async () => {
    setSaving(true)
    try {
      await fetch(`${API}/api/settings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(settings),
      })
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    } catch (e) {
      alert("Error al guardar: " + e.message)
    } finally {
      setSaving(false)
    }
  }

  const reset = () => {
    if (confirm("¿Restablecer todos los valores por defecto?")) {
      setSettings(DEFAULTS)
      setSaved(false)
    }
  }

  const tabs = [
    { id:"perfil",         label:"👤 Perfil" },
    { id:"apuestas",       label:"⚽ Apuestas" },
    { id:"notificaciones", label:"🔔 Notificaciones" },
    { id:"modelo",         label:"🧠 Modelo" },
  ]

  if (loading) return (
    <div style={{ display:"flex", flexDirection:"column", gap:12 }}>
      {Array(3).fill(0).map((_,i) => (
        <div key={i} style={{ height:120, borderRadius:6, background:C.bg2,
          border:`1px solid ${C.border}`, animation:"shimmer 1.5s infinite" }}/>
      ))}
    </div>
  )

  return (
    <div style={{ display:"flex", flexDirection:"column", gap:12 }}>
      <style>{`
        @keyframes fadeIn{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:translateY(0)}}
        @keyframes shimmer{0%{background-position:200% 0}100%{background-position:-200% 0}}
        input[type=range]{accent-color:${C.green}}
      `}</style>

      {/* Tabs de sección */}
      <div style={{ display:"flex", gap:4, padding:"10px 14px",
        background:C.bg2, border:`1px solid ${C.border}`, borderRadius:6 }}>
        {tabs.map(t => (
          <button key={t.id} onClick={() => setActiveTab(t.id)}
            style={{ background: activeTab===t.id ? C.bg3 : "none",
              border: activeTab===t.id ? `1px solid ${C.green}40` : `1px solid transparent`,
              color: activeTab===t.id ? C.green : C.text2,
              borderRadius:4, padding:"6px 16px", fontSize:13,
              cursor:"pointer", fontFamily:"'DM Sans',sans-serif",
              fontWeight: activeTab===t.id ? 600 : 400,
              transition:"all .15s" }}>
            {t.label}
          </button>
        ))}
      </div>

      {/* Contenido según tab */}
      <div style={{ animation:"fadeIn .2s ease" }}>
        {activeTab === "perfil"         && <PerfilSection s={settings} set={set}/>}
        {activeTab === "apuestas"       && <ApuestasSection s={settings} set={set}/>}
        {activeTab === "notificaciones" && <NotificacionesSection s={settings} set={set}/>}
        {activeTab === "modelo"         && <ModeloSection s={settings} set={set}/>}
      </div>

      <SaveBar onSave={save} onReset={reset} saving={saving} saved={saved}/>
    </div>
  )
}

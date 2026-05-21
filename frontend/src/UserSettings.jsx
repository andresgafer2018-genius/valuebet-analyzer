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
  username:     "",
  currency:     "USD",
  timezone:     "America/Argentina/Buenos_Aires",
  // Apuestas
  min_stake:    10,
  max_stake:    500,
  max_daily_pct: 20,
  min_edge:     3,
  fav_leagues:  [],
  fav_markets:  [],
  // Notificaciones
  notif_telegram:  false,
  telegram_token:  "",
  notif_email:     false,
  notif_email_addr:"",
  notif_on_value:  true,
  notif_on_result: false,
  // Modelo
  model_weights:   { poisson: 60, logistic: 40 },
  kelly_fraction:  0.5,
  home_advantage:  1.131,
  min_confidence:  "BAJA",
}

/* --- COMPONENTES BASE --- */

function Panel({ title, icon, children }) {
  return (
    <div style={{
      background: C.bg2,
      border: `1px solid ${C.border}`,
      borderRadius: 8,
      overflow: "hidden",
    }}>
      <div style={{
        padding: "12px 16px",
        borderBottom: `1px solid ${C.border}`,
        display: "flex", alignItems: "center", gap: 8,
      }}>
        {icon && <span style={{ fontSize: 16 }}>{icon}</span>}
        <span style={{
          fontSize: 13, fontWeight: 600, color: C.text0,
          fontFamily: "'DM Sans',sans-serif", letterSpacing: "0.02em",
        }}>{title}</span>
      </div>
      <div style={{ padding: "16px" }}>
        {children}
      </div>
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
      style={{
        background:C.bg3, border:`1px solid ${C.border2}`, color: disabled ? C.text2 : C.text0,
        borderRadius:4, padding:"8px 12px", fontSize:13,
        fontFamily: type==="number" ? "'JetBrains Mono',monospace" : "'DM Sans',sans-serif",
        width:"100%", outline:"none", cursor: disabled ? "not-allowed" : "text",
        transition:"border .15s"
      }}
      onFocus={e => { if(!disabled) e.target.style.borderColor = C.green+"60" }}
      onBlur={e => e.target.style.borderColor = C.border2}
    />
  )
}

function Select({ value, onChange, options }) {
  return (
    <select value={value} onChange={onChange}
      style={{
        background:C.bg3, border:`1px solid ${C.border2}`, color:C.text0,
        borderRadius:4, padding:"8px 12px", fontSize:13,
        fontFamily:"'DM Sans',sans-serif", width:"100%",
        outline:"none", cursor:"pointer"
      }}>
      {options.map(o => (
        <option key={o.value} value={o.value}>{o.label}</option>
      ))}
    </select>
  )
}

function Toggle({ value, onChange, label }) {
  return (
    <div style={{
      display:"flex", alignItems:"center", justifyContent:"space-between",
      padding:"10px 14px", background:C.bg3, borderRadius:5,
      border:`1px solid ${value ? C.green+"40" : C.border}`
    }}>
      <span style={{ fontSize:13, color: value ? C.text0 : C.text1 }}>{label}</span>
      <div onClick={() => onChange(!value)}
        style={{
          width:40, height:22, borderRadius:11, cursor:"pointer",
          background: value ? C.green : C.bg1,
          border:`1px solid ${value ? C.green : C.border2}`,
          position:"relative", transition:"all .2s"
        }}>
        <div style={{
          position:"absolute", top:2,
          left: value ? 20 : 2,
          width:16, height:16, borderRadius:"50%",
          background: value ? C.bg0 : C.text2,
          transition:"left .2s"
        }}/>
      </div>
    </div>
  )
}

function SaveBar({ onSave, onReset, saving, saved }) {
  return (
    <div style={{
      display:"flex", justifyContent:"flex-end", gap:10,
      padding:"12px 0", borderTop:`1px solid ${C.border}`, marginTop:4,
    }}>
      <button onClick={onReset}
        style={{
          background:"none", border:`1px solid ${C.border2}`,
          color:C.text1, borderRadius:5, padding:"7px 18px",
          fontSize:13, cursor:"pointer", fontFamily:"'DM Sans',sans-serif",
        }}>
        Restablecer
      </button>
      <button onClick={onSave} disabled={saving}
        style={{
          background: saved ? C.greenDim : C.green,
          border:`1px solid ${saved ? C.green+"40" : C.green}`,
          color: saved ? C.green : C.bg0,
          borderRadius:5, padding:"7px 22px",
          fontSize:13, fontWeight:600, cursor: saving ? "wait" : "pointer",
          fontFamily:"'DM Sans',sans-serif", transition:"all .2s",
        }}>
        {saving ? "Guardando…" : saved ? "✓ Guardado" : "Guardar cambios"}
      </button>
    </div>
  )
}

/* --- SECCIONES --- */

function PerfilSection({ s, set }) {
  return (
    <Panel title="Perfil de Usuario" icon="👤">
      <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr 1fr", gap:14 }}>
        <Field label="Nombre de usuario" hint="Cómo querés que te llame el sistema">
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
  const total = (s.model_weights?.poisson || 60) + (s.model_weights?.logistic || 40)
  return (
    <Panel title="Preferencias de Apuestas" icon="🎯">
      <div style={{ display:"flex", flexDirection:"column", gap:16 }}>
        <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:14 }}>
          <Field label="Stake mínimo por apuesta" hint="No se sugerirán apuestas por debajo de este monto">
            <Input type="number" value={s.min_stake} min={1} max={s.max_stake}
              onChange={e => set("min_stake", +e.target.value)}/>
          </Field>
          <Field label="Stake máximo por apuesta" hint="Límite superior por apuesta individual">
            <Input type="number" value={s.max_stake} min={s.min_stake}
              onChange={e => set("max_stake", +e.target.value)}/>
          </Field>
          <Field label="Máximo diario (% del bankroll)" hint="Límite de exposición diaria">
            <div style={{ display:"flex", alignItems:"center", gap:12 }}>
              <input type="range" min={1} max={50} value={s.max_daily_pct}
                onChange={e => set("max_daily_pct", +e.target.value)}
                style={{ flex:1, accentColor:C.green, cursor:"pointer" }}/>
              <span style={{ fontSize:14, fontWeight:700, color:C.green,
                fontFamily:"'JetBrains Mono',monospace", minWidth:40 }}>
                {s.max_daily_pct}%
              </span>
            </div>
          </Field>
          <Field label="Edge mínimo requerido (%)" hint="Solo se mostrarán apuestas con ventaja mayor a este valor">
            <div style={{ display:"flex", alignItems:"center", gap:12 }}>
              <input type="range" min={1} max={20} value={s.min_edge}
                onChange={e => set("min_edge", +e.target.value)}
                style={{ flex:1, accentColor:C.amber, cursor:"pointer" }}/>
              <span style={{ fontSize:14, fontWeight:700, color:C.amber,
                fontFamily:"'JetBrains Mono',monospace", minWidth:40 }}>
                {s.min_edge}%
              </span>
            </div>
          </Field>
        </div>

        <Field label="Pesos del modelo (Poisson / Regresión Logística)">
          <div style={{ display:"flex", alignItems:"center", gap:12 }}>
            <span style={{ fontSize:12, color:C.text1, minWidth:70 }}>Poisson</span>
            <input type="range" min={0} max={100}
              value={s.model_weights?.poisson || 60}
              onChange={e => set("model_weights", { poisson:+e.target.value, logistic:100-(+e.target.value) })}
              style={{ flex:1, accentColor:C.blue, cursor:"pointer" }}/>
            <span style={{ fontSize:13, fontWeight:700, color:C.blue,
              fontFamily:"'JetBrains Mono',monospace", minWidth:35 }}>
              {s.model_weights?.poisson || 60}%
            </span>
            <span style={{ fontSize:12, color:C.text1, minWidth:80 }}>Logística</span>
            <span style={{ fontSize:13, fontWeight:700, color:C.purple,
              fontFamily:"'JetBrains Mono',monospace", minWidth:35 }}>
              {s.model_weights?.logistic || 40}%
            </span>
          </div>
          {total !== 100 && (
            <span style={{ fontSize:11, color:C.red }}>⚠ Los pesos deben sumar 100%</span>
          )}
        </Field>

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

function NotificacionesSection({ s, set }) {
  return (
    <Panel title="Notificaciones" icon="🔔">
      <div style={{ display:"flex", flexDirection:"column", gap:14 }}>
        <Toggle value={s.notif_telegram} label="Notificaciones por Telegram"
          onChange={v => set("notif_telegram", v)}/>
        {s.notif_telegram && (
          <Field label="Token del bot de Telegram" hint="Obtenelo desde @BotFather en Telegram">
            <Input value={s.telegram_token} placeholder="1234567890:ABCdefGHIjklMNOpqrsTUVwxyz"
              onChange={e => set("telegram_token", e.target.value)}/>
          </Field>
        )}
        <Toggle value={s.notif_email} label="Notificaciones por Email"
          onChange={v => set("notif_email", v)}/>
        {s.notif_email && (
          <Field label="Dirección de email">
            <Input type="email" value={s.notif_email_addr} placeholder="tu@email.com"
              onChange={e => set("notif_email_addr", e.target.value)}/>
          </Field>
        )}
        <div style={{ borderTop:`1px solid ${C.border}`, paddingTop:12, display:"flex", flexDirection:"column", gap:8 }}>
          <span style={{ fontSize:12, color:C.text1, fontWeight:600 }}>Cuándo notificar:</span>
          <Toggle value={s.notif_on_value} label="Al detectar una apuesta de valor"
            onChange={v => set("notif_on_value", v)}/>
          <Toggle value={s.notif_on_result} label="Al conocerse el resultado de una apuesta"
            onChange={v => set("notif_on_result", v)}/>
        </div>
      </div>
    </Panel>
  )
}

function ModeloSection({ s, set }) {
  return (
    <Panel title="Configuración del Modelo" icon="🧠">
      <div style={{ display:"flex", flexDirection:"column", gap:14 }}>
        <Field label="Fracción Kelly" hint="0.5 = Kelly al 50% (recomendado para reducir varianza)">
          <div style={{ display:"flex", alignItems:"center", gap:12 }}>
            <input type="range" min={0.1} max={1} step={0.05}
              value={s.kelly_fraction}
              onChange={e => set("kelly_fraction", +parseFloat(e.target.value).toFixed(2))}
              style={{ flex:1, accentColor:C.purple, cursor:"pointer" }}/>
            <span style={{ fontSize:14, fontWeight:700, color:C.purple,
              fontFamily:"'JetBrains Mono',monospace", minWidth:40 }}>
              {(s.kelly_fraction * 100).toFixed(0)}%
            </span>
          </div>
          <div style={{ display:"flex", justifyContent:"space-between",
            fontSize:10, color:C.text2, fontFamily:"'JetBrains Mono',monospace" }}>
            <span>10% (conservador)</span>
            <span style={{ color:C.purple }}>50% (defecto)</span>
            <span>100% (Kelly completo)</span>
          </div>
        </Field>

        <div style={{ padding:"10px 14px", background:C.greenDim,
          border:`1px solid ${C.green}30`, borderRadius:5 }}>
          <span style={{ fontSize:12, color:C.text1 }}>
            ✅ Configuración actual: Poisson {s.model_weights?.poisson || 60}% + 
            Logística {s.model_weights?.logistic || 40}% · 
            Kelly al {(s.kelly_fraction * 100).toFixed(0)}% · 
            Edge mínimo {s.min_edge}%
          </span>
        </div>
      </div>
    </Panel>
  )
}

/* --- COMPONENTE PRINCIPAL --- */

export default function UserSettings() {
  const [settings, setSettings] = useState(DEFAULTS)
  const [saving,   setSaving]   = useState(false)
  const [saved,    setSaved]    = useState(false)
  const [activeTab, setActiveTab] = useState("perfil")

  const tabs = [
    { id:"perfil",         label:"👤 Perfil" },
    { id:"apuestas",       label:"🎯 Apuestas" },
    { id:"notificaciones", label:"🔔 Notificaciones" },
    { id:"modelo",         label:"🧠 Modelo" },
  ]

  useEffect(() => {
    fetch(`${API}/api/settings`)
      .then(r => r.json())
      .then(d => setSettings({ ...DEFAULTS, ...d }))
      .catch(() => setSettings(DEFAULTS))
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
    } catch(e) {
      alert("Error al guardar. Verificá la conexión al servidor.")
    } finally {
      setSaving(false)
    }
  }

  const reset = () => {
    setSettings(DEFAULTS)
    setSaved(false)
  }

  return (
    <div style={{ display:"flex", flexDirection:"column", gap:12 }}>
      <style>{`
        @keyframes fadeIn{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:translateY(0)}}
        input[type=range]{accent-color:${C.green}}
        select option{background:${C.bg3}}
      `}</style>

      {/* Tabs */}
      <div style={{ display:"flex", gap:4, padding:"10px 14px",
        background:C.bg2, border:`1px solid ${C.border}`, borderRadius:6 }}>
        {tabs.map(t => (
          <button key={t.id} onClick={() => setActiveTab(t.id)}
            style={{
              background: activeTab===t.id ? C.bg3 : "none",
              border: activeTab===t.id ? `1px solid ${C.green}40` : `1px solid transparent`,
              color: activeTab===t.id ? C.green : C.text2,
              borderRadius:4, padding:"6px 16px", fontSize:13,
              cursor:"pointer", fontFamily:"'DM Sans',sans-serif",
              fontWeight: activeTab===t.id ? 600 : 400,
              transition:"all .15s"
            }}>
            {t.label}
          </button>
        ))}
      </div>

      {/* Contenido */}
      <div style={{ animation:"fadeIn .2s ease" }}>
        {activeTab === "perfil"         && <PerfilSection         s={settings} set={set}/>}
        {activeTab === "apuestas"       && <ApuestasSection       s={settings} set={set}/>}
        {activeTab === "notificaciones" && <NotificacionesSection s={settings} set={set}/>}
        {activeTab === "modelo"         && <ModeloSection         s={settings} set={set}/>}
      </div>

      <SaveBar onSave={save} onReset={reset} saving={saving} saved={saved}/>
    </div>
  )
}

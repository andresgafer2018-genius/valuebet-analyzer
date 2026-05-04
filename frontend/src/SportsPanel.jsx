import { useState } from "react"

const C = { bg1:"#0d1117",bg2:"#161b22",bg3:"#21262d",border:"#30363d",text1:"#e6edf3",text2:"#8b949e",green:"#3fb950",greenDim:"#3fb95020",red:"#f85149",amber:"#d29922",amberDim:"#d2992220",blue:"#4d9cf5",blueDim:"#4d9cf512",purple:"#9b6dff" }

function Badge({text,color}){return <span style={{fontSize:10,fontWeight:700,padding:"2px 7px",borderRadius:3,background:color+"20",color,fontFamily:"'JetBrains Mono',monospace",letterSpacing:".08em",whiteSpace:"nowrap"}}>{text}</span>}

function SportCard({alert,sport}){
  const conf = alert.confidence==="ALTA"
  return(
    <div style={{background:C.bg3,border:`1px solid ${conf?C.green+"40":C.border}`,borderRadius:6,padding:"12px 16px",display:"flex",flexDirection:"column",gap:8}}>
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",flexWrap:"wrap",gap:6}}>
        <div>
          <div style={{fontSize:13,fontWeight:600,color:C.text1}}>{sport==="tennis"?alert.player:alert.team}</div>
          <div style={{fontSize:11,color:C.text2,marginTop:2}}>{alert.match}</div>
        </div>
        <div style={{display:"flex",gap:6,flexWrap:"wrap",alignItems:"center"}}>
          <Badge text={alert.confidence} color={conf?C.green:C.amber}/>
          {sport==="tennis"&&<Badge text={alert.surface} color={C.blue}/>}
          {sport==="basketball"&&<Badge text={alert.league} color={C.purple}/>}
        </div>
      </div>
      <div style={{display:"flex",gap:10,flexWrap:"wrap"}}>
        <div style={{background:C.bg2,borderRadius:4,padding:"6px 12px",flex:1,minWidth:90}}>
          <div style={{fontSize:10,color:C.text2,marginBottom:2}}>MERCADO</div>
          <div style={{fontSize:12,color:C.text1,fontWeight:500}}>{alert.market}</div>
        </div>
        <div style={{background:C.bg2,borderRadius:4,padding:"6px 12px",minWidth:70}}>
          <div style={{fontSize:10,color:C.text2,marginBottom:2}}>PROB.</div>
          <div style={{fontSize:14,fontWeight:700,color:C.blue}}>{alert.model_prob}%</div>
        </div>
        <div style={{background:C.bg2,borderRadius:4,padding:"6px 12px",minWidth:70}}>
          <div style={{fontSize:10,color:C.text2,marginBottom:2}}>EDGE</div>
          <div style={{fontSize:14,fontWeight:700,color:C.green}}>+{alert.edge_pct}%</div>
        </div>
        <div style={{background:C.bg2,borderRadius:4,padding:"6px 12px",minWidth:70}}>
          <div style={{fontSize:10,color:C.text2,marginBottom:2}}>CUOTA</div>
          <div style={{fontSize:14,fontWeight:700,color:C.text1}}>{alert.odd}</div>
        </div>
        <div style={{background:C.bg2,borderRadius:4,padding:"6px 12px",minWidth:70}}>
          <div style={{fontSize:10,color:C.text2,marginBottom:2}}>KELLY</div>
          <div style={{fontSize:14,fontWeight:700,color:C.amber}}>{(alert.kelly_frac*100).toFixed(1)}%</div>
        </div>
      </div>
      {sport==="tennis"&&alert.set_probs&&(
        <div style={{display:"flex",gap:6,flexWrap:"wrap"}}>
          {Object.entries(alert.set_probs).map(([k,v])=>(
            <span key={k} style={{fontSize:10,color:C.text2,background:C.bg1,padding:"2px 8px",borderRadius:3}}>{k}: <b style={{color:C.text1}}>{(v*100).toFixed(0)}%</b></span>
          ))}
          <span style={{fontSize:10,color:C.text2,background:C.bg1,padding:"2px 8px",borderRadius:3}}>Games est: <b style={{color:C.text1}}>{alert.total_games_est}</b></span>
        </div>
      )}
      {sport==="basketball"&&(
        <div style={{display:"flex",gap:6,flexWrap:"wrap"}}>
          <span style={{fontSize:10,color:C.text2,background:C.bg1,padding:"2px 8px",borderRadius:3}}>Local: <b style={{color:C.text1}}>{alert.home_pts_est}</b></span>
          <span style={{fontSize:10,color:C.text2,background:C.bg1,padding:"2px 8px",borderRadius:3}}>Visitante: <b style={{color:C.text1}}>{alert.away_pts_est}</b></span>
          <span style={{fontSize:10,color:C.text2,background:C.bg1,padding:"2px 8px",borderRadius:3}}>Total est: <b style={{color:C.blue}}>{alert.total_pts_est}</b></span>
          <span style={{fontSize:10,color:C.text2,background:C.bg1,padding:"2px 8px",borderRadius:3}}>Dif est: <b style={{color:C.amber}}>{alert.point_diff_est>0?"+":""}{alert.point_diff_est}</b></span>
        </div>
      )}
    </div>
  )
}

export default function SportsPanel(){
  const [sport,setSport]=useState("tennis")
  const [tour,setTour]=useState("ATP 2024")
  const [league,setLeague]=useState("NBA")
  const [data,setData]=useState(null)
  const [loading,setLoading]=useState(false)
  const [error,setError]=useState(null)

  async function load(){
    setLoading(true);setError(null);setData(null)
    try{
      const url=sport==="tennis"?`/api/tennis?tour=${encodeURIComponent(tour)}`:`/api/basketball?league=${encodeURIComponent(league)}`
      const res=await fetch(url)
      const json=await res.json()
      if(json.error)throw new Error(json.error)
      setData(json)
    }catch(e){setError(e.message)}finally{setLoading(false)}
  }

  const alerts=data?.alerts||[]
  const alta=alerts.filter(a=>a.confidence==="ALTA")
  const media=alerts.filter(a=>a.confidence==="MEDIA")

  return(
    <div style={{padding:20,display:"flex",flexDirection:"column",gap:16}}>
      <div style={{background:C.bg2,border:`1px solid ${C.border}`,borderRadius:6,padding:16,display:"flex",gap:16,flexWrap:"wrap",alignItems:"flex-end"}}>
        <div style={{display:"flex",flexDirection:"column",gap:6}}>
          <label style={{fontSize:11,color:C.text2,fontFamily:"'JetBrains Mono',monospace",letterSpacing:".08em"}}>DEPORTE</label>
          <div style={{display:"flex",gap:8}}>
            {["tennis","basketball"].map(s=>(
              <button key={s} onClick={()=>{setSport(s);setData(null)}}
                style={{background:sport===s?C.green:C.bg3,color:sport===s?"#0d1117":C.text2,border:`1px solid ${sport===s?C.green:C.border}`,borderRadius:4,padding:"6px 16px",fontWeight:700,fontSize:12,cursor:"pointer",fontFamily:"'JetBrains Mono',monospace"}}>
                {s==="tennis"?"🎾 Tenis":"🏀 Básquet"}
              </button>
            ))}
          </div>
        </div>
        {sport==="tennis"&&(
          <div style={{display:"flex",flexDirection:"column",gap:6}}>
            <label style={{fontSize:11,color:C.text2,fontFamily:"'JetBrains Mono',monospace",letterSpacing:".08em"}}>TOUR</label>
            <select value={tour} onChange={e=>setTour(e.target.value)} style={{background:C.bg3,border:`1px solid ${C.border}`,color:C.text1,borderRadius:4,padding:"6px 10px",fontSize:13}}>
              {["ATP 2024","ATP 2023","WTA 2024"].map(t=><option key={t}>{t}</option>)}
            </select>
          </div>
        )}
        {sport==="basketball"&&(
          <div style={{display:"flex",flexDirection:"column",gap:6}}>
            <label style={{fontSize:11,color:C.text2,fontFamily:"'JetBrains Mono',monospace",letterSpacing:".08em"}}>LIGA</label>
            <select value={league} onChange={e=>setLeague(e.target.value)} style={{background:C.bg3,border:`1px solid ${C.border}`,color:C.text1,borderRadius:4,padding:"6px 10px",fontSize:13}}>
              {["NBA","Euroliga","FIBA"].map(l=><option key={l}>{l}</option>)}
            </select>
          </div>
        )}
        <button onClick={load} disabled={loading} style={{background:loading?C.bg3:C.blue,color:loading?C.text2:"#fff",border:"none",borderRadius:4,padding:"8px 20px",fontWeight:700,fontSize:13,cursor:loading?"not-allowed":"pointer",fontFamily:"'JetBrains Mono',monospace"}}>
          {loading?"Cargando...":"▶ ANALIZAR"}
        </button>
      </div>
      {error&&<div style={{background:C.red+"20",border:`1px solid ${C.red}`,borderRadius:6,padding:14,color:C.red,fontSize:13}}>{error}</div>}
      {loading&&<div style={{background:C.bg2,border:`1px solid ${C.border}`,borderRadius:6,padding:30,textAlign:"center",color:C.text2}}>Analizando {sport==="tennis"?tour:league}...</div>}
      {data&&<>
        <div style={{display:"flex",gap:12,flexWrap:"wrap"}}>
          <div style={{background:C.bg2,border:`1px solid ${C.border}`,borderRadius:6,padding:"14px 20px",flex:1,minWidth:120}}>
            <div style={{fontSize:11,color:C.text2,fontFamily:"'JetBrains Mono',monospace",letterSpacing:".08em"}}>OPORTUNIDADES</div>
            <div style={{fontSize:24,fontWeight:700,color:C.text1,marginTop:4}}>{alerts.length}</div>
          </div>
          <div style={{background:C.bg2,border:`1px solid ${C.green}40`,borderRadius:6,padding:"14px 20px",flex:1,minWidth:120}}>
            <div style={{fontSize:11,color:C.text2,fontFamily:"'JetBrains Mono',monospace",letterSpacing:".08em"}}>CONFIANZA ALTA</div>
            <div style={{fontSize:24,fontWeight:700,color:C.green,marginTop:4}}>{alta.length}</div>
          </div>
          {sport==="tennis"&&<div style={{background:C.bg2,border:`1px solid ${C.border}`,borderRadius:6,padding:"14px 20px",flex:1,minWidth:120}}>
            <div style={{fontSize:11,color:C.text2,fontFamily:"'JetBrains Mono',monospace",letterSpacing:".08em"}}>JUGADORES</div>
            <div style={{fontSize:24,fontWeight:700,color:C.blue,marginTop:4}}>{data.total_players}</div>
          </div>}
          {sport==="basketball"&&<div style={{background:C.bg2,border:`1px solid ${C.border}`,borderRadius:6,padding:"14px 20px",flex:1,minWidth:120}}>
            <div style={{fontSize:11,color:C.text2,fontFamily:"'JetBrains Mono',monospace",letterSpacing:".08em"}}>PTS PROMEDIO</div>
            <div style={{fontSize:24,fontWeight:700,color:C.amber,marginTop:4}}>{data.avg_total_points}</div>
          </div>}
        </div>
        {alta.length>0&&<div>
          <div style={{fontSize:11,color:C.green,fontFamily:"'JetBrains Mono',monospace",letterSpacing:".08em",marginBottom:10}}>CONFIANZA ALTA</div>
          <div style={{display:"flex",flexDirection:"column",gap:8}}>{alta.map((a,i)=><SportCard key={i} alert={a} sport={sport}/>)}</div>
        </div>}
        {media.length>0&&<div>
          <div style={{fontSize:11,color:C.amber,fontFamily:"'JetBrains Mono',monospace",letterSpacing:".08em",margin:"8px 0 10px"  }}>CONFIANZA MEDIA</div>
          <div style={{display:"flex",flexDirection:"column",gap:8}}>{media.map((a,i)=><SportCard key={i} alert={a} sport={sport}/>)}</div>
        </div>}
      </>}
    </div>
  )
}

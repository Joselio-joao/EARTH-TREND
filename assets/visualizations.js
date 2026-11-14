(() => {
  const $ = id => document.getElementById(id);
  let api = localStorage.getItem("earthtrend-api-url") || "";
  let map, cells, trends, lastResult, mapMode = "values";
  const status = (msg, kind) => { const e=$("viz-status"); if(e){e.textContent=msg;e.dataset.kind=kind||"info";} };
  const base = () => api.trim().replace(/\/+$/, "");
  async function get(path, options) {
    if (!base()) throw new Error("Introduz o endereço público do backend.");
    const res = await fetch(base()+path, options || {});
    const data = await res.json().catch(()=>({}));
    if (!res.ok) throw new Error(data.error?.message || data.detail || ("Erro HTTP "+res.status));
    return data;
  }
  function initMap() {
    if (map || !window.L || !$("earthtrend-map")) return;
    map=L.map("earthtrend-map").setView([-12.5,18.5],5);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",{maxZoom:18,attribution:"© OpenStreetMap"}).addTo(map);
    cells=L.layerGroup().addTo(map); trends=L.layerGroup();
  }
  function drawMap(m) {
    initMap(); if(!map || !m || !m.values) return;
    cells.clearLayers(); trends.clearLayers();
    const valid=m.values.flat().filter(Number.isFinite);
    if(!valid.length) return;
    const lo=Number.isFinite(m.min)?m.min:Math.min(...valid), hi=Number.isFinite(m.max)?m.max:Math.max(...valid);
    const dy=m.cell_size_deg?.[0] || 0.1, dx=m.cell_size_deg?.[1] || 0.1;
    m.values.forEach((row,j)=>row.forEach((v,i)=>{
      if(!Number.isFinite(v)) return;
      const t=hi===lo?0.5:(v-lo)/(hi-lo), color="hsl("+(125-115*t)+",66%,46%)";
      L.rectangle([[m.lats[j]-dy/2,m.lons[i]-dx/2],[m.lats[j]+dy/2,m.lons[i]+dx/2]],{
        color:color,weight:0.3,fillColor:color,fillOpacity:0.72
      }).bindPopup(v.toFixed(3)+" "+(m.unit||"")).addTo(cells);
    }));
    if(m.lats.length && m.lons.length) map.fitBounds([[m.lats[0]-dy/2,m.lons[0]-dx/2],[m.lats[m.lats.length-1]+dy/2,m.lons[m.lons.length-1]+dx/2]]);
    const legend=$("map-legend"); if(legend) legend.textContent=(m.statistic||"Média espacial")+" · "+(m.unit||"")+" · "+lo.toFixed(2)+" a "+hi.toFixed(2);
  }
  function drawTrendMap(m) {
    if(!map || !m || !m.slopes_per_year) return;
    trends.clearLayers(); const dy=m.cell_size_deg?.[0]||0.1, dx=m.cell_size_deg?.[1]||0.1;
    m.lats.forEach((lat,j)=>m.lons.forEach((lon,i)=>{
      const slope=m.slopes_per_year[j]?.[i]; if(!Number.isFinite(slope)) return;
      const dir=m.directions[j]?.[i], sig=!!m.significant[j]?.[i];
      const color=dir==="increasing"?"#b34b36":dir==="decreasing"?"#2767a8":"#858b86";
      L.rectangle([[lat-dy/2,lon-dx/2],[lat+dy/2,lon+dx/2]],{
        color:color,weight:0.4,fillColor:color,fillOpacity:sig?0.75:0.2
      }).bindPopup(dir+" · Sen: "+slope.toPrecision(4)+" "+(m.unit_per_year||"")+" · p="+(m.p_values[j][i]??"n/d")).addTo(trends);
    }));
  }
  function chart(r) {
    if(!window.Plotly || !r.series) return;
    const s=r.series, traces=[{x:s.labels,y:s.values,type:"scatter",mode:"lines+markers",name:"Série observada",line:{color:"#315f8c",width:2}}];
    if(Array.isArray(s.trend_line)) traces.push({x:s.labels,y:s.trend_line,type:"scatter",mode:"lines",name:"Tendência de Sen",line:{color:"#bd6a42",dash:"dash",width:2}});
    Plotly.react("earthtrend-chart",traces,{margin:{l:55,r:15,t:15,b:55},paper_bgcolor:"#fff",plot_bgcolor:"#fff",
      xaxis:{title:"Período",gridcolor:"#edf1ed"},yaxis:{title:s.unit||r.unit||"Valor",gridcolor:"#edf1ed"},
      legend:{orientation:"h",y:-0.25},font:{family:"Inter,system-ui,sans-serif",size:11}},{responsive:true,displaylogo:false});
  }
  function render(r) {
    lastResult=r; chart(r); drawMap(r.map);
    if(r.trend_map) drawTrendMap(r.trend_map);
    const t=r.trend||{}, mag=t.magnitude||{}, mk=t.mann_kendall||{};
    const metrics=[["Direção",t.direction_label||t.direction||"Inconclusivo"],
      ["Declive de Sen",Number.isFinite(mag.slope_per_year)?mag.slope_per_year.toPrecision(4)+" "+(mag.unit_per_year||""):"Não estimado"],
      ["Valor-p",Number.isFinite(mk.p_value)?mk.p_value.toFixed(4):"n/d"],["Observações",t.n_observations??"—"]];
    $("trend-metrics").innerHTML=metrics.map(x=>'<div class="viz-metric"><span>'+x[0]+'</span><strong>'+x[1]+'</strong></div>').join("");
    const p=r.provenance||{}, d=r.dataset||{};
    $("viz-provenance").textContent="Fonte: "+(d.name||p.product||"—")+" · Unidade: "+(r.unit||"—")+" · Período: "+(r.period?.analyzed?.first||"—")+" a "+(r.period?.analyzed?.last||"—");
    const notes=[...(r.warnings||[]),...(r.limitations||[])];
    $("viz-warnings").innerHTML=notes.length?notes.map(x=>"<li>"+String(x).replace(/[&<>]/g,"")+"</li>").join(""):"<li>Sem avisos adicionais devolvidos pelo backend.</li>";
    $("result-id").textContent=r.id||"—";
    $("map-mode").disabled=!r.trend_map;
    status(r.status==="inconclusive"?"Análise concluída, mas inconclusiva.":"Análise recebida do backend.",r.status==="inconclusive"?"warning":"success");
  }
  async function catalogues() {
    const ds=await get("/datasets"), rs=await get("/regions");
    $("viz-dataset").innerHTML=(ds.datasets||[]).map(d=>'<option value="'+d.id+'" '+(d.ready?"":"disabled")+'>'+d.name+" — "+(d.ready?"dados prontos":d.status==="available"?"sem ficheiros":"planeado")+"</option>").join("");
    $("viz-region").innerHTML=(rs.regions||[]).map(r=>'<option value="'+r.id+'" '+(r.ready?"":"disabled")+'>'+r.name+(r.approximate?" (aproximada)":"")+"</option>").join("");
    $("catalogue-note").textContent=(ds.datasets||[]).filter(d=>d.ready).length+" dataset(s) com ficheiros · "+(rs.regions||[]).filter(r=>r.ready).length+" região(ões) utilizáveis.";
  }
  async function connect() {
    api=$("viz-api-url").value.trim(); localStorage.setItem("earthtrend-api-url",api);
    try { const h=await get("/health"); status("Backend ligado · versão "+(h.version||"—"),"success"); await catalogues(); }
    catch(e){status(e.message,"error");}
  }
  async function analyze(ev) {
    ev.preventDefault(); const btn=$("run-viz-analysis"); btn.disabled=true; status("A executar análise…");
    try {
      const payload={dataset_id:$("viz-dataset").value,region_id:$("viz-region").value,
        start:$("viz-start").value,end:$("viz-end").value,scale:$("viz-scale").value,
        question:$("viz-question").value||null,include_trend_map:true};
      const r=await get("/analyze",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
      render(r);
    } catch(e){status(e.message,"error");}
    finally{btn.disabled=false;}
  }
  document.addEventListener("DOMContentLoaded",()=>{
    initMap(); $("viz-api-url").value=api;
    $("save-api-url").addEventListener("click",connect);
    $("viz-analysis-form").addEventListener("submit",analyze);
    $("map-mode").addEventListener("click",()=>{
      if(!lastResult?.trend_map) return;
      if(mapMode==="values"){map.removeLayer(cells);trends.addTo(map);mapMode="trend";
        $("map-legend").textContent="Vermelho: aumento · azul: diminuição · cinzento: sem tendência clara; opacidade forte: significativo.";
      } else {map.removeLayer(trends);cells.addTo(map);mapMode="values";drawMap(lastResult.map);}
    });
    if(api) connect(); else status("Introduz o endereço público do backend para carregar os dados.");
    setTimeout(()=>map?.invalidateSize(),250);
  });
})();
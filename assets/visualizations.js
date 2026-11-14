(() => {
  "use strict";
  const DEFAULT_API = "https://earthtrend-ai-api.onrender.com";
  const $ = id => document.getElementById(id);
  let api = localStorage.getItem("earthtrend-api-url") || DEFAULT_API;
  let map, valuesLayer, trendLayer, lastResult, mapMode = "values";

  function status(message, kind = "info") {
    const el = $("viz-status");
    if (el) { el.textContent = message; el.dataset.kind = kind; }
  }
  const base = () => api.trim().replace(/\\/+$/, "");
  async function request(path, options) {
    if (!base()) throw new Error("Endereço do backend não configurado.");
    const response = await fetch(base() + path, options || {});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = data.detail || data.error?.message || ("Erro HTTP " + response.status);
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    return data;
  }
  function initMap() {
    if (map || !window.L || !$("earthtrend-map")) return;
    map = L.map("earthtrend-map").setView([-12.5, 18.5], 5);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18, attribution: "© OpenStreetMap"
    }).addTo(map);
    valuesLayer = L.layerGroup().addTo(map);
    trendLayer = L.layerGroup();
  }
  function drawMap(m) {
    initMap();
    if (!map || !m || !Array.isArray(m.values)) return;
    valuesLayer.clearLayers();
    trendLayer.clearLayers();
    const valid = m.values.flat().filter(Number.isFinite);
    if (!valid.length) return;
    const lo = Number.isFinite(m.min) ? m.min : Math.min(...valid);
    const hi = Number.isFinite(m.max) ? m.max : Math.max(...valid);
    const dy = m.cell_size_deg?.[0] || 0.1;
    const dx = m.cell_size_deg?.[1] || 0.1;
    m.values.forEach((row, j) => row.forEach((value, i) => {
      if (!Number.isFinite(value)) return;
      const ratio = hi === lo ? 0.5 : (value - lo) / (hi - lo);
      const color = "hsl(" + (125 - 115 * ratio) + ",66%,46%)";
      L.rectangle([[m.lats[j] - dy/2, m.lons[i] - dx/2],
                   [m.lats[j] + dy/2, m.lons[i] + dx/2]], {
        color, weight: 0.3, fillColor: color, fillOpacity: 0.72
      }).bindPopup(value.toFixed(3) + " " + (m.unit || "")).addTo(valuesLayer);
    }));
    if (m.lats?.length && m.lons?.length) {
      map.fitBounds([[m.lats[0] - dy/2, m.lons[0] - dx/2],
                     [m.lats[m.lats.length-1] + dy/2, m.lons[m.lons.length-1] + dx/2]]);
    }
    const legend = $("map-legend");
    if (legend) legend.textContent = (m.statistic || "Média espacial") + " · " +
      (m.unit || "") + " · " + lo.toFixed(2) + " a " + hi.toFixed(2);
  }
  function drawTrendMap(m) {
    if (!map || !m || !Array.isArray(m.slopes_per_year)) return;
    trendLayer.clearLayers();
    const dy = m.cell_size_deg?.[0] || 0.1;
    const dx = m.cell_size_deg?.[1] || 0.1;
    m.lats.forEach((lat, j) => m.lons.forEach((lon, i) => {
      const slope = m.slopes_per_year[j]?.[i];
      if (!Number.isFinite(slope)) return;
      const direction = m.directions[j]?.[i] || "inconclusive";
      const significant = !!m.significant[j]?.[i];
      const color = direction === "increasing" ? "#b34b36" :
        direction === "decreasing" ? "#2767a8" : "#858b86";
      const p = m.p_values?.[j]?.[i];
      const popup = direction + " · Sen: " + slope.toPrecision(4) + " " +
        (m.unit_per_year || "") + " · p=" + (Number.isFinite(p) ? p.toFixed(4) : "n/d");
      L.rectangle([[lat-dy/2, lon-dx/2], [lat+dy/2, lon+dx/2]], {
        color, weight: 0.4, fillColor: color, fillOpacity: significant ? 0.75 : 0.2
      }).bindPopup(popup).addTo(trendLayer);
    }));
  }
  function drawChart(result) {
    if (!window.Plotly || !result.series) {
      status("A biblioteca de gráficos não foi carregada.", "error");
      return;
    }
    const series = result.series;
    const traces = [{
      x: series.labels, y: series.values, type: "scatter", mode: "lines+markers",
      name: "Série observada", line: { color: "#315f8c", width: 2 }
    }];
    if (Array.isArray(series.trend_line)) traces.push({
      x: series.labels, y: series.trend_line, type: "scatter", mode: "lines",
      name: "Tendência de Sen", line: { color: "#bd6a42", dash: "dash", width: 2 }
    });
    Plotly.react("earthtrend-chart", traces, {
      margin: { l: 58, r: 15, t: 15, b: 58 }, paper_bgcolor: "#fff",
      plot_bgcolor: "#fff", xaxis: { title: "Período", gridcolor: "#edf1ed" },
      yaxis: { title: series.unit || result.unit || "Valor", gridcolor: "#edf1ed" },
      legend: { orientation: "h", y: -0.25 },
      font: { family: "Inter,system-ui,sans-serif", size: 11 }
    }, { responsive: true, displaylogo: false });
  }
  function renderMetrics(result) {
    const trend = result.trend || {};
    const magnitude = trend.magnitude || {};
    const mk = trend.mann_kendall || {};
    const metrics = [
      ["Direção", trend.direction_label || trend.direction || "Inconclusivo"],
      ["Declive de Sen", Number.isFinite(magnitude.slope_per_year) ?
        magnitude.slope_per_year.toPrecision(4) + " " + (magnitude.unit_per_year || "") : "Não estimado"],
      ["Valor-p (Mann–Kendall)", Number.isFinite(mk.p_value) ? mk.p_value.toFixed(4) : "n/d"],
      ["Observações válidas", trend.n_observations ?? "—"]
    ];
    const root = $("trend-metrics");
    root.replaceChildren(...metrics.map(([label, value]) => {
      const item = document.createElement("div");
      item.className = "viz-metric";
      const name = document.createElement("span");
      name.textContent = label;
      const strong = document.createElement("strong");
      strong.textContent = value;
      item.append(name, strong);
      return item;
    }));
    const ci = $("trend-confidence");
    if (ci) ci.textContent = Number.isFinite(magnitude.ci_low) && Number.isFinite(magnitude.ci_high)
      ? "IC " + (magnitude.ci_level || 0.95) + ": " + magnitude.ci_low.toPrecision(4) +
        " a " + magnitude.ci_high.toPrecision(4) + " " + (magnitude.unit_per_year || "")
      : "Intervalo de confiança não estimado.";
  }
  function render(result) {
    lastResult = result;
    drawChart(result);
    drawMap(result.map);
    if (result.trend_map) drawTrendMap(result.trend_map);
    renderMetrics(result);
    const provenance = result.provenance || {};
    const dataset = result.dataset || {};
    $("viz-provenance").textContent = "Fonte: " + (dataset.name || provenance.product || "—") +
      " · Unidade: " + (result.unit || "—") + " · Período: " +
      (result.period?.analyzed?.first || "—") + " a " + (result.period?.analyzed?.last || "—") +
      " · Região: " + (result.region?.name || "—") +
      (result.region?.approximate ? " (limite aproximado)" : "");
    const notes = [...(result.warnings || []), ...(result.limitations || [])];
    const list = $("viz-warnings");
    list.replaceChildren();
    (notes.length ? notes : ["O backend não devolveu avisos adicionais."]).forEach(note => {
      const li = document.createElement("li");
      li.textContent = String(note);
      list.append(li);
    });
    $("result-id").textContent = result.id || "—";
    $("map-mode").disabled = !result.trend_map;
    status(result.status === "inconclusive" ?
      "Análise concluída, mas inconclusiva. Consulte as limitações." :
      "Análise recebida do backend.", result.status === "inconclusive" ? "warning" : "success");
  }
  function fillSelect(select, entries, kind) {
    select.replaceChildren();
    const ready = entries.filter(item => item.ready);
    if (!ready.length) {
      const option = document.createElement("option");
      option.value = "";
      option.textContent = kind === "dataset" ?
        "Nenhum dataset com ficheiros disponíveis" : "Nenhuma região utilizável";
      select.append(option);
      select.disabled = true;
      return 0;
    }
    ready.forEach(item => {
      const option = document.createElement("option");
      option.value = item.id;
      option.textContent = item.name + (item.approximate ? " (limite aproximado)" : "");
      select.append(option);
    });
    select.disabled = false;
    return ready.length;
  }
  async function loadCatalogues() {
    const [datasetsResponse, regionsResponse] = await Promise.all([
      request("/datasets"), request("/regions")
    ]);
    const datasetCount = fillSelect($("viz-dataset"), datasetsResponse.datasets || [], "dataset");
    const regionCount = fillSelect($("viz-region"), regionsResponse.regions || [], "region");
    $("catalogue-note").textContent = datasetCount + " dataset(s) com ficheiros prontos · " +
      regionCount + " região(ões) utilizáveis. Limites aproximados são assinalados.";
    $("run-viz-analysis").disabled = datasetCount === 0 || regionCount === 0;
  }
  async function connect() {
    api = $("viz-api-url").value.trim();
    localStorage.setItem("earthtrend-api-url", api);
    try {
      const health = await request("/health");
      await loadCatalogues();
      status("Backend ligado · versão " + (health.version || "—") +
        (datasetReadyCount() === 0 ? " · à espera de ficheiros científicos" : ""), "success");
    } catch (error) {
      status(error.message, "error");
    }
  }
  function datasetReadyCount() {
    const select = $("viz-dataset");
    return select.disabled ? 0 : select.options.length;
  }
  async function analyze(event) {
    event.preventDefault();
    const button = $("run-viz-analysis");
    button.disabled = true;
    status("A executar análise científica…");
    try {
      const payload = {
        dataset_id: $("viz-dataset").value,
        region_id: $("viz-region").value,
        start: $("viz-start").value,
        end: $("viz-end").value,
        scale: $("viz-scale").value,
        question: $("viz-question").value || null,
        include_trend_map: true
      };
      const result = await request("/analyze", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      render(result);
    } catch (error) {
      status(error.message, "error");
    } finally {
      button.disabled = datasetReadyCount() === 0 || $("viz-region").disabled;
    }
  }
  document.addEventListener("DOMContentLoaded", () => {
    initMap();
    $("viz-api-url").value = api;
    $("save-api-url").addEventListener("click", connect);
    $("viz-analysis-form").addEventListener("submit", analyze);
    $("map-mode").addEventListener("click", () => {
      if (!lastResult?.trend_map) return;
      if (mapMode === "values") {
        map.removeLayer(valuesLayer);
        trendLayer.addTo(map);
        mapMode = "trend";
        $("map-legend").textContent =
          "Vermelho: aumento · azul: diminuição · cinzento: sem tendência clara. Opacidade forte: significativo.";
      } else {
        map.removeLayer(trendLayer);
        valuesLayer.addTo(map);
        mapMode = "values";
        drawMap(lastResult.map);
      }
    });
    $("viz-start").value = "2015";
    $("viz-end").value = "2025";
    connect();
    window.setTimeout(() => map?.invalidateSize(), 300);
  });
})();

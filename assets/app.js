(() => {
  "use strict";
  const KEY = "earthtrend-state-v2";
  const DEFAULTS = {
    region: "Angola", variable: "Precipitação", period: "2015–2024",
    aggregation: "Anual", method: "Mann–Kendall + declive de Sen",
    question: "", investigations: []
  };
  let saved = {};
  try { saved = JSON.parse(localStorage.getItem(KEY) || "{}") || {}; } catch (_) {}
  const S = { ...DEFAULTS, ...saved };
  const $ = id => document.getElementById(id);
  const save = () => localStorage.setItem(KEY, JSON.stringify(S));
  function toast(message) {
    let el = $("toast");
    if (!el) { el = document.createElement("div"); el.id = "toast"; el.className = "toast"; document.body.append(el); }
    el.textContent = message; el.classList.add("show");
    window.setTimeout(() => el.classList.remove("show"), 2400);
  }
  function render() {
    document.querySelectorAll("[data-bind]").forEach(el => {
      const key = el.dataset.bind;
      const value = S[key];
      el.textContent = value == null || value === "" ? "—" : value;
    });
  }
  function sync() {
    document.querySelectorAll("[data-state]").forEach(el => {
      if (S[el.dataset.state] != null) el.value = S[el.dataset.state];
      el.addEventListener("change", () => {
        S[el.dataset.state] = el.value; save(); render();
      });
    });
  }
  function addInvestigation() {
    const name = $("iname")?.value.trim() || `Análise de ${S.variable} em ${S.region}`;
    const region = $("iregion")?.value || S.region;
    const theme = $("itheme")?.value || S.variable;
    const stage = $("istage")?.value || "Pergunta definida";
    S.investigations = [{ name, region, variable: theme, stage, createdAt: new Date().toISOString() }, ...(S.investigations || [])];
    save(); rows(); toast("Investigação guardada neste dispositivo.");
  }
  function rows() {
    const body = $("investigationRows");
    if (!body) return;
    body.replaceChildren();
    (S.investigations || []).forEach(item => {
      const tr = document.createElement("tr");
      [item.name, item.region, item.variable, item.stage].forEach(value => {
        const td = document.createElement("td"); td.textContent = value || "—"; tr.append(td);
      });
      body.append(tr);
    });
    if (!(S.investigations || []).length) {
      const tr = document.createElement("tr"), td = document.createElement("td");
      td.colSpan = 4; td.textContent = "Ainda não existem investigações guardadas.";
      td.className = "muted"; tr.append(td); body.append(tr);
    }
  }
  function prepare() {
    document.querySelectorAll("[data-state]").forEach(el => { S[el.dataset.state] = el.value; });
    save(); render();
    const note = $("analysis-note");
    if (note) { note.hidden = false; note.textContent = "Configuração guardada. Para calcular resultados, executa uma análise no Trend Lab. Nenhum valor científico foi gerado nesta página."; }
    toast("Configuração guardada; ainda sem análise científica.");
  }
  function exportReport() {
    toast("Executa primeiro uma análise no Trend Lab para obter um relatório com resultados reais.");
  }
  const PREF_KEY = "earthtrend-preferences-v1";
  let P = { language: "pt", mapType: "Relief", chartType: "Linha", compactMode: false };
  try { P = { ...P, ...(JSON.parse(localStorage.getItem(PREF_KEY) || "{}") || {}) }; } catch (_) {}
  const I18N = {
    pt: { "settings.title":"Configurações","settings.subtitle":"Personaliza a forma como investigas o sistema Terra.","settings.language":"Idioma da interface","settings.map":"Tipo de mapa predefinido","settings.chart":"Tipo de gráfico predefinido","settings.save":"Guardar preferências","settings.saved":"Preferências guardadas neste dispositivo.","settings.appearance":"Visualização","settings.compact":"Modo compacto","settings.scientific":"As preferências alteram a apresentação, não os cálculos científicos." },
    en: { "settings.title":"Settings","settings.subtitle":"Personalize how you investigate the Earth system.","settings.language":"Interface language","settings.map":"Default map type","settings.chart":"Default chart type","settings.save":"Save preferences","settings.saved":"Preferences saved on this device.","settings.appearance":"Visualization","settings.compact":"Compact mode","settings.scientific":"Preferences change presentation, not scientific calculations." }
  };
  function translateNavigation() {
    const en = P.language === "en";
    const labels = { "index.html":en?"Overview":"Visão geral","explore.html":en?"Explore Earth":"Explorar a Terra","trend-lab.html":en?"Trend Lab":"Laboratório","data-library.html":en?"Data Library":"Biblioteca de dados","investigate.html":en?"Investigations":"Investigações","methodology.html":en?"Methodology":"Metodologia","about.html":en?"About":"Sobre","settings.html":en?"Settings":"Configurações" };
    document.querySelectorAll(".navlink").forEach(a => {
      const label = labels[a.getAttribute("href")]; if (!label) return;
      const icon = a.querySelector(".ico")?.textContent || "";
      a.replaceChildren();
      const span = document.createElement("span"); span.className = "ico"; span.textContent = icon;
      a.append(span, document.createTextNode(label));
    });
  }
  function savePrefs() {
    localStorage.setItem(PREF_KEY, JSON.stringify(P));
    document.documentElement.lang = P.language === "en" ? "en" : "pt-PT";
    document.body.classList.toggle("compact-mode", P.compactMode === true || P.compactMode === "true");
    document.querySelectorAll("[data-pref]").forEach(el => { if (P[el.dataset.pref] != null) el.value = P[el.dataset.pref]; });
    document.querySelectorAll("[data-i18n]").forEach(el => {
      const value = I18N[P.language]?.[el.dataset.i18n] || I18N.pt[el.dataset.i18n];
      if (value) el.textContent = value;
    });
    translateNavigation();
  }
  function setupSettings() {
    document.querySelectorAll("[data-pref]").forEach(el => {
      el.value = P[el.dataset.pref] ?? el.value;
      el.addEventListener("change", () => {
        P[el.dataset.pref] = el.type === "checkbox" ? el.checked : el.value; savePrefs();
      });
    });
    document.querySelectorAll('[data-action="save-preferences"]').forEach(button => button.addEventListener("click", () => {
      document.querySelectorAll("[data-pref]").forEach(el => { P[el.dataset.pref] = el.type === "checkbox" ? el.checked : el.value; });
      savePrefs(); toast(I18N[P.language]?.["settings.saved"] || I18N.pt["settings.saved"]);
    }));
    savePrefs();
  }
  document.addEventListener("DOMContentLoaded", () => {
    sync(); render(); rows(); setupSettings();
    document.querySelectorAll('[data-action="prepare"]').forEach(button => button.addEventListener("click", prepare));
    document.querySelectorAll('[data-action="add-investigation"]').forEach(button => button.addEventListener("click", addInvestigation));
    document.querySelectorAll('[data-action="export"]').forEach(button => button.addEventListener("click", exportReport));
    document.querySelectorAll('[data-action="print"]').forEach(button => button.addEventListener("click", () => window.print()));
    const region = $("region");
    if (region) {
      region.value = S.region;
      region.addEventListener("change", () => { S.region = region.value; save(); render(); });
    }
  });
  window.addInvestigation = addInvestigation;
})();
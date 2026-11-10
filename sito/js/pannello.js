/* Pannelli riservati (/statistiche, /sistema): testata, periodo, formati, tabelle e grafici in comune.
   Il periodo sta nell'indirizzo (?dal=…&al=…), così passa da un pannello all'altro e resta dopo un ricarico. */
(function () {
  const P = (window.P = {});
  const $ = (P.$ = (s, r = document) => r.querySelector(s));
  P.esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  P.num = (n, c = 0) => Number(n || 0).toLocaleString("it-IT", { maximumFractionDigits: c, minimumFractionDigits: c });
  P.usd = (n, c = 2) => Number(n || 0).toLocaleString("it-IT", { style: "currency", currency: "USD", currencyDisplay: "narrowSymbol", minimumFractionDigits: c, maximumFractionDigits: c });
  P.gb = (b) => `${P.num(b / 1e9, 1)} GB`;
  P.data = (d, anno) => d ? new Date(String(d).length === 10 ? d + "T12:00:00" : d).toLocaleDateString("it-IT", { day: "numeric", month: "short", ...(anno ? { year: "numeric" } : {}) }) : "–";
  P.quando = (t) => t ? new Date(typeof t === "number" ? t * 1000 : t).toLocaleString("it-IT", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "–";
  P.durata = (s) => s == null ? "–" : s < 90 ? `${Math.round(s)} s` : s < 5400 ? `${Math.round(s / 60)} min` : `${P.num(s / 3600, 1)} ore`;
  const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  const piu = (s, n) => { const d = new Date(s + "T12:00:00"); d.setDate(d.getDate() + n); return iso(d); };
  P.oggi = () => iso(new Date());
  P.giorni = (dal, al) => { const c = []; for (let g = dal; g <= al; g = piu(g, 1)) c.push(g); return c; };

  /* ---------- testata: marchio, pannelli, tema, esci ---------- */
  P.testata = (attiva) => {
    const el = $("[data-testata]"); if (!el) return;
    const q = location.search;
    el.className = "testata";
    el.innerHTML = `<div class="barra"><a class="marchio" href="/"><svg viewBox="15 15 194 153" aria-hidden="true"><path d="M 35.91 139.73 A 81 81 0 1 1 188.09 139.73" fill="none" stroke="currentColor" stroke-width="32" stroke-linecap="round"/><circle cx="112" cy="146" r="22"/></svg>ParliamentRAG</a>
      <nav class="nav" aria-label="Pannelli">${[["statistiche", "Statistiche"], ["sistema", "Sistema"]].map(([k, t]) => `<a href="/${k}${q}"${k === attiva ? ' aria-current="page"' : ""}>${t}</a>`).join("")}</nav>
      <div class="pn-destra barra__dx"><button type="button" id="pn-tema" aria-label="Cambia tema">${document.documentElement.dataset.tono === "scuro" ? "Chiaro" : "Scuro"}</button><a href="/esci">Esci</a></div></div>`;
    $("#pn-tema").onclick = () => {
      const scuro = document.documentElement.dataset.tono !== "scuro", r = document.documentElement;
      if (scuro) { r.dataset.scelta = "netto"; r.dataset.tono = "scuro"; } else { r.dataset.scelta = "chiaro"; delete r.dataset.tono; }
      try { localStorage.setItem("parliamentrag-scelta", scuro ? "scuro" : "chiaro"); } catch { /* resta per questa pagina */ }
      $("#pn-tema").textContent = scuro ? "Chiaro" : "Scuro";
      P.ridisegna && P.ridisegna();
    };
  };

  /* ---------- periodo ---------- */
  const RAPIDI = [["oggi", "Oggi", 0, 0], ["ieri", "Ieri", 1, 1], ["7", "7 giorni", 6, 0], ["30", "30 giorni", 29, 0], ["90", "90 giorni", 89, 0], ["365", "12 mesi", 364, 0]];
  P.periodo = (el, predefinito, cambia) => {
    const q = new URLSearchParams(location.search), oggi = P.oggi();
    let al = q.get("al") || oggi, dal = q.get("dal") || piu(al, -(predefinito - 1));
    el.className = "periodo";
    el.innerHTML = `<div class="periodo__rapidi" role="group" aria-label="Periodo">${RAPIDI.map(([k, t]) => `<button type="button" data-k="${k}">${t}</button>`).join("")}</div>
      <div class="periodo__date"><label><span class="vh">Dal</span><input type="date" id="pn-dal" max="${oggi}"></label><span>–</span><label><span class="vh">Al</span><input type="date" id="pn-al" max="${oggi}"></label></div>`;
    const segna = () => {
      $("#pn-dal").value = dal; $("#pn-al").value = al;
      el.querySelectorAll("[data-k]").forEach((b) => { const r = RAPIDI.find((x) => x[0] === b.dataset.k); b.setAttribute("aria-pressed", String(piu(oggi, -r[2]) === dal && piu(oggi, -r[3]) === al)); });
      const u = new URLSearchParams({ dal, al }); history.replaceState(null, "", `${location.pathname}?${u}`);
      document.querySelectorAll(".nav a").forEach((a) => { a.href = `${a.pathname}?${u}`; });
    };
    const vai = () => { segna(); cambia(dal, al); };
    el.querySelectorAll("[data-k]").forEach((b) => b.addEventListener("click", () => { const r = RAPIDI.find((x) => x[0] === b.dataset.k); dal = piu(oggi, -r[2]); al = piu(oggi, -r[3]); vai(); }));
    $("#pn-dal").addEventListener("change", (e) => { if (!e.target.value) return; dal = e.target.value; if (dal > al) al = dal; vai(); });
    $("#pn-al").addEventListener("change", (e) => { if (!e.target.value) return; al = e.target.value; if (al < dal) dal = al; vai(); });
    vai();
    return { get: () => ({ dal, al }) };
  };
  // «dal 3 al 5 nov», «oggi», «il 4 nov»
  P.descrivi = (dal, al) => dal === al ? (al === P.oggi() ? "oggi" : `il ${P.data(al, true)}`) : `dal ${P.data(dal)} al ${P.data(al, true)}`;

  /* ---------- dati: chi ha perso l'accesso torna alla pagina di login ---------- */
  P.leggi = async (url) => {
    const r = await fetch(url, { credentials: "same-origin" });
    if (r.status === 401) { location.href = `/accedi?dopo=${encodeURIComponent(location.pathname)}`; throw new Error("accesso scaduto"); }
    if (!r.ok) throw new Error(String(r.status));
    return r.json();
  };

  /* ---------- scheletri: la forma di ciò che sta per arrivare, mentre i dati si caricano ---------- */
  // P.scheletro({ "#cifre": ["cifre", 6], "#giri": ["tabella", 5], "#db": ["righe", 4], "#macchina": ["barre", 3] })
  const riga = (classi = "") => `<i class="skel ${classi}"></i>`;
  const FORME = {
    cifre: (n) => `<div class="cifra pn-sk-cifra">${riga("pn-sk-etichetta")}${riga("pn-sk-numero")}${riga("pn-sk-nota")}</div>`.repeat(n),
    avvisi: (n) => `<li class="pn-sk-avviso">${riga()}</li>`.repeat(n),
    righe: (n) => `<div class="carica">${"<i></i>".repeat(n)}</div>`,
    barre: (n) => `<div class="pn-sk-barra">${riga("pn-sk-etichetta")}${riga("pn-sk-linea")}</div>`.repeat(n),
    tabella: (n) => `<div class="pn-sk-tab">${`<div>${riga().repeat(4)}</div>`.repeat(n)}</div>`,
    grafico: () => riga("pn-sk-grafico"),
  };
  P.scheletro = (dove) => {
    for (const [sel, [forma, n]] of Object.entries(dove)) {
      const el = P.$(sel); if (!el) continue;
      el.innerHTML = FORME[forma](n || 3); el.dataset.scheletro = "1"; el.setAttribute("aria-hidden", "true");
    }
    document.querySelector("main")?.setAttribute("aria-busy", "true");
  };
  // a dati arrivati ogni blocco si ridisegna da solo: qui si toglie il segno; con `svuota` (errore) si tolgono anche le forme
  P.fineScheletro = (svuota) => {
    document.querySelectorAll("[data-scheletro]").forEach((el) => { if (svuota) el.innerHTML = ""; delete el.dataset.scheletro; el.removeAttribute("aria-hidden"); });
    document.querySelector("main")?.removeAttribute("aria-busy");
  };

  /* ---------- tabelle ---------- */
  // tab([["Passo"], ["Durata", "n"], ["Note", "lungo"]], righe di celle già in HTML)
  // oltre PER_PAGINA righe si impagina: nel documento c'è solo la pagina aperta, e il ridisegno ogni minuto non la cambia
  const PER_PAGINA = 10, pagine = new Map();
  const tabella = (testa, righe) => `<div class="scorri"><table><thead><tr>${testa.map(([t, c]) => `<th class="${c || ""}">${t}</th>`).join("")}</tr></thead><tbody>${righe.map((r) => `<tr>${r.map((v, i) => `<td class="${testa[i][1] || ""}">${v}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
  const pagina = (t) => {
    const totale = Math.ceil(t.righe.length / PER_PAGINA);
    t.n = Math.min(t.n, totale - 1);
    return tabella(t.testa, t.righe.slice(t.n * PER_PAGINA, (t.n + 1) * PER_PAGINA))
      + `<nav class="pagine" aria-label="Pagine della tabella"><button class="mostra" data-vai="-1"${t.n ? "" : " disabled"}>Precedenti</button>`
      + `<span>Pagina ${t.n + 1} di ${totale} · ${t.righe.length} righe</span><button class="mostra" data-vai="1"${t.n < totale - 1 ? "" : " disabled"}>Successive</button></nav>`;
  };
  P.tab = (testa, righe, vuoto = "Nessun dato nel periodo.") => {
    if (!righe.length) return `<p class="vuoto">${vuoto}</p>`;
    if (righe.length <= PER_PAGINA) return tabella(testa, righe);
    const chiave = `${testa.map(([t]) => t).join("|")}|${righe.length}`;     // cambia col periodo: si riparte dalla prima pagina
    const t = pagine.get(chiave) || { n: 0 };
    pagine.set(chiave, Object.assign(t, { testa, righe }));
    return `<div data-tabella="${P.esc(chiave)}">${pagina(t)}</div>`;
  };
  document.addEventListener("click", (e) => {
    const b = e.target.closest("[data-vai]"), box = b?.closest("[data-tabella]"), t = box && pagine.get(box.dataset.tabella);
    if (!t) return;
    t.n += Number(b.dataset.vai);
    box.innerHTML = pagina(t);
    box.querySelector(`[data-vai="${b.dataset.vai}"]:not([disabled])`)?.focus();
  });
  // classifica con la barra nella prima colonna: colonne = [[chiave, titolo], …], la prima fa la barra
  P.classifica = (el, righe, colonne, nome = (v) => v) => {
    if (!righe || !righe.length) { el.innerHTML = '<p class="vuoto">Nessun dato nel periodo.</p>'; return; }
    const max = Math.max(...righe.map((r) => r[colonne[0][0]])) || 1;
    el.innerHTML = `<table><thead><tr><th></th>${colonne.map(([, t]) => `<th class="n">${t}</th>`).join("")}</tr></thead><tbody>${righe.map((r) =>
      `<tr><td class="voce" title="${P.esc(nome(r.voce))}"><span style="width:${(100 * r[colonne[0][0]] / max).toFixed(1)}%"></span><em>${P.esc(nome(r.voce))}</em></td>${colonne.map(([k]) => `<td class="n">${P.num(r[k])}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
  };
  P.stato = (s, t) => `<span class="stato ${s}">${P.esc(t)}</span>`;

  /* ---------- grafico a barre ---------- */
  // colonne: [{k, etichetta, titolo}]; serie: [{nome, colore, v: (k) => numero, punto?}] (le barre si impilano, i punti no);
  // formato: dei numeri sull'asse e nel fumetto
  const fumetto = document.createElement("div"); fumetto.className = "fumetto"; fumetto.hidden = true;
  document.addEventListener("DOMContentLoaded", () => document.body.appendChild(fumetto));
  P.barre = (el, colonne, serie, formato = P.num) => {
    const svg = el.querySelector("svg"), W = svg.clientWidth || 900, H = svg.clientHeight || 240;
    const P0 = { l: 52, r: 8, t: 12, b: 26 }, barre = serie.filter((s) => !s.punto), punti = serie.filter((s) => s.punto);
    const tot = (k) => barre.reduce((a, s) => a + (s.v(k) || 0), 0);
    let max = Math.max(...colonne.map((c) => Math.max(tot(c.k), ...punti.map((s) => s.v(c.k) || 0))), 0);
    let passoY = (() => { const g = max / 4 || 1, e = 10 ** Math.floor(Math.log10(g)), f = g / e; return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * e; })();
    if (formato === P.num) passoY = Math.max(1, Math.round(passoY));   // si contano persone e domande: niente mezzi
    max = Math.max(passoY, Math.ceil(max / passoY) * passoY);
    const lw = (W - P0.l - P0.r) / Math.max(1, colonne.length), x = (i) => P0.l + i * lw, y = (v) => H - P0.b - v * (H - P0.t - P0.b) / max;
    const bw = Math.max(1.5, Math.min(40, lw * .68));
    let s = "";
    for (let v = 0; v <= max + 1e-9; v += passoY) s += `<line class="${v ? "griglia-y" : "asse"}" x1="${P0.l}" x2="${W - P0.r}" y1="${y(v)}" y2="${y(v)}"/><text x="${P0.l - 8}" y="${y(v) + 4}" text-anchor="end">${formato(v)}</text>`;
    colonne.forEach((c, i) => {
      let base = 0, g = `<rect class="sfondo" x="${x(i)}" y="${P0.t}" width="${lw}" height="${H - P0.t - P0.b}" fill="transparent"/>`;
      for (const b of barre) { const v = b.v(c.k) || 0; if (v) g += `<rect x="${x(i) + (lw - bw) / 2}" y="${y(base + v)}" width="${bw}" height="${Math.max(.5, y(base) - y(base + v))}" rx="2" fill="${b.colore}"/>`; base += v; }
      for (const p of punti) { const v = p.v(c.k); if (v) g += `<circle cx="${x(i) + lw / 2}" cy="${y(v)}" r="3.5" fill="${p.colore}" stroke="var(--sup)" stroke-width="1.5"/>`; }
      s += `<g class="col" data-i="${i}">${g}</g>`;
    });
    const ogni = Math.ceil(colonne.length / Math.max(2, Math.floor((W - P0.l) / 64)));
    colonne.forEach((c, i) => { if (i % ogni === 0) s += `<text x="${x(i) + lw / 2}" y="${H - 8}" text-anchor="middle">${P.esc(c.etichetta)}</text>`; });
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`); svg.innerHTML = s;
    svg.onmousemove = (ev) => {
      const g = ev.target.closest(".col"); if (!g) { fumetto.hidden = true; return; }
      const c = colonne[+g.dataset.i];
      fumetto.innerHTML = `<b>${P.esc(c.titolo || c.etichetta)}</b><br>${serie.map((s) => `${P.esc(s.nome)}: ${formato(s.v(c.k) || 0)}`).join("<br>")}`;
      fumetto.hidden = false;
      const fx = Math.min(ev.clientX + 14, innerWidth - fumetto.offsetWidth - 8);
      fumetto.style.left = `${fx}px`; fumetto.style.top = `${Math.max(8, ev.clientY - fumetto.offsetHeight - 12)}px`;
    };
    svg.onmouseleave = () => { fumetto.hidden = true; };
  };
  P.legenda = (serie) => `<div class="pn-legenda">${serie.map((s) => `<span><i class="${s.punto ? "punto" : ""}" style="background:${s.colore}"></i>${P.esc(s.nome)}</span>`).join("")}</div>`;
})();

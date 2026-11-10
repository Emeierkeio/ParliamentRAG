/* Dossier del tema (card 284): sotto le posizioni dei gruppi del fascicolo, le sezioni tecniche da /api/dossier
   (emendamenti presentati e com'è finita, atti, chi ci lavora, in arrivo), e l'esportazione in PDF di un turno della
   chat: copertina con logo, indice, una sezione per pagina, contatti in ogni pagina, nota sul metodo. Il PDF lo fa il
   browser («Salva come PDF») da una pagina di stampa: niente librerie. */
(function () {
  const e = B.esc;
  const D = (window.DOSSIER = {});
  const LOGO = '<svg viewBox="15 15 194 153" aria-hidden="true"><path d="M 35.91 139.73 A 81 81 0 1 1 188.09 139.73" fill="none" stroke="currentColor" stroke-width="32" stroke-linecap="round"/><circle cx="112" cy="146" r="22" fill="currentColor"/></svg>';
  const MESI = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"];
  const data = (d) => { if (!d) return ""; const x = String(d).slice(0, 10).split("-"); return `${+x[2]} ${MESI[+x[1] - 1]} ${x[0]}`; };
  const classe = (x) => (/^approvato/.test(x) ? "ok" : x === "respinto" ? "no" : "neutro");

  /* ---------- sezioni tecniche sotto il fascicolo ---------- */
  D.sezioni = async (t, tema, blocco) => {
    let d;
    try { d = await fetch("/api/dossier", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ tema: tema.slice(0, 300) }) }).then((r) => (r.ok ? r.json() : null)); }
    catch { d = null; }
    if (!d) return;
    const em = d.emendamenti;
    if (em.elenco.length) blocco(t, "emendamenti", TT("Emendamenti sul tema", "Amendments on the topic"), B.info(TT("I più vicini al tema per significato, in tutta la legislatura. L'esito viene dalla fonte indicata; «non pubblicato» non vuol dire respinto.", "The closest to the topic by meaning, across the legislature. The outcome comes from the stated source; «not published» does not mean rejected.")),
      `<p class="dos-sotto">${Object.entries(em.per_esito).map(([k, n]) => `<span class="dos-chip">${e(TR(k))} <b>${n}</b></span>`).join("")}</p>
       <ul class="lista dos-em">${em.elenco.map((x) => `<li><span class="meta">${e(x.numero)} · ${e(x.sigla_atto)} · ${e(x.sede)}${x.data ? ` · ${data(x.data)}` : ""} · <span class="dos-es dos-es--${classe(x.esito)}">${e(TR(x.etichetta))}</span></span>
         <span>${e(B.taglia(x.testo.replace(/\s+/g, " "), 220))}</span>
         <span class="dos-firme">${e(x.firmatari.filter((f) => f.primo).map((f) => `${f.nome}${f.gruppo ? ` (${f.gruppo})` : ""}`).join(", ") || x.gruppi.join(", "))}${x.link_atto ? ` · <a href="${e(x.link_atto)}" target="_blank" rel="noopener">${TT("scheda dell'atto", "bill page")}</a>` : ""}</span></li>`).join("")}</ul>`);
    const chi = d.chi_ci_lavora;
    if (chi.gruppi.length) blocco(t, "chi", TT("Chi ci lavora", "Who works on it"), B.info(TT("Primi firmatari degli emendamenti qui sopra: un dato pubblico sul lavoro parlamentare.", "First signatories of the amendments above: public data on parliamentary work.")),
      `<table class="dos-tab"><thead><tr><th>${TT("Gruppo", "Group")}</th><th>${TT("Emendamenti", "Amendments")}</th><th>${TT("Approvati", "Adopted")}</th></tr></thead><tbody>${chi.gruppi.map((g) => `<tr><td>${e(g.gruppo)}</td><td>${g.presentati}</td><td>${g.approvati}</td></tr>`).join("")}</tbody></table>
       ${chi.persone.length ? `<ul class="lista">${chi.persone.map((p) => `<li><span><b>${e(p.nome)}</b> · ${e(p.gruppo)}</span><span class="meta">${p.presentati} ${TT("presentati", "tabled")} · ${p.approvati} ${TT("approvati", "adopted")}</span></li>`).join("")}</ul>` : ""}`);
    const arr = d.in_arrivo;
    blocco(t, "arrivo", TT("In arrivo", "Coming up"), "",
      arr.termini.length || arr.audizioni.length
        ? `${arr.termini.length ? `<h4>${TT("Termini per gli emendamenti", "Amendment deadlines")}</h4><ul class="lista">${arr.termini.map((x) => `<li><span class="meta">${data(x.scadenza)}${x.ora ? `, ${String(x.ora).slice(0, 5)}` : ""} · ${e(x.organo || "")}</span><span>${e(x.frase)}</span></li>`).join("")}</ul>` : ""}
           ${arr.audizioni.length ? `<h4>${TT("Audizioni sugli atti del tema", "Hearings on the topic's bills")}</h4><ul class="lista">${arr.audizioni.map((x) => `<li><span class="meta">${data(x.data)} · ${e(x.organo || "")}</span><span>${e(x.chi)}</span></li>`).join("")}</ul>` : ""}`
        : `<p class="dos-sotto">${TT("Nessun termine aperto né audizione recente sugli atti trovati.", "No open deadline or recent hearing on the bills found.")}</p>`);
    if (d.atti.length) blocco(t, "atti", TT("Atti sul tema", "Bills and acts on the topic"), "",
      `<ul class="lista">${d.atti.map((a) => `<li><span class="meta">${e(a.ramo === "senato" ? "Senato" : "Camera")}${a.data ? ` · ${data(a.data)}` : ""}</span><span>${a.url ? `<a href="${e(a.url)}" target="_blank" rel="noopener">${e(B.taglia(a.titolo, 200))}</a>` : e(B.taglia(a.titolo, 200))}</span></li>`).join("")}</ul>`);
  };

  /* ---------- PDF ---------- */
  const STAMPA_CSS = `@page{size:A4;margin:18mm 16mm 22mm;
      @bottom-left{content:"ParliamentRAG · www.parliamentrag.it · contatti@parliamentrag.it";font:8pt "Schibsted Grotesk",Arial,sans-serif;color:#666b79}
      @bottom-right{content:counter(page) " / " counter(pages);font:8pt "Schibsted Grotesk",Arial,sans-serif;color:#666b79}}
    @page:first{margin:0;@bottom-left{content:none}@bottom-right{content:none}}
    *{box-sizing:border-box}body{margin:0;font:400 10.5pt/1.55 "Schibsted Grotesk",Arial,sans-serif;color:#14161d;-webkit-print-color-adjust:exact;print-color-adjust:exact}
    a{color:#2a4bd7;text-decoration:none}
    .copertina{position:relative;overflow:hidden;width:210mm;height:296mm;padding:20mm 18mm 18mm;background:#14161d;color:#fff;display:flex;flex-direction:column;page-break-after:always}
    .copertina>*{position:relative}.copertina>div:nth-of-type(2){margin-top:46mm}.copertina .contatti{margin-top:auto}
    .copertina .aula{position:absolute;right:-30mm;bottom:36mm;width:180mm;opacity:.9}
    .marchio{display:flex;align-items:center;gap:10px;font:600 16pt "Geist",Arial,sans-serif;letter-spacing:-.035em}
    .marchio svg{width:30px;height:22px}
    .copertina h1{font-size:40pt;line-height:1.04;letter-spacing:-.035em;margin:0 0 6mm;font-weight:600;max-width:165mm}
    .copertina h1.lungo{font-size:26pt;line-height:1.12}
    .copertina .temi{font-size:14pt;line-height:1.4;color:#7AA6D2;margin:0 0 8mm;max-width:160mm;font-weight:500}
    .copertina .sotto{font-size:10.5pt;color:#d4d4d8;max-width:140mm}
    .copertina .tag{display:inline-block;font-size:9pt;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:#9b9ba4;margin-bottom:7mm}
    .contatti{font-size:9.5pt;color:#d4d4d8;border-top:1px solid rgba(255,255,255,.24);padding-top:5mm;display:grid;gap:1mm}
    .contatti b{color:#fff}
    .indice{page-break-after:always}.indice h2,.sez h2{font-size:15pt;letter-spacing:-.02em;margin:0 0 6mm;font-weight:600}
    .indice ol{padding-left:9mm;font-size:11pt;line-height:2}
    .sez{page-break-before:always}.sez:first-of-type{page-break-before:auto}
    .sez h3{display:none}.sez h4{font-size:11pt;margin:5mm 0 2mm}
    .sez ul.lista{list-style:none;padding:0;margin:0}.sez .lista>li{padding:2.5mm 0;border-bottom:1px solid #e4e6eb;display:grid;gap:.8mm;break-inside:avoid}
    .sez .prosa li{margin:0 0 1.5mm}
    .meta,.dos-firme,.dos-sotto{font-size:9pt;color:#666b79}
    .dos-chip{display:inline-block;border:1px solid #cdd1da;border-radius:99px;padding:.5mm 2.5mm;margin:0 1.5mm 1.5mm 0;font-size:9pt}
    .dos-es--ok{color:#1d6b4a;font-weight:600}.dos-es--no{color:#a52a14;font-weight:600}
    table{border-collapse:collapse;width:100%;font-size:9.5pt;margin-bottom:4mm}th,td{border-bottom:1px solid #e4e6eb;padding:1.5mm 2mm;text-align:left}th{font-weight:600;color:#3b3f4b}
    blockquote,q{color:#14161d}
    .metodo{page-break-before:always;font-size:9.5pt;color:#3b3f4b}.metodo h2{font-size:13pt;color:#14161d}
    button,.azioni,.avviso-r,.dx,.info,svg.ic,.indice-r,.indice-g,nav,.sei-passi,details.come{display:none!important}`;

  // un emiciclo di punti per la copertina, nei colori del sito
  const AULA = (() => {
    const col = ["#7AA6D2", "#ffffff", "#2D5F8F", "#9b9ba4", "#6cc49a", "#e2ae4c", "#ee8a73"];
    let p = "", k = 0;
    for (let r = 0; r < 8; r++) {
      const R = 46 + r * 7, n = Math.round(R * 0.62);
      for (let i = 0; i <= n; i++) {
        const a = Math.PI - (Math.PI * i) / n, x = 100 + R * Math.cos(a), y = 100 - R * Math.sin(a);
        const c = col[(i * 7 + r * 3 + (k++ % 5)) % col.length];
        p += `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="2.3" fill="${c}" fill-opacity="${c === "#ffffff" ? .22 : .7}"/>`;
      }
    }
    return `<svg class="aula" viewBox="0 0 200 104" aria-hidden="true">${p}</svg>`;
  })();

  D.pdf = (el) => {
    const q = (el.querySelector(".turno__dom") || {}).textContent || "Dossier";
    // «Dossier su Acme Bevande, temi: …; associazioni: ….» → titolo il soggetto, sottotitolo i temi scelti
    const m = q.match(/^(?:Dossier su|Dossier on) (.+?)(?:, (?:temi|topics): (.+?))?(?:; (?:associazioni|associations): (.+?))?\. /);
    const titolo = m ? m[1] : q, temi = m ? [m[2], m[3]].filter(Boolean).join(", ").split(/, /).join(" · ") : "";
    const oggi = new Date().toLocaleDateString(window.LANG === "en" ? "en-GB" : "it-IT", { day: "numeric", month: "long", year: "numeric" });
    const sezioni = [...el.querySelectorAll("[data-blocco]")].filter((b) => !b.hidden && b.textContent.trim())
      .map((b) => ({ titolo: b.dataset.blocco === "risposta" ? TT("Posizioni e risposta", "Positions and answer") : ((b.querySelector("h3") || {}).firstChild || {}).textContent || "", html: b.innerHTML }));
    const html = `<!doctype html><html lang="${window.LANG || "it"}"><head><meta charset="utf-8"><title>${e(titolo)} · ParliamentRAG</title>
      <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Geist:wght@600&family=Schibsted+Grotesk:wght@400;500;600&display=swap"><style>${STAMPA_CSS}</style></head><body>
      <section class="copertina"><div class="marchio">${LOGO}ParliamentRAG</div>
        ${AULA}<div><span class="tag">${TT("Dossier", "Dossier")}</span><h1${titolo.length > 60 ? ' class="lungo"' : ""}>${e(titolo)}</h1>${temi ? `<p class="temi">${e(temi)}</p>` : ""}<p class="sotto">${TT(`Dati ufficiali di Camera e Senato, XIX legislatura, aggiornati al ${oggi}. Ogni citazione è copiata dal resoconto e ha il link alla seduta.`, `Official data of the Italian Chamber and Senate, 19th legislature, as of ${oggi}. Every quote is copied from the record and links to the sitting.`)}</p></div>
        <div class="contatti"><b>ParliamentRAG</b><span>${TT("Progetto di ricerca dell'Università di Milano-Bicocca. Non è un servizio ufficiale del Parlamento.", "Research project of the University of Milano-Bicocca. Not an official service of Parliament.")}</span><span>www.parliamentrag.it · contatti@parliamentrag.it</span></div></section>
      <section class="indice"><h2>${TT("Indice", "Contents")}</h2><ol>${sezioni.map((s) => `<li>${e(s.titolo)}</li>`).join("")}<li>${TT("Metodo e fonti", "Method and sources")}</li></ol></section>
      ${sezioni.map((s) => `<section class="sez"><h2>${e(s.titolo)}</h2>${s.html}</section>`).join("")}
      <section class="metodo"><h2>${TT("Metodo e fonti", "Method and sources")}</h2>
        <p>${TT("ParliamentRAG organizza i dati del Parlamento per un accesso facile e verificabile. Le risposte rispettano tre garanzie, controllate da un programma prima di mostrarle: tutti i gruppi sono considerati (il Gruppo Misto per componente); per ogni gruppo parla chi segue il tema, secondo criteri pubblici; ogni citazione è copiata parola per parola dal resoconto.", "ParliamentRAG organises the data of the Italian Parliament for easy and verifiable access. Answers meet three guarantees, checked by a program before they are shown: every group is considered (the Mixed Group by component); for each group the member who follows the topic speaks, by public criteria; every quote is copied word for word from the record.")}</p>
        <p>${TT("Fonti: dati.camera.it, dati.senato.it, resoconti stenografici e sommari delle commissioni, schede degli atti. Gli esiti degli emendamenti vengono dai file di Camera e Senato, dai voti elettronici dell'Aula o dalla regola della fiducia; «non pubblicato» vuol dire che nessuna fonte lo dice. Un modello di AI scrive il testo e può sbagliare: fanno fede le fonti linkate.", "Sources: dati.camera.it, dati.senato.it, verbatim records and committee summaries, bill pages. Amendment outcomes come from the Chamber and Senate files, the floor's electronic votes or the confidence-vote rule; «not published» means no source states it. An AI model writes the text and can be wrong: the linked sources prevail.")}</p>
        <p>www.parliamentrag.it · contatti@parliamentrag.it</p></section>
      <script>document.fonts.ready.then(()=>setTimeout(()=>{print()},300));<\/script></body></html>`;
    const w = window.open("", "_blank");
    if (w) { w.document.open(); w.document.write(html); w.document.close(); return; }
    // finestre bloccate: si stampa da un riquadro nascosto
    const f = document.createElement("iframe"); f.style.cssText = "position:fixed;width:0;height:0;border:0;right:0;bottom:0";
    document.body.appendChild(f); f.contentDocument.open(); f.contentDocument.write(html); f.contentDocument.close();
    setTimeout(() => f.remove(), 60000);
  };
  document.addEventListener("click", (ev) => { const b = ev.target.closest("[data-pdf]"); if (!b) return; const el = b.closest(".turno"); if (el) D.pdf(el); });
})();

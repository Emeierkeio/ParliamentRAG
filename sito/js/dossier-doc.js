/* Il documento del dossier (card 284): copertina, indice, una sezione per pagina, metodo. Lo usano la chat (per il PDF)
   e la pagina condivisibile /dossier/<id>; sullo schermo le pagine sono fogli con i margini, in stampa A4. */
(function () {
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const LOGO = '<svg viewBox="15 15 194 153" aria-hidden="true"><path d="M 35.91 139.73 A 81 81 0 1 1 188.09 139.73" fill="none" stroke="currentColor" stroke-width="32" stroke-linecap="round"/><circle cx="112" cy="146" r="22" fill="currentColor"/></svg>';
  // margini dentro le sezioni (ripetuti su ogni pagina con box-decoration-break), non nella @page: così valgono anche
  // quando nella finestra di stampa «Margini» è su «Nessuno»
  const CSS = `@page{size:A4;margin:0}
    @media print{.indice,.sez,.metodo{padding:16mm 16mm 18mm;box-decoration-break:clone;-webkit-box-decoration-break:clone}}
    *{box-sizing:border-box}body{margin:0;font:400 10.5pt/1.55 "Schibsted Grotesk",Arial,sans-serif;color:#14161d;-webkit-print-color-adjust:exact;print-color-adjust:exact}
    a{color:#2a4bd7;text-decoration:none}
    .copertina{position:relative;overflow:hidden;width:210mm;height:296mm;padding:20mm 18mm 18mm;background:#f6f7f9;color:#14161d;display:flex;flex-direction:column;page-break-after:always}
    .copertina>*{position:relative}.copertina>div:nth-of-type(1){margin-top:22mm}.copertina .contatti{margin-top:auto}
    .copertina .aula{position:absolute;left:-97mm;top:124mm;width:369mm;opacity:.2;-webkit-mask-image:radial-gradient(60% 70% at 50% 60%,#000 20%,transparent 75%);mask-image:radial-gradient(60% 70% at 50% 60%,#000 20%,transparent 75%)}
    .marchio{display:flex;align-items:center;gap:10px;font:600 16pt "Geist",Arial,sans-serif;letter-spacing:-.035em}
    .marchio svg{width:30px;height:22px}
    .copertina .marchio{gap:4mm;font-size:26pt;margin-bottom:12mm}.copertina .marchio svg{width:14mm;height:auto}
    .copertina h1{font-size:44pt;line-height:1.02;letter-spacing:-.035em;margin:0 0 6mm;font-weight:600;max-width:170mm}
    .copertina h1.lungo{font-size:28pt;line-height:1.1}
    .copertina .temi{font-size:15pt;line-height:1.4;color:#2D5F8F;margin:0 0 7mm;max-width:165mm;font-weight:600;letter-spacing:-.01em}
    .copertina .sotto{font-size:10.5pt;color:#3b3f4b;max-width:140mm}
    .copertina .tag{display:inline-block;font-size:9pt;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:#666b79;margin-bottom:5mm}
    .partner{display:flex;align-items:center;gap:8.5mm;margin-bottom:6mm}.partner img{display:block;width:auto}
    .partner .disco{height:11.3mm}.partner .ue{display:flex;align-items:center;gap:2.7mm;font-size:9.5pt;font-weight:600;color:#3b3f4b}.partner .ue img{height:7.8mm}.partner .datai{height:4.3mm}
    .contatti{font-size:9pt;color:#3b3f4b;display:grid;gap:.6mm}
    .contatti b{color:#14161d}
    .indice{page-break-after:always}.indice h2,.sez h2{font-size:15pt;letter-spacing:-.02em;margin:0 0 6mm;font-weight:600}
    .indice ol{padding-left:9mm;font-size:11pt;line-height:2}
    .sez{page-break-before:always}.sez:first-of-type{page-break-before:auto}
    .sez h3{display:none}.sez h4{font-size:11pt;margin:5mm 0 2mm}
    .sez ul.lista{list-style:none;padding:0;margin:0}.sez .lista>li{padding:2.5mm 0;border-bottom:1px solid #e4e6eb;display:grid;gap:.8mm;break-inside:avoid}
    .sez .prosa li{margin:0 0 1.5mm}
    .meta,.dos-firme,.dos-sotto{font-size:9pt;color:#666b79}
    .dos-chip{display:inline-block;border:1px solid #cdd1da;border-radius:99px;padding:.5mm 2.5mm;margin:0 1.5mm 1.5mm 0;font-size:9pt}
    .dos-es--ok{color:#1d6b4a;font-weight:600}
    .dos-quadro{font-size:9pt}.dos-quadro td{vertical-align:top}.dos-quadro td:first-child{white-space:nowrap}.dos-quadro th{font-size:8.5pt;text-transform:none}.dos-es--no{color:#a52a14;font-weight:600}
    table{border-collapse:collapse;width:100%;font-size:9.5pt;margin-bottom:4mm}th,td{border-bottom:1px solid #e4e6eb;padding:1.5mm 2mm;text-align:left}th{font-weight:600;color:#3b3f4b}
    blockquote,q{color:#14161d}
    .metodo{page-break-before:always;font-size:9.5pt;color:#3b3f4b}.metodo h2{font-size:13pt;color:#14161d}
    section button,section .azioni,.avviso-r,.dx,.info,section svg.ic,.indice-r,.indice-g,section nav,.sei-passi,details.come,.pdf-dossier{display:none!important}
    .fonti{list-style:none;padding:0;margin:0}.fonti li{display:grid;grid-template-columns:7mm 1fr;gap:1mm 2mm;padding:2mm 0;border-bottom:1px solid #e4e6eb;break-inside:avoid}
    .fonti .n{font-weight:600;color:#666b79}.fonti li>span:last-child{display:flex;flex-wrap:wrap;gap:0 2mm;align-items:baseline}.fonti small{flex-basis:100%;font-size:9pt;color:#666b79}
    .fonte-g{color:#3b3f4b}
    @media screen{
      html{background:#e9ebf0}body{padding:72px 16px 48px}
      .copertina,.indice,.sez,.metodo{width:min(210mm,100%);margin:0 auto 24px;background:#fff;padding:16mm 16mm 18mm;box-shadow:0 1px 2px rgba(20,22,29,.06),0 12px 32px -16px rgba(20,22,29,.25);border-radius:4px}
      .copertina{background:#f6f7f9;height:auto;aspect-ratio:210/297;padding:20mm 18mm 18mm}
      .barra{position:fixed;top:0;left:0;right:0;z-index:5;display:flex;align-items:center;gap:10px;padding:12px 16px;background:rgba(255,255,255,.92);backdrop-filter:blur(8px);border-bottom:1px solid #e4e6eb}
      .barra .marchio{font-size:15pt;margin-right:auto;color:#14161d;text-decoration:none}.barra .marchio svg{width:26px}
      .barra button,.barra a.bt{font:600 14px "Schibsted Grotesk",Arial,sans-serif;border-radius:999px;padding:9px 16px;cursor:pointer;border:1px solid #cdd1da;background:#fff;color:#14161d;text-decoration:none}
      .barra .primo{background:#14161d;color:#fff;border-color:#14161d}
      @media (max-width:760px){body{padding:64px 10px 32px}.copertina,.indice,.sez,.metodo{padding:22px 18px}.copertina{aspect-ratio:auto;min-height:150vw}.copertina>div:nth-of-type(1){margin-top:24px}.copertina .marchio{font-size:20pt;margin-bottom:28px}.copertina .marchio svg{width:34px;flex:none}.copertina h1{font-size:30pt}.copertina .temi{font-size:13pt}.partner{flex-wrap:wrap;gap:12px 18px}.barra .marchio span{display:none}.barra .marchio svg{flex:none}table{display:block;overflow-x:auto}}
    }
    @media print{.barra{display:none}}`;

  // copertina come le grafiche: l'emiciclo della home, sfumato, e i loghi dei partner (file in /img/copertina)
  const IMG = `${location.origin}/img/copertina/`;
  const AULA = `<img class="aula" src="${IMG}aula-camera.svg" alt="">`;
  const PARTNER = `<div class="partner"><img class="disco" src="${IMG}disco.png" alt="Università di Milano-Bicocca, DISCo"><span class="ue"><img src="${IMG}EN_FundedbytheEU_RGB_POS.png" alt="Funded by the European Union">DataPACT</span><img class="datai" src="${IMG}datai-logo.svg" alt="dat·AI"></div>`;

  // d: { titolo, temi, lingua, data (ISO), sezioni: [{ titolo, html }], link }; stampa: apre subito la finestra di stampa
  window.DOSSIER_DOC = (d, stampa) => {
    const en = d.lingua === "en", TT = (it, eng) => (en ? eng : it), e = esc, titolo = d.titolo || "Dossier", temi = d.temi || "", sezioni = d.sezioni || [];
    const oggi = new Date(d.data || Date.now()).toLocaleDateString(en ? "en-GB" : "it-IT", { day: "numeric", month: "long", year: "numeric" });
    const barra = d.link ? `<div class="barra"><a class="marchio" href="/">${LOGO}<span>ParliamentRAG</span></a>
      <button type="button" onclick="navigator.clipboard&&navigator.clipboard.writeText('${e(d.link)}');this.textContent='${TT("Link copiato", "Link copied")}'">${TT("Copia il link", "Copy link")}</button>
      <button type="button" class="primo" onclick="print()">${TT("Scarica in PDF", "Download PDF")}</button></div>` : "";
    const html = `<!doctype html><html lang="${en ? "en" : "it"}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${e(titolo)} · ParliamentRAG</title>
      <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Geist:wght@600&family=Schibsted+Grotesk:wght@400;500;600&display=swap"><style>${CSS}</style></head><body>${barra}
      <section class="copertina">${AULA}<div><div class="marchio">${LOGO}ParliamentRAG</div><span class="tag">${TT("Dossier", "Dossier")}</span><h1${titolo.length > 60 ? ' class="lungo"' : ""}>${e(titolo)}</h1>${temi ? `<p class="temi">${e(temi)}</p>` : ""}<p class="sotto">${TT(`Dati ufficiali di Camera e Senato, XIX legislatura, aggiornati al ${oggi}. Ogni citazione è copiata dal resoconto e ha il link alla seduta.`, `Official data of the Italian Chamber and Senate, 19th legislature, as of ${oggi}. Every quote is copied from the record and links to the sitting.`)}</p></div>
        <div class="contatti">${PARTNER}<b>ParliamentRAG</b><span>${TT("Progetto di ricerca dell'Università di Milano-Bicocca. Non è un servizio ufficiale del Parlamento.", "Research project of the University of Milano-Bicocca. Not an official service of Parliament.")}</span><span>www.parliamentrag.it · contatti@parliamentrag.it</span></div></section>
      <section class="indice"><h2>${TT("Indice", "Contents")}</h2><ol>${sezioni.map((s) => `<li>${e(s.titolo)}</li>`).join("")}<li>${TT("Metodo e fonti", "Method and sources")}</li></ol></section>
      ${sezioni.map((s) => `<section class="sez"><h2>${e(s.titolo)}</h2>${s.html}</section>`).join("")}
      <section class="metodo"><h2>${TT("Metodo e fonti", "Method and sources")}</h2>
        <p>${TT("ParliamentRAG organizza i dati del Parlamento per un accesso facile e verificabile. Le risposte rispettano tre garanzie, controllate da un programma prima di mostrarle: tutti i gruppi sono considerati (il Gruppo Misto per componente); per ogni gruppo parla chi segue il tema, secondo criteri pubblici; ogni citazione è copiata parola per parola dal resoconto.", "ParliamentRAG organises the data of the Italian Parliament for easy and verifiable access. Answers meet three guarantees, checked by a program before they are shown: every group is considered (the Mixed Group by component); for each group the member who follows the topic speaks, by public criteria; every quote is copied word for word from the record.")}</p>
        <p>${TT("Fonti: dati.camera.it, dati.senato.it, resoconti stenografici e sommari delle commissioni, schede degli atti. Gli esiti degli emendamenti vengono dai file di Camera e Senato, dai voti elettronici dell'Aula o dalla regola della fiducia; «non pubblicato» vuol dire che nessuna fonte lo dice. Un modello di AI scrive il testo e può sbagliare: fanno fede le fonti linkate.", "Sources: dati.camera.it, dati.senato.it, verbatim records and committee summaries, bill pages. Amendment outcomes come from the Chamber and Senate files, the floor's electronic votes or the confidence-vote rule; «not published» means no source states it. An AI model writes the text and can be wrong: the linked sources prevail.")}</p>
        <p>www.parliamentrag.it · contatti@parliamentrag.it</p>
        <p><b>${TT("Ricevi le novità per email:", "Get the news by email:")}</b> <a href="https://www.parliamentrag.it/iscriviti">www.parliamentrag.it/iscriviti</a></p></section>
      ${stampa ? `<script>Promise.all([document.fonts.ready,...[...document.images].map((i)=>i.complete?0:new Promise((r)=>{i.onload=i.onerror=r}))]).then(()=>setTimeout(()=>{print()},300));<\/script>` : ""}</body></html>`;
    return html;
  };
})();

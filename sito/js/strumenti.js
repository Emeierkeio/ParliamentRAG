/* Strumenti usabili da soli. Ogni pagina interroga in diretta il server MCP pubblico. */
(function () {
  const { $, esc: e } = B;
  const S = (window.ST = {});
  S.ELENCO = [
    { k: "gruppi", a: "Parlamento", b: "Schede, seggi, commissioni", i: "gruppi", t: "Gruppi e parlamentari", d: "Gruppi, deputati e senatori, seggi e schede con commissioni e attività." },
    { k: "voti", a: "Voti e leggi", b: "Ogni votazione, deputato per deputato", i: "voto", t: "Voti", d: "Ogni votazione elettronica, con il voto di ogni parlamentare." },
    { k: "emendamenti", a: "Voti e leggi", b: "Testo ed esito di ogni emendamento", i: "emend", t: "Emendamenti", d: "Gli emendamenti messi ai voti, con il testo e l'esito." },
    { k: "proposte", a: "Voti e leggi", b: "Progetti di legge e leggi pubblicate", i: "atto", t: "Proposte di legge", d: "Progetti di legge votati in Aula e leggi pubblicate." },
    { k: "autorevolezza", a: "Cerca", b: "Chi segue un tema, con i criteri", i: "bilancia", t: "Autorevolezza", d: "Chi segue un tema in Parlamento, secondo sei criteri pubblici." },
    { k: "atti", a: "Cerca", b: "Interventi, mozioni, interrogazioni", i: "cerca", t: "Ricerca", d: "Interventi in Aula e atti: mozioni, interrogazioni, ordini del giorno." },
    { k: "sedute", a: "Parlamento", b: "Cosa è successo, giorno per giorno", i: "sed", t: "Sedute", d: "Cosa è successo in Aula, giorno per giorno." },
    { k: "agenda", a: "Parlamento", b: "Sedute, scadenze e leggi in calendario", i: "cal", t: "Agenda", d: "Il calendario del Parlamento: sedute, termini per gli emendamenti, progetti di legge, voti finali e leggi." },
  ];
  const CRITERI = [
    { t: "Interventi in Aula", p: .25, d: "Quanto, e quanto di recente, ha parlato del tema in Aula." },
    { t: "Commissione", p: .25, d: "Quanto la sua commissione è vicina al tema." },
    { t: "Atti firmati", p: .20, d: "Proposte e altri atti sul tema che ha firmato, pesati per recenza." },
    { t: "Professione", p: .15, d: "Affinità tra il suo lavoro fuori dall'Aula e il tema." },
    { t: "Formazione", p: .10, d: "Affinità tra i suoi titoli di studio e il tema." },
    { t: "Ruolo istituzionale", p: .05, d: "Incarichi in corso, per esempio in Governo o in commissione." },
  ];
  S.CRITERI = CRITERI;
  const sedute = new Map();
  const TELEFONO = () => matchMedia("(max-width: 760px)").matches;
  const carica = (t) => `<div class="carica" role="status"><span class="vh">${e(t)}</span><i></i><i></i><i></i></div>`;
  const errore = (err) => `<div class="errore">Il servizio non ha risposto: ${e(err.message)}. Riprova tra poco.</div>`;
  const ricorda = (ss) => ss.forEach((s) => sedute.set(s.id, s));

  function testa(k, titolo, sotto, chiedi) {
    const x = S.ELENCO.find((y) => y.k === k) || {};
    CH.imposta({ etichetta: titolo || x.t, testo: titolo ? `${x.t}: ${titolo}${sotto ? `, ${sotto}` : ""}` : `${x.t}. ${x.d}` });
    return `<nav class="briciole" aria-label="Percorso"><a href="#strumenti">Strumenti</a><span>/</span>${titolo ? `<a href="#/strumenti/${k}">${e(x.t)}</a><span>/</span><b>${e(titolo)}</b>` : `<b>${e(x.t)}</b>`}</nav>
      <div class="testa-str"><div><h1>${e(titolo || x.t)}${titolo ? "" : B.info(x.d)}</h1>${titolo && sotto ? `<p>${e(sotto)}</p>` : ""}</div>${chiedi ? `<button class="ic-a ic-a--grande" data-chiedi="${e(chiedi)}" aria-label="${e(chiedi)}" data-tip="${e(chiedi)}">${B.ico("chiedi")}</button>` : ""}</div>`;
  }
  // apertura comune: una frase visibile su cosa fa lo strumento e qualche esempio da cliccare, che riempie il campo e cerca
  function avvio(frase, esempi, campo) {
    return `<div class="avvio" data-campo="${e(campo)}"><p class="avvio__frase">${e(frase)}</p>${esempi.length ? `<div class="avvio__es"><span>${TT("Prova con", "Try")}</span>${esempi.map((x) => `<button type="button" data-es="${e(x)}">${e(x)}</button>`).join("")}</div>` : ""}</div>`;
  }
  S.avvio = avvio;
  S.testa = testa;
  S.carica = carica;
  S.errore = errore;
  document.addEventListener("click", (ev) => {
    const b = ev.target.closest(".avvio [data-es]"); if (!b) return;
    const c = document.getElementById(b.closest(".avvio").dataset.campo); if (!c) return;
    c.value = b.dataset.es; c.form ? c.form.requestSubmit() : c.dispatchEvent(new Event("input", { bubbles: true }));
  });
  // barra laterale degli strumenti, raggruppati per area come nel menu
  const lato = (k) => { const aree = [...new Set(S.ELENCO.map((x) => x.a))]; return aree.map((a) => `${S.ELENCO.filter((x) => x.a === a).map((x) => `<a href="#/strumenti/${x.k}"${x.k === k ? ' aria-current="page"' : ""} aria-label="${e(x.t)}" data-tip="${e(x.t)}">${B.ico(x.i)}${e(x.t)}</a>`).join("")}`).join('<span class="sep"></span>'); };

  /* ---------- gruppi e deputati ---------- */
  let filtroG = null, cercaD = "";
  // Gruppi e parlamentari: Camera e Senato, filtro per iniziale del cognome, gruppo e nome
  let ramoG = "camera", letteraG = "A", senatori = null;
  const cognome = (n) => { const p = n.split(" "); return p.length > 2 && /^(De|Di|Del|Della|Dalla|Lo|La|Le|Da)$/i.test(p[p.length - 2]) ? p.slice(-2).join(" ") : p[p.length - 1]; };
  async function gruppi(box) {
    if (ramoG === "senato") await B.caricaSenato().catch(() => {});
    if (ramoG === "senato" && !senatori) { try { const d = await fetch("/dati/senatori.json").then((r) => r.json()); senatori = d.deputies.map((x) => ({ id: x.id, n: x.name, sigla: x.group, gruppo: x.groupName, foto: `/dati/foto/senatori/${x.id}.jpg` })); } catch (err) { senatori = []; } }
    const elenco = () => ramoG === "camera" ? B.persone().map((p) => ({ ...p, gruppo: B.NOMI[p.sigla] || p.sigla })) : senatori;
    const gruppiR = () => { const m = {}; elenco().forEach((p) => { m[p.sigla] = m[p.sigla] || { sigla: p.sigla, nome: p.gruppo, n: 0 }; m[p.sigla].n++; }); return Object.values(m).sort((a, b) => b.n - a.n); };
    const foto = (p) => ramoG === "camera" ? B.fotoHtml(p) : `<span class="foto"><img src="${p.foto}" alt="" loading="lazy" onerror="this.remove()"></span>`;
    const disegna = () => {
      const tutti = elenco().filter((p) => (!filtroG || p.sigla === filtroG));
      const lettere = [...new Set(tutti.map((p) => B.norm(cognome(p.n))[0].toUpperCase()))].sort();
      if (!cercaD && !lettere.includes(letteraG)) letteraG = lettere[0] || "A";
      const xs = tutti.filter((p) => cercaD ? B.norm(p.n).includes(B.norm(cercaD)) : B.norm(cognome(p.n))[0].toUpperCase() === letteraG).sort((a, b) => cognome(a.n).localeCompare(cognome(b.n)));
      box.querySelector("#alfa").innerHTML = "ABCDEFGHIJKLMNOPQRSTUVWXYZ".split("").map((l) => `<button data-lettera="${l}" ${lettere.includes(l) ? "" : "disabled"} aria-pressed="${!cercaD && l === letteraG}">${l}</button>`).join("");
      box.querySelector("#el-dep").innerHTML = `<p class="aut-conta">${xs.length} ${ramoG === "camera" ? TT("deputati", "deputies") : TT("senatori", "senators")}${filtroG ? ` · ${e(gruppiR().find((g) => g.sigla === filtroG)?.nome || filtroG)}` : ""}${cercaD ? "" : ` · ${letteraG}`}</p><div class="carte-p">${xs.map((p) => `<a href="#/strumenti/${ramoG === "camera" ? "deputato" : "senatore"}/${p.id}">${foto(p)}<b style="font-weight:600">${e(p.n)}</b>${B.sigLungo(p.sigla).replace(e(B.NOMI[p.sigla] || p.sigla), e(p.gruppo || p.sigla))}</a>`).join("")}</div>`;
      box.querySelector("#gr-g").innerHTML = gruppiR().map((g) => `<button data-fg="${e(g.sigla)}" aria-pressed="${g.sigla === filtroG}"><i style="background:${B.col(g.sigla)}"></i><span>${e(g.nome)}</span><b>${g.n}</b></button>`).join("");
      box.querySelector("#emi-g").innerHTML = ramoG === "camera" ? B.emiciclo({ filtra: filtroG ? (s) => B.siglaSeggio(s) === filtroG : null, etichetta: TT("Aula della Camera per gruppo", "Chamber floor by group") })
        : B.emicicloSenato(senatori.map((p) => ({ first_name: p.n, last_name: "", party: p.sigla, outcome: "", sid: p.id })), TT("Senato per gruppo", "Senate by group"), true, filtroG);
    };
    box.innerHTML = testa("gruppi", null, null, TT("Come si dividono i gruppi in Parlamento?", "How are the groups split in Parliament?")) + avvio(TT("Chi siede alla Camera e al Senato, gruppo per gruppo e con le componenti del Misto. Ogni nome apre la scheda: commissioni, incarichi, interventi e voti.", "Who sits in the Chamber and the Senate, group by group, with the Mixed group's components. Each name opens the profile: committees, roles, speeches and votes."), [], "cd") + `
      <div class="seg-ramo" role="tablist"><button data-ramo="camera" aria-selected="${ramoG === "camera"}">${TT("Camera", "Chamber")}</button><button data-ramo="senato" aria-selected="${ramoG === "senato"}">${TT("Senato", "Senate")}</button></div>
      <div class="gr-layout"><div class="gr-emi" id="emi-g"></div><div class="gr-gruppi" id="gr-g"></div></div>
      <div class="gr-cerca"><input id="cd" placeholder="${TT("Cerca per nome", "Search by name")}" value="${e(cercaD)}" aria-label="${TT("Cerca per nome", "Search by name")}"><div class="alfa" id="alfa" aria-label="${TT("Iniziale del cognome", "Surname initial")}"></div></div>
      <div id="el-dep"></div>`;
    box.querySelector("#cd").addEventListener("input", (ev) => { cercaD = ev.target.value; disegna(); });
    box._gr = disegna;
    if (!box._grClic) box.addEventListener("click", box._grClic = (ev) => {
      if (!box.querySelector("#gr-g")) return;
      const b = ev.target.closest("[data-fg]"); if (b) { filtroG = filtroG === b.dataset.fg ? null : b.dataset.fg; box._gr(); return; }
      const l = ev.target.closest("[data-lettera]"); if (l) { letteraG = l.dataset.lettera; cercaD = ""; box.querySelector("#cd").value = ""; box._gr(); return; }
      const r = ev.target.closest("[data-ramo]"); if (r && r.dataset.ramo !== ramoG) { ramoG = r.dataset.ramo; filtroG = null; letteraG = "A"; gruppi(box); }
    });
    disegna();
  }

  const MINORI = new Set("di del della dello dei degli delle dell' e ed per il lo la l' i gli le a al alla allo ai agli alle all' da dal dalla dall' in nel nella nell' nei negli nelle su sul sulla sui sugli sulle con tra fra".split(" "));
  const organo = (n) => n.replace(/\s+/g, " ").trim().split(" ").map((w, i) => { const m = /^([A-Za-z]+')(.*)$/.exec(w); if (i && m && MINORI.has(m[1].toLowerCase())) return m[1].toLowerCase() + m[2]; return i && MINORI.has(w.toLowerCase()) ? w.toLowerCase() : w; }).join(" ");
  const periodo = (da, a) => a ? `${B.data(da)} – ${B.data(a)}` : `${TT("dal", "since")} ${B.data(da)}`;

  async function deputato(box, id) {
    const p = B.persona(id);
    if (!p) { box.innerHTML = testa("gruppi") + `<div class="errore">Deputato non trovato.</div>`; return; }
    box.innerHTML = testa("gruppi", p.n, B.NOMI[p.sigla] || p.sigla, `Cosa ha detto ${p.n} in Aula di recente?`) + `<div id="sch-d">${carica("Leggo la scheda")}</div>`;
    let d = null;
    try { const r = await fetch(`/dati/schede/${encodeURIComponent(id)}.json`); if (r.ok) d = await r.json(); } catch (err) { /* resta la scheda minima */ }
    const c = d && d.counts || {}, v = d && d.votes || null;
    const ruoli = d ? [d.institutionalRole, d.group && d.group.role && `${d.group.role} del gruppo`, ...(d.governmentOffices || []).map((g) => g.role || g.name), ...(d.committees || []).filter((x) => !x.to && x.role).map((x) => `${x.role}, ${organo(x.name)}`)].filter(Boolean).map((r) => organo(r.replace(/\b([A-ZÀ-Ý]{2,}(?:\s+[A-ZÀ-Ý]{2,})*)\b/g, (w) => /^[IVXL]+$/.test(w) ? w : w.charAt(0) + w.slice(1).toLowerCase()))).filter((r, i, a) => a.findIndex((y) => y.toLowerCase().replace(/[^\p{L}\d]/gu, "") === r.toLowerCase().replace(/[^\p{L}\d]/gu, "")) === i) : [];
    if (d) CH.imposta({ etichetta: p.n, testo: `scheda di ${p.n}, ${B.NOMI[p.sigla] || p.sigla}, Camera, XIX legislatura${ruoli.length ? "; ruoli: " + ruoli.join("; ") : ""}` });
    const num = (x) => x == null ? "–" : B.num(x);
    $("#sch-d").innerHTML = `<section class="blocco"><div class="scheda-d">${B.fotoHtml(p)}<div>
        <div style="display:flex;flex-wrap:wrap;align-items:center;gap:10px">${B.sig(p.sigla)}${d && d.group && d.group.since ? `<span style="color:var(--t3);font-size:14px">${TT("nel gruppo dal", "in the group since")} ${B.data(d.group.since)}</span>` : ""}</div>
        ${ruoli.length ? `<div class="ruoli">${ruoli.map((r) => `<span>${e(r)}</span>`).join("")}</div>` : ""}
        ${d && (d.profession || d.education) ? `<p data-tr style="margin:12px 0 0;color:var(--t2);font-size:15px">${e([d.profession, d.education].filter(Boolean).join(" · "))}</p>` : ""}
        <dl>
          <div><dt>In carica dal</dt><dd>${d && d.mandateStart ? B.data(d.mandateStart) : "–"}</dd></div>
          <div><dt>Interventi in Aula</dt><dd>${num(c.speeches)} <small>${c.sessionsWithSpeeches ? `in ${c.sessionsWithSpeeches} sedute` : ""}</small></dd></div>
          <div><dt>Atti con la sua prima firma</dt><dd>${num(c.actsPrimary)}</dd></div>
          <div><dt>Atti cofirmati</dt><dd>${num(c.actsCosigned)}</dd></div>
          <div><dt>Partecipazione ai voti</dt><dd>${v ? `${String(v.participationPct).replace(".", ",")}%` : "–"} <small>${v ? `su ${B.num(v.total)}` : ""}</small></dd></div>
        </dl>
        <dl class="anag" id="anag-d"><div><dt>Nascita</dt><dd><i class="skel"></i></dd></div><div><dt>Elezione</dt><dd><i class="skel"></i></dd></div><div><dt>Proclamazione e convalida</dt><dd><i class="skel"></i></dd></div></dl>
        <div class="fonte-r">${B.info(d ? `Dati di dati.camera.it al ${B.data(d.dataAsOf)}. Dichiarazioni di cariche e documentazione patrimoniale sono sulla scheda della Camera.` : "Dati di dati.camera.it")}${B.link(d && d.cameraUrl || `https://www.camera.it/deputati/elenco/19-${id}`, "Scheda su camera.it, con dichiarazioni e documentazione patrimoniale")}</div>
      </div></div></section>
      <div class="tre-d">
        <section class="blocco"><h3>Commissioni</h3>${d && d.committees.length ? `<ul class="cron">${d.committees.map((x) => `<li class="${x.to ? "" : "ora"}"><b data-tr>${e(organo(x.name))}</b><span>${x.role ? `<span data-tr>${e(x.role)}</span> · ` : ""}${periodo(x.from, x.to)}</span></li>`).join("")}</ul>` : `<p style="color:var(--t3)">Nessuna commissione nei dati.</p>`}</section>
        <section class="blocco"><h3>Gruppi nella legislatura</h3>${d && d.groupHistory.length ? `<ul class="cron">${d.groupHistory.map((x) => `<li class="${x.to ? "" : "ora"}"><b>${e(x.name)}</b><span>${x.role ? e(x.role) + " · " : ""}${periodo(x.from, x.to)}</span></li>`).join("")}${(d.mistoComponents || []).map((x) => `<li><b>Misto, componente ${e(x.name || x.acronym || "")}</b><span>${periodo(x.from, x.to)}</span></li>`).join("")}</ul>` : `<p style="color:var(--t3)">Dati non disponibili.</p>`}</section>
        <section class="blocco voti-d"><h3>Voti nella legislatura</h3>${v ? `${B.barra(v.favor, v.against, v.abstain, v.absent)}<ul>${[["favor", v.favor], ["against", v.against], ["abstain", v.abstain], ["absent", v.absent]].map(([k, n]) => `<li><span><i style="background:${B.colVoto(k)}"></i>${B.VOTO[k]}</span><b>${B.num(n)}</b></li>`).join("")}</ul><p style="margin:10px 0 0;font-size:13px;color:var(--t3)">Votazioni elettroniche dall'inizio della legislatura. «Assente» comprende le missioni.</p>` : `<p style="color:var(--t3)">Dati non disponibili.</p>`}</section>
      </div>
      <div class="due-col" style="margin-top:16px"><section class="blocco"><h3>Interventi recenti</h3>${d && d.recentSpeeches.length ? `<ul class="lista" data-per="2">${d.recentSpeeches.map((x) => `<li><span class="meta">${B.data(x.date)} · seduta ${x.session}</span><span>${e(B.taglia(x.debate, 150))}</span><span class="estratto">«${e(x.excerpt)}»</span>${B.link(x.url, "Apri il resoconto")}</li>`).join("")}</ul>` : `<div id="int-d">${carica("Cerco i suoi interventi")}</div>`}</section>
      <section class="blocco"><h3>Il seggio</h3>${B.emiciclo({ evidenzia: p.id, r: 15, etichetta: `Il seggio di ${p.n}` })}<p class="meta" style="margin:10px 0 0">Fiducia sulla legge elettorale, 7 ott 2026</p><div class="sig" style="margin-top:4px"><i style="background:${B.colVoto(p.v)};border-radius:50%"></i>${p.v ? B.VOTO[p.v] || p.v : "non registrato"}</div></section></div>`;
    B.anagrafica(id).then((a) => { const x = $("#anag-d"); if (!x) return;
      x.innerHTML = `<div><dt>Nascita</dt><dd>${a.nascita ? `${B.data(a.nascita)}${a.luogo ? `, ${e(a.luogo)}` : ""}<small>${TT(`${a.eta} anni`, `${a.eta} years old`)}</small>` : "–"}</dd></div>
        <div><dt>Elezione</dt><dd>${a.coll ? `${e(a.coll)}<small>${e(TT({ maggioritario: "collegio uninominale", proporzionale: "listino proporzionale" }[a.tipo] || a.tipo || "", { maggioritario: "single-member district", proporzionale: "proportional list" }[a.tipo] || a.tipo || ""))}${a.elezione ? ` · ${B.data(a.elezione)}` : ""}</small>` : "–"}</dd></div>
        <div><dt>Proclamazione e convalida</dt><dd>${a.inizio ? B.data(a.inizio) : "–"}<small>${a.convalida ? `${TT("convalida", "validated")} ${B.data(a.convalida)}` : ""}</small></dd></div>`;
      if (d) CH.imposta({ etichetta: p.n, testo: `${CH.contesto ? CH.contesto.testo : p.n}; nascita ${a.nascita || "?"} a ${a.luogo || "?"}; elezione ${a.coll || "?"}` }); }).catch(() => { const x = $("#anag-d"); if (x) x.remove(); });
    if (d && d.recentSpeeches.length) return;
    try {
      const r = await B.mcp("search_parliament", { query: p.n, doc_type: "speech", max_results: 20 });
      const xs = (r.dati.results || []).filter((x) => B.norm(`${x.first_name} ${x.last_name}`) === B.norm(p.n));
      $("#int-d").innerHTML = xs.length ? `<ul class="lista" data-per="2">${xs.map((x) => `<li><span class="meta">${B.data(x.date)} · seduta ${x.session_number}</span><span>${e(B.taglia(x.debate_title, 150))}</span><span class="estratto">«${e(x.text)}»</span>${B.link(x.url, "Apri il resoconto")}</li>`).join("")}</ul>` : `<p style="color:var(--t3)">Nessun intervento trovato con il suo nome fra i risultati.</p>`;
    } catch (err) { $("#int-d").innerHTML = errore(err); }
  }

  /* ---------- atto: pagina interna, poi la fonte ufficiale ---------- */
  const parametri = () => new URLSearchParams((location.hash.split("?")[1]) || "");
  // interrogazioni, interpellanze, mozioni: il testo dell'atto da dati.camera.it
  async function attoAic(box, num, urlH) {
    box.innerHTML = testa("atti", num, TT("Camera dei deputati", "Chamber of Deputies")) + `<div id="atto-c">${carica(TT("Leggo l'atto", "Reading the act"))}</div>`;
    try {
      const a = await fetch(`/dati/aic?n=${encodeURIComponent(num)}`).then((r) => r.json());
      if (!a.testo && !a.titolo) throw new Error(TT("Atto non trovato su dati.camera.it", "Act not found on dati.camera.it"));
      const tipo = B.frase(a.tipo || ""), data = a.data ? `${a.data.slice(0, 4)}-${a.data.slice(4, 6)}-${a.data.slice(6, 8)}` : "", autore = (a.autore || "").replace(/\s*\(.*\)\s*$/, "");
      const gruppo = ((/\(([^)]+)\)\s*$/.exec(a.autore || "") || [])[1]) || "";
      CH.imposta({ etichetta: `${tipo} ${num}`, testo: `${tipo} ${num} di ${autore}: ${B.taglia(a.testo || "", 600)}` });
      const url = a.doc || urlH;
      $("#atto-c").innerHTML = `<section class="blocco atto-p"><dl class="kv"><div><dt>${TT("Tipo", "Type")}</dt><dd>${e(tipo)}</dd></div><div><dt>${TT("Presentata da", "Tabled by")}</dt><dd>${e(B.nome(autore))}${gruppo ? ` · ${e(B.frase(gruppo))}` : ""}</dd></div>${data ? `<div><dt>${TT("Data", "Date")}</dt><dd>${B.data(data)}</dd></div>` : ""}${a.dest ? `<div><dt>${TT("Destinatario", "Addressed to")}</dt><dd>${e(B.frase(a.dest))}</dd></div>` : ""}<div><dt>${TT("Stato", "Status")}</dt><dd>${a.concluso === "1" ? TT("Concluso", "Closed") : TT("In corso", "Open")}</dd></div></dl>
        <div class="atto-testo" translate="no">${B.entita(a.testo || "").split(/\n+|(?<=[;:])\s+(?=-|\d\))/).map((x) => `<p>${e(x.trim())}</p>`).join("")}</div>
        ${url ? `<div class="fonte-az"><a class="bt bt--primario" href="${e(url)}" target="_blank" rel="noopener">${B.ico("esterno")}${TT("Raggiungi la fonte", "Go to the source")}</a><span class="fonte-dom">${e(new URL(url).hostname)}</span></div>` : ""}</section>`;
    } catch (err) { $("#atto-c").innerHTML = errore(err); }
  }
  async function atto(box, id) {
    const [ramo, numR] = String(id || "").split(/-(.+)/), pr = parametri(), titoloH = pr.get("t") || "", urlH = pr.get("u") || "";
    const num = (numR || "").replace("~", "/");
    if (/^\d\/\d+/.test(num)) return attoAic(box, num, urlH);
    const etichetta = `${ramo === "senato" ? "S." : "C."} ${num}`;
    box.innerHTML = testa("proposte", etichetta, ramo === "senato" ? TT("Senato della Repubblica", "Senate") : TT("Camera dei deputati", "Chamber of Deputies"), TT(`Cosa è successo all'atto ${etichetta}?`, `What happened to bill ${etichetta}?`)) + `<div id="atto-c">${carica(TT("Cerco l'atto", "Looking up the act"))}</div>`;
    let a = null;
    try {
      const q = titoloH.replace(/^\s*[CS]\.\s*[\w-]+\s*·\s*/, "") || num;
      const r = await B.mcp("search_parliament", { query: q, doc_type: "act", max_results: 20, ...(ramo ? { chamber: ramo } : {}) });
      a = (r.dati.results || []).find((x) => String(x.act_number).toLowerCase() === String(num).toLowerCase()) || null;
    } catch (err) { /* resta la pagina con i dati del link */ }
    const url = (a && a.url) || urlH || (ramo === "camera" ? `https://www.camera.it/leg19/126?tab=1&leg=19&idDocumento=${num}` : "");
    const titolo = B.frase((a && a.act_title) || titoloH.replace(/^\s*[CS]\.\s*[\w-]+\s*·\s*/, "") || etichetta);
    const firma = a && a.last_name ? `${B.nome(`${a.first_name} ${a.last_name}`)}` : "";
    $("#atto-c").innerHTML = `<section class="blocco atto-p"><h2 class="atto-t" translate="no">${e(titolo)}</h2>
      <dl class="kv">${a && a.act_type ? `<div><dt>${TT("Tipo", "Type")}</dt><dd>${e(a.act_type)}</dd></div>` : ""}<div><dt>${TT("Numero", "Number")}</dt><dd>${e(etichetta)}</dd></div>${a && a.date ? `<div><dt>${TT("Presentato", "Introduced")}</dt><dd>${B.data(a.date)}</dd></div>` : ""}${firma ? `<div><dt>${TT("Prima firma", "First signatory")}</dt><dd>${e(firma)} ${a.group ? B.sig(B.sigla(a.group, a.misto_component)) : ""}</dd></div>` : ""}${a && a.law ? `<div><dt>${TT("Legge", "Law")}</dt><dd>${e(a.law.label)}</dd></div>` : ""}</dl>
      <div class="fonte-az">${url ? `<a class="bt bt--primario" href="${e(url)}" target="_blank" rel="noopener">${B.ico("esterno")}${TT("Raggiungi la fonte", "Go to the source")}</a>` : ""}<span class="fonte-dom">${e(url ? new URL(url).hostname.replace(/^www\./, "www.") : "")}</span></div></section>
      <section class="blocco" style="margin-top:16px"><h3>${TT("Interventi in Aula su questo atto", "Floor speeches on this act")}</h3><div id="atto-int">${carica(TT("Cerco gli interventi", "Looking for speeches"))}</div></section>`;
    try {
      const r = await B.mcp("search_parliament", { query: titolo, doc_type: "speech", max_results: 6, ...(ramo ? { chamber: ramo } : {}) });
      const xs = r.dati.results || [];
      $("#atto-int").innerHTML = xs.length ? `<ul class="lista">${xs.map((x) => `<li><span class="meta">${B.ramo(x.chamber)} · ${B.data(x.date)} · ${TT("seduta", "sitting")} ${x.session_number}</span><span>${e(B.nome(`${x.first_name} ${x.last_name}`))} ${B.sig(B.sigla(x.group, x.misto_component))}</span><span class="estratto">«${e(B.taglia(x.text, 300))}»</span>${B.link(`#/strumenti/seduta/${x.chamber === "senato" ? "sen_" : ""}leg19_sed${x.session_number}`, TT("Apri la seduta", "Open the sitting"))}</li>`).join("")}</ul>` : `<p style="color:var(--t3)">${TT("Nessun intervento trovato.", "No speeches found.")}</p>`;
    } catch (err) { $("#atto-int").innerHTML = errore(err); }
  }
  /* ---------- fonte generica ---------- */
  function fonte(box) {
    const pr = parametri(), url = pr.get("u") || "", t = pr.get("t") || TT("Fonte", "Source"), ag = pr.get("a") || "", d = pr.get("d") || "", x = pr.get("x") || "";
    box.innerHTML = testa("atti", t.length > 80 ? B.taglia(t, 80) : t, ag) + `<section class="blocco atto-p"><h2 class="atto-t" translate="no">${e(t)}</h2>
      <dl class="kv">${ag ? `<div><dt>${TT("Fonte", "Source")}</dt><dd>${e(ag)}</dd></div>` : ""}${d ? `<div><dt>${TT("Data", "Date")}</dt><dd>${B.data(d)}</dd></div>` : ""}</dl>
      ${x ? `<p class="estratto" style="font-size:16px">«${e(x)}»</p>` : ""}
      <div class="fonte-az">${url ? `<a class="bt bt--primario" href="${e(url)}" target="_blank" rel="noopener">${B.ico("esterno")}${TT("Raggiungi la fonte", "Go to the source")}</a><span class="fonte-dom">${e(new URL(url).hostname)}</span>` : ""}</div></section>`;
  }

  /* ---------- scheda del senatore ---------- */
  async function senatore(box, id) {
    box.innerHTML = testa("gruppi", TT("Senatore", "Senator"), TT("Senato della Repubblica", "Senate")) + `<div id="sch-s">${carica(TT("Leggo la scheda", "Reading the profile"))}</div>`;
    try {
      const [d] = await Promise.all([fetch(`/dati/senatori/${encodeURIComponent(id)}.json`).then((r) => { if (!r.ok) throw new Error(TT("Senatore non trovato", "Senator not found")); return r.json(); }), B.caricaSenato().catch(() => {})]);
      const g = d.group && d.group.acronym || "", c = d.counts || {}, v = d.votes || null, num = (x) => x == null ? "–" : B.num(x);
      box.querySelector(".testa-str h1").textContent = d.name; const sp = box.querySelector(".testa-str p"); if (sp) sp.textContent = d.group ? d.group.name : "";
      CH.imposta({ etichetta: d.name, testo: `scheda di ${d.name}, ${d.group ? d.group.name : ""}, Senato, XIX legislatura` });
      const ruoli = [d.institutionalRole, ...(d.governmentOffices || []).map((x) => x.role || x.name), ...(d.committees || []).filter((x) => !x.to && x.role).map((x) => `${x.role}, ${x.name}`)].filter(Boolean).filter((r, i, a) => { const k = (y) => y.toLowerCase().replace(/ministr[ao]/g, "ministr"); return !a.some((y, j) => j !== i && (k(y) === k(r) ? j < i : k(y).startsWith(k(r)))); });
      $("#sch-s").innerHTML = `<section class="blocco"><div class="scheda-d"><span class="foto"><img src="/dati/foto/senatori/${e(id)}.jpg" alt="" onerror="this.remove()"></span><div>
          ${B.sigLungo(g).replace(e(B.NOMI[g] || g), e(d.group ? d.group.name : g))}
          ${ruoli.length ? `<div class="ruoli">${ruoli.map((r) => `<span>${e(r)}</span>`).join("")}</div>` : ""}
          ${d.profession || d.education ? `<p data-tr style="margin:12px 0 0;color:var(--t2);font-size:15px">${e([d.profession, d.education].filter(Boolean).join(" · "))}</p>` : ""}
          <dl><div><dt>${TT("In carica dal", "In office since")}</dt><dd>${d.mandateStart ? B.data(d.mandateStart) : "–"}</dd></div><div><dt>${TT("Interventi in Aula", "Floor speeches")}</dt><dd>${num(c.speeches)}</dd></div><div><dt>${TT("Atti con la sua prima firma", "Acts as first signatory")}</dt><dd>${num(c.actsPrimary)}</dd></div><div><dt>${TT("Atti cofirmati", "Co-signed acts")}</dt><dd>${num(c.actsCosigned)}</dd></div><div><dt>${TT("Partecipazione ai voti", "Vote participation")}</dt><dd>${v ? `${window.LANG === "en" ? v.participationPct : String(v.participationPct).replace(".", ",")}%` : "–"}</dd></div></dl>
          <div class="fonte-r">${B.info(TT(`Dati di dati.senato.it al ${B.data(d.dataAsOf)}`, `Data from dati.senato.it as of ${B.data(d.dataAsOf)}`))}${d.senatoUrl ? B.link(d.senatoUrl, TT("Scheda su senato.it", "Profile on senato.it")) : ""}</div></div></div></section>
        <div class="tre-d"><section class="blocco"><h3>${TT("Commissioni", "Committees")}</h3><ul class="cron">${(d.committees || []).map((x) => `<li class="${x.to ? "" : "ora"}"><b>${e(x.name)}</b><span>${x.role ? e(x.role) + " · " : ""}${x.to ? `${B.data(x.from)} – ${B.data(x.to)}` : `${TT("dal", "since")} ${B.data(x.from)}`}</span></li>`).join("")}</ul></section>
          <section class="blocco"><h3>${TT("Il seggio", "The seat")}</h3>${B.SEN ? B.emicicloSenato([], d.name, true, "") .replace(`data-sen-id="${id}"`, `data-sen-id="${id}" class="acceso-s"`) : ""}</section>
          <section class="blocco voti-d"><h3>${TT("Voti nella legislatura", "Votes in the legislature")}</h3>${v ? `${B.barra(v.favor, v.against, v.abstain, v.absent)}<ul>${[["favor", v.favor], ["against", v.against], ["abstain", v.abstain], ["absent", v.absent]].map(([k, n]) => `<li><span><i style="background:${B.colVoto(k)}"></i>${B.VOTO[k]}</span><b>${B.num(n)}</b></li>`).join("")}</ul>` : ""}</section></div>
        ${(d.recentSpeeches || []).length ? `<section class="blocco" style="margin-top:16px"><h3>${TT("Interventi recenti", "Recent speeches")}</h3><ul class="lista" data-per="2">${d.recentSpeeches.map((x) => `<li><span class="meta">${B.data(x.date)} · ${TT("seduta", "sitting")} ${x.session}</span><span>${e(B.taglia(x.debate, 150))}</span><span class="estratto">«${e(x.excerpt)}»</span>${B.link(x.url, TT("Apri il resoconto", "Open the verbatim record"))}</li>`).join("")}</ul></section>` : ""}`;
    } catch (err) { $("#sch-s").innerHTML = errore(err); }
  }

  /* ---------- voti ---------- */
  async function voti(box, sid) {
    box.innerHTML = testa("voti", null, null, "Quali sono state le ultime votazioni?") + avvio(TT("Ogni votazione elettronica di Camera e Senato, con l'esito e il voto di ogni parlamentare. Scegli una seduta a sinistra: a destra compaiono le sue votazioni.", "Every electronic vote in both houses, with the outcome and how each member voted. Pick a sitting on the left: its votes appear on the right."), [], "") + `<div class="due-col"><section class="blocco"><h3>Sedute con votazioni</h3><div id="sed-v">${carica("Cerco le ultime sedute")}</div><button class="bt bt--linea piu" id="altre-v" hidden>Sedute precedenti</button></section><section class="blocco"><h3 id="tit-v">Votazioni</h3><div id="voti-v"><p style="color:var(--t3)">Scegli una seduta.</p></div></section></div>`;
    let prima = null;
    const elenco = async () => {
      try {
        const r = await B.mcp("list_sessions", { limit: 20, ...(prima ? { before: prima } : {}) });
        const ss = (r.dati.sessions || []).filter((s) => s.vote_count > 0); ricorda(r.dati.sessions || []); prima = r.dati.next_cursor;
        const ul = $("#sed-v").querySelector("ul") || (($("#sed-v").innerHTML = '<ul class="lista"></ul>'), $("#sed-v").querySelector("ul"));
        ul.insertAdjacentHTML("beforeend", ss.map((s) => `<li><a class="sed-r" href="#/strumenti/${TELEFONO() ? "seduta" : "voti"}/${s.id}"><b>${B.ramo(s.chamber)}, ${TT("seduta", "sitting")} ${s.number}</b><span class="meta">${B.data(s.date)} · ${s.vote_count} ${TT("votazioni", "votes")} · ${s.speech_count} ${TT("interventi", "speeches")}</span></a></li>`).join(""));
        $("#altre-v").hidden = !r.dati.has_more;
        if (!sid && ss[0] && !TELEFONO()) mostra(ss[0].id);
      } catch (err) { $("#sed-v").innerHTML = errore(err); }
    };
    const mostra = async (id) => {
      const s = sedute.get(id);
      $("#tit-v").textContent = s ? `Votazioni · ${B.ramo(s.chamber)}, ${B.data(s.date)}` : "Votazioni";
      $("#voti-v").innerHTML = carica("Apro le votazioni della seduta");
      try {
        const r = await B.mcp("get_session_votes", { session_id: id });
        const vs = r.dati.votes || [];
        $("#voti-v").innerHTML = `<div class="tab"><table><thead><tr><th class="n">N.</th><th>Votazione</th><th>Esito</th><th>Ripartizione</th></tr></thead><tbody>${vs.map((v) => { const [t, k] = B.esito(v); return `<tr class="clic" data-vai="#/strumenti/voto/${v.id}"><td class="n">${v.number}</td><td>${e(B.taglia(v.act_subject || v.description || v.subject, 110))}${v.final_vote ? ' <span class="badge badge--neutro">finale</span>' : ""}</td><td><span class="badge badge--${k}">${t}</span></td><td>${v.kind === "quorum_check" ? "" : B.barra(v.in_favor, v.against, v.abstained)}<span class="meta">${v.kind === "quorum_check" ? "" : `${v.in_favor} · ${v.against} · ${v.abstained}`}</span></td></tr>`; }).join("")}</tbody></table></div>`;
      } catch (err) { $("#voti-v").innerHTML = errore(err); }
    };
    $("#altre-v").addEventListener("click", elenco);
    await elenco();
    if (sid) mostra(sid);
  }
  async function voto(box, id) {
    box.innerHTML = testa("voti", "Votazione", id.startsWith("senato") ? "Senato della Repubblica" : "Camera dei deputati") + `<section class="blocco"><div class="aula-box"></div></section><section class="blocco" id="tv" style="margin-top:16px" hidden><h3>Il testo messo ai voti</h3><div id="tv-c"></div></section>`;
    CH.aulaVoto(box.querySelector(".aula-box"), { id, ramo: id.startsWith("senato") ? "senato" : "camera" });
    CH.imposta({ etichetta: TT("Votazione", "Vote"), testo: `votazione con vote_id ${id} (${id.startsWith("senato") ? "Senato" : "Camera"})` });
    try {
      const r = await B.mcp("get_voted_text", { vote_id: id });
      const tx = r.dati && (r.dati.text || r.dati.testo) || (r.testi || []).join("\n");
      if (tx && !/non (è|e') disponibile|only works|not available/i.test(tx)) { $("#tv").hidden = false; $("#tv-c").innerHTML = `<div class="testo-votato">${e(tx)}</div>${r.dati && r.dati.source_url ? `${B.link(r.dati.source_url, "Apri la fonte")}` : ""}`; }
    } catch (err) { /* nessun testo per questo tipo di voto */ }
  }
  async function emendamenti(box, arg) {
    if (window.EM) return EM.apri(box, arg, testa);
    box.innerHTML = testa("emendamenti") + `<div class="filtri"><label class="vh" for="fe">Filtra</label><input id="fe" placeholder="Filtra per atto o presentatore"></div><div id="em">${carica("Cerco gli emendamenti nelle ultime sedute con votazioni")}</div>`;
    try {
      const r = await B.mcp("list_sessions", { limit: 25 }); ricorda(r.dati.sessions || []);
      const ss = (r.dati.sessions || []).filter((s) => s.vote_count > 0).slice(0, 6), xs = [];
      for (const s of ss) { const v = await B.mcp("get_session_votes", { session_id: s.id }); (v.dati.votes || []).filter((x) => /emendament/i.test(`${x.subject} ${x.description}`)).forEach((x) => xs.push({ ...x, s })); }
      const disegna = (f) => { const ys = xs.filter((x) => !f || B.norm(`${x.subject} ${x.description} ${x.act_title}`).includes(B.norm(f)));
        $("#em").innerHTML = `<p class="occ">${ys.length} emendamenti votati nelle ultime ${ss.length} sedute con votazioni</p><div class="tab"><table><thead><tr><th>Seduta</th><th>Emendamento</th><th>Atto</th><th>Esito</th><th class="n">Sì</th><th class="n">No</th></tr></thead><tbody>${ys.map((x) => { const [t, k] = B.esito(x); return `<tr class="clic" data-vai="#/strumenti/voto/${x.id}"><td style="white-space:nowrap">${B.data(x.s.date)}<div class="meta">${B.ramo(x.s.chamber)}</div></td><td>${e(x.description || x.subject)}</td><td style="font-size:13.5px;color:var(--t2)">${e(B.taglia(x.act_title || "", 90))}</td><td><span class="badge badge--${k}">${t}</span></td><td class="n">${x.in_favor}</td><td class="n">${x.against}</td></tr>`; }).join("")}</tbody></table></div>`; };
      disegna(""); $("#fe").addEventListener("input", (ev) => disegna(ev.target.value));
    } catch (err) { $("#em").innerHTML = errore(err); }
  }

  /* ---------- proposte di legge ---------- */
  async function proposte(box) {
    box.innerHTML = testa("proposte") + `<form class="filtri" id="fp"><label class="vh" for="qp">Cerca una proposta</label><input id="qp" placeholder="Cerca una proposta di legge (es. cittadinanza, caregiver)" style="flex:1"><button class="bt" style="min-height:38px">Cerca</button></form>${avvio(TT("I progetti di legge di Camera e Senato, con l'iter, il voto finale e la legge pubblicata.", "Bills in both houses, with their path, the final vote and the published law."), ["cittadinanza", "caregiver", "legge elettorale", "salario minimo"], "qp")}<div id="ris-p"></div>
      <section class="blocco" style="margin-top:16px"><h3>Votate di recente in Aula<span class="dx">voti finali</span></h3><div id="fin-p">${carica("Cerco i voti finali nelle ultime sedute")}</div></section>`;
    $("#fp").addEventListener("submit", async (ev) => {
      ev.preventDefault(); const q = $("#qp").value.trim(); if (!q) return; $("#ris-p").innerHTML = carica("Cerco negli atti");
      try { const r = await B.mcp("search_parliament", { query: q, doc_type: "act", max_results: 20 }); const xs = (r.dati.results || []).filter((a) => /pdl|ddl|legge|progetto/i.test(`${a.act_kind} ${a.act_type}`));
        $("#ris-p").innerHTML = `<section class="blocco"><h3>${xs.length} proposte<span class="dx">fra ${B.num(r.dati.total)} atti trovati</span></h3><ul class="lista">${xs.map((a) => `<li><span class="meta">${e(a.act_number || "")} · ${B.ramo(a.chamber)} · ${B.data(a.date)}</span>${a.url ? `<span>${e(B.frase(a.act_title))}</span>${B.link(B.interno(a.url, `${a.chamber === "senato" ? "S." : "C."} ${a.act_number} · ${a.act_title}`), TT("Apri l'atto", "Open the act"))}` : `<span>${e(B.frase(a.act_title))}</span>`}${a.law ? `<span style="font-size:14px">Diventata <a href="${e(a.law.eli || a.law.normattiva_url)}" target="_blank" rel="noopener">${e(a.law.label)}</a></span>` : ""}</li>`).join("") || "<li>Nessuna proposta con queste parole.</li>"}</ul></section>`;
      } catch (err) { $("#ris-p").innerHTML = errore(err); }
    });
    try {
      const r = await B.mcp("list_sessions", { limit: 25 }); ricorda(r.dati.sessions || []);
      const ss = (r.dati.sessions || []).filter((s) => s.vote_count > 0).slice(0, 8), xs = [];
      for (const s of ss) { const v = await B.mcp("get_session_votes", { session_id: s.id }); (v.dati.votes || []).filter((x) => x.final_vote && x.act_title).forEach((x) => xs.push({ ...x, s })); }
      $("#fin-p").innerHTML = xs.length ? `<ul class="lista">${xs.map((x) => { const [t, k] = B.esito(x); return `<li><span class="meta">${B.data(x.s.date)} · ${B.ramo(x.s.chamber)} · ${e(x.act_number || "")}</span><a href="#/strumenti/voto/${x.id}">${e(B.taglia(x.act_title, 200))}</a><span><span class="badge badge--${k}">${t}</span> <span class="meta">${x.in_favor} sì · ${x.against} no</span></span></li>`; }).join("")}</ul>` : `<p style="color:var(--t3)">Nessun voto finale nelle ultime sedute.</p>`;
    } catch (err) { $("#fin-p").innerHTML = errore(err); }
  }

  /* ---------- autorevolezza ---------- */
  // Autorevolezza: un tema, la classifica di tutti i deputati, filtri; i pesi si cambiano dalle impostazioni
  const commissione = (c) => B.frase(c || "").replace(/^([ivxl]+)\b/i, (m) => m.toUpperCase()).replace(/\bcommissione\b/, "Commissione");
  const CHIAVI_C = ["speeches", "committee", "acts", "profession", "education", "role"];
  const pesiAut = CRITERI.map((c) => c.p);
  function autorevolezza(box) {
    const pr = parametri(), tema0 = pr.get("tema") || "";
    box.innerHTML = testa("autorevolezza", null, null) + `
      <form class="aut-cerca" id="aut-f"><label class="vh" for="aut-t">${TT("Tema", "Topic")}</label><input id="aut-t" placeholder="${TT("Un tema: salario minimo, sanità, legge elettorale…", "A topic: minimum wage, healthcare, electoral law…")}" value="${e(tema0)}"><button class="bt bt--primario">${TT("Calcola", "Compute")}</button>
        <button type="button" class="ic-a ic-a--grande" id="aut-imp" aria-label="${TT("Criteri e pesi", "Criteria and weights")}" data-tip="${TT("Criteri e pesi", "Criteria and weights")}">${B.ico("impost")}</button></form>
      ${avvio(TT("Chi segue un tema in Parlamento, secondo sei criteri pubblici: interventi in Aula, commissione, atti firmati, professione, formazione e ruolo. Con l'ingranaggio cambi i pesi.", "Who follows a topic in Parliament, by six public criteria: floor speeches, committee, signed acts, profession, education and role. The gear changes the weights."), ["salario minimo", "legge elettorale", "intelligenza artificiale", "sanità"], "aut-t")}
      <div id="aut-r"></div>`;
    let dati = null;
    const punteggio = (d) => { const b = d.score_breakdown || {}, t = pesiAut.reduce((x, y) => x + y, 0) || 1; return CHIAVI_C.reduce((x, k, i) => x + (b[k] || 0) * pesiAut[i], 0) / t; };
    const disegna = () => {
      if (!dati) return;
      const fg = $("#aut-g").value, fc = $("#aut-c").value, fco = $("#aut-co").value, fn = B.norm($("#aut-n").value || "");
      const xs = dati.filter((d) => (!fg || d.sig === fg) && (!fc || d.coalition === fc) && (!fco || (d.committees || []).includes(fco)) && (!fn || B.norm(d.nome).includes(fn))).map((d) => ({ ...d, s: punteggio(d) })).sort((a, b) => b.s - a.s);
      const max = xs.length ? xs[0].s : 1;
      $("#aut-l").innerHTML = `<p class="aut-conta">${B.num(xs.length)} ${TT("deputati", "deputies")}</p><ol class="classifica aut-lista">${xs.slice(0, 80).map((d, i) => { const p = d.pid && B.persona(d.pid) || { id: d.pid, n: d.nome, sigla: d.sig }; const bd = d.score_breakdown || {}; const tip = CRITERI.map((c, k) => `${c.t} ${(bd[CHIAVI_C[k]] || 0).toFixed(2)}`).join(" · ");
        return `<li data-aut="${e(d.id)}"><span class="pos-n">${i + 1}</span>${B.fotoHtml(p)}<span class="cl-nome"><b>${e(d.nome)}</b>${B.sigLungo(d.sig)}<small class="aut-comm">${e(commissione((d.committees || [])[0]))}</small></span><span class="aut-barra" data-tip="${e(tip)}"><i style="width:${(d.s / max * 100).toFixed(1)}%"></i></span><span class="cl-val">${d.s.toFixed(2)}</span>${d.pid ? B.link(`#/strumenti/deputato/${d.pid}`, TT(`Apri la scheda di ${d.nome}`, `Open ${d.nome}'s profile`)) : ""}</li>`; }).join("")}</ol>`;
    };
    const calcola = async (tema) => {
      if (!tema) return;
      history.replaceState(null, "", `#/strumenti/autorevolezza?tema=${encodeURIComponent(tema)}`);
      CH.imposta({ etichetta: TT(`Autorevolezza: ${tema}`, `Authority: ${tema}`), testo: TT(`classifica di autorevolezza dei deputati sul tema «${tema}»`, `authority ranking of deputies on «${tema}»`) });
      $("#aut-r").innerHTML = `<div class="blocco">${carica(TT("Calcolo l'autorevolezza di tutti i deputati sul tema", "Computing every deputy's authority on the topic"))}</div>`;
      try {
        const r = await fetch("/api/autorevolezza", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ topic: tema }) });
        if (!r.ok) throw new Error(TT("Il calcolo dell'autorevolezza non è disponibile: serve il backend locale.", "The authority computation is not available: the local backend is needed."));
        const j = await r.json(), attuali = new Set(B.persone().map((p) => p.id));
        dati = (j.deputies || []).map((d) => { const pid = (/p(\d+)$/.exec(d.id || "") || [])[1]; return { ...d, pid, nome: B.nome(`${d.first_name} ${d.last_name}`), sig: B.sigla(d.group) }; }).filter((d) => attuali.has(d.pid));
        const gruppi = B.ORDINE.filter((g) => dati.some((d) => d.sig === g)), comm = [...new Set(dati.flatMap((d) => d.committees || []))].filter((c) => /COMMISSIONE/i.test(c) && !/INCHIESTA|BICAMERALE|PARLAMENTARE/i.test(c)).sort();
        $("#aut-r").innerHTML = `<section class="blocco"><div class="filtri aut-filtri">
            <select id="aut-g" aria-label="${TT("Gruppo", "Group")}"><option value="">${TT("Tutti i gruppi", "All groups")}</option>${gruppi.map((g) => `<option value="${g}">${e(B.NOMI[g] || g)}</option>`).join("")}</select>
            <select id="aut-c" aria-label="${TT("Coalizione", "Coalition")}"><option value="">${TT("Maggioranza e opposizione", "Majority and opposition")}</option><option value="maggioranza">${TT("Maggioranza", "Majority")}</option><option value="opposizione">${TT("Opposizione", "Opposition")}</option></select>
            <select id="aut-co" aria-label="${TT("Commissione", "Committee")}"><option value="">${TT("Tutte le commissioni", "All committees")}</option>${comm.map((c) => `<option value="${e(c)}">${e(commissione(c))}</option>`).join("")}</select>
            <input id="aut-n" placeholder="${TT("Cerca un deputato", "Find a deputy")}" aria-label="${TT("Cerca un deputato", "Find a deputy")}"></div><div id="aut-l"></div></section>`;
        $("#aut-r").addEventListener("input", disegna); $("#aut-r").addEventListener("change", disegna);
        $("#aut-r").addEventListener("click", (ev) => { if (ev.target.closest("a")) return; const li = ev.target.closest("[data-aut]"); if (!li) return; const d = dati.find((x) => x.id === li.dataset.aut); if (d) B.criteri(d, pesiAut); });
        disegna();
      } catch (err) { $("#aut-r").innerHTML = errore(err); }
    };
    $("#aut-f").addEventListener("submit", (ev) => { ev.preventDefault(); calcola($("#aut-t").value.trim()); });
    $("#aut-imp").addEventListener("click", () => {
      const html = () => `<p style="margin:0 0 14px;color:var(--t2);font-size:14px">${TT("Sei criteri, una somma pesata. I pesi fanno sempre 100%: se ne alzi uno, gli altri scendono in proporzione. La classifica si aggiorna subito.", "Six criteria, one weighted sum. The weights always add up to 100%: raise one and the others go down in proportion. The ranking updates at once.")}</p>${CRITERI.map((c, i) => `<div class="peso-r"><div><b>${e(c.t)}</b>${B.info(c.d)}</div><input type="range" min="0" max="100" step="1" value="${Math.round(pesiAut[i] * 100)}" data-peso="${i}" aria-label="${e(c.t)}"><span>${Math.round(pesiAut[i] * 100)}%</span></div>`).join("")}<button class="bt-mini" data-ripristina style="margin-top:14px">${TT("Ripristina i pesi del paper", "Reset to the paper's weights")}</button>`;
      B.pannello(TT("Criteri e pesi", "Criteria and weights"), html());
      const pan = document.getElementById("pannello");
      pan.oninput = (ev) => { const r = ev.target.closest("[data-peso]"); if (!r) return; B.ribilancia(pesiAut, +r.dataset.peso, r.value / 100).forEach((x, k) => { pesiAut[k] = x; }); pan.querySelectorAll("[data-peso]").forEach((q, k) => { if (q !== r) q.value = Math.round(pesiAut[k] * 100); q.nextElementSibling.textContent = `${Math.round(pesiAut[k] * 100)}%`; }); disegna(); };
      pan.onclick = (ev) => { if (!ev.target.closest("[data-ripristina]")) return; CRITERI.forEach((c, i) => { pesiAut[i] = c.p; }); B.pannello(TT("Criteri e pesi", "Criteria and weights"), html()); disegna(); };
    });
    if (tema0) calcola(tema0); else temiPronti();
    // da guardare subito: i temi già calcolati, con le prime tre voci
    async function temiPronti() {
      let d; try { d = await fetch("/dati-autorevolezza.json").then((r) => r.json()); } catch { return; }
      if ($("#aut-r").children.length) return;
      $("#aut-r").innerHTML = `<section class="blocco"><h3>${TT("Temi già calcolati", "Topics already computed")}</h3><div class="aut-temi">${(d.temi || []).map((t) => `<button type="button" class="aut-tema" data-tema="${e(t.tema)}"><b>${e(t.tema)}</b><ol>${t.voci.slice(0, 3).map((v) => `<li>${B.sig(B.sigla(v.gruppo))} <span>${e(B.nome(v.nome))}</span></li>`).join("")}</ol><small>${TT("Vedi la classifica", "See the ranking")} →</small></button>`).join("")}</div></section>`;
      $("#aut-r").querySelectorAll("[data-tema]").forEach((b) => b.addEventListener("click", () => { $("#aut-t").value = b.dataset.tema; calcola(b.dataset.tema); }));
    }
  }


  // da guardare subito, prima di cercare: le ultime sedute di Camera e Senato con i loro dibattiti
  const DI_SERVIZIO = /^(missioni|modifica nella composizione|annunzi|annuncio|comunicazioni del presidente|sull'ordine dei lavori|ordine del giorno della|calendario|congedi|preavviso|in morte|sui lavori|sulla pubblicit|integrazione dell'ordine|autorizzazione alla relazione orale)/i;
  async function ultimeSedute(dove) {
    dove.innerHTML = `<section class="blocco"><h3>${TT("Ultime sedute", "Latest sittings")}<span class="dx">${TT("Camera e Senato", "Chamber and Senate")}</span></h3>${carica(TT("Leggo le ultime sedute", "Reading the latest sittings"))}</section>`;
    try {
      const ss = ((await B.mcp("list_sessions", { limit: 6 })).dati.sessions || []); ricorda(ss);
      dove.querySelector(".blocco").innerHTML = `<h3>${TT("Ultime sedute", "Latest sittings")}<span class="dx">${TT("Camera e Senato", "Chamber and Senate")}</span></h3><ul class="lista">${ss.map((x) => `<li><a class="sed-r" href="#/strumenti/seduta/${e(x.id)}"><span class="meta">${B.ramo(x.chamber)} · ${TT("seduta", "sitting")} ${x.number} · ${B.data(x.date)}</span><b data-tr>${e((x.debates || []).filter((d) => !DI_SERVIZIO.test(d.title || "")).slice(0, 2).map((d) => B.taglia(d.title.replace(/\.$/, ""), 110)).join(" · ") || TT("Comunicazioni e adempimenti", "Announcements and formalities"))}</b></a></li>`).join("")}</ul>`;
    } catch (err) { dove.innerHTML = ""; }
  }

  /* ---------- ricerca ---------- */
  async function atti(box, q) {
    q = q || "";
    box.innerHTML = testa("atti") + `<form class="filtri" id="fr"><label class="vh" for="qr">Cerca</label><input id="qr" value="${e(q)}" placeholder="Parole, nomi, numeri di legge (es. legge 180/2026)" style="flex:1">
      <select id="tr" aria-label="Tipo"><option value="all">Tutto</option><option value="speech">Interventi</option><option value="act">Atti</option></select>
      <select id="rr" aria-label="Ramo"><option value="both">Camera e Senato</option><option value="camera">Camera</option><option value="senato">Senato</option></select>
      <select id="gr" aria-label="Gruppo"><option value="">Tutti i gruppi</option>${["FRATELLI D'ITALIA", "PARTITO DEMOCRATICO", "LEGA", "MOVIMENTO 5 STELLE", "FORZA ITALIA", "ALLEANZA VERDI E SINISTRA", "AZIONE", "ITALIA VIVA", "NOI MODERATI"].map((g) => `<option>${g}</option>`).join("")}</select>
      <button class="bt" style="min-height:40px">Cerca</button></form>${avvio(TT("Cerca nelle parole dette in Aula e negli atti di Camera e Senato: mozioni, interrogazioni, ordini del giorno. La ricerca unisce significato e parole esatte.", "Search what was said on the floor and the acts of both houses: motions, questions, agenda orders. The search combines meaning and exact words."), ["caro energia", "legge 180/2026", "medici di base", "autonomia differenziata"], "qr")}<div id="rr-c"></div>`;
    const cerca = async () => {
      const qq = $("#qr").value.trim(); if (!qq) return; history.replaceState(null, "", `#/strumenti/atti?q=${encodeURIComponent(qq)}`);
      $("#rr-c").innerHTML = carica("Cerco");
      try {
        const r = await B.mcp("search_parliament", { query: qq, doc_type: $("#tr").value, chamber: $("#rr").value, max_results: 30, ...($("#gr").value ? { group: $("#gr").value } : {}) });
        const xs = r.dati.results || [];
        $("#rr-c").innerHTML = `<p class="occ">${B.num(r.dati.total)} risultati · i primi ${xs.length}</p><ul class="lista">${xs.map((x) => x.type === "speech"
          ? `<li><span class="meta">Intervento · ${B.ramo(x.chamber)} · ${B.data(x.date)} · seduta ${x.session_number}</span><span>${e(B.taglia(x.debate_title, 150))}</span><span class="estratto">«${e(x.text)}»</span><span style="font-size:13.5px">${e(B.nome(`${x.first_name} ${x.last_name}`))} ${B.sig(B.sigla(x.group, x.misto_component))} · ${B.link(x.url, "Apri il resoconto")}</span></li>`
          : `<li><span class="meta"><b class="ramo-b">${B.ramo(x.chamber)}</b> · ${e((x.act_kind || x.act_type || "atto").replace(/_/g, " "))} ${e(x.act_number || "")} · ${B.data(x.date)}</span>${x.url ? `<span>${e(B.taglia(x.act_subject || B.frase(x.act_title), 160))}</span>${B.link(B.interno(x.url, `${x.chamber === "senato" ? "S." : "C."} ${x.act_number} · ${x.act_title}`), TT("Apri l'atto", "Open the act"))}` : `<span>${e(B.taglia(x.act_subject || B.frase(x.act_title), 160))}</span>`}${x.text ? `<span class="estratto">${e(B.taglia(x.text, 260))}</span>` : ""}${x.law ? `<span style="font-size:14px">Diventato <a href="${e(x.law.eli || x.law.normattiva_url)}" target="_blank" rel="noopener">${e(x.law.label)}</a></span>` : ""}</li>`).join("")}</ul>`;
      } catch (err) { $("#rr-c").innerHTML = errore(err); }
    };
    $("#fr").addEventListener("submit", (ev) => { ev.preventDefault(); cerca(); });
    if (q) cerca(); else ultimeSedute($("#rr-c"));
  }

  /* ---------- sedute ---------- */
  async function seduteP(box) {
    box.innerHTML = testa("sedute", null, null, "Cosa è successo in Aula questa settimana?") + `<form class="filtri" id="fs"><label class="vh" for="qs">Cerca nelle sedute</label><input id="qs" placeholder="Cerca un argomento, una legge, un nome" style="flex:1"><select id="rs" aria-label="Ramo"><option value="both">Camera e Senato</option><option value="camera">Camera</option><option value="senato">Senato</option></select><button class="bt" style="min-height:40px">Cerca</button></form>${avvio(TT("Cosa è successo in Aula, giorno per giorno: i dibattiti, chi ha parlato e cosa si è votato in ogni seduta.", "What happened on the floor, day by day: the debates, who spoke and what was voted in each sitting."), ["legge di bilancio", "question time", "commemorazione", "fiducia"], "qs")}<div id="el-s">${carica("Carico le ultime sedute")}</div><button class="bt bt--linea piu" id="altre-s" hidden>Sedute precedenti</button>`;
    let prima = null, cerca = "", ramo = "both";
    const carica_ = async (nuovo) => {
      if (nuovo) { prima = null; $("#el-s").innerHTML = carica("Cerco"); }
      try {
        const r = await B.mcp("list_sessions", { limit: 15, chamber: ramo, ...(cerca ? { search: cerca } : {}), ...(prima ? { before: prima } : {}) });
        const ss = r.dati.sessions || []; ricorda(ss); prima = r.dati.next_cursor;
        // gerarchia: in alto ramo e data, poi di cosa si è parlato (il titolo), sotto il riassunto
        const html = ss.map((s) => { const temi = (s.debates || []).map((d) => d.title || "").filter((t) => t && !DI_SERVIZIO.test(t)).slice(0, 2).map((t) => B.taglia(t.replace(/\.$/, ""), 110));
          return `<li><a href="#/strumenti/seduta/${s.id}" class="sed-r"><span class="meta">${B.ramo(s.chamber)} · ${TT("seduta", "sitting")} ${s.number} · ${B.data(s.date)} · ${s.speech_count} ${TT("interventi", "speeches")}${s.vote_count ? ` · ${s.vote_count} ${TT("voti", "votes")}` : ""}</span><b${temi.length ? " data-tr" : ""}>${e(temi.join(" · ") || TT("Comunicazioni e adempimenti", "Announcements and formalities"))}</b><span class="sed-r__t" data-tr>${e(B.taglia((s.recap || "").replace(/^Nella sessione parlamentare del \d+ \S+ \d{4},?\s*/, "").replace(/^./, (x) => x.toUpperCase()), 240))}</span></a></li>`; }).join("");
        if (nuovo || !$("#el-s ul")) $("#el-s").innerHTML = `<ul class="lista">${html || "<li>Nessuna seduta trovata.</li>"}</ul>`; else $("#el-s ul").insertAdjacentHTML("beforeend", html);
        $("#altre-s").hidden = !r.dati.has_more;
      } catch (err) { $("#el-s").innerHTML = errore(err); }
    };
    $("#fs").addEventListener("submit", (ev) => { ev.preventDefault(); cerca = $("#qs").value.trim(); ramo = $("#rs").value; carica_(true); });
    $("#altre-s").addEventListener("click", () => carica_(false));
    carica_(true);
  }
  // dibattiti: prima quelli di merito, la procedura d'Aula piegata in fondo; titoli ripetuti contati una volta
  const PROCEDURA = /^(missioni|preavviso di votazioni|ordine del giorno della prossima seduta|trasmissione dal senato|annunzio|modifica nella composizione)/i;
  function dibattiti(xs) {
    const visti = new Map();
    xs.forEach((d) => { const t = String(d.title || "").replace(/\.\s*$/, ""); const k = t.toLowerCase(); if (visti.has(k)) visti.get(k).n++; else visti.set(k, { id: d.id, t, n: 1 }); });
    const tutti = [...visti.values()], merito = tutti.filter((d) => !PROCEDURA.test(d.t)), proc = tutti.filter((d) => PROCEDURA.test(d.t));
    const riga = (d) => `<li><button class="riga-a" data-dib="${e(d.id)}" aria-expanded="false"><span>${e(d.t)}${d.n > 1 ? ` <small>×${d.n}</small>` : ""}</span>${B.ico("dx")}</button><div class="dib-c"></div></li>`;
    return `<h3 class="sd-h">${TT("Dibattiti", "Debates")}<span class="dx">${merito.length}</span></h3><ul class="righe">${merito.map(riga).join("")}</ul>`
      + (proc.length ? `<details class="piega"><summary>${TT("Comunicazioni", "Announcements")}<span>${proc.length}</span></summary><ul class="righe">${proc.map(riga).join("")}</ul></details>` : "");
  }
  // votazioni: i voti sugli articoli e i finali in alto, ordini del giorno ed emendamenti raggruppati e piegati
  function votazioniSeduta(vs) {
    if (!vs.length) return `<p style="color:var(--t3)">${TT("Nessuna votazione elettronica.", "No electronic votes.")}</p>`;
    const ok = vs.filter((x) => B.esito(x)[1] === "ok").length;
    const tipo = (x) => /^ordine del giorno/i.test(x.description || "") ? "odg" : /emendament/i.test(`${x.subject} ${x.description}`) ? "em" : "princ";
    const titolo = (x) => { const m = /^Ordine del giorno n\. (\S+)\s+(.+?)\s*\(([^)]+)\)\s*$/.exec(x.description || ""); return m ? `${e(B.nome(m[2]))} <small>${e(m[3])} · ${e(m[1])}</small>` : e(B.taglia(x.act_subject || x.description || x.subject, 110)); };
    const riga = (x) => { const [t, k] = B.esito(x), tot = (+x.in_favor || 0) + (+x.against || 0) + (+x.abstained || 0) || 1;
      return `<li><a class="riga-v" href="#/strumenti/voto/${x.id}"><i class="esito-p esito-p--${k}" title="${e(t)}"></i><span class="riga-v__t">${titolo(x)}</span><span class="riga-v__n"><span class="mini-b"><b style="width:${(x.in_favor / tot) * 100}%"></b><b style="width:${(x.against / tot) * 100}%"></b></span>${x.in_favor}–${x.against}</span>${B.ico("dx")}</a></li>`; };
    const gruppi = [["princ", TT("Articoli e voti finali", "Articles and final votes"), true], ["em", TT("Emendamenti", "Amendments"), false], ["odg", TT("Ordini del giorno", "Agenda motions"), false]];
    return `<p class="sd-sint">${vs.length} ${TT("votazioni", "votes")} · ${ok} ${TT("approvate", "passed")} · ${vs.length - ok} ${TT("respinte", "rejected")}</p>`
      + gruppi.map(([k, n, aperto]) => { const xs = vs.filter((x) => tipo(x) === k); if (!xs.length) return ""; return `<details class="piega" ${aperto ? "open" : ""}><summary>${n}<span>${xs.length}</span></summary><ul class="righe">${xs.map(riga).join("")}</ul></details>`; }).join("");
  }
  async function seduta(box, id) {
    let s = sedute.get(id);
    box.innerHTML = testa("sedute", "Seduta", "") + `<div id="sd">${carica("Apro la seduta")}</div>`;
    try {
      if (!s) { const r = await B.mcp("list_sessions", { limit: 30 }); ricorda(r.dati.sessions || []); s = sedute.get(id); }
      if (!s) { const r = await B.mcp("list_sessions", { limit: 1, session_id: id }); ricorda(r.dati.sessions || []); s = sedute.get(id); }
      box.querySelector(".testa-str h1").textContent = s ? `Seduta n. ${s.number}` : "Seduta";
      if (s) CH.imposta({ etichetta: `${TT("Seduta", "Sitting")} ${s.number}`, testo: `seduta n. ${s.number} della ${B.ramo(s.chamber)} del ${s.date} (session_id ${id}); dibattiti: ${s.debates.map((d) => d.title).join("; ").slice(0, 900)}` });
      { const h = box.querySelector(".testa-str h1"), p = box.querySelector(".testa-str p") || h.insertAdjacentElement("afterend", document.createElement("p")); p.textContent = s ? `${B.ramo(s.chamber)} · ${B.dataLunga(s.date)}` : id; }
      $("#sd").innerHTML = `<div class="due-col"><section class="blocco"><h3>Di cosa si è parlato${B.info("Riepilogo scritto in automatico dal resoconto")}</h3>${s ? `<p style="margin:0;line-height:1.7">${e(s.recap)}</p><div class="grandi"><div><b>${s.speech_count}</b><span>interventi</span></div><div><b>${s.vote_count}</b><span>votazioni</span></div></div>` : ""}${s ? dibattiti(s.debates) : ""}</section>
        <section class="blocco"><h3>Votazioni</h3><div id="sd-v">${s && s.vote_count ? carica("Apro le votazioni") : "<p style='color:var(--t3)'>Nessuna votazione elettronica.</p>"}</div></section></div>`;
      if (s && s.vote_count) { const v = await B.mcp("get_session_votes", { session_id: id }); $("#sd-v").innerHTML = votazioniSeduta(v.dati.votes || []); }
    } catch (err) { $("#sd").innerHTML = errore(err); }
  }
  document.addEventListener("click", async (ev) => {
    const b = ev.target.closest("[data-dib]"); if (!b) return;
    const c = b.nextElementSibling; if (c.innerHTML) { c.innerHTML = ""; b.setAttribute("aria-expanded", "false"); return; } b.setAttribute("aria-expanded", "true");
    c.innerHTML = carica("Apro il dibattito");
    try {
      const d = (await B.mcp("get_debate", { debate_id: b.dataset.dib })).dati;
      // alcune voci del resoconto non hanno interventi (missioni, preavvisi): lo diciamo invece di non aprire niente
      if (!d.recap && !(d.speakers || []).length && !(d.acts || []).length) { c.innerHTML = `<p class="meta" style="margin:4px 0 0">${TT("Nessun intervento: è una comunicazione della Presidenza, letta in Aula senza dibattito.", "No speeches: an announcement read by the Chair, with no debate.")}</p>`; return; }
      c.innerHTML = `${d.recap ? `<p style="margin:8px 0;color:var(--t2)">${e(d.recap)}</p>` : ""}${(d.speakers || []).length ? `<p class="meta" style="margin:8px 0 4px">Chi è intervenuto</p><ul class="oratori">${d.speakers.map((p) => { const g = p.group || p.party ? B.sigla(p.group || p.party, p.misto_component) : null; return `<li><i style="background:${g ? B.col(g) : "var(--t3)"}"></i><span>${e(B.nome(p.name || `${p.first_name} ${p.last_name}`))}</span><small>${g ? e(B.NOMI[g] || g) : ""}</small></li>`; }).join("")}</ul>` : ""}${(d.acts || []).map((a) => `<p style="margin:8px 0 0;font-size:14px">${a.url ? `<span>${e(a.title)}</span> ${B.link(B.interno(a.url, a.title), TT("Apri la fonte", "Open the source"))}` : e(a.title)}${a.law ? ` · diventato ${e(a.law.label)}` : ""}</p>`).join("")}`;
    } catch (err) { c.innerHTML = errore(err); }
  });

  /* ---------- aula ---------- */
  function aula(box) {
    let modo = "gruppo";
    const disegna = () => {
      const voti = modo === "fiducia" ? Object.fromEntries(B.persone().filter((p) => p.v).map((p) => [p.id, p.v])) : null;
      box.querySelector("#aula-g").innerHTML = (voti ? B.emiciclo({ voti, etichetta: "Fiducia sulla legge elettorale, 7 ottobre 2026" }) + B.legendaVoto() : B.emiciclo({ etichetta: "Aula della Camera per gruppo" }));
      box.querySelector("#aula-g").dataset.titoloVoto = voti ? "Fiducia sulla legge elettorale, 7 ott 2026" : "";
      B.$$("[data-modo]", box).forEach((b) => b.setAttribute("aria-pressed", b.dataset.modo === modo));
    };
    box.innerHTML = testa("aula", null, null, "Com'è andata la fiducia sulla legge elettorale?") + `<div class="filtri"><button data-modo="gruppo">Per gruppo</button><button data-modo="fiducia">Fiducia, 7 ott 2026</button>${B.link("#/strumenti/voti", "Scegli un'altra votazione")}</div>
      <section class="blocco"><div id="aula-g"></div><div class="filtri" style="margin:0">${B.gruppiCamera().map((g) => `<a href="#/strumenti/gruppi" style="text-decoration:none">${B.sig(g.sigla)} <span class="meta">${g.seggi}</span></a>`).join("")}</div></section>`;
    box.addEventListener("click", (ev) => { const b = ev.target.closest("[data-modo]"); if (b) { modo = b.dataset.modo; disegna(); } });
    disegna();
  }

  /* ---------- dati ---------- */
  S.FILE = [
    { n: "parliamentrag_kg.ttl", d: "Il grafo in Turtle: persone, gruppi, commissioni, atti, temi EuroVoc, sedute, dibattiti e interventi con il testo integrale.", u: "https://doi.org/10.5281/zenodo.21560331", f: "Zenodo · RDF · DOI" },
    { n: "Voti individuali", d: "In un file a parte, perché è il più grande: il voto di ogni parlamentare in ogni votazione.", u: "https://doi.org/10.5281/zenodo.21560331", f: "Zenodo · RDF" },
    { n: "emeierkeio/parliamentrag-leg19", d: "Gli stessi dati in tabelle, per chi lavora con pandas, R o un foglio di calcolo.", u: "https://huggingface.co/datasets/emeierkeio/parliamentrag-leg19", f: "Hugging Face · tabelle" },
    { n: "ParliamentRAG / pipeline", d: "Il codice che ogni notte scarica gli open data di Camera e Senato, li controlla e li carica: chi vuole lo rifà da capo.", u: "https://github.com/Emeierkeio/ParliamentRAG/tree/main/pipeline", f: "GitHub · pipeline" },
  ];
  S.MCP = [["search_parliament", "cerca negli interventi in Aula e negli atti"], ["list_sessions", "elenca le sedute"], ["get_debate", "apre un dibattito"], ["get_session_votes", "le votazioni di una seduta"], ["get_vote_details", "il voto per gruppo e per parlamentare"], ["get_vote_hemicycle", "l'emiciclo di una votazione"], ["get_voted_text", "il testo messo ai voti"], ["get_parliament_agenda", "l'agenda: sedute, termini per gli emendamenti, leggi"], ["verify_answer", "controlla le tre garanzie su una risposta"]];
  function dati(box) {
    box.innerHTML = testa("dati", "Il grafo è di tutti", "La XIX legislatura di Camera e Senato come grafo RDF, con licenza CC BY-SA 4.0: puoi copiarlo, modificarlo e ridistribuirlo, anche per uso commerciale, citando la fonte e usando la stessa licenza.") +
      `<div class="file">${S.FILE.map((f) => `<a href="${f.u}" target="_blank" rel="noopener"><small>${e(f.f)}</small><b>${e(f.n)}</b><span>${e(f.d)}</span></a>`).join("")}</div>
       <h2 class="h3">Non serve scaricarlo per usarlo</h2><p class="lead">Il server MCP espone il grafo agli assistenti AI, con il link al resoconto in ogni risultato. Questo sito usa gli stessi strumenti. Indirizzo: <span class="mono">https://mcp.parliamentrag.it/mcp</span></p>
       <ul class="mcp">${S.MCP.map(([a, b]) => `<li><b>${a}</b><span>${b}</span></li>`).join("")}</ul>
       <p style="font-size:14px;color:var(--t3);margin-top:24px">L'export non contiene gli embedding, le conversazioni degli utenti né i riassunti scritti dall'AI. Fonti: dati.camera.it, dati.senato.it, thesaurus EuroVoc.</p>`;
  }

  S.apri = (k, arg, q) => {
    const pag = $("#pagina");
    if (!$("#pagina-c")) pag.innerHTML = `<nav class="lato-str" id="lato-str" aria-label="Strumenti"></nav><div class="pagina-c" id="pagina-c"></div>`;
    $("#lato-str").innerHTML = lato({ deputato: "gruppi", senatore: "gruppi", voto: "voti", seduta: "sedute", atto: "proposte", fonte: "atti" }[k] || k);
    const box = $("#pagina-c");
    document.body.dataset.vista = "strumento"; window.scrollTo(0, 0);
    const f = { gruppi, deputato, senatore, voti, voto, emendamenti, proposte, autorevolezza, atti, sedute: seduteP, seduta, aula, dati, atto, fonte, agenda: (b, a) => window.AGENDA(b, a) }[k] || gruppi;
    // la frase dell'apertura fa da sottotitolo: sale sotto il titolo, sopra la ricerca
    const sali = () => { const fr = box.querySelector(".avvio .avvio__frase"), ts = box.querySelector(".testa-str > div"); if (fr && ts) { fr.className = "testa-str__sotto"; ts.append(fr); } };
    Promise.resolve(f(box, arg ? decodeURIComponent(arg) : (k === "atti" ? q : undefined))).finally(sali); sali();
    document.title = "ParliamentRAG";
  };
})();

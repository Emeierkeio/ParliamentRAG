/* Home: domanda, instradamento, strumenti, grafo, metodo, dati. */
(function () {
  const { $, esc: e } = B;
  const H = (window.HOME = {});
  const STRUM = [
    { k: "risposta", i: "chiedi", t: "Risposta con le fonti", s: "ogni frase con il suo resoconto" },
    { k: "posizioni", i: "gruppi", t: "Posizioni dei gruppi", s: "una voce per gruppo" },
    { k: "voti", i: "voto", t: "Voti e Aula", s: "il voto di ogni parlamentare" },
    { k: "sedute", i: "sed", t: "Sedute e dibattiti", s: "chi ha parlato, cosa si è votato" },
    { k: "atti", i: "atto", t: "Atti e proposte", s: "mozioni, interrogazioni, leggi" },
    { k: "persone", i: "pers", t: "Deputati", s: "scheda, seggio, interventi" },
    { k: "verifica", i: "scudo", t: "Tre garanzie", s: "controllo del testo con un programma" },
  ];
  const AVVII = [
    { t: "Chi ha votato contro la fiducia sulla legge elettorale?", s: "La fiducia sulla legge elettorale, deputato per deputato.", q: "Chi ha votato contro la fiducia sulla legge elettorale?", u: ["risposta", "voti", "verifica"] },
    { t: "Cosa pensano i partiti del salario minimo?", s: "Il salario minimo, con le parole di ogni gruppo.", q: "Cosa hanno detto i gruppi sul salario minimo?", u: ["risposta", "posizioni", "atti", "sedute", "voti", "verifica"] },
    { t: "Com'è finito il decreto sul salario giusto?", s: "Il decreto sul salario giusto: il voto finale e la legge pubblicata.", q: "Com'è andato il voto finale sul ddl salario giusto?", u: ["risposta", "voti", "atti", "verifica"] },
    { t: "Cosa è successo in Aula questa settimana?", s: "Le sedute di Camera e Senato di questa settimana.", q: "Di cosa hanno discusso Camera e Senato il 28 ottobre 2026?", u: ["risposta", "sedute", "voti"] },
    { t: "Cosa ha detto Maria Cecilia Guerra sul salario minimo?", s: "Maria Cecilia Guerra sul salario minimo.", q: "Cosa ha detto Maria Cecilia Guerra sul salario minimo?", u: ["risposta", "persone", "verifica"] },
  ];
  // Metodo, dal paper ISWC 2026 (ricerca/paper.tex, sezioni 3 e 4)

  // anteprime disegnate con i colori veri di gruppi e voti
  const ANTEPRIMA = {
    gruppi: () => { const g = B.ORDINE.map((k) => B.gruppiCamera().find((x) => x.sigla === k)).filter(Boolean), tot = g.reduce((a, x) => a + x.seggi, 0), file = [[30, 14], [41, 19], [52, 24], [63, 29]], pos = []; file.forEach(([r, n]) => { for (let i = 0; i < n; i++) { const a = Math.PI * (1 - (i + .5) / n); pos.push({ a, x: 80 + Math.cos(a) * r, y: 68 - Math.sin(a) * r }); } }); pos.sort((p, q) => q.a - p.a); const col = []; g.forEach((x) => { const n = Math.round(x.seggi / tot * pos.length); for (let k = 0; k < n; k++) col.push(B.col(x.sigla)); }); return `<svg viewBox="0 0 160 72">${pos.map((p, i) => `<circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="2.6" fill="${col[i] || col[col.length - 1]}"/>`).join("")}</svg>`; },
    voti: () => { const v = [["favor", .58], ["against", .37], ["abstain", .05]]; let x = 8; return `<svg viewBox="0 0 160 72">${v.map(([k, w]) => { const r = `<rect x="${x}" y="30" width="${w * 144 - 2}" height="12" rx="3" fill="${B.colVoto(k)}"/>`; x += w * 144; return r; }).join("")}<text x="8" y="22" font-size="11" font-weight="600" fill="currentColor">137 · 73 · 2</text></svg>`; },
    emendamenti: () => `<svg viewBox="0 0 160 72"><rect x="8" y="10" width="120" height="6" rx="3" fill="currentColor" opacity=".18"/><rect x="8" y="24" width="60" height="6" rx="3" fill="currentColor" opacity=".18"/><rect x="72" y="24" width="56" height="6" rx="3" fill="${B.colVoto("against")}" opacity=".7"/><rect x="8" y="38" width="88" height="6" rx="3" fill="${B.colVoto("favor")}" opacity=".75"/><rect x="8" y="52" width="104" height="6" rx="3" fill="currentColor" opacity=".18"/></svg>`,
    proposte: () => {
      // il percorso di una legge: Camera, Senato, di nuovo Camera, poi la legge; ogni tappa ha il suo nome sotto il cerchio
      const f = [["C", TT("Camera", "Chamber")], ["S", TT("Senato", "Senate")], ["C", TT("Camera", "Chamber")], ["L", TT("Legge", "Law")]];
      return `<svg viewBox="0 0 160 84"><line x1="20" y1="32" x2="140" y2="32" stroke="currentColor" opacity=".25" stroke-width="2"/>${f.map(([t, n], i) => `<circle cx="${20 + i * 40}" cy="32" r="9" fill="${i === 3 ? B.colVoto("favor") : "var(--fondo)"}" stroke="currentColor" stroke-opacity=".5"/><text x="${20 + i * 40}" y="36" font-size="10" font-weight="600" text-anchor="middle" fill="${i === 3 ? "#fff" : "currentColor"}">${t}</text><text x="${20 + i * 40}" y="58" font-size="8" text-anchor="middle" fill="currentColor" opacity=".65">${n}</text>`).join("")}<text x="80" y="76" font-size="7.5" text-anchor="middle" fill="currentColor" opacity=".5">${TT("il percorso della legge fra le Camere", "the bill's path between the houses")}</text></svg>`; },
    autorevolezza: () => { const w = [.92, .74, .61, .45, .3]; return `<svg viewBox="0 0 160 72">${w.map((x, i) => `<rect x="8" y="${6 + i * 13}" width="${x * 144}" height="7" rx="3.5" fill="var(--acc)" opacity="${1 - i * .15}"/>`).join("")}</svg>`; },
    atti: () => `<svg viewBox="0 0 160 72"><rect x="8" y="10" width="144" height="22" rx="11" fill="none" stroke="currentColor" stroke-opacity=".3"/><circle cx="24" cy="21" r="5" fill="none" stroke="currentColor" stroke-width="1.6"/><line x1="28" y1="25" x2="31" y2="28" stroke="currentColor" stroke-width="1.6"/><rect x="40" y="18" width="70" height="6" rx="3" fill="currentColor" opacity=".25"/><rect x="8" y="44" width="110" height="6" rx="3" fill="currentColor" opacity=".18"/><rect x="8" y="56" width="80" height="6" rx="3" fill="currentColor" opacity=".18"/></svg>`,
    sedute: () => { let c = ""; for (let i = 0; i < 21; i++) { const on = [2, 3, 8, 9, 10, 15, 16].includes(i); c += `<rect x="${10 + (i % 7) * 20}" y="${8 + Math.floor(i / 7) * 20}" width="14" height="14" rx="3" fill="${on ? "var(--acc)" : "currentColor"}" opacity="${on ? .85 : .14}"/>`; } return `<svg viewBox="0 0 160 72">${c}</svg>`; },
    agenda: () => { let c = ""; for (let i = 0; i < 14; i++) { const x = 10 + (i % 7) * 20, y = 8 + Math.floor(i / 7) * 30; c += `<rect x="${x}" y="${y}" width="16" height="24" rx="3" fill="currentColor" opacity=".08"/>`; if ([1, 3, 9].includes(i)) c += `<rect x="${x + 3}" y="${y + 4}" width="10" height="4" rx="2" fill="var(--acc)"/>`; if ([2, 3, 8, 10, 11].includes(i)) c += `<rect x="${x + 3}" y="${y + 11}" width="10" height="4" rx="2" fill="currentColor" opacity=".35"/>`; } return `<svg viewBox="0 0 160 72">${c}</svg>`; },
    verifica: () => `<svg viewBox="0 0 160 72">${[0, 1, 2].map((i) => `<circle cx="${30 + i * 50}" cy="30" r="14" fill="${B.colVoto("favor")}" opacity=".16"/><path d="M${23 + i * 50} 30l5 5 9-10" fill="none" stroke="${B.colVoto("favor")}" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>`).join("")}<rect x="16" y="56" width="128" height="5" rx="2.5" fill="currentColor" opacity=".15"/></svg>`,
  };
  // un solo percorso per ogni domanda (agente.py); i passi 3 e 4 valgono per le posizioni dei gruppi su un tema (paper ISWC 2026)
  const TEMA = TT("domande su un tema", "questions on a topic");
  const SEI = [
    [TT("Capisce la domanda", "Understands the question"), TT("Un modello di AI legge la domanda e sceglie quali dati servono: voti, sedute, interventi, schede dei parlamentari, testi di legge, programma dei lavori.", "An AI model reads the question and picks the data it needs: votes, sittings, speeches, member profiles, law texts, the schedule of work."), { chip: [TT("fino a 8 passaggi", "up to 8 steps")] }],
    [TT("Cerca nei dati ufficiali", "Searches official data"), TT("Camera, Senato e Normattiva. Negli interventi cerca per significato; dagli atti risale a chi li ha firmati e ai suoi interventi.", "Chamber, Senate and Normattiva. In speeches it searches by meaning; from acts it moves to who signed them and their speeches."), { chip: [TT("ricerca per significato", "search by meaning"), TT("atti → firmatari → interventi", "acts → signatories → speeches")] }],
    [TT("Ordina le evidenze", "Ranks the evidence"), TT("Unisce i risultati e li ordina con un punteggio pesato. Il contenuto politico pesa più del linguaggio procedurale.", "Merges the results and ranks them with a weighted score. Political content counts more than procedural language."), { tema: true, pesi: [[TT("pertinenza", "relevance"), .35], [TT("salienza", "salience"), .25], [TT("copertura", "coverage"), .20], [TT("diversità", "diversity"), .15], [TT("autorevolezza", "authority"), .05]] }],
    [TT("Una voce per gruppo", "One voice per group"), TT("Per ogni gruppo parla chi segue il tema: commissioni, interventi, atti, professione, formazione, ruoli. Il Misto conta per componente.", "For each group, the member who follows the topic speaks: committees, speeches, acts, profession, education, roles. The Mixed Group counts by component."), { tema: true, pesi: [[TT("commissione", "committee"), .25], [TT("interventi", "speeches"), .25], [TT("atti", "acts"), .20], [TT("professione", "profession"), .15], [TT("formazione", "education"), .10], [TT("ruolo", "role"), .05]] }],
    [TT("Scrive la risposta", "Writes the answer"), TT("I numeri si contano dai dati. Quello che un parlamentare dice in Aula resta una dichiarazione. Il modello non scrive il testo delle citazioni: lo prendiamo dal resoconto.", "Numbers are counted from the data. What a member says on the floor stays a statement. The model does not write quotation text: we take it from the record."), { chip: [TT("conteggi dai dati", "counts from data"), TT("citazioni dal resoconto", "quotes from the record")] }],
    [TT("Controlla prima di mostrare", "Checks before showing"), TT("Toglie i link che non compaiono nei dati letti. Un programma confronta ogni frase tra virgolette con il resoconto.", "Removes links that are not in the data it read. A program compares every quoted sentence with the record."), { chip: [TT("link alla fonte", "source links"), TT("fedeltà citazioni 1,00", "quote faithfulness 1.00")] }],
  ];
  // per ogni passo un esempio disegnato con elementi veri dell'interfaccia (niente dati inventati: solo forme e «…»)
  const ICO_M = ["chiedi", "cerca", "menu", "bilancia", "atto", "scudo"];
  const VIS = [
    () => `<div class="mv-q">${e(TT("Chi ha votato contro la fiducia sulla legge elettorale?", "Who voted against the confidence vote on the electoral law?"))}</div><div class="mv-giu">${B.ico("giu")}</div><div class="mv-tool">${[[TT("Cerco la votazione", "Finding the vote"), "aula"], [TT("Leggo i voti per deputato", "Reading votes by member"), "menu"], [TT("Apro le schede", "Opening profiles"), "atto"]].map(([t, i], k) => `<span style="--k:${k}">${B.ico(i)}${e(t)}</span>`).join("")}</div>`,
    () => `<div class="mv-2"><div><small>${TT("per significato", "by meaning")}</small>${[.92, .81, .74].map((x, k) => `<p style="--k:${k}"><i style="--w:${x * 100}%"></i><em>${String(x.toFixed(2)).replace(".", window.LANG === "en" ? "." : ",")}</em></p>`).join("")}</div><div><small>${TT("dal grafo", "from the graph")}</small><svg viewBox="0 0 200 92" class="mv-g"><g stroke="currentColor" stroke-opacity=".35"><path d="M30 46 90 18M30 46h60M30 46l60 28M106 18h60M106 46h60M106 74h60"/></g><rect x="6" y="34" width="48" height="24" rx="6" class="mv-n1"/><text x="30" y="50" text-anchor="middle">${TT("atto", "act")}</text>${[18, 46, 74].map((y) => `<circle cx="98" cy="${y}" r="8" class="mv-n2"/><rect x="160" y="${y - 7}" width="34" height="14" rx="4" class="mv-n3"/>`).join("")}</svg></div></div>`,
    () => "",
    () => `<div class="mv-gr">${B.ORDINE.filter((g) => !["Governo", "Misto", "MinLing", "SCN", "FNV", "+Europa"].includes(g)).map((g, k) => `<span style="--k:${k};--c:${B.col(g)}" title="${e(B.NOMI[g] || g)}"><i></i>${e(g)}</span>`).join("")}</div>`,
    () => `<div class="mv-cit"><p>${TT("Il modello scrive", "The model writes")}: <code>${TT("la relatrice ha detto", "the rapporteur said")} ⟦c1⟧</code></p><div class="mv-giu">${B.ico("giu")}</div><p>${TT("Noi inseriamo", "We insert")}: <q>…${TT("testo esatto del resoconto", "exact text of the record")}…</q></p></div><div class="m-fasi">${["Analyze", "Generate", "Integrate"].map((f) => `<span>${f}</span>`).join(B.ico("freccia"))}</div>`,
    () => `<ul class="mv-ck"><li class="si">${B.ico("ok")}<span>senato.it/…/Ddliter/56048.htm</span><em>${TT("nei dati", "in the data")}</em></li><li class="no">${B.ico("chiudi")}<span>senato.it/…/pagina-inventata</span><em>${TT("tolto", "removed")}</em></li><li class="si">${B.ico("ok")}<span>«…» = ${TT("resoconto", "record")}</span><em>${TT("verificata", "verified")}</em></li></ul>`,
  ];
  const GAR = [["Tutti i gruppi", "La risposta considera ogni gruppo. Se un gruppo non è intervenuto sul tema, lo scrive. Il Misto è diviso per componente."],
    ["Voci autorevoli", "Per ogni gruppo citiamo chi segue il tema, secondo sei criteri con pesi pubblici, calcolati per ogni domanda."],
    ["Citazioni esatte", "Le frasi tra virgolette risultano dal resoconto e sono della persona a cui le attribuiamo. Se una parola non coincide, togliamo la citazione."]];

  H.prepara = () => {
    $("#avvii").innerHTML = AVVII.slice(0, 3).map((a, i) => `<button ${a.v ? `data-vai="${a.v}"` : `data-chiedi="${e(a.q)}"`} data-avvio="${i}"><b>${e(a.t)}</b><span>${e(a.s)}</span></button>`).join("");
    { const voci = ST.ELENCO.map((x) => `<a href="#/strumenti/${x.k}"><div class="anteprima" aria-hidden="true">${ANTEPRIMA[x.k] ? ANTEPRIMA[x.k]() : ""}</div><div class="sc-t">${B.ico(x.i)}<b>${e(x.t)}</b></div><span>${e(x.d)}</span></a>`).join("") + `<a class="futuro" href="#domande">${B.ico("piu")}<b>Legislature precedenti</b><span>Dati delle legislature prima della XIX, nella chat e qui.</span><small>in arrivo</small></a>`; $("#griglia-str").innerHTML = `<div class="binario"><div class="nastro">${voci}</div><div class="nastro" aria-hidden="true">${voci.replace(/<a /g, '<a tabindex="-1" ')}</div><div class="nastro" aria-hidden="true">${voci.replace(/<a /g, '<a tabindex="-1" ')}</div></div>`; nastro(); };
    // pannelli affiancati: quello sotto il mouse (o col fuoco) si allarga, gli altri si stringono
    $("#sei").innerHTML = SEI.map(([t, d, x], i) => `<li tabindex="0"${i ? "" : ' class="on"'}><div class="m-num"><span class="n">${String(i + 1).padStart(2, "0")}</span>${x.tema ? `<small class="m-tema">${e(TEMA)}</small>` : ""}</div><div class="m-c"><b>${e(t)}</b><span>${e(d)}</span>${x.pesi ? `<div class="m-pesi">${x.pesi.map(([n, w]) => `<div><span>${e(n)}</span><i><b style="width:${w / .35 * 100}%"></b></i><em>${Math.round(w * 100)}%</em></div>`).join("")}</div>` : `<div class="m-chip">${x.chip.map((c) => `<span>${e(c)}</span>`).join("")}</div>`}${VIS[i]() ? `<div class="m-vis">${VIS[i]()}</div>` : ""}</div><span class="m-v" aria-hidden="true">${e(t)}</span><span class="m-ic" aria-hidden="true">${B.ico(ICO_M[i])}</span></li>`).join("");
    { const apri = (li) => { if (!li || li.classList.contains("on")) return; B.$$("#sei > li").forEach((x) => x.classList.toggle("on", x === li)); };
      $("#sei").addEventListener("mouseover", (ev) => apri(ev.target.closest("#sei > li")));
      $("#sei").addEventListener("focusin", (ev) => apri(ev.target.closest("#sei > li"))); }
    $("#tre-g").innerHTML = `<p class="tg-et"><strong>${e(TT("Le tre garanzie", "The three guarantees"))}</strong><span>${e(TT("Le controlla un programma, non un modello di AI, prima di mostrare la risposta.", "A program checks them, not an AI model, before showing the answer."))}</span></p>` + GAR.map(([t, d]) => `<div><span class="tg-i">${B.ico("ok")}</span><b>${e(TR(t))}</b><p>${e(TR(d))}</p></div>`).join("");
    $("#file").innerHTML = ST.FILE.map((f) => `<a href="${f.u}" target="_blank" rel="noopener"><small>${e(f.f)}</small><b>${e(f.n)}</b><span>${e(f.d)}</span></a>`).join("");
    $("#mcp").innerHTML = ST.MCP.map(([a, b]) => `<li><b>${a}</b><span>${b}</span></li>`).join("");
    segnaposto();
    grafo(); oggi(); aulaSfondo(); vetrina();
  };

  /* chi conta su un tema: tre temi che si alternano, la voce più autorevole di ogni gruppo, i pesi che usiamo */
  async function vetrina() {
    const box = $("#vetrina"); if (!box) return;
    let d; try { d = await fetch("/dati-autorevolezza.json").then((r) => r.json()); } catch { return; }
    const CRIT = [["speeches", TT("Interventi in Aula", "Floor speeches")], ["committee", TT("Commissione", "Committee")], ["acts", TT("Atti firmati", "Signed acts")], ["profession", TT("Professione", "Profession")], ["education", TT("Formazione", "Education")], ["role", TT("Ruolo istituzionale", "Institutional role")]];
    const FERMO = matchMedia("(prefers-reduced-motion: reduce)").matches, DURATA = 7000;
    let i = 0, timer = null, pausa = false;
    box.innerHTML = `<div class="vt-sx"><p class="vt-et">${TT("Tema", "Topic")}</p><p class="vt-tema" id="vt-tema"></p>
      <div class="vt-temi" role="tablist">${d.temi.map((t, k) => `<button role="tab" data-vt="${k}"><span>${e(TR(t.tema))}</span><i></i></button>`).join("")}</div>
      <div class="vt-pesi"><p>${TT("Il punteggio è una nostra scelta: somma sei criteri con questi pesi.", "The score is our choice: it adds up six criteria with these weights.")}</p>
      <ul>${CRIT.map(([k, n]) => `<li><span>${n}</span><b style="--w:${d.pesi[k] * 100 * 4}%"></b><em>${Math.round(d.pesi[k] * 100)}%</em></li>`).join("")}</ul>
      <p class="vt-nota">${TT("Non è l'unico modo di misurare chi conta su un tema, e forse nemmeno il migliore. Se per te pesa di più la commissione, o la professione, cambia i pesi: la classifica si ricalcola subito.", "It is not the only way to measure who matters on a topic, and maybe not the best one. If committee work or profession matters more to you, change the weights: the ranking updates at once.")}</p>
      <a class="bt bt--linea" href="#/strumenti/autorevolezza">${B.ico("bilancia")}${TT("Prova i tuoi pesi", "Try your own weights")}</a></div></div>
      <ol class="vt-voci" id="vt-voci"></ol>`;
    const mostra = (k) => {
      i = k; const t = d.temi[k];
      B.$$("[data-vt]", box).forEach((b) => { b.setAttribute("aria-selected", +b.dataset.vt === k); b.classList.remove("corre"); void b.offsetWidth; if (+b.dataset.vt === k && !FERMO) b.classList.add("corre"); });
      const tm = $("#vt-tema"); tm.classList.remove("entra"); void tm.offsetWidth; tm.textContent = TR(t.tema); tm.classList.add("entra");
      const max = Math.max(...t.voci.map((v) => v.punteggio));
      $("#vt-voci").innerHTML = t.voci.map((v, n) => { const p = B.persona(v.id), g = p ? p.sigla : B.sigla(v.gruppo);
        return `<li style="--n:${n}"><a href="#/strumenti/deputato/${e(v.id)}">${B.fotoHtml(p || { id: v.id, n: v.nome, sigla: g })}<span class="vt-n"><b>${e(v.nome)}</b><small><i style="background:${B.col(g)}"></i>${e(B.NOMI[g] || g)}</small></span><span class="vt-s"><b>${window.LANG === "en" ? v.punteggio.toFixed(2) : v.punteggio.toFixed(2).replace(".", ",")}</b><i><u style="--p:${(v.punteggio / max) * 100}%"></u></i></span></a></li>`; }).join("");
    };
    const avanti = () => { if (!pausa) mostra((i + 1) % d.temi.length); };
    const parti = () => { clearInterval(timer); if (!FERMO) timer = setInterval(avanti, DURATA); };
    box.addEventListener("click", (ev) => { const b = ev.target.closest("[data-vt]"); if (b) { mostra(+b.dataset.vt); parti(); } });
    box.addEventListener("mouseenter", () => { pausa = true; box.classList.add("in-pausa"); });
    box.addEventListener("mouseleave", () => { pausa = false; box.classList.remove("in-pausa"); });
    mostra(0); parti();
  }

  /* segnaposto che propone domande diverse */
  function segnaposto() {
    const ta = $("#q-eroe"); if (!ta) return;
    // da telefono il campo è una riga sola: niente domande che si scrivono da sole, gli esempi stanno sopra
    if (matchMedia("(max-width: 760px)").matches) { ta.placeholder = TT("Chiedi al Parlamento", "Ask Parliament"); return; }
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const fr = AVVII.filter((a) => a.q && (window.LANG !== "en" || TR(a.q) !== a.q)).map((a) => TR(a.q)); let i = 0, j = 0, giu = false;
    setInterval(() => {
      if (document.activeElement === ta || ta.value || document.body.dataset.vista) return;
      const f = fr[i];
      if (!giu) { j++; if (j > f.length + 26) giu = true; } else { j -= 3; if (j <= 0) { giu = false; j = 0; i = (i + 1) % fr.length; } }
      ta.placeholder = f.slice(0, Math.min(j, f.length));
    }, 55);
  }

  // nastro continuo: tre copie su un binario, quando una esce del tutto si riparte senza stacco
  function nastro() {
    const g = $("#griglia-str"), b = g && g.querySelector(".binario"); if (!b || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let x = 0, fermo = false, visto = false, prima = performance.now(), w = 0;
    g.addEventListener("mouseenter", () => { fermo = true; }); g.addEventListener("mouseleave", () => { fermo = false; });
    // larghezza letta solo quando cambia, non a ogni fotogramma: leggerla forzava il ricalcolo durante lo scorrimento
    const misura = () => { w = b.firstElementChild ? b.firstElementChild.offsetWidth : 0; };
    new ResizeObserver(misura).observe(b); misura();
    // fuori dallo schermo il nastro si ferma
    new IntersectionObserver(([v]) => { visto = v.isIntersecting; prima = performance.now(); }).observe(g);
    // frecce in alto a destra: il nastro avanza o torna di una scheda, poi riparte da solo dopo qualche secondo
    let salto = null, pausa = 0;
    const giro = () => { let d = 0; while (w && -x >= w) { x += w; d += w; } while (w && x > 0) { x -= w; d -= w; } if (d && salto) { salto.da += d; salto.a += d; } };
    B.giostra = (dir) => {
      const card = b.querySelector("a"), lungo = (card ? card.offsetWidth : 300) + 14;
      salto = { da: x, a: (salto ? salto.a : x) - dir * lungo, t0: performance.now() };
      pausa = performance.now() + 7000;
      return true;
    };
    const passo = (t) => {
      const dt = Math.min(64, t - prima); prima = t;
      if (salto) { const k = Math.min(1, (t - salto.t0) / 420), e = 1 - Math.pow(1 - k, 3); x = salto.da + (salto.a - salto.da) * e; if (k >= 1) salto = null; }
      else if (visto && !fermo && w && t > pausa) x -= dt * 0.04;
      giro();
      b.style.transform = `translate3d(${x}px,0,0)`;
      requestAnimationFrame(passo);
    };
    requestAnimationFrame(passo);
  }

  /* ---------- apertura: l'emiciclo vero della Camera, in trasparenza ---------- */
  function aulaSfondo() {
    const svg = $("#eroe-aula"); if (!svg || !window.AULA) return;
    const disegna = () => {
      svg.setAttribute("viewBox", "0 0 2552 1760");
      svg.innerHTML = AULA.seats.map((x) => `<circle cx="${x.x}" cy="${x.y}" r="15" fill="${x.g ? B.col(x.g) : "currentColor"}"${x.g ? "" : ' opacity=".35"'}/>`).join("");
    };
    disegna(); H.ridisegna = disegna;
  }

  /* ---------- apertura: ultime votazioni finali, in diretta ---------- */
  async function oggi() {
    const ol = $("#oggi-v"); if (!ol) return;
    let righe;
    // le prepara il servizio, una volta ogni ora (api/sito_parlamentari.py, ultimi_voti): una richiesta sola
    try { const r = await fetch("/dati/ultimi-voti.json"); if (!r.ok) throw new Error(r.status); righe = await r.json(); }
    catch (err) { ol.innerHTML = `<li class="oggi__car">${TT("Non riesco a leggere le sedute ora. Riprova tra poco.", "I can't read the sittings right now. Try again shortly.")}</li>`; return; }
    if (!righe.length) { ol.innerHTML = `<li class="oggi__car">${TT("Nessuna votazione finale nelle ultime sedute.", "No final votes in the latest sittings.")}</li>`; return; }
    ol.innerHTML = righe.map(({ v, s }) => {
      const tot = (v.in_favor + v.against + v.abstained) || 1, ok = /^approv/.test(v.outcome);
      const tit = B.frase((v.description || v.act_title || v.subject).replace(/\s*\((?:approvat|modificat|PDL|DDL)[^)]*\)/gi, "").replace(/, comprensiva dell'errata corrige/i, ""));
      return `<li><a href="#/strumenti/voto/${e(v.id)}"><small>${B.data(s.date)} · ${s.chamber === "senato" ? "Senato" : "Camera"}${v.act_number && v.act_number.length < 12 ? ` · ${s.chamber === "senato" ? "DDL" : "PDL"} ${e(v.act_number)}` : ""}</small><b data-tr>${e(B.taglia(tit, 110))}</b><em style="color:${B.colVoto(ok ? "favor" : "against")}">${ok ? "Approvata" : "Respinta"}</em><div class="bv"><span><i style="width:${v.in_favor / tot * 100}%;background:${B.colVoto("favor")}"></i><i style="width:${v.against / tot * 100}%;background:${B.colVoto("against")}"></i><i style="width:${v.abstained / tot * 100}%;background:${B.colVoto("abstain")}"></i></span>${v.in_favor} ${TT("sì", "yes")} · ${v.against} no${v.abstained ? ` · ${v.abstained} ${TT("ast.", "abst.")}` : ""}</div></a></li>`;
    }).join("");
  }

  /* ---------- grafo: schema dell'ontologia e due votazioni vere, in triple ---------- */
  // Schema del grafo dei dati; sotto ogni nodo la classe RDF dell'esportazione
  const CLASSI = [
    { k: "se", c: "Session", s: "pr:Session", x: 1430, y: 240 },
    { k: "db", c: "Debate", s: "pr:Debate", x: 1430, y: 420 },
    { k: "ph", c: "Phase", s: "pr:Phase", x: 1110, y: 780 },
    { k: "sp", c: "Speech", s: "pr:Speech", x: 790, y: 780 },
    { k: "ch", c: "Chunk", s: "testo indicizzato", x: 790, y: 600 },
    { k: "iv", c: "IndividualVote", s: "ocd:voto", x: 790, y: 60 },
    { k: "v", c: "Vote", s: "ocd:votazione", x: 1110, y: 60 },
    { k: "a", c: "ParliamentaryAct", s: "ocd:atto", x: 1110, y: 240 },
    { k: "t", c: "EurovocConcept", s: "skos:Concept", x: 1430, y: 60 },
    { k: "p", c: "Person", s: "foaf:Person", x: 470, y: 420 },
    { k: "am", c: "Amendment", s: "pr:Amendment", x: 790, y: 240 },
    { k: "lp", c: "LegislativeProcess", s: "pr:LegislativeProcess", x: 1110, y: 420 },
    { k: "mc", c: "MistoComponent", s: "org:Organization", x: 150, y: 240 },
    { k: "g", c: "ParliamentaryGroup", s: "org:Organization", x: 150, y: 420 },
    { k: "co", c: "Committee", s: "org:Organization", x: 470, y: 600 },
    { k: "gv", c: "Government", s: "org:Organization", x: 470, y: 240 },
    { k: "l", c: "Law", s: "eli:LegalResource", x: 1110, y: 600 },
    { k: "tv", c: "TextVersion", s: "pr:TextVersion", x: 790, y: 420 },
  ];
  // [da, relazione, a, posizione dell'etichetta, scostamento, predicato RDF]
  const PROP = [["se", "HAS_DEBATE", "db", .5, 0, "dcterms:hasPart"], ["db", "HAS_PHASE", "ph", .5, 0, "dcterms:hasPart"], ["ph", "CONTAINS_SPEECH", "sp", .5, 0, "dcterms:hasPart"], ["sp", "HAS_CHUNK", "ch", .5, 0, ""],
    ["sp", "SPOKEN_BY", "p", .5, 0, "pr:spokenBy"], ["ch", "MENTIONS", "p", .5, 0, "schema:mentions"], ["ch", "CITES", "a", .5, 0, "dcterms:references"], ["db", "DISCUSSES", "a", .5, 0, "pr:discusses"],
    ["se", "HAS_VOTE", "v", .5, 0, "pr:heldVote"], ["p", "VOTED", "iv", .55, 0, "pr:voter"], ["iv", "ON_VOTE", "v", .5, 0, "pr:onVote"], ["v", "ON_ACT", "a", .5, 0, "pr:onAct"], ["v", "ON_AMENDMENT", "am", .5, 0, "pr:onAmendment"],
    ["p", "PRIMARY_SIGNATORY · CO_SIGNATORY", "a", .66, -9, "pr:primarySignatoryOf"], ["a", "REPORTED_BY", "p", .34, -9, "pr:reportedBy"], ["p", "SIGNED_AMENDMENT", "am", .34, 0, "pr:coSignatoryOf"], ["am", "AMENDS", "a", .5, 0, "pr:amends"],
    ["a", "HAS_SUBJECT", "t", .5, 0, "dcterms:subject"], ["a", "PART_OF", "lp", .5, 0, "dcterms:isPartOf"], ["lp", "BECAME_LAW", "l", .5, 0, "prov:generated"], ["a", "HAS_VERSION", "tv", .5, 0, "dcterms:hasVersion"],
    ["p", "MEMBER_OF_GROUP", "g", .5, 0, "org:Membership"], ["p", "MEMBER_OF_COMPONENT", "mc", .5, 0, "org:Membership"], ["p", "MEMBER_OF_COMMITTEE", "co", .5, 0, "org:Membership"], ["p", "HOLDS_OFFICE", "gv", .5, 0, "org:Post"]];

  async function grafo() {
    const svg = $("#kg-svg"); if (!svg) return;
    const SCH = Object.fromEntries(CLASSI.map((n) => [n.k, n]));
    const H = 44;
    const FAM = { se: "proc", db: "proc", ph: "proc", sp: "proc", ch: "proc", iv: "voti", v: "voti", a: "atti", am: "atti", lp: "atti", l: "atti", tv: "atti", t: "atti", p: "pers", g: "org", mc: "org", co: "org", gv: "org" };
    const casella = (n) => `<g class="kg-n kg-n--${FAM[n.k] || "proc"}" data-n="${n.k}"><rect x="${n.x - 60}" y="${n.y - H / 2}" width="120" height="${H}" rx="${H / 2}"/><circle class="kg-pt" cx="${n.x - 44}" cy="${n.y}" r="5"/><text class="c" x="${n.x + 8}" y="${n.y + 5.5}">${e(n.c)}</text></g>`;
    svg.setAttribute("viewBox", "0 0 1580 830");
    svg.innerHTML = `<defs><marker id="kg-fr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z"/></marker></defs><g class="kg-archi"></g>${CLASSI.map(casella).join("")}`;
    // larghezze misurate sul testo vero
    CLASSI.forEach((n) => { const g = svg.querySelector(`[data-n="${n.k}"]`), t = g.querySelector("text"), w = t.getBBox().width + 54, r = g.querySelector("rect"), pt = g.querySelector(".kg-pt"); n.w = w; r.setAttribute("x", n.x - w / 2); r.setAttribute("width", w); pt.setAttribute("cx", n.x - w / 2 + 20); t.setAttribute("x", n.x - w / 2 + 34); t.setAttribute("text-anchor", "start"); });
    const bordo = (n, ox, oy) => { const w = n.w / 2, h = H / 2, dx = ox - n.x, dy = oy - n.y; const t = Math.min(dx ? w / Math.abs(dx) : 1e9, dy ? h / Math.abs(dy) : 1e9); return [n.x + dx * t, n.y + dy * t]; };
    const arco = ([a, p, b, u, o, rdf, via]) => {
      const A = SCH[a], Bn = SCH[b];
      if (via) { const [cx, cy] = via, [x1, y1] = bordo(A, cx, cy), [x2, y2] = bordo(Bn, cx, cy), q = 1 - u, lx = q * q * x1 + 2 * q * u * cx + u * u * x2, ly = q * q * y1 + 2 * q * u * cy + u * u * y2;
        return `<g class="kg-e" data-a="${a}" data-b="${b}"><path d="M${x1.toFixed(1)},${y1.toFixed(1)} Q${cx},${cy} ${x2.toFixed(1)},${y2.toFixed(1)}" marker-end="url(#kg-fr)"/><text x="${lx - 6}" y="${ly - 6}" text-anchor="end">${e(p)}</text></g>`; }
      let [x1, y1] = bordo(A, Bn.x, Bn.y), [x2, y2] = bordo(Bn, A.x, A.y);
      if (o) { const L = Math.hypot(x2 - x1, y2 - y1), nx = -(y2 - y1) / L * o, ny = (x2 - x1) / L * o; x1 += nx; y1 += ny; x2 += nx; y2 += ny; }
      const lx = x1 + (x2 - x1) * u, ly = y1 + (y2 - y1) * u, vert = Math.abs(x2 - x1) < 4;
      return `<g class="kg-e" data-a="${a}" data-b="${b}"><path d="M${x1.toFixed(1)},${y1.toFixed(1)} L${x2.toFixed(1)},${y2.toFixed(1)}" marker-end="url(#kg-fr)"/><text x="${vert ? lx + 10 : lx}" y="${vert ? ly + 4 : ly - 7}" text-anchor="${vert ? "start" : "middle"}">${e(p)}</text></g>`;
    };
    svg.querySelector(".kg-archi").innerHTML = PROP.map(arco).join("");
    svg.addEventListener("mouseover", (ev) => { const g = ev.target.closest(".kg-n"); svg.querySelectorAll(".kg-e").forEach((x) => x.classList.toggle("acc", !!g && (x.dataset.a === g.dataset.n || x.dataset.b === g.dataset.n))); svg.classList.toggle("fuoco", !!g); });
    $("#didascalia").innerHTML = `<span><b>${CLASSI.length}</b> tipi di nodo</span><span><b>${PROP.length}</b> relazioni</span><span><b>863.834</b> triple nell'export</span><span>CC BY-SA 4.0</span>`;
  }

  // «Ne hanno parlato»: i loghi scorrono in un nastro continuo; la seconda copia serve solo a chiudere il giro
  const stampa = $("#riconoscimenti .stampa");
  if (stampa && !matchMedia("(prefers-reduced-motion: reduce)").matches) {
    [...stampa.children].forEach((li) => {
      const c = li.cloneNode(true); c.setAttribute("aria-hidden", "true"); c.querySelector("a")?.setAttribute("tabindex", "-1"); stampa.appendChild(c);
    });
    stampa.parentElement.classList.add("scorre");
  }
})();

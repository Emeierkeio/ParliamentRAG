/* Conversazione: una domanda, tutti gli strumenti.
   La risposta in prosa viene dall'agente (/api/agente, streaming); l'instradatore aggiunge in parallelo
   posizioni per gruppo, atti, sedute, voti con l'Aula e, alla fine, la verifica delle tre garanzie (verify_answer). */
(function () {
  const { $, esc: e } = B;
  const CH = (window.CH = {});
  const storia = [];
  let nTurno = 0;

  const VUOTE = new Set("a ad al alla alle ai agli all che chi cosa come con da dal dalla dai dei del della delle degli di e ed è fra gli ha hanno ho i il in la le lo ma mi ne nel nella nei non o per perché più qual quale quali quando quanto quanti questo questa se si sono su sul sulla sui tra un una uno vs gruppi gruppo partiti partito detto dice dicono parlato parla parlano pensano pensa posizione posizioni camera senato parlamento aula deputati deputato senatori legislatura votato voto voti votazione votazioni cos com dove ieri oggi tutti stati stata stato fatto contro favore chi quanti quante ultima ultime ultimo come andata andato finita finito successo".split(" "));
  CH.parole = (q) => B.norm(q).replace(/[«»"“”?!.,;:()']/g, " ").split(/\s+/).filter((w) => w.length > 2 && !VUOTE.has(w));

  /* ---------- markdown minimo e riferimenti ---------- */
  CH.pulisci = (t) => String(t || "").replace(/\n{3,}/g, "\n\n");
  const prosa = (t, nT) => e(CH.pulisci(t)).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\[([^\]\n]+)\]\(((?:https?:\/\/|#\/)[^\s)]+)\)/g, (m, tx, u) => `<a href="${u}"${u.startsWith("#") ? "" : ' target="_blank" rel="noopener"'}>${tx}</a>`)
    .replace(/«([^«»\n]{3,}?)»/g, "<q>$1</q>").replace(/\[(\d+(?:\s*,\s*\d+)*)\]/g, (m, ns) => ns.split(/\s*,\s*/).map((n) => `<button class="rif" data-fonte="${nT}-${n}" aria-label="Fonte ${n}">${n}</button>`).join(""))
    .split(/\n{2,}/).map((p) => p.split(/\n/).reduce((acc, l) => { const el = /^\s*[-•]\s/.test(l); const ult = acc[acc.length - 1]; if (ult && ult.el === el) ult.r.push(l); else acc.push({ el, r: [l] }); return acc; }, [])
      .map((g) => g.el ? `<ul>${g.r.map((l) => `<li>${l.replace(/^\s*[-•]\s*/, "")}</li>`).join("")}</ul>` : `<p>${g.r.join("<br>")}</p>`).join("")).join("");

  // il testo arriva già controllato e si scrive una parola alla volta: al massimo tre secondi circa
  const scrivi = (el, t, nT) => new Promise((ok) => {
    const parole = t.split(/(\s+)/), fine = () => { el.innerHTML = prosa(t, nT); ok(); };
    if (matchMedia("(prefers-reduced-motion: reduce)").matches || parole.length < 8) return fine();
    const passo = Math.max(1, Math.ceil(parole.length / 200)); let k = 0;
    const via = () => { k = Math.min(parole.length, k + passo * 2); el.innerHTML = prosa(parole.slice(0, k).join(""), nT); if (k < parole.length) setTimeout(via, 28); else fine(); };
    via();
  });

  /* ---------- passi ---------- */
  // quanti dibattiti distinti (ramo, seduta, titolo) parlano del tema fra i primi 30 interventi; null se la ricerca non risponde
  async function contaDibattiti(t, q) {
    const sd = passo(t, "dibattiti", TT("Conto i dibattiti sul tema", "Counting debates on the topic"), "search_parliament · distinct(seduta, dibattito)");
    try {
      const chiave = CH.parole(q).slice(0, 4).join(" ");
      const r = await B.mcp("search_parliament", { query: chiave, doc_type: "speech", max_results: 30 });
      const xs = (r.dati.results || []).filter((x) => x.score == null || x.score >= .55);
      const d = new Set(xs.map((x) => `${x.chamber}|${x.session_number}|${String(x.debate_title || "").slice(0, 60)}`));
      sd.fatto(TT(`${d.size} dibattiti`, `${d.size} debates`));
      return d.size;
    } catch (err) { sd.errore(); return null; }
  }
  function passo(t, id, testo, chiamata) {
    let li = t.passi.querySelector(`[data-id="${id}"]`);
    if (!li) { li = document.createElement("li"); li.dataset.id = id; li.className = "corre"; li.innerHTML = `<span class="p">${B.ico("ok")}</span><span>${e(testo)}${chiamata ? `<span class="call">${e(chiamata)}</span>` : ""}</span><span class="num"></span>`; t.passi.appendChild(li); }
    return { fatto: (num) => { li.classList.remove("corre"); if (num != null) li.querySelector(".num").textContent = num; }, errore: () => { li.classList.remove("corre"); li.querySelector(".num").textContent = "non disponibile"; } };
  }
  function blocco(t, chiave, titolo, dx, html, prima) {
    if (t.annullato && chiave !== "risposta") return document.createElement("section");
    let b = t.el.querySelector(`[data-blocco="${chiave}"]`);
    if (!b) { b = document.createElement("section"); b.className = "blocco"; b.dataset.blocco = chiave; b.id = `t${t.n}-${chiave}`; const pos = ORDINE_B.indexOf(chiave); const dopo = B.$$("[data-blocco]", t.blocchi).find((x) => ORDINE_B.indexOf(x.dataset.blocco) > pos); dopo ? t.blocchi.insertBefore(b, dopo) : t.blocchi.appendChild(b); if (t.trattieni && chiave !== "risposta") b.hidden = true; aggiornaIndice(t); }
    b.innerHTML = `<h3>${e(titolo)}${dx ? `<span class="dx">${dx}</span>` : ""}</h3>${html}`;
    return b;
  }
  const ORDINE_B = ["risposta", "classifica", "garanzie", "posizioni", "voti", "persona", "interventi", "schede", "atti", "sedute", "fonti"];
  const NOMI_BLOCCHI = { risposta: "Risposta", garanzie: "Garanzie", posizioni: "Per gruppo", voti: "Voti e Aula", persona: "Persona", interventi: "Interventi", atti: "Atti", sedute: "Sedute", schede: "Schede", fonti: "Fonti", classifica: "Classifica" };
  // l'indice serve solo quando la risposta ha almeno due parti oltre al testo
  function aggiornaIndice(t) {
    const bs = B.$$("[data-blocco]", t.blocchi).filter((b) => !b.hidden);
    t.indice.hidden = bs.filter((b) => b.dataset.blocco !== "risposta").length < 2;
    t.indice.innerHTML = t.indice.hidden ? "" : `<div class="indice-r__in"><span class="occ" style="margin:0;padding:5px 4px">${TT("In questa risposta", "In this answer")}</span>` + bs.map((b) => `<a href="#${b.id}" data-salta>${NOMI_BLOCCHI[b.dataset.blocco] || b.dataset.blocco}</a>`).join("") + `</div>`;
  }

  /* ---------- voti e Aula ---------- */
  async function dettaglioVoto(id) { const r = await B.mcp("get_vote_details", { vote_id: id, include_individual_votes: true }); return r.dati; }
  CH.aulaVoto = async (contenitore, voto) => {
    contenitore.innerHTML = `<div class="carica" role="status"><span class="vh">Apro la votazione e il voto di ogni parlamentare</span><i></i><i></i><i></i></div>`;
    try {
      const d = await dettaglioVoto(voto.id);
      const senato = /^senato/.test(voto.id) || voto.ramo === "senato";
      let aula;
      if (d.secret_vote) aula = `<div class="avviso">Voto segreto: i voti dei singoli non sono pubblici.</div>`;
      else if (senato) { await B.caricaSenato().catch(() => {}); } if (!d.secret_vote && senato) aula = (d.individual_votes || []).length && B.SEN ? B.emicicloSenato(d.individual_votes, `${d.subject}: ${d.in_favor} favorevoli, ${d.against} contrari, ${d.abstained} astenuti`) + B.legendaVoto() + `<p class="nota-r">${TT("Pianta reale dei posti del Senato", "Actual Senate seating plan")} ${B.info(TT("Posti da senato.it, «Dove siedono i senatori». I cerchi vuoti sono assenti o posti liberi.", "Seats from senato.it, «Where senators sit». Empty circles are absent members or free seats."))}</p>` : `<div class="avviso">${TT("Voti individuali non disponibili.", "Individual votes not available.")}</div>`;
      else { const vs = B.votiSeggi(d.individual_votes); aula = B.emiciclo({ voti: vs, etichetta: `${d.subject}: ${d.in_favor} favorevoli, ${d.against} contrari, ${d.abstained} astenuti` }) + B.legendaVoto(); contenitore.dataset.titoloVoto = d.subject; }
      const legge = (d.acts || []).map((a) => a.law).find(Boolean), atto = (d.acts || [])[0];
      const gruppi = (d.breakdown_by_group || []).map((b) => ({ ...b, sigla: B.sigla(b.party) })).sort((a, b) => B.ORDINE.indexOf(a.sigla) - B.ORDINE.indexOf(b.sigla));
      const [t, k] = B.esito(d);
      contenitore.innerHTML = `<div class="aula-v"><div>${aula}</div><div style="display:grid;gap:12px;min-width:0"><p class="cap" data-tr>${e(d.subject)}</p>
        <div><span class="badge badge--${k}">${t}</span> <span class="badge badge--neutro">${senato ? "Senato" : "Camera"}${voto.data ? " · " + B.data(voto.data) : ""}</span></div>
        <div class="grandi"><div><b>${d.in_favor}</b><span>sì</span></div><div><b>${d.against}</b><span>no</span></div><div><b>${d.abstained}</b><span>astenuti</span></div></div>
        ${d.description ? `<p style="margin:0;font-size:14px;color:var(--t2)" data-tr>${e(B.taglia(d.description, 220))}</p>` : ""}
        ${((sig) => { // atto, legge e pagina del voto come righe da toccare, non icone sparse
          const r = [];
          if (atto && atto.url) r.push(`<a class="colleg" href="${e(B.interno(atto.url, `${sig} ${atto.number} · ${atto.title}`))}">${B.ico("atto")}<span><b>${sig} ${e(atto.number || "")}</b><small data-tr>${e(B.taglia(atto.subject || atto.title, 110))}</small></span>${B.ico("dx")}</a>`);
          if (legge) r.push(`<a class="colleg" href="${e(legge.eli || legge.normattiva_url)}" target="_blank" rel="noopener">${B.ico("legge")}<span><b>${e(legge.label)}</b><small>${TT("Testo pubblicato su Normattiva", "Published text on Normattiva")}</small></span>${B.ico("esterno")}</a>`);
          if (!location.hash.includes(voto.id)) r.push(`<a class="colleg" href="#/strumenti/voto/${encodeURIComponent(voto.id)}">${B.ico("voto")}<span><b>${TT("La votazione", "The vote")}</b><small>${TT("L'Aula seggio per seggio e il voto dei gruppi", "The floor seat by seat and how groups voted")}</small></span>${B.ico("dx")}</a>`);
          return r.length ? `<div class="collegati">${r.join("")}</div>` : "";
        })(voto.ramo === "senato" || /^senato/.test(voto.id) ? "S." : "C.")}</div></div>
        <div class="gr-voti" role="table" aria-label="${TT("Voto per gruppo", "Vote by group")}">${gruppi.map((b) => `<div class="gr-voti__r" role="row"><span role="cell">${B.sig(b.sigla)}</span><span role="cell">${B.barraLati(b.favor, b.against, b.abstain, b.absent)}</span><span role="cell" class="gr-voti__n"><b style="color:${B.colVoto("favor")}">${b.favor}</b><b style="color:${B.colVoto("abstain")}">${b.abstain}</b><b style="color:${B.colVoto("against")}">${b.against}</b></span></div>`).join("")}</div>`;
    } catch (err) { contenitore.innerHTML = `<div class="errore">Non riesco ad aprire la votazione: ${e(err.message)}</div>`; }
  };
  function bloccoVoti(t, voti, nota) {
    t.voti = t.voti || [];
    voti.forEach((v) => { if (!t.voti.some((x) => x.id === v.id)) t.voti.push(v); });
    if (!t.voti.length) return;
    const b = blocco(t, "voti", "Voti e Aula", nota || `${t.voti.length} ${t.voti.length === 1 ? "votazione" : "votazioni"}`,
      `<div class="sel-voti" role="group" aria-label="Votazione">${t.voti.map((v, i) => { const [es] = B.esito(v); return `<button data-voto-i="${i}" aria-pressed="${i === 0}"><b data-tr>${e(B.taglia(v.titolo || v.subject, 70))}</b><small>${B.ramo(v.ramo)} · ${v.data ? B.data(v.data) + " · " : ""}${es} ${v.in_favor ?? ""}${v.in_favor != null ? ` ${TT("a", "to")} ` + v.against : ""}</small></button>`; }).join("")}</div><div class="aula-box"></div>`, "atti");
    b._voti = t.voti;
    CH.aulaVoto(b.querySelector(".aula-box"), t.voti[0]);
  }

  /* ---------- instradatore: quali strumenti per questa domanda ---------- */

  /* ---------- cosa chiede la domanda ----------
     classifica: una misura su tutti i deputati («chi ha partecipato meno ai voti?»)
     tema: un confronto fra gruppi («cosa hanno detto i gruppi sul salario minimo?»)
     puntuale: tutto il resto, che risponde la chat senza le sezioni per gruppo */
  const METRICHE = [
    { k: "pp", re: /partecip|particip|present|attendance|turnout/, nome: TT("partecipazione ai voti", "participation in votes"), unita: (v) => `${window.LANG === "en" ? String(v) : String(v).replace(".", ",")}%`, basso: true },
    { k: "ass", re: /assen|absen/, nome: TT("assenze nelle votazioni", "absences from votes"), unita: (v) => B.num(v), basso: false },
    { k: "sp", re: /intervent|parlat|speech|spoke|speak/, nome: TT("interventi in Aula", "floor speeches"), unita: (v) => B.num(v), basso: false },
    { k: "ap", re: /prim[ao] firm|propost|atti|present[ao]t|bills?|first signator|sponsor/, nome: TT("atti con la prima firma", "acts as first signatory"), unita: (v) => B.num(v), basso: false },
    { k: "ac", re: /cofirm|firmat|cosign|co-sign/, nome: TT("atti cofirmati", "co-signed acts"), unita: (v) => B.num(v), basso: false },
  ];
  CH.intento = (q) => {
    const n = B.norm(q);
    if (/\bemendament|\bamendment/.test(n)) return { tipo: "emendamento" };
    if (/\b(quanti anni|eta|nat[oa]|nascita|compleanno|dove e nat|collegio|circoscrizion|elett[oa]|proclamat|convalid|how old|age|born|birth|constituency|district|elected)\b/.test(n)) return { tipo: "anagrafica" };
    const superl = /\b(meno|piu|maggior|minor|massim|minim|ultim|peggior|miglior|record|least|most|lowest|highest|fewest|worst|best)\w*/.test(n);
    const metrica = METRICHE.find((x) => x.re.test(n));
    // classifica: un superlativo con una misura, oppure un seguito («e il meno?») della classifica precedente
    const seguito = superl && !metrica && CH.ultimoIntento && CH.ultimoIntento.tipo === "classifica" && n.split(/\s+/).length <= 6;
    const classifica = superl && (metrica || seguito);
    if (classifica) { const m = metrica || CH.ultimoIntento.m; if (m) { const meno = /\b(meno|minor|minim|ultim|peggior|least|lowest|fewest|worst)\w*/.test(n); return { tipo: "classifica", m, asc: m.k === "ass" ? meno : (meno ? true : !/\b(piu|maggior|massim|miglior|most|highest|best)\w*/.test(n) && m.basso) }; } }
    if (/\b(gruppi|partiti|posizion|dibattit|opposizion|maggioranza|confronto|cosa (hanno|ne) (detto|pensano)|cosa dicono|groups|parties|positions|debate|opposition|majority|compare|what did .* say|what do .* think)\b/.test(n)) return { tipo: "tema" };
    // poche parole senza domanda («tartufo», «salario minimo»): l'attività più recente sull'argomento
    if (!/\?/.test(q) && n.split(/\s+/).filter(Boolean).length <= 4 && !/^(chi|cosa|come|quando|quanti|quale|perche|dove|who|what|how|when|which|why|where)\b/.test(n)) return { tipo: "argomento" };
    return { tipo: "puntuale" };
  };

  async function classifica(t, it, prosaEl) {
    const s = passo(t, "classifica", "Leggo le schede di tutti i deputati", "schede deputati · dati.camera.it");
    const r = await fetch("/dati/schede/indice.json").then((x) => x.json());
    const presenze = it.m.k === "pp" || it.m.k === "ass", senzaGov = presenze && !it.conGoverno;
    const xs = r.deputati.filter((d) => d[it.m.k] != null && (it.m.k !== "pp" || d.tot > 0) && !(senzaGov && d.gov)).sort((a, b) => it.asc ? a[it.m.k] - b[it.m.k] : b[it.m.k] - a[it.m.k]);
    s.fatto(`${xs.length} deputati`);
    const primo = xs[0], dieci = xs.slice(0, 10), p = B.persona(primo.id) || { id: primo.id, n: primo.n, sigla: primo.g };
    const versoN = it.asc ? TT("il numero più basso", "the lowest number") : TT("il numero più alto", "the highest number");
    const frase = it.m.k === "pp" ? TT(`${it.asc ? "La partecipazione ai voti più bassa" : "La partecipazione ai voti più alta"} è di <strong>${e(primo.n)}</strong> (${e(B.NOMI[primo.g] || primo.g)}): ${it.m.unita(primo.pp)} delle ${B.num(primo.tot)} votazioni elettroniche della legislatura.`,
        `<strong>${e(primo.n)}</strong> (${e(B.NOMI[primo.g] || primo.g)}) has the ${it.asc ? "lowest" : "highest"} participation in votes: ${it.m.unita(primo.pp)} of the ${B.num(primo.tot)} electronic votes of the legislature.`)
      : TT(`${e(primo.n)} (${e(B.NOMI[primo.g] || primo.g)}) ha ${versoN} di ${it.m.nome}: <strong>${it.m.unita(primo[it.m.k])}</strong>.`, `${e(primo.n)} (${e(B.NOMI[primo.g] || primo.g)}) has ${versoN} of ${it.m.nome}: <strong>${it.m.unita(primo[it.m.k])}</strong>.`);
    prosaEl.innerHTML = `<p>${frase}</p>${presenze ? `<p class="nota-r">${senzaGov ? TT("Esclusi i membri del governo", "Government members excluded") : TT("Compresi i membri del governo", "Government members included")} ${B.info(TT("Chi ha un incarico di governo risulta quasi sempre «in missione»: nei dati della Camera la missione conta come assenza.", "Government members are almost always recorded as «on mission»: in the Chamber's data a mission counts as an absence."))}<button class="bt-mini" data-chiedi-cl="${e(t.q)}" data-gov="${senzaGov ? 1 : 0}">${senzaGov ? TT("Includili", "Include them") : TT("Escludili", "Exclude them")}</button></p>` : ""}`;
    prosaEl.classList.remove("cursore");
    blocco(t, "classifica", `Classifica: ${it.m.nome}`, `${B.info(`Dati di dati.camera.it al ${B.data(r.dataAsOf)}. ${it.m.k === "pp" || it.m.k === "ass" ? "Le assenze comprendono le missioni." : ""}`)}`,
      `<ol class="classifica">${dieci.map((d, i) => { const pp = B.persona(d.id) || { id: d.id, n: d.n, sigla: d.g }; return `<li><span class="pos-n">${i + 1}</span>${B.fotoHtml(pp)}<span class="cl-nome"><b>${e(d.n)}</b>${B.sig(d.g)}</span><span class="cl-val">${it.m.unita(d[it.m.k])}</span>${B.link(`#/strumenti/deputato/${d.id}`, `Apri la scheda di ${d.n}`)}</li>`; }).join("")}</ol>`);
    return `${primo.n}: ${it.m.nome} ${it.m.unita(primo[it.m.k])}`;
  }

  CH.trovaPersona = (q) => { const tutti = [...B.persone(), ...B.senatori()]; return tutti.find((p) => B.norm(q).includes(B.norm(p.n))) || (() => { const c = tutti.filter((p) => { const s = B.norm(p.n.split(" ").pop()); return s.length > 4 && new RegExp(`\\b${s}\\b`).test(B.norm(q)); }); return c.length === 1 ? c[0] : null; })(); };
  async function anagrafica(t, persona, prosaEl) {
    const s = passo(t, "anagrafica", `Leggo l'anagrafica di ${persona.n}`, "dati.camera.it · SPARQL");
    const a = await B.anagrafica(persona.id); s.fatto("");
    const tipo = TT({ maggioritario: "collegio uninominale", proporzionale: "listino proporzionale" }[a.tipo] || a.tipo || "", { maggioritario: "single-member district", proporzionale: "proportional list" }[a.tipo] || a.tipo || "");
    const righe = [a.nascita && TT(`<p><strong>${e(persona.n)}</strong> ha <strong>${a.eta} anni</strong>: data di nascita ${B.data(a.nascita)}${a.luogo ? `, a ${e(a.luogo)}` : ""}.</p>`, `<p><strong>${e(persona.n)}</strong> is <strong>${a.eta}</strong>: born on ${B.data(a.nascita)}${a.luogo ? ` in ${e(a.luogo)}` : ""}.</p>`),
      a.coll && TT(`<p>Elezione: ${e(a.coll)}, ${e(tipo)}, ${B.data(a.elezione)}. Proclamazione ${B.data(a.inizio)}${a.convalida ? `, convalida ${B.data(a.convalida)}` : ""}.</p>`, `<p>Election: ${e(a.coll)}, ${e(tipo)}, ${B.data(a.elezione)}. Proclaimed ${B.data(a.inizio)}${a.convalida ? `, election validated ${B.data(a.convalida)}` : ""}.</p>`)].filter(Boolean);
    prosaEl.innerHTML = (righe.join("") || TT(`<p>La Camera non pubblica questi dati per ${e(persona.n)}.</p>`, `<p>The Chamber does not publish these data for ${e(persona.n)}.</p>`)) + `<p class="nota-r">dati.camera.it ${B.link(a.fonte, TT("Apri la fonte su dati.camera.it", "Open the source on dati.camera.it"))}</p>`;
    prosaEl.classList.remove("cursore");
    return prosaEl.innerText;
  }
  // la scheda del parlamentare dentro la risposta: foto, gruppo, cariche in corso e numeri, con il link alla scheda intera
  async function schedaPersona(t, p) {
    const sen = !!p.senato, url = sen ? `#/strumenti/senatore/${p.id}` : `#/strumenti/deputato/${p.id}`;
    const foto = sen ? `<span class="foto"><img src="/dati/foto/senatori/${e(p.id)}.jpg" alt="" onerror="this.remove()"></span>` : B.fotoHtml(p);
    const d = await fetch(sen ? `/dati/senatori/${encodeURIComponent(p.id)}.json` : `/dati/schede/${encodeURIComponent(p.id)}.json`).then((r) => (r.ok ? r.json() : null)).catch(() => null);
    let dati = "";
    if (d) {
      const c = d.counts || {}, v = d.votes || {}, num = (x) => (x == null ? "–" : B.num(x));
      const ruoli = [d.institutionalRole, ...(d.committees || []).filter((x) => !x.to).map((x) => (x.role ? `${x.role}, ${x.name}` : x.name))].filter(Boolean).slice(0, 4);
      dati = `${d.group ? `<p style="margin:8px 0 0;color:var(--t2)">${e(d.mistoComponent ? `${d.group.name} · ${d.mistoComponent.name}` : d.group.name)}</p>` : ""}${ruoli.length ? `<div class="ruoli">${ruoli.map((x) => `<span>${e(x)}</span>`).join("")}</div>` : ""}
        <dl class="persona__n"><div><dt>${TT("Interventi in Aula", "Floor speeches")}</dt><dd>${num(c.speeches)}</dd></div><div><dt>${TT("Atti con la prima firma", "Acts as first signatory")}</dt><dd>${num(c.actsPrimary)}</dd></div>${v.participationPct != null ? `<div><dt>${TT("Presenza ai voti", "Votes attended")}</dt><dd>${String(v.participationPct).replace(".", window.LANG === "en" ? "." : ",")}%</dd></div>` : ""}</dl>`;
    }
    blocco(t, "persona", TT("Scheda", "Profile"), "", `<div class="persona${sen ? " persona--sen" : ""}">${foto}<div><div class="persona__testa"><h4>${e(p.n)}</h4>${B.link(url, TT("Apri la scheda completa", "Open the full profile"))}</div><div style="margin-top:6px">${sen ? TT("Senato", "Senate") + " · " : ""}${B.sig(p.sigla)}</div>${dati}</div>${sen ? "" : `<div>${B.emiciclo({ evidenzia: p.id, r: 15, etichetta: `Il seggio di ${p.n}` })}</div>`}</div>`, "voti");
  }
  async function instrada(t, q, it) {
    const parole = CH.parole(q), chiave = parole.slice(0, 4).join(" ");
    const persona = it.persona || CH.trovaPersona(q);
    if (persona) CH.ultimaPersona = persona;
    const lavori = [];
    if (persona) {
      t.tipo = "persona";
      schedaPersona(t, persona);
      const s = passo(t, "persona-int", `Cerco gli interventi di ${persona.n}`, `search_parliament(query="${persona.n}", doc_type="speech")`);
      lavori.push(B.mcp("search_parliament", { query: persona.n, doc_type: "speech", max_results: 8 }).then((r) => {
        const xs = (r.dati.results || []).filter((x) => B.norm(`${x.first_name} ${x.last_name}`) === B.norm(persona.n));
        s.fatto(`${xs.length} interventi`);
        if (xs.length) blocco(t, "interventi", `Interventi di ${persona.n}`, B.info("Estratti dal resoconto, dal più pertinente"), `<ul class="lista">${xs.map((x) => `<li><span class="meta">${B.ramo(x.chamber)} · ${B.data(x.date)} · seduta ${x.session_number}</span><span>${e(B.taglia(x.debate_title, 140))}</span><span class="estratto">«${e(x.text)}»</span>${B.link(x.url, "Apri il resoconto")}</li>`).join("")}</ul>`, "atti");
      }).catch(() => s.errore()));
    }
    if (parole.length && !persona && (it.tipo === "tema" || it.tipo === "argomento" || it.atto)) {
      const s1 = passo(t, "posizioni", "Cerco negli interventi di Camera e Senato", `search_parliament(query="${chiave}", doc_type="speech")`);
      const pInt = B.mcp("search_parliament", { query: chiave, doc_type: "speech", max_results: 30 });
      lavori.push(pInt.then((r) => {
        const xs = r.dati.results || [], per = {};
        t.interventi = xs; t.totInterventi = r.dati.total;
        xs.forEach((x) => { const g = B.sigla(x.group, x.misto_component); if (!per[g]) per[g] = x; });
        s1.fatto(`${B.num(r.dati.total)} risultati`);
        const gr = B.ORDINE.filter((g) => per[g]);
        if (it.tipo === "argomento") {
          const visti = new Set(), recenti = [...xs].sort((p, q2) => String(q2.date).localeCompare(String(p.date))).filter((x) => { const k = `${x.chamber}${x.session_number}${x.debate_title}`; if (visti.has(k)) return false; visti.add(k); return true; }).slice(0, 5);
          if (recenti.length) blocco(t, "interventi", TT("Interventi più recenti", "Most recent speeches"), B.info(TT("Dibattiti in Aula sull'argomento, dal più recente", "Floor debates on the topic, most recent first")), `<ul class="lista">${recenti.map((x) => `<li><span class="meta">${B.ramo(x.chamber)} · ${B.data(x.date)} · ${TT("seduta", "sitting")} ${x.session_number}</span><span>${e(B.frase(B.taglia(String(x.debate_title || "").replace(/\s*\(ore [\d,.]+\)\.?/g, "").trim(), 140)))}</span><span class="estratto">${e(B.nome(`${x.first_name} ${x.last_name}`))}: «${e(B.taglia(x.text, 240))}»</span>${B.link(`#/strumenti/seduta/${x.chamber === "senato" ? "sen_" : ""}leg19_sed${x.session_number}`, TT("Apri la seduta", "Open the sitting"))}</li>`).join("")}</ul>`, "atti");
          return;
        }
        if (!gr.length || it.fascicolo || it.atto || it.tipo === "tema") return;
        const mancano = B.gruppiCamera().map((g) => g.sigla).filter((g) => !per[g]);
        blocco(t, "posizioni", "Per gruppo", B.info(`L'intervento più pertinente di ogni gruppo, fra i primi ${xs.length} risultati. Sono estratti dal resoconto: le citazioni controllate sono nella risposta.`),
          `<div class="posizioni">${gr.map((g) => { const x = per[g]; return `<div class="pos" style="--g:${B.col(g)}"><div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">${B.sig(g)}<b style="font-weight:600;font-size:14.5px">${e(B.nome(`${x.first_name} ${x.last_name}`))}</b><span class="meta" style="margin-left:auto">${B.ramo(x.chamber)} · ${B.data(x.date)}</span></div><span class="estratto">«${e(B.taglia(x.text, 330))}»</span>${B.link(x.url, `Resoconto, seduta ${x.session_number}`)}</div>`; }).join("")}</div>
          ${mancano.length ? `<p style="margin:0;font-size:13.5px;color:var(--t3)">Fra i primi ${xs.length} risultati non ci sono interventi di: ${mancano.map((g) => e(B.NOMI[g] || g)).join(", ")}. Non vuol dire che non abbiano mai parlato del tema.</p>` : ""}
`, "voti");
      }).catch(() => s1.errore()));
      const s2 = passo(t, "atti", "Cerco negli atti: proposte, mozioni, interrogazioni", `search_parliament(query="${chiave}", doc_type="act")`);
      lavori.push(B.mcp("search_parliament", { query: chiave, doc_type: "act", max_results: 15 }).then((r) => {
        const xs = (r.dati.results || []).sort((p, q2) => String(q2.date).localeCompare(String(p.date))).slice(0, 6); s2.fatto(`${B.num(r.dati.total)} atti`); t.totAtti = r.dati.total;
        if (xs.length) blocco(t, "atti", "Atti", `${B.num(r.dati.total)} ${B.link(`#/strumenti/atti?q=${encodeURIComponent(chiave)}`, "Vedi tutti gli atti")}`, `<ul class="lista">${xs.map((a) => `<li><span class="meta">${e((a.act_kind || a.act_type || "").replace(/_/g, " "))} ${e(a.act_number || "")} · ${B.ramo(a.chamber)} · ${B.data(a.date)}</span><span>${a.url ? `<a href="${e(B.interno(a.url, `${a.chamber === "senato" ? "S." : "C."} ${a.act_number} · ${a.act_title}`))}">${e(B.taglia(a.act_subject || B.frase(a.act_title), 150))}</a>` : e(B.taglia(a.act_subject || B.frase(a.act_title), 150))}</span>${a.last_name ? `<span style="font-size:13.5px;color:var(--t3)">${e(B.nome(`${a.first_name} ${a.last_name}`))} ${a.group ? B.sig(B.sigla(a.group, a.misto_component)) : ""}</span>` : ""}${a.law ? `<span style="font-size:14px">Diventato <a href="${e(a.law.eli || a.law.normattiva_url)}" target="_blank" rel="noopener">${e(a.law.label)}</a></span>` : ""}</li>`).join("")}</ul>`);
      }).catch(() => s2.errore()));
      const s3 = passo(t, "sedute", "Cerco le sedute in cui se n'è parlato, e le loro votazioni", `list_sessions(search="${chiave}") · get_session_votes`);
      lavori.push(B.mcp("list_sessions", { search: chiave, limit: 6 }).then(async (r) => {
        const ss = r.dati.sessions || [];
        if (ss.length) blocco(t, "sedute", "Sedute", B.info("Le più recenti in cui se n'è parlato"), `<ul class="lista">${ss.map((s) => `<li><span class="meta">${B.data(s.date)} · ${B.ramo(s.chamber)} · seduta ${s.number} · ${s.speech_count} interventi · ${s.vote_count} voti</span><span>${e(B.taglia((s.matches && s.matches.length ? s.matches.map((m) => m.text || m.title || m).join(" · ") : s.recap) || "", 260))}</span>${B.link(`#/strumenti/seduta/${s.id}`, "Apri la seduta")}</li>`).join("")}</ul>`);
        const daInterventi = await pInt.then((x) => x.dati.results || []).catch(() => []);
        const visti = new Set(), candidate = [];
        [...daInterventi].sort((a, b) => String(b.date).localeCompare(String(a.date))).forEach((x) => { const id = (x.chamber === "senato" ? "sen_" : "") + "leg19_sed" + x.session_number; if (!visti.has(id)) { visti.add(id); candidate.push({ id, chamber: x.chamber, date: x.date }); } });
        ss.filter((s) => s.vote_count > 0).forEach((s) => { if (!visti.has(s.id)) { visti.add(s.id); candidate.push({ id: s.id, chamber: s.chamber, date: s.date }); } });
        const conVoti = candidate.slice(0, 6), trovati = [];
        for (const s of conVoti) {
          try {
            const v = await B.mcp("get_session_votes", { session_id: s.id });
            (v.dati.votes || []).filter((x) => x.kind !== "quorum_check" && parole.some((w) => B.norm(`${x.subject} ${x.description} ${x.act_title} ${x.act_subject}`).includes(w)))
              .sort((a, b) => b.final_vote - a.final_vote).slice(0, 3)
              .forEach((x) => trovati.push({ ...x, ramo: s.chamber, data: s.date, titolo: x.act_subject || (x.final_vote ? `Voto finale: ${B.taglia(x.act_title || x.description, 60)}` : x.description || x.subject) }));
          } catch (err) { /* una seduta in meno */ }
        }
        s3.fatto(`${conVoti.length} sedute controllate · ${trovati.length} votazioni`);
        if (trovati.length) bloccoVoti(t, trovati.slice(0, 6));
      }).catch(() => s3.errore()));
    }
    await Promise.allSettled(lavori);
  }

  /* ---------- schede nelle risposte ---------- */
  function scheda(t, ev) {
    const d = ev.data;
    if (ev.kind === "vote" && !t.tipo) t.tipo = "voto";
    if (ev.kind === "vote") return bloccoVoti(t, [{ id: d.id, subject: d.subject, description: d.description, titolo: d.description || d.subject, ramo: d.chamber, data: d.date, outcome: d.outcome, in_favor: d.counts && d.counts.inFavor, against: d.counts && d.counts.against }]);
    if (ev.kind === "deputy" || ev.kind === "person") {
      const p = B.perNome(d.name || d.fullName || "");
      if (p && !t.el.querySelector('[data-blocco="persona"]')) blocco(t, "persona", "Persona", "", `<div class="persona">${B.fotoHtml(p)}<div><h4>${e(p.n)}</h4><div style="margin-top:6px">${B.sig(p.sigla)}</div><span style="display:inline-block;margin-top:8px">${B.link(`#/strumenti/deputato/${p.id}`, "Apri la scheda")}</span></div><div>${B.emiciclo({ evidenzia: p.id, r: 15 })}</div></div>`, "voti");
      return;
    }
    const titolo = { act: "Atto", session: "Seduta", group: "Gruppo" }[ev.kind] || "Scheda";
    const prima = t.el.querySelector('[data-blocco="schede"]');
    const riga = `<li><span class="meta">${titolo}${d.date ? " · " + B.data(d.date) : ""}</span><span>${d.url ? `<a href="${e(B.interno(d.url, d.title || d.name || d.subject || ""))}">${e(d.title || d.name || d.subject || "")}</a>` : e(d.title || d.name || d.subject || "")}</span>${d.law ? `<span style="font-size:14px">Diventato ${e(d.law.label || "")}</span>` : ""}</li>`;
    if (prima) prima.querySelector("ul").insertAdjacentHTML("beforeend", riga);
    else blocco(t, "schede", "Schede", "", `<ul class="lista">${riga}</ul>`, "atti");
  }

  /* ---------- fascicolo: una voce autorevole per gruppo, con gli strumenti ---------- */
  const frase = (testo, parole) => {
    const fr = testo.split(/(?<=[.!?;])\s+/).map((x) => x.trim()).filter((x) => x.length > 50 && x.length < 300 && !/…/.test(x));
    return fr.find((x) => parole.some((w) => B.norm(x).includes(w))) || fr[0] || null;
  };
  async function fascicolo(t, q, prosaEl, url) {
    const parole = CH.parole(q), xs = t.interventi || [];
    if (!xs.length) { prosaEl.innerHTML = `<p>${TT("Non ho trovato interventi in Aula su questa domanda. Prova con parole diverse, o apri la ricerca.", "I found no floor speeches on this question. Try other words, or open the search.")} ${B.link(`#/strumenti/atti?q=${encodeURIComponent(parole.join(" "))}`, TT("Apri la ricerca", "Open the search"))}</p>`; return null; }
    const cand = {};
    xs.forEach((x) => { const g = B.sigla(x.group, x.misto_component), nome = B.nome(`${x.first_name} ${x.last_name}`), f = frase(x.text, parole); if (!f) return; cand[g] = cand[g] || []; if (cand[g].length < 3 && !cand[g].some((c) => c.nome === nome)) cand[g].push({ nome, f, x, g }); });
    const gruppi = B.ORDINE.filter((g) => cand[g]);
    const s = passo(t, "autorevolezza", `Scelgo la voce più autorevole di ogni gruppo fra ${Object.values(cand).flat().length} oratori`, "verify_answer · criteri di autorevolezza");
    const testo = gruppi.map((g) => cand[g].map((c) => `Per ${B.NOMI[g]}, ${c.nome}: «${c.f}»`).join(" ")).join(" ");
    let d = null;
    try { d = (await B.mcp("verify_answer", { answer: testo, question: q })).dati; } catch (err) { s.errore(); }
    const voci = (d && d.authority && d.authority.voices) || [], cit = (d && d.quotes) || [];
    const scelte = gruppi.map((g) => { const cs = cand[g].map((c) => ({ ...c, v: voci.find((v) => B.norm(v.name) === B.norm(c.nome)), q: cit.find((z) => B.norm(z.speaker || "") === B.norm(c.nome)) })); return cs.find((c) => c.v && c.v.authoritative) || cs.sort((a, b) => ((a.v && a.v.rank) || 99) - ((b.v && b.v.rank) || 99))[0]; });
    if (d) s.fatto(`${scelte.filter((c) => c.v && c.v.authoritative).length} voci autorevoli su ${scelte.length}`);
    const mancano = B.gruppiCamera().map((g) => g.sigla).filter((g) => !cand[g]);
    prosaEl.innerHTML = TT(`<p>Su questa domanda il Parlamento ha ${B.num(t.totInterventi)} interventi in Aula${t.totAtti ? ` e ${B.num(t.totAtti)} atti` : ""}. Qui sotto trovi la voce più autorevole di ogni gruppo che ne ha parlato, con una frase presa dal resoconto e controllata parola per parola${mancano.length ? `. Fra i risultati più pertinenti mancano: ${mancano.map((g) => e(B.NOMI[g])).join(", ")}` : ""}.</p>`,
    `<p>Parliament has ${B.num(t.totInterventi)} floor speeches on this question${t.totAtti ? ` and ${B.num(t.totAtti)} acts` : ""}. Below is the most authoritative voice of each group that spoke about it, with a sentence taken from the verbatim record and checked word by word${mancano.length ? `. Missing from the most relevant results: ${mancano.map((g) => e(B.NOMI[g])).join(", ")}` : ""}. Quotes stay in the original Italian.</p>`) + ``;
    blocco(t, "posizioni", "Una voce per gruppo", B.info("Per ogni gruppo la voce più autorevole fra chi ha parlato del tema, secondo i nostri criteri"),
      `<div class="posizioni">${scelte.map((c) => { const ok = c.q && /verbatim|exact/.test(c.q.status); return `<div class="pos" style="--g:${B.col(c.g)}"><div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">${B.sig(c.g)}<b style="font-weight:600;font-size:14.5px">${e(c.nome)}</b>${c.v && c.v.rank ? `<span class="meta" style="margin-left:auto">${c.v.authoritative ? "autorevole · " : ""}${c.v.rank}° su ${c.v.pool_size} nel gruppo</span>` : ""}</div><q style="font-size:16.5px;line-height:1.45">${e(c.f)}</q><span style="font-size:13px;color:var(--t3)">${B.ramo(c.x.chamber)} · ${B.data(c.x.date)} · seduta ${c.x.session_number}${ok ? ' · <span style="color:var(--ok)">identica al resoconto</span>' : ""} · ${B.link(c.x.url, TT("Apri il resoconto", "Open the verbatim record"))}</span></div>`; }).join("")}</div>
      ${mancano.length ? `<p style="margin:0;font-size:13.5px;color:var(--t3)">Senza interventi fra i primi ${xs.length} risultati: ${mancano.map((g) => e(B.NOMI[g])).join(", ")}. Non vuol dire che non ne abbiano mai parlato.</p>` : ""}`, "voti");
    return scelte.map((c) => `Per ${B.NOMI[c.g]}, ${c.nome}: «${c.f}»`).join(" ");
  }

  /* ---------- garanzie ---------- */
  const STATO = { pass: ["ok", "Superata"], warn: ["av", "Con avviso"], fail: ["no", "Non superata"], na: ["av", "Non si applica"] };
  async function garanzie(t, testo, q) {
    const s = passo(t, "verifica", "Controllo le tre garanzie sul testo della risposta", "verify_answer(answer, question)");
    try {
      // prima il controllo del backend in locale (allineato al fascicolo), poi quello del server MCP pubblico
      const loc = await fetch("/api/verifica", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ answer: testo, question: q }) }).then((r) => (r.ok ? r.json() : null)).catch(() => null);
      const d = loc && loc.dati ? loc.dati : (await B.mcp("verify_answer", { answer: testo, question: q })).dati;
      const o = d.outcome || {}, g = d.groups || {};
      const cit = d.quotes || [];
      const ok = cit.filter((x) => x.status === "verbatim" || x.status === "exact").length;
      const voci = (d.authority && d.authority.voices) || [];
      const singolo = t.tipo && o.groups !== "pass";
      if (singolo) o.groups = "na";
      const carte = [
        ["Tutti i gruppi", o.groups, singolo ? `Non si applica: la domanda riguarda ${t.tipo === "persona" ? "una persona" : "un singolo voto"}, non il confronto fra i gruppi.` : g.present ? `${g.present.length} presenti nella risposta.${g.missing && g.missing.length ? ` Mancano: ${g.missing.join(", ")}.` : ""}${g.silent && g.silent.length ? ` Senza interventi sul tema: ${g.silent.join(", ")}.` : ""}` : "Non calcolabile su questa risposta."],
        ["Voci autorevoli", o.authority, voci.length ? `${voci.filter((v) => v.authoritative).length} su ${voci.length} voci citate sono autorevoli secondo i nostri criteri.${voci.filter((v) => !v.authoritative).map((v) => ` ${v.name} (${B.NOMI[B.sigla(v.group)] || v.group || "gruppo non indicato"}) ${v.rank ? `è ${v.rank}ª su ${v.pool_size} nel suo gruppo per autorevolezza sul tema, e contano le prime 5` : "non risulta fra chi ha parlato del tema"}.`).join("")}` : "Nessuna voce citata da valutare."],
        ["Citazioni esatte", o.quotes, cit.length ? `${ok} su ${cit.length} citazioni coincidono con il resoconto.${cit.filter((x) => x.status === "modified").length ? ` ${cit.filter((x) => x.status === "modified").length} modificate rispetto al resoconto.` : ""}${cit.filter((x) => x.status === "omissions").length ? ` ${cit.filter((x) => x.status === "omissions").length} con parti tagliate.` : ""}${cit.filter((x) => x.status === "not_found").length ? ` ${cit.filter((x) => x.status === "not_found").length} non trovate negli interventi.` : ""}` : "Nessuna citazione tra virgolette da controllare."],
      ];
      { const app = Object.values(o).filter((x) => x && x !== "na").length, esito = app ? `${Object.values(o).filter((x) => x === "pass").length} su ${app} garanzie superate` : "nessun controllo applicabile"; s.fatto(esito); if (t.sp) t.sp.controllato(esito); }
      blocco(t, "garanzie", "Le tre garanzie", B.info("Controllo automatico sul testo della risposta, fatto da un programma e non da un modello di AI"), `<div class="garanzie g2">${carte.map(([ti, es, tx]) => { const [k, st] = STATO[es] || ["av", "Non applicabile"]; return `<div class="g2__c g2--${k}"><span class="g2__ico">${B.ico(k === "ok" ? "ok" : k === "no" ? "chiudi" : "info")}</span><div><div class="g2__t"><b>${ti}</b><em>${st}</em></div><p>${e(tx)}</p></div></div>`; }).join("")}</div>
        ${cit.filter((x) => x.status === "modified").map((x) => `<div class="avviso"><b>Citazione modificata.</b> «${e(x.quote)}». Il testo del resoconto: «${e(x.closest_passage || "")}» · <a href="${e(x.record_url)}" target="_blank" rel="noopener">resoconto</a></div>`).join("")}`, "posizioni");
    } catch (err) { s.errore(); if (t.sp) t.sp.controllato(TT("controllo non disponibile", "check not available")); }
  }

  /* ---------- segnala un errore: una finestra con il tipo e un commento, che arriva per email a chi cura il progetto ---------- */
  const TIPI_ERR = [["Citazione sbagliata o attribuita alla persona sbagliata", "Wrong quote, or quote given to the wrong person"], ["Dato, numero o data errati", "Wrong figure, number or date"],
    ["Manca un gruppo o una voce importante", "A group or a key voice is missing"], ["Link che non funziona o porta altrove", "Broken link, or a link to the wrong page"], ["Risposta fuori tema", "The answer is off topic"], ["Altro", "Something else"]];
  function segnala(tt) {
    if (!tt) return;
    let d = document.getElementById("dlg-segnala");
    if (!d) { d = document.createElement("dialog"); d.id = "dlg-segnala"; d.className = "dlg"; document.body.appendChild(d); }
    const q = (tt.querySelector(".turno__dom") || {}).textContent || "", risp = ((tt.querySelector('[data-blocco="risposta"] .prosa') || {}).innerText || "").trim();
    d.innerHTML = `<form method="dialog" class="dlg__f"><header><h2>${TT("Segnala un errore", "Report a mistake")}</h2><button type="button" class="dlg__x" data-chiudi aria-label="${TT("Chiudi", "Close")}">×</button></header>
      <p class="dlg__q">${TT("Sulla risposta a", "On the answer to")} «${e(B.taglia(q, 120))}»</p>
      <fieldset><legend>${TT("Che cosa non va?", "What is wrong?")}</legend>${TIPI_ERR.map(([it, en], i) => `<label><input type="radio" name="tipo" value="${e(it)}"${i === 0 ? " required" : ""}> ${TT(it, en)}</label>`).join("")}</fieldset>
      <label class="dlg__t">${TT("Raccontaci cosa hai visto (facoltativo)", "Tell us what you saw (optional)")}<textarea name="testo" rows="4" maxlength="3000" placeholder="${TT("Per esempio: la citazione di X non è nel resoconto del 12 marzo", "For example: X's quote is not in the 12 March record")}"></textarea></label>
      <p class="dlg__n">${TT("Arriva a chi cura il progetto, insieme alla domanda e alla risposta. Non serve la tua email e non la chiediamo.", "It reaches the people behind the project, with the question and the answer. We don't need your email and we don't ask for it.")}</p>
      <p class="dlg__e" role="status"></p>
      <div class="dlg__az"><button type="button" class="bt-mini" data-chiudi>${TT("Annulla", "Cancel")}</button><button type="submit" class="bt-pieno">${TT("Invia", "Send")}</button></div></form>`;
    const f = d.querySelector("form"), msg = d.querySelector(".dlg__e");
    d.querySelectorAll("[data-chiudi]").forEach((b) => b.addEventListener("click", () => d.close()));
    f.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const tipo = (f.querySelector("input[name=tipo]:checked") || {}).value; if (!tipo) { msg.textContent = TT("Scegli che cosa non va.", "Pick what is wrong."); return; }
      const b = f.querySelector("[type=submit]"); b.disabled = true; msg.textContent = TT("Invio…", "Sending…");
      try {
        // un'istantanea della conversazione, come per «Condividi»: il link va nella segnalazione per rivederla com'era
        let link = "";
        try { const tt2 = turni(); const c = await fetch("/api/condividi", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ titolo: tt2[0].q, lingua: window.LANG, turni: tt2 }) }).then((x) => x.json()); if (c.id) link = `${location.origin}/#/c/${c.id}`; } catch { /* la segnalazione parte anche senza link */ }
        const r = await fetch("/api/segnala", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ tipo, testo: f.testo.value.trim(), domanda: q, risposta: risp.slice(0, 6000), lingua: window.LANG, link }) });
        const j = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(j.errore || r.status);
        f.innerHTML = `<header><h2>${TT("Grazie", "Thank you")}</h2><button type="button" class="dlg__x" aria-label="${TT("Chiudi", "Close")}">×</button></header><p>${TT("Abbiamo ricevuto la segnalazione. La guardiamo e, se serve, correggiamo la risposta o il sistema.", "We got your report. We will look at it and fix the answer or the system if needed.")}</p><div class="dlg__az"><button type="button" class="bt-pieno">${TT("Chiudi", "Close")}</button></div>`;
        f.querySelectorAll("button").forEach((x) => x.addEventListener("click", () => d.close()));
        const sg = tt.querySelector("[data-segnala]"); if (sg) { sg.classList.add("fatto"); sg.dataset.tip = TT("Segnalazione inviata", "Report sent"); }
      } catch (err) { b.disabled = false; msg.textContent = TT(`Non siamo riusciti a inviarla (${err.message}). Riprova tra poco.`, `We could not send it (${err.message}). Try again shortly.`); }
    });
    d.showModal();
  }

  /* ---------- un turno ---------- */
  CH.contesto = null; // { etichetta, testo }: la pagina che l'utente sta guardando
  // mentre arriva una risposta i bottoni «Chiedi» restano bloccati: una domanda alla volta
  const blocca = (si) => { CH.inCorso = si; B.$$(".invia").forEach((b) => { b.disabled = si; b.setAttribute("aria-busy", String(si)); }); };
  CH.chiedi = async (q, ctx) => {
    q = q.trim(); if (!q || CH.inCorso) return;
    blocca(true); setTimeout(() => { if (CH.inCorso && !document.querySelector(".turno .stato-v:not(.fatto)")) blocca(false); }, 4000);
    // una domanda fatta dalla home apre sempre una chat nuova; i pesi scelti prima della domanda restano
    if (!document.body.dataset.vista) { aperta(null); CH.idChat = null; storia.length = 0; delete CH.ultimaPersona; CH.proponi(null); $("#conversazione").innerHTML = ""; }
    if (!CH.idChat) CH.idChat = nuovoId();
    aperta({ id: CH.idChat, attesa: q });
    const qx = (ctx ? `${q}\n\n(Domanda fatta dalla pagina «${ctx.testo}»: usala come contesto.)` : q) + (window.LANG === "en" ? "\n\n(Answer in English. Keep quotes in the original Italian.)" : "");
    document.body.dataset.vista = "conversazione"; location.hash !== "#/chiedi" && history.replaceState(null, "", "#/chiedi");
    const n = ++nTurno, box = $("#conversazione");
    const el = document.createElement("article"); el.className = "turno"; el.id = `turno-${n}`;
    el.innerHTML = `<div class="dom-utente">${ctx ? `<span class="turno__ctx">${e(ctx.etichetta)}</span>` : ""}<h2 class="turno__dom">${e(q)}</h2></div><details class="come" open><summary><span class="stato-v">Al lavoro</span><span class="testo-stato">Leggo la domanda</span></summary><ol class="passi"></ol></details><nav class="indice-r" aria-label="In questa risposta"></nav><div class="blocchi"></div><div class="seguiti"></div>`;
    box.appendChild(el); el.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });
    const t = { n, q, el, passi: el.querySelector(".passi"), blocchi: el.querySelector(".blocchi"), indice: el.querySelector(".indice-r"), stato: el.querySelector(".testo-stato") };
    const bRisp = blocco(t, "risposta", "Risposta", "", `<div class="prosa cursore"><div class="carica" role="status"><span class="vh">Scrivo la risposta</span><i></i><i></i><i></i></div></div>`);
    const prosaEl = bRisp.querySelector(".prosa");
    let testo = "", fonti = [], strumenti = {};
    el._t = t;
    await B.caricaSenato().catch(() => {});   // i nomi dei senatori servono a riconoscere una persona nella domanda
    const it = CH.intento(q); CH.ultimoIntento = it;
    if (CH.AGENTE) {
      // regola: un tema con almeno 3 dibattiti va al fascicolo, con i passaggi del metodo; il resto all'agente
      let d = null;
      // una domanda che continua la precedente («e cosa hanno detto?») resta all'agente, che ha il contesto
      const seguito = storia.length && (/^\s*(e|ma|invece|e invece|and|but)\b/i.test(q) || CH.parole(q).length <= 1);
      // numeri, classifiche, elenchi di atti e voti vanno all'agente, che ha gli strumenti di conteggio; il fascicolo è per le posizioni
      const numerica = /\b(quant[aeio]\w*|numero|percentual\w*|indice|coesion\w*|classific\w*|matrice|conta\w*|conteggi\w*|elenc\w*|come (?:vota|votano|hanno votato|ha votato)|quali (?:interrogazioni|interpellanze|mozioni|atti|leggi|emendamenti|proposte|disegni)|how many|how much|count|ranking|list)\b/.test(B.norm(q));
      if (!seguito && !numerica && (it.tipo === "tema" || it.tipo === "argomento") && !CH.trovaPersona(q)) d = await contaDibattiti(t, q);
      if (!(d >= 3)) {
        // una domanda su una persona mostra subito la sua scheda, mentre l'agente scrive
        const pers = CH.trovaPersona(q); if (pers) { CH.ultimaPersona = pers; t.persona = pers; }   // la scheda arriva dopo la risposta
        await turnoAgente(t, el, n, q, qx, prosaEl); return;
      }
      it.tipo = "tema"; it.dibattiti = d; it.contati = true;
    }
    if (it.tipo === "anagrafica") { it.persona = CH.trovaPersona(q) || (ctx && CH.trovaPersona(ctx.etichetta)) || CH.ultimaPersona; if (!it.persona) it.tipo = "puntuale"; }
    // regola: tema con più dibattiti → fascicolo; una sola discussione o un solo atto → risposta rapida che cita l'atto
    if ((it.tipo === "tema" || it.tipo === "argomento") && !it.contati && !CH.trovaPersona(q)) {
      const d = await contaDibattiti(t, q);
      if (d != null) { it.dibattiti = d; if (d >= 3) it.tipo = "tema"; else { it.tipo = "puntuale"; it.atto = true; } }
    }
    const lavoro = it.tipo === "anagrafica" || it.tipo === "emendamento" ? Promise.resolve() : instrada(t, ctx ? `${q} ${ctx.etichetta}` : q, it);
    if (it.tipo === "anagrafica") { it.persona = CH.trovaPersona(q) || (ctx && CH.trovaPersona(ctx.etichetta)) || CH.ultimaPersona; if (!it.persona) it.tipo = "puntuale"; }
    if (it.tipo === "anagrafica") {
      const lav = instrada(t, it.persona.n, { tipo: "puntuale", persona: it.persona });
      t.senzaModello = true;
      try { testo = await anagrafica(t, it.persona, prosaEl); } catch (err) { prosaEl.innerHTML = `<div class="errore">${e(err.message)}</div>`; }
      storia.push({ role: "user", content: q }, { role: "assistant", content: testo });
      await lav; chiudi(t, el, n, q); return;
    }
    if (it.tipo === "emendamento") {
      try { testo = await emendamenti(t, q, ctx, prosaEl); } catch (err) { prosaEl.innerHTML = `<div class="errore">${e(err.message)}</div>`; }
      storia.push({ role: "user", content: q }, { role: "assistant", content: testo });
      chiudi(t, el, n, q); return;
    }
    if (it.tipo === "classifica") {
      t.senzaModello = true;
      try { testo = await classifica(t, it, prosaEl); } catch (err) { prosaEl.innerHTML = `<div class="errore">${TT("Non riesco a leggere le schede", "I can't read the deputies' records")}: ${e(err.message)}</div>`; }
      storia.push({ role: "user", content: q }, { role: "assistant", content: testo });
      await lavoro; chiudi(t, el, n, q); return;
    }
    if (it.tipo === "tema") {
      // finché il fascicolo non è pronto gli altri blocchi (atti, sedute) restano nascosti: si vedono insieme alla risposta
      t.trattieni = true;
      try { const f = await fascicoloVero(t, qx, prosaEl); if (f) { testo = f; it.fascicolo = true; } } catch (err) { /* resta la chat */ }
      if (t.limite) { limite(t, prosaEl); storia.push({ role: "user", content: q }); chiudi(t, el, n, q); return; }
      t.trattieni = false; B.$$("[data-blocco]", t.blocchi).forEach((b) => { b.hidden = false; }); aggiornaIndice(t);
      // se il fascicolo non arriva, con il motore agente risponde l'agente
      if (!it.fascicolo && CH.AGENTE) {
        // senza fascicolo i sei passaggi non hanno senso: si tolgono e si mostra il percorso dell'agente
        t.el.querySelector(".sei-passi")?.remove(); const come = t.el.querySelector("details.come"); if (come) come.hidden = false;
        await lavoro; await turnoAgente(t, el, n, q, qx, prosaEl); return;
      }
    }
    if (!it.fascicolo) try {
      const r = await fetch("/api/chat", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ prompt: qx.slice(0, 700), history: storia.slice(-8), locale: window.LANG, conversation: CH.idChat, turn: storia.filter((m) => m.role === "user").length + 1 }) });
      if (!r.ok) { const j = await r.json().catch(() => ({})); throw new Error(j.errore || j.detail || String(r.status)); }
      const lettore = r.body.getReader(), dec = new TextDecoder(); let buf = "";
      for (;;) {
        const { value, done } = await lettore.read(); if (done) break;
        buf += dec.decode(value, { stream: true });
        let i;
        while ((i = buf.indexOf("\n")) >= 0) {
          const riga = buf.slice(0, i).trim(); buf = buf.slice(i + 1); if (!riga) continue;
          let ev; try { ev = JSON.parse(riga); } catch { continue; }
          if (ev.type === "status") t.stato.textContent = ev.text;
          else if (ev.type === "tool") { if (ev.state === "start") strumenti[ev.id] = passo(t, `s-${ev.id}`, ev.label, ev.name); else if (strumenti[ev.id]) strumenti[ev.id].fatto(ev.count ? `${ev.count} trovati` : ""); }
          else if (ev.type === "delta") testo += ev.text;
          // la risposta viene ricontrollata e riscritta: resta visibile la versione precedente finché la nuova non la raggiunge
          else if (ev.type === "reset") testo = "";
          else if (ev.type === "sources") { fonti = ev.sources; blocco(t, "fonti", "Fonti", `${fonti.length}`, `<ol class="fonti">${fonti.map((f) => `<li id="f-${n}-${f.number}"><span class="n">${f.number}</span><span><a href="${e(B.interno(f.url, f.title, { a: f.agency || "", d: f.eventDate || "", x: (f.excerpt || "").slice(0, 600) }))}">${e(f.title)}</a><small>${e(f.agency || "")}${f.eventDate ? " · " + B.data(f.eventDate) : ""}${f.excerpt ? " · «" + e(B.taglia(f.excerpt, 180)) + "»" : ""}</small></span></li>`).join("")}</ol>`); }
          else if (ev.type === "card") scheda(t, ev);
          else if (ev.type === "handoff") { t.handoff = ev.url; t.stato.textContent = TT("Domanda di confronto: metto insieme le posizioni dei gruppi", "Comparison question: putting the groups' positions together"); }
          else if (ev.type === "unavailable") prosaEl.insertAdjacentHTML("beforeend", `<div class="avviso">${e(CH.pulisci(ev.title))}</div>`);
          else if (ev.type === "clarify") el.querySelector(".seguiti").innerHTML = `<p style="width:100%;margin:0 0 4px">${e(ev.question)}</p>` + ev.options.map((o) => `<button data-chiedi="${e(o.prompt)}">${e(o.label)}</button>`).join("");
          else if (ev.type === "suggestions") el.querySelector(".seguiti").innerHTML = ((xs) => { CH.proponi(xs[0]); return xs; })(ev.questions).map((x) => `<button data-chiedi="${e(x)}">${e(x)}</button>`).join("");
          else if (ev.type === "error" && (/rate|limit|quota/i.test(ev.code || "") || /limit|limite/i.test(ev.text || ""))) t.limite = ev.text || "limite";
          else if (ev.type === "error") prosaEl.insertAdjacentHTML("beforeend", `<div class="errore">${e(ev.text)}</div>`);
        }
      }
    } catch (err) { prosaEl.insertAdjacentHTML("beforeend", `<div class="errore">${TT("La risposta in prosa non è arrivata", "The written answer did not arrive")}: ${e(err.message)}. ${TT("Gli altri strumenti continuano.", "The other tools keep going.")}</div>`); }
    if (t.limite) { limite(t, prosaEl); storia.push({ role: "user", content: q }); chiudi(t, el, n, q); return; }
    // il fascicolo è già scritto con titoli, citazioni e ancore dei gruppi: riscriverlo le perderebbe
    if (testo.trim() && !it.fascicolo) await scrivi(prosaEl, testo, n);
    let ver = Promise.resolve();
    if (t.handoff && !testo.trim()) {
      bRisp.querySelector("h3").innerHTML = `Risposta`;
      await lavoro;
      const composto = await fascicolo(t, q, prosaEl, t.handoff);
      prosaEl.classList.remove("cursore");
      if (composto) { testo = composto; ver = garanzie(t, composto, q); }
    } else {
      prosaEl.classList.remove("cursore");
      if (!testo.trim()) prosaEl.innerHTML = (`<p style="color:var(--t3)">${TT("Nessun testo per questa domanda: guarda i risultati degli strumenti qui sotto.", "No written answer for this question: see the tool results below.")}</p>`);
      if (testo.trim() && it.tipo === "tema") ver = garanzie(t, testo, q);
    }
    storia.push({ role: "user", content: q }, { role: "assistant", content: testo.slice(0, 4000) });
    await Promise.allSettled([lavoro, ver]);
    await citazioniInglese(prosaEl);
    chiudi(t, el, n, q);
  };
  CH.AGENTE = true;
  async function turnoAgente(t, el, n, q, qx, prosaEl, modo) {
    let testo = ""; const strumenti = {};
    try {
      const r = await fetch("/api/agente", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ prompt: qx.slice(0, 1500), history: storia.slice(-8), locale: window.LANG, conversation: CH.idChat, turn: storia.filter((m) => m.role === "user").length + 1, modo, ...(CH.pesi ? { pesi: Object.fromEntries(CHIAVI_P.map((k, i) => [k, CH.pesi[i]])) } : {}) }) });
      if (!r.ok) { const j = await r.json().catch(() => ({})); throw new Error(j.errore || j.detail || String(r.status)); }
      const lettore = r.body.getReader(), dec = new TextDecoder(); let buf = "";
      for (;;) {
        const { value, done } = await lettore.read(); if (done) break;
        buf += dec.decode(value, { stream: true }); let i;
        while ((i = buf.indexOf("\n")) >= 0) {
          const riga = buf.slice(0, i).trim(); buf = buf.slice(i + 1); if (!riga) continue;
          let ev; try { ev = JSON.parse(riga); } catch { continue; }
          if (ev.type === "status") t.stato.textContent = ev.text;
          else if (ev.type === "tool") { if (ev.state === "start") { strumenti[ev.id] = passo(t, `a-${ev.id}`, TR(ev.label), ev.name); t.stato.textContent = TR(ev.label); } else if (strumenti[ev.id]) strumenti[ev.id].fatto(ev.count ? TT(`${ev.count} trovati`, `${ev.count} found`) : ""); }
          else if (ev.type === "dati") { try { daiDati(t, ev); } catch (err) { /* una scheda che non si disegna non ferma la risposta */ } }
          else if (ev.type === "delta") testo += ev.text;
          else if (ev.type === "suggestions") el.querySelector(".seguiti").innerHTML = ((xs) => { CH.proponi(xs[0]); return xs; })(ev.questions).map((x) => `<button data-chiedi="${e(x)}">${e(x)}</button>`).join("");
          else if (ev.type === "error") prosaEl.insertAdjacentHTML("beforeend", `<div class="errore">${e(ev.text)}</div>`);
        }
      }
    } catch (err) { prosaEl.insertAdjacentHTML("beforeend", `<div class="errore">${TT("La risposta non è arrivata", "The answer did not arrive")}: ${e(err.message)}</div>`); }
    if (t.limite) { limite(t, prosaEl); storia.push({ role: "user", content: q }); chiudi(t, el, n, q); return; }
    prosaEl.querySelector(".carica")?.remove();
    if (testo.trim()) await scrivi(prosaEl, testo, n); else if (!prosaEl.textContent.trim()) prosaEl.innerHTML = `<p style="color:var(--t3)">${TT("Nessuna risposta per questa domanda.", "No answer for this question.")}</p>`;
    prosaEl.classList.remove("cursore");
    storia.push({ role: "user", content: q }, { role: "assistant", content: testo.slice(0, 4000) });
    await citazioniInglese(prosaEl);
    if (t.persona && !t.blocchi.querySelector('[data-blocco="persona"]')) await schedaPersona(t, t.persona);
    chiudi(t, el, n, q);
  }
  // quello che l'agente ha preso dai dati diventa una scheda sotto la risposta
  function daiDati(t, ev) {
    const r = ev.result || {}, d = r.dati || r, a = ev.args || {};
    if (!t.persona && (ev.name === "scheda_persona" || (ev.name === "cerca_persone" && Array.isArray(ev.result) && ev.result.length === 1))) {
      const x = ev.name === "scheda_persona" ? ev.result : ev.result[0], m = /^it:person:(camera|senato):(\d+)$/.exec((x && x.uri) || "");
      if (m) { const p = m[1] === "camera" ? B.persona(m[2]) : B.senatori().find((y) => y.id === m[2]); if (p) t.persona = t.persona || p; }
    }
    if (ev.name === "confronto_gruppi" && r.errore && /rate|quota|limit/i.test(`${r.codice} ${r.errore}`)) { t.limite = r.errore; return; }
    if (ev.name === "get_vote_details" && d && (d.in_favor != null)) {
      const id = a.vote_id || d.id; bloccoVoti(t, [{ id, titolo: d.subject, subject: d.subject, ramo: /^senato/.test(id) ? "senato" : "camera", data: d.date, in_favor: d.in_favor, against: d.against, abstained: d.abstained, outcome: d.outcome }]);
    } else if (ev.name === "parlamentari" && (r.risultati || []).length > 1) {
      const k = { partecipazione: ["partecipazione_pct", (x) => `${String(x).replace(".", ",")}%`], assenze: ["assenze", B.num], interventi: ["interventi", B.num], atti_prima_firma: ["atti_prima_firma", B.num], atti_cofirmati: ["atti_cofirmati", B.num] }[a.ordina_per];
      blocco(t, "classifica", TT("Parlamentari", "Members"), `${r.risultati.length}`, `<ol class="classifica">${r.risultati.map((x, i) => { const p = x.camera === "camera" ? (B.persona(x.id) || { id: x.id, n: x.nome, sigla: x.sigla }) : null;
        return `<li><span class="pos-n">${i + 1}</span>${p ? B.fotoHtml(p) : `<span class="foto"><img src="/dati/foto/senatori/${e(x.id)}.jpg" alt="" onerror="this.remove()"></span>`}<span class="cl-nome"><a href="${e(x.pagina)}"><b>${e(x.nome)}</b></a><small>${e(x.camera === "camera" ? TT("Camera", "Chamber") : TT("Senato", "Senate"))} · ${e(B.NOMI[x.sigla] || x.gruppo || "")}</small></span>${k ? `<span class="cl-v">${k[1](x[k[0]])}</span>` : ""}</li>`; }).join("")}</ol>`);
    } else if (ev.name === "list_sessions" && a.search && (d.sessions || []).length) {
      blocco(t, "sedute", TT("Sedute", "Sittings"), `${d.sessions.length}`, `<ul class="lista">${d.sessions.slice(0, 8).map((s) => `<li><a class="sed-r" href="#/strumenti/seduta/${e(s.id)}"><b>${B.ramo(s.chamber)}, seduta ${s.number}</b><span class="meta">${B.data(s.date)}</span><span class="sed-r__t">${e(((ws) => (s.debates || []).filter((x) => ws.some((w) => B.norm(x.title).includes(w))).map((x) => x.title).join(" · "))(B.norm(String(a.search)).split(/\s+/).filter((w) => w.length >= 4).map((w) => w.slice(0, 5))) || B.taglia(s.recap || "", 200))}</span></a></li>`).join("")}</ul>`);
    } else if (ev.name === "confronto_gruppi" && (r.voci_autorevoli || []).length) {
      blocco(t, "posizioni", TT("Una voce per gruppo", "One voice per group"), "", `<ul class="oratori">${r.voci_autorevoli.map((x) => { const g = B.sigla(x.gruppo); return `<li><i style="background:${B.col(g)}"></i><span>${e(x.nome)}</span><small>${e(B.NOMI[g] || x.gruppo)} · ${TT("autorevolezza", "authority")} ${x.autorevolezza}</small></li>`; }).join("")}</ul>`);
    }
  }
  // limite di domande raggiunto: solo l'avviso e gli strumenti, che non hanno limiti; nessuna risposta, garanzia o blocco
  function limite(t, prosaEl) {
    t.annullato = true; t.senzaModello = true;
    B.$$("[data-blocco]", t.blocchi).forEach((b) => { if (b.dataset.blocco !== "risposta") b.remove(); });
    aggiornaIndice(t); t.indice.hidden = true;
    const min = (/(\d+)\s*(?:minut|min)/i.exec(t.limite) || [])[1], quante = (/(\d+)\s*(?:domande|questions)/i.exec(t.limite) || [])[1];
    prosaEl.classList.remove("cursore", "in-verifica");
    prosaEl.innerHTML = `<div class="limite" role="status"><b>${quante ? TT(`Hai fatto ${quante} domande nell'ultima ora`, `You asked ${quante} questions in the last hour`) : TT("Hai raggiunto il limite di domande", "You reached the question limit")}</b><p>${min ? TT(`Puoi farne un'altra fra circa ${min} minuti. Gli strumenti invece non hanno limiti.`, `You can ask another in about ${min} minutes. The tools have no limit.`) : TT("Fra poco potrai farne un'altra. Gli strumenti invece non hanno limiti.", "You can ask another soon. The tools have no limit.")}</p></div>
      <div class="limite-str">${ST.ELENCO.map((x) => `<a href="#/strumenti/${x.k}">${B.ico(x.i)}<b>${e(TR(x.t))}</b><span>${e(TR(x.d))}</span></a>`).join("")}</div>`;
    const bR = prosaEl.closest(".blocco"); if (bR) { const h = bR.querySelector("h3"); if (h) h.hidden = true; }
  }
  function chiudi(t, el, n, q) {
    blocca(false);
    const pr = el.querySelector('[data-blocco="risposta"] .prosa');
    if (pr && !t.senzaModello && !el.querySelector(".avviso-r")) pr.insertAdjacentHTML("afterend", `<div class="avviso-r" role="note">${B.ico("info")}<p>${TT("ParliamentRAG è un progetto di ricerca: un modello di AI scrive il testo e può sbagliare. Garantiamo solo le citazioni, che copiamo parola per parola dal resoconto e colleghiamo alla seduta.", "ParliamentRAG is a research project: an AI model writes the text and can be wrong. We only guarantee the quotes, which we copy word for word from the verbatim record and link to the sitting.")} <button type="button" class="avviso-r__s" data-segnala>${TT("Segnala un errore", "Report a mistake")}</button></p></div>`);
    el.querySelector(".stato-v").textContent = "Fatto"; el.querySelector(".stato-v").classList.add("fatto");
    t.stato.textContent = `${t.passi.children.length} ${t.passi.children.length === 1 ? "passaggio" : "passaggi"}`;
    el.insertAdjacentHTML("beforeend", `<div class="azioni"><button data-copia="${n}" aria-label="Copia la risposta" data-tip="Copia la risposta">${B.ico("copia")}</button><button data-utile aria-label="Utile" data-tip="Utile">${B.ico("su")}</button><button data-utile aria-label="Non utile" data-tip="Non utile">${B.ico("giuP")}</button><button data-segnala="${n}" aria-label="Segnala un errore" data-tip="Segnala un errore">${B.ico("segnala")}</button><button data-condividi aria-label="Condividi la conversazione" data-tip="Condividi la conversazione">${B.ico("condividi")}</button></div>`);
    salva(); aperta({ id: CH.idChat, attesa: null });
    if (!CH.contesto) CH.imposta(null);
  }




  /* ---------- emendamenti: ricerca nei testi degli emendamenti (dati di Camera e Senato) ---------- */
  const FASE = (x) => ({ "camera-commissione": TT("Camera, Commissione", "Chamber, Committee"), "camera-aula": TT("Camera, Aula", "Chamber, floor"), "senato-commissione": TT("Senato, Commissione", "Senate, Committee"), "senato-aula": TT("Senato, Aula", "Senate, floor") }[x] || x || "");
  async function emendamenti(t, q, ctx, prosaEl) {
    const s1 = passo(t, "em-legge", TT("Scelgo la legge", "Choosing the law"), "leggi/index.json");
    const indice = await fetch("/dati/emendamenti/leggi/index.json").then((r) => r.json());
    const parole = CH.parole(`${q} ${ctx ? ctx.etichetta : ""}`).filter((w) => !/^emendament|^amendment/.test(w));
    const punti = (x) => parole.reduce((a, w) => a + (B.norm(`${x.title} ${(x.numbers || []).join(" ")}`).includes(w) ? 1 : 0), 0);
    let leggi = [{ slug: "legge-elettorale", title: "Legge elettorale", file: "legge-elettorale", base: /elettoral|fuorisede|voto|collegi|elezion/.test(B.norm(q + (ctx ? ctx.etichetta : ""))) ? 2 : 0 }, ...indice.map((x) => ({ ...x, file: `leggi/${x.slug}` }))]
      .map((x) => ({ ...x, p: punti(x) + (x.base || 0) })).filter((x) => x.p > 0).sort((a, b) => b.p - a.p).slice(0, 2);
    if (!leggi.length) leggi = [{ slug: "legge-elettorale", title: "Legge elettorale", file: "legge-elettorale" }];
    s1.fatto(leggi.map((x) => B.taglia(x.title, 40)).join(" · "));
    const VUOTE_EM = new Set("quale quali chi cosa come quando dove emendamento emendamenti chiedeva chiede chiedono proponeva propone prevedeva prevede voleva introdurre legge articolo comma which what amendment asked proposed".split(" "));
    const SIN = { fuorisede: ["fuori sede"], fuori: [], estero: ["estero", "circoscrizione estero"], preferenze: ["preferenz"], premio: ["premio di maggioranza", "premio"] };
    const termini = [...new Set(B.norm(q).replace(/[«»"“”?!.,;:()']/g, " ").split(/\s+/).filter((w) => w.length > 3 && !VUOTE_EM.has(w)).flatMap((w) => SIN[w] || [w.length > 7 ? w.slice(0, w.length - 2) : w]))];
    const s2 = passo(t, "em-cerca", TT("Cerco nei testi degli emendamenti", "Searching amendment texts"), `amendments · ${termini.join(", ")}`);
    const trovati = [];
    for (const L of leggi) {
      const d = await fetch(L.file === "legge-elettorale" ? "/dati/emendamenti/legge-elettorale.json" : `/dati/emendamenti/leggi/${encodeURIComponent(L.slug)}.json`).then((r) => r.json());
      const am = (d.amendments || []).map((a) => ({ a, tx: B.norm(a.text || "") }));
      // peso: le parole rare contano di più (log N/df)
      const peso = Object.fromEntries(termini.map((w) => { const df = am.filter((x) => x.tx.includes(w)).length; return [w, df ? Math.log((am.length + 1) / df) : 0]; }));
      am.forEach(({ a, tx }) => { const p = termini.reduce((x, w) => x + (tx.includes(w) ? peso[w] : 0), 0); if (p > 0) trovati.push({ a, L, p }); });
    }
    trovati.sort((x, y) => y.p - x.p || (y.a.outcome === "approvato") - (x.a.outcome === "approvato"));
    s2.fatto(TT(`${trovati.length} emendamenti`, `${trovati.length} amendments`));
    const top = trovati.slice(0, 6);
    if (!top.length) { prosaEl.innerHTML = `<p>${TT("Non ho trovato emendamenti con queste parole.", "I found no amendments with these words.")}</p>`; prosaEl.classList.remove("cursore"); return ""; }
    const esito = (a) => a.outcome ? B.frase(a.outcome) : TT("esito non pubblicato", "outcome not published");
    const primo = top[0].a, firma = (primo.signers || []).find((x) => x.first) || (primo.signers || [])[0];
    prosaEl.innerHTML = `<p>${TT(`L'emendamento più vicino alla domanda è il <strong>${e(primo.number)}</strong> (${e(B.taglia(top[0].L.title, 60))}, ${e(FASE(primo.stage))})${firma ? `, prima firma ${e(firma.name)} (${e(firma.group)})` : ""}: ${e(esito(primo))}.`, `The amendment closest to the question is <strong>${e(primo.number)}</strong> (${e(B.taglia(top[0].L.title, 60))}, ${e(FASE(primo.stage))})${firma ? `, first signatory ${e(firma.name)} (${e(firma.group)})` : ""}: ${e(esito(primo))}.`)}</p>`;
    prosaEl.classList.remove("cursore");
    blocco(t, "atti", TT("Emendamenti trovati", "Amendments found"), B.info(TT("Ordinati per parole della domanda presenti nel testo", "Ordered by question words found in the text")),
      `<ul class="lista">${top.map(({ a, L }) => { const f = (a.signers || []).find((x) => x.first) || (a.signers || [])[0]; return `<li><span class="meta">${e(a.number)} · ${e(FASE(a.stage))} · ${e(esito(a))}</span><span>${e(B.taglia(L.title, 90))}${f ? ` · ${e(f.name)} ${B.sig(f.group)}` : ""}</span><span class="estratto" translate="no">${e(B.taglia(a.text || "", 280))}</span>${B.link(`#/strumenti/emendamenti/${L.slug}?em=${encodeURIComponent(a.id)}`, TT("Apri l'emendamento nel testo", "Open the amendment in the text"))}</li>`; }).join("")}</ul>`);
    return prosaEl.innerText;
  }

  /* ---------- fascicolo per le domande di tema ---------- */
  // Markdown del fascicolo: titoli, grassetti, separatori, citazioni [«…»](chunk_id) numerate verso le fonti
  // formule di passaggio che il modello ripete in ogni sezione: si tolgono e la frase comincia dal fatto
  const PASSAGGI = /\b(?:In linea con (?:questa|tale|la stessa) (?:impostazione|posizione|linea|visione|prospettiva)|Coerentemente con (?:questa|tale) (?:impostazione|posizione|linea|visione)|In (?:questa|tale) prospettiva|In tale quadro|In questo quadro),\s+(\p{L})/gu;
  function mdFascicolo(md, n, num) {
    md = md.replace(PASSAGGI, (m, c) => c.toUpperCase());
    const blocchi = md.split(/\n{2,}/).map((b) => b.trim()).filter(Boolean);
    const inline = (x) => e(x).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/\[«([\s\S]+?)»\]\(([\w.-]+)\)/g, (m, q, id) => { if (!num.has(id)) num.set(id, num.size + 1); return `<q>${q}</q><button class="rif" data-fonte="${n}-${num.get(id)}" aria-label="Fonte ${num.get(id)}">${num.get(id)}</button>`; });
    const gr = (h) => h.replace(/^(Per|For)\s+([^,<]{2,160}?)(?=,|\s+nel\b|\s+in\b)/, '$1 <strong class="f-gr">$2</strong>');
    return blocchi.map((b) => /^##\s/.test(b) ? `<h4 class="f-tit">${e(b.replace(/^##\s+/, ""))}</h4>` : /^---$/.test(b) ? "" : /^[-*]\s/m.test(b) ? `<ul>${b.split("\n").map((l) => `<li>${inline(l.replace(/^[-*]\s+/, ""))}</li>`).join("")}</ul>` : `<p>${gr(inline(b))}</p>`).join("");
  }
  // nell'introduzione «64 interventi» e «50 deputati» aprono a lato l'elenco, da scorrere e cliccare
  function numeriCliccabili(prosaEl, n) {
    const ps = [...prosaEl.querySelectorAll("p")].slice(0, 2);
    ps.forEach((p) => { p.innerHTML = p.innerHTML.replace(/(\d[\d.]*)(\s+)(interventi|interventions)\b/g, `<button type="button" class="num-el" data-elenco="interventi" data-turno="${n}">$1$2$3</button>`)
      .replace(/(\d[\d.]*)(\s+)(deputati|parlamentari|senatori|members|deputies)\b/g, `<button type="button" class="num-el" data-elenco="persone" data-turno="${n}">$1$2$3</button>`); });
  }
  const idSeduta = (x) => `${x.chamber === "senato" ? "sen_" : ""}leg19_sed${x.session_number}`;
  const pidCamera = (id) => (/p(\d+)$/.exec(id || "") || [])[1];
  function elencoTema(stat, tipo, chi) {
    if (tipo === "persone") {
      const xs = [...(stat.speakers_detail || [])].sort((a, b) => b.intervention_count - a.intervention_count);
      B.pannello(TT(`${xs.length} parlamentari sul tema`, `${xs.length} members on the topic`), `<p class="nota-r" style="margin:0 0 10px">${TT("Chi ha parlato del tema fra gli interventi analizzati, da chi è intervenuto di più. Clicca il numero per vedere i suoi interventi.", "Who spoke on the topic among the speeches analysed, most active first. Click the number to see their speeches.")}</p>
        <ul class="el-tema">${xs.map((x) => { const pid = pidCamera(x.speaker_id), p = pid && B.persona(pid);
          return `<li>${p ? B.fotoHtml(p) : `<span class="foto"></span>`}<span class="el-tema__n">${pid ? `<a href="#/strumenti/deputato/${pid}">${e(x.speaker_name)}</a>` : `<b>${e(x.speaker_name)}</b>`}<small>${e(x.institutional_role || B.NOMI[B.sigla(x.party)] || x.party || "")}</small></span><button type="button" class="num-el" data-elenco="interventi" data-chi="${e(x.speaker_id)}">${B.num(x.intervention_count)} ${x.intervention_count === 1 ? TT("intervento", "speech") : TT("interventi", "speeches")}</button></li>`; }).join("")}</ul>`);
      return;
    }
    const tutti = [...(stat.interventions_detail || [])].sort((a, b) => String(b.date).localeCompare(String(a.date)));
    const xs = chi ? tutti.filter((x) => x.speaker_id === chi) : tutti;
    const titolo = chi && xs[0] ? TT(`Interventi di ${xs[0].speaker_name}`, `Speeches by ${xs[0].speaker_name}`) : TT(`${xs.length} interventi sul tema`, `${xs.length} speeches on the topic`);
    B.pannello(titolo, `${chi ? `<p style="margin:0 0 10px"><button type="button" class="em-link" data-elenco="persone">${TT("Torna a tutti i parlamentari", "Back to all members")}</button></p>` : `<p class="nota-r" style="margin:0 0 10px">${TT("Gli interventi analizzati per la risposta, dal più recente. Ognuno apre la sua seduta.", "The speeches analysed for the answer, most recent first. Each opens its sitting.")}</p>`}
      <ul class="el-tema el-tema--int">${xs.map((x) => `<li><a href="#/strumenti/seduta/${idSeduta(x)}"><span class="meta">${B.data(x.date)} · ${B.ramo(x.chamber)} · ${TT("seduta", "sitting")} ${x.session_number}</span><b>${e(x.speaker_name)}</b> <span class="el-tema__g">${e(B.NOMI[B.sigla(x.party)] || x.party || "")}</span>${x.debate_title && !/^si riprende/i.test(x.debate_title) ? `<span class="el-tema__d">${e(B.taglia(x.debate_title, 140))}</span>` : ""}</a></li>`).join("")}</ul>`);
  }
  function mostraCoda(t, prosaEl) {
    if (t.codaTimer) return;
    const t0 = Date.now(); t.stato.textContent = TT("In coda", "In the queue");
    prosaEl.innerHTML = `<div class="coda" role="status"><div><b>${TT("La tua risposta è in coda", "Your answer is in the queue")}</b><p>${TT("Prepariamo poche risposte di confronto alla volta. La tua parte da sola appena si libera un posto: non serve ricaricare la pagina.", "We prepare a few comparison answers at a time. Yours starts on its own as soon as a slot frees up: no need to reload the page.")}</p></div><div class="coda__t"><small>${TT("attesa", "waiting")}</small><span aria-live="off">0:00</span></div><i class="coda__barra" aria-hidden="true"></i></div>`;
    const tm = prosaEl.querySelector(".coda__t span"); t.codaTimer = setInterval(() => { if (!tm.isConnected) { clearInterval(t.codaTimer); return; } const s = Math.floor((Date.now() - t0) / 1000); tm.textContent = `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`; }, 1000);
  }
  // i passaggi del metodo, come nel paper: recupero a due canali, autorevolezza, citazioni, generazione
  // i sei passaggi della sezione «Il metodo» della home, nello stesso ordine e con gli stessi nomi
  const SEI = [["capisce", "Capisce la domanda", "Understands the question"], ["cerca", "Cerca nei dati ufficiali", "Searches official data"], ["ordina", "Ordina le evidenze", "Ranks the evidence"], ["voci", "Una voce per gruppo", "One voice per group"], ["scrive", "Scrive la risposta", "Writes the answer"], ["controlla", "Controlla prima di mostrare", "Checks before showing"]];
  // passo del backend del fascicolo (evento progress) → passaggio del metodo
  const DA_PROGRESS = { 1: "cerca", 2: "ordina", 3: "voci", 4: "scrive", 5: "scrive" };
  function seiPassi(prosaEl, capito) {
    const ol = document.createElement("ol"); ol.className = "sei-passi"; ol.setAttribute("aria-label", TT("Passaggi", "Steps"));
    ol.innerHTML = SEI.map(([k, it, en], i) => `<li data-k="${k}"><span class="sp__c" aria-hidden="true"><span class="sp__n">${i + 1}</span>${B.ico("ok")}</span><b>${TT(it, en)}</b><small></small></li>`).join("");
    prosaEl.before(ol);
    const fatti = new Set(), esito = {};
    let coda = false;
    const disegna = (corre) => {
      const ora = corre || (SEI.find(([k]) => !fatti.has(k)) || [])[0];
      SEI.forEach(([k], i) => { const li = ol.children[i]; const st = fatti.has(k) ? "fatto" : k === ora ? (coda ? "coda" : "ora") : "dopo"; li.dataset.stato = st; li.toggleAttribute("aria-current", st === "ora"); li.querySelector("small").textContent = st === "coda" ? TT("in coda", "queued") : esito[k] || ""; });
    };
    const fai = (k, testo) => { fatti.add(k); if (testo) esito[k] = testo; };
    const finoA = (k) => { for (const [x] of SEI) { if (x === k) break; fatti.add(x); } };
    fai("capisce", capito);
    disegna();
    return {
      evento(ev) {
        if (ev.type === "waiting") { coda = true; disegna(); return; }
        // finita l'attesa parte il lavoro: il riquadro della coda lascia il posto allo scheletro
        if (coda) { coda = false; prosaEl.dispatchEvent(new Event("fine-coda")); }
        if (ev.type === "progress" && DA_PROGRESS[ev.step]) {
          const k = DA_PROGRESS[ev.step]; finoA(k);
          if (ev.step === 2) { const n = (/\d[\d.,]*/.exec(ev.message || "") || [])[0]; if (n) esito.cerca = TT(`${n} evidenze`, `${n} pieces of evidence`); }
          disegna(k); return;
        }
        else if (ev.type === "experts" && !fatti.has("voci")) { const n = (ev.data || []).length; finoA("voci"); fai("voci", n ? TT(`${n} voci autorevoli`, `${n} authoritative voices`) : ""); }
        else if (ev.type === "citation_details") { const n = (ev.citations || []).length; esito.controlla = TT(`${n} citazioni sul resoconto`, `${n} quotes on the record`); }
        else if (ev.type === "chunk") { finoA("scrive"); disegna("scrive"); return; }
        disegna();
      },
      // la risposta è scritta; resta il controllo delle tre garanzie, che chiude con controllato()
      fine(n) { finoA("controlla"); if (n) esito.scrive = TT(`${n} gruppi`, `${n} groups`); disegna("controlla"); },
      controllato(testo) { SEI.forEach(([k]) => fatti.add(k)); if (testo) esito.controlla = testo; disegna(); ol.classList.add("finito"); },
      togli() { ol.remove(); },
    };
  }
  // in inglese le citazioni si leggono tradotte; l'icona accanto mostra l'originale del resoconto
  async function citazioniInglese(el) {
    if (window.LANG !== "en") return;
    const qs = [...el.querySelectorAll("q")].filter((x) => !x.dataset.it); if (!qs.length) return;
    const orig = qs.map((x) => x.textContent);
    try {
      const r = await fetch("/api/traduci", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ testi: orig }) });
      const { tradotti } = await r.json();
      qs.forEach((x, i) => { const en = tradotti[i]; if (!en || en === orig[i]) return; x.dataset.it = orig[i]; x.dataset.en = en; x.textContent = en; x.lang = "en";
        x.insertAdjacentHTML("afterend", `<button class="q-lingua" type="button" data-q-lingua aria-label="Read in Italian" data-tip="Read in Italian">${B.ico("traduci")}</button>`); });
    } catch { /* restano in italiano */ }
  }
  document.addEventListener("click", (ev) => { const b = ev.target.closest("[data-q-lingua]"); if (!b) return; const q = b.previousElementSibling; if (!q || !q.dataset.it) return;
    const it = q.lang !== "it"; q.textContent = it ? q.dataset.it : q.dataset.en; q.lang = it ? "it" : "en"; b.dataset.tip = it ? "Read in English" : "Read in Italian"; b.setAttribute("aria-label", b.dataset.tip); b.classList.toggle("attivo", it); });
  async function fascicoloVero(t, q, prosaEl) {
    // ?demo=coda: simula 8 secondi di coda prima della risposta, per vedere l'avviso
    if (new URLSearchParams(location.search).get("demo") === "coda") await new Promise((ok) => { mostraCoda(t, prosaEl); setTimeout(ok, 8000); });
    const nd = (CH.ultimoIntento || {}).dibattiti, sp = seiPassi(prosaEl, nd ? TT(`${nd} dibattiti sul tema`, `${nd} debates on the topic`) : "");
    t.sp = sp; const come = t.el.querySelector("details.come"); if (come) come.hidden = true;
    prosaEl.addEventListener("fine-coda", () => { if (t.codaTimer) { clearInterval(t.codaTimer); t.codaTimer = null; } prosaEl.innerHTML = `<div class="carica" role="status"><span class="vh">${TT("Scrivo la risposta", "Writing the answer")}</span><i></i><i></i><i></i></div>`; });
    B.caricaSenato().catch(() => {});
    const r = await fetch("/api/fascicolo", { method: "POST", headers: { "Content-Type": "application/json", "Accept-Language": window.LANG }, body: JSON.stringify({ query: q, ...(CH.pesi ? { authority_weights: Object.fromEntries(CHIAVI_P.map((k, i) => [k, CH.pesi[i]])) } : {}) }) });
    if (!r.ok || !r.body) return null;
    const lettore = r.body.getReader(), dec = new TextDecoder(); let buf = "", md = "", dettagli = [], esperti = [], stat = null; const num = new Map(), passi = {};
    for (;;) {
      const { value, done } = await lettore.read(); if (done) break;
      buf += dec.decode(value, { stream: true }); let i;
      while ((i = buf.indexOf("\n")) >= 0) {
        const riga = buf.slice(0, i).trim(); buf = buf.slice(i + 1); if (!riga.startsWith("data:")) continue;
        let ev; try { ev = JSON.parse(riga.slice(5)); } catch { continue; }
        sp.evento(ev);
        if (ev.type === "progress") t.stato.textContent = TR(ev.message);
        else if (ev.type === "waiting") mostraCoda(t, prosaEl);
        else if (false) {
          const t0 = Date.now(); t.stato.textContent = TT("In coda", "In the queue");
          prosaEl.innerHTML = `<div class="coda" role="status"><div><b>${TT("La tua risposta è in coda", "Your answer is in the queue")}</b><p>${TT("Prepariamo poche risposte di confronto alla volta. La tua parte da sola appena si libera un posto: non serve ricaricare la pagina.", "We prepare a few comparison answers at a time. Yours starts on its own as soon as a slot frees up: no need to reload the page.")}</p></div><div class="coda__t"><small>${TT("attesa", "waiting")}</small><span aria-live="off">0:00</span></div><i class="coda__barra" aria-hidden="true"></i></div>`;
          const tm = prosaEl.querySelector(".coda__t span"); t.codaTimer = setInterval(() => { if (!tm.isConnected) return clearInterval(t.codaTimer); const s = Math.floor((Date.now() - t0) / 1000); tm.textContent = `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`; }, 1000);
        }
        else if (ev.type === "chunk") { if (t.codaTimer) { clearInterval(t.codaTimer); t.codaTimer = null; } md += ev.data || ""; prosaEl.innerHTML = mdFascicolo(md, t.n, num); }
        else if (ev.type === "experts") esperti = ev.data || [];
        else if (ev.type === "topic_stats") stat = ev;
        else if (ev.type === "citation_details") dettagli = ev.citations || [];
        else if (ev.type === "error" && /rate_limited|quota_exhausted/.test(ev.code || "")) t.limite = ev.message || "limite";
        else if (ev.type === "error") prosaEl.insertAdjacentHTML("beforeend", `<div class="errore">${e(ev.message || ev.text || "Errore")}</div>`);
      }
    }
    Object.values(passi).forEach((p) => p.fatto());
    if (!md.trim() || t.limite) { sp.togli(); t.sp = null; const come = t.el.querySelector("details.come"); if (come) come.hidden = false; return null; }
    prosaEl.innerHTML = mdFascicolo(md, t.n, num); prosaEl.classList.remove("cursore");
    if (stat) { t.el._stat = stat; numeriCliccabili(prosaEl, t.n); }
    citazioniInglese(prosaEl);
    // indice laterale: un salto per ogni gruppo e per le sezioni del fascicolo
    const voci = [];
    prosaEl.querySelectorAll("h4.f-tit, p").forEach((el, i) => {
      if (el.tagName === "H4") { el.id = `t${t.n}-s${i}`; voci.push({ id: el.id, t: el.textContent, sez: true }); return; }
      const m = /^(?:Per|For)\s+(.+?)(?:,|\s+nel\b|\s+in\b)/.exec(el.textContent); if (!m) return;
      const g = B.sigla(m[1]); if (!g || voci.some((v) => v.g === g)) return;
      el.id = `t${t.n}-g-${g.replace(/\W/g, "")}`; voci.push({ id: el.id, t: B.NOMI[g] || m[1], g });
    });
    const gv = voci.filter((v) => v.g);
    if (gv.length > 2) {
      const MAGG = ["FdI", "Lega", "FI", "NM"], seggi = {};
      B.gruppiCamera().forEach((g) => { seggi[g.sigla] = g.seggi; });
      if (B.SEN) Object.values(B.SEN.perId).forEach((x) => { const g = B.sigla(x.group); seggi[g] = (seggi[g] || 0) + 1; });
      const ord = (xs) => xs.sort((a, b) => (seggi[b.g] || 0) - (seggi[a.g] || 0));
      // le componenti del Misto in un gruppo a parte, dopo maggioranza e opposizione
      const misto = (v) => /\(Misto\)|^Misto\b/i.test(`${v.t} ${B.NOMI[v.g] || ""}`);
      const parti = [[TT("Maggioranza", "Majority"), ord(gv.filter((v) => MAGG.includes(v.g) && !misto(v)))], [TT("Opposizione", "Opposition"), ord(gv.filter((v) => !MAGG.includes(v.g) && !misto(v)))],
        [TT("Componenti del Gruppo misto", "Mixed group components"), ord(gv.filter(misto))]].filter(([, xs]) => xs.length);
      const bR = prosaEl.closest(".blocco"); bR.classList.add("con-indice");
      bR.insertAdjacentHTML("afterbegin", `<nav class="indice-g" aria-label="${TT("Gruppi in questa risposta", "Groups in this answer")}"><ul>${parti.map(([tit, xs]) => `<li class="indice-g__t">${tit}</li>${xs.map((v) => `<li><a href="#${v.id}" data-salta="${v.id}"><i style="background:${B.col(v.g)}"></i>${e(v.t)}</a></li>`).join("")}`).join("")}</ul></nav>`);
    }
    // fonti numerate nell'ordine delle citazioni
    const perId = Object.fromEntries(dettagli.map((d) => [d.chunk_id, d]));
    const fonti = [...num.entries()].sort((a, b) => a[1] - b[1]).map(([id, k]) => ({ k, d: perId[id] })).filter((x) => x.d);
    if (fonti.length) blocco(t, "fonti", TT("Fonti", "Sources"), `${fonti.length}`, `<ol class="fonti">${fonti.map(({ k, d }) => `<li id="f-${t.n}-${k}"><span class="n">${k}</span><span><a ${B.allaFonte(d.url, d.quote_text) ? `href="${e(B.allaFonte(d.url, d.quote_text))}" target="_blank" rel="noopener"` : `href="${e(B.interno(d.url, `${d.deputy_first_name} ${d.deputy_last_name}`, { a: d.debate || "", d: d.date || "", x: (d.quote_text || "").slice(0, 600) }))}"`}>${e(`${d.deputy_first_name} ${d.deputy_last_name}`)}</a>${d.group ? `<span class="fonte-g">${e(B.NOMI[B.sigla(d.group)] || B.frase(d.group))}</span>` : ""}<small>${B.data(d.date)}${d.debate ? ` · ${e(B.taglia(d.debate, 80))}` : ""}${d.verified ? ` · ${TT("verificata", "verified")}` : ""}</small></span></li>`).join("")}</ol>`);
    // una voce per gruppo, con l'autorevolezza calcolata dal backend
    const perG = {}; esperti.forEach((x) => { const g = B.sigla(x.group); if (!perG[g] || x.authority_score > perG[g].authority_score) perG[g] = x; });
    const gr = B.ORDINE.filter((g) => perG[g]), pesiT = CH.pesi && CH.pesi.slice();
    esperti.forEach((x) => { x._pesi = pesiT; });
    if (gr.length) blocco(t, "posizioni", TT("Una voce per gruppo", "One voice per group"), `${B.info(TT("Per ogni gruppo l'oratore con l'autorevolezza più alta sul tema, fra quelli trovati nelle evidenze", "For each group the speaker with the highest authority on the topic among those in the evidence"))}<button type="button" class="ic-a" data-pesi-voci="${t.n}" aria-label="${TT("Criteri e pesi", "Criteria and weights")}" data-tip="${TT("Criteri e pesi", "Criteria and weights")}">${B.ico("impost")}</button>`,
      `${pesiT ? `<p class="pesi-pers"><span>${TT("Pesi personalizzati", "Custom weights")}</span><small>${CRIT_P().map(([, tt], i) => `${e(tt)} ${Math.round(pesiT[i] * 100)}%`).join(" · ")}</small><button type="button" class="ic-a" data-pesi-paper="${t.n}" aria-label="${TT("Rifai con i pesi del paper", "Redo with the paper's weights")}" data-tip="${TT("Rifai con i pesi del paper. Conta come una domanda.", "Redo with the paper's weights. Counts as one question.")}">${B.ico("ripristina")}</button></p>` : ""}<div class="esperti">${gr.map((g) => { const x = perG[g], id = (/p(\d+)$/.exec(x.id || "") || [])[1], p = id ? (B.persona(id) || { id, n: `${x.first_name} ${x.last_name}`, sigla: g }) : null; CH._esperti = CH._esperti || {}; CH._esperti[x.id] = x; return `<button class="esperto" data-esperto="${e(x.id)}">${p ? B.fotoHtml(p) : `<span class="foto"><img src="/dati/foto/senatori/${e((/senatore\/(\d+)$/.exec(x.id || "") || [])[1] || "")}.jpg" alt="" onerror="this.remove()"></span>`}<span><b>${e(`${x.first_name} ${x.last_name}`)}</b><span class="ramo-v">${B.carica(x)}</span>${B.sigLungo(g)}</span><span class="aut"><b>${Number(x.authority_score).toFixed(2)}</b><small>${TT("autorevolezza", "authority")}</small></span></button>`; }).join("")}</div>`);
    sp.fine(gr.length);
    if (stat) t.stato.textContent = TT(`${stat.intervention_count} interventi di ${stat.speaker_count} parlamentari`, `${stat.intervention_count} speeches by ${stat.speaker_count} members`);
    return md.replace(/\[«([\s\S]+?)»\]\([\w.-]+\)/g, "«$1»").replace(/\*\*/g, "");
  }

  /* ---------- criteri e pesi della conversazione ---------- */
  // chiavi del backend nell'ordine dei criteri dello strumento Autorevolezza
  const CHIAVI_P = ["interventions", "committee", "acts", "profession", "education", "role"];
  const CRIT_P = () => [[.25, TT("Interventi in Aula", "Floor speeches"), TT("Quanto, e quanto di recente, ha parlato del tema in Aula.", "How much, and how recently, they spoke on the topic in the chamber.")], [.25, TT("Commissione", "Committee"), TT("Quanto la sua commissione è vicina al tema.", "How close their committee is to the topic.")], [.20, TT("Atti firmati", "Signed acts"), TT("Proposte e altri atti sul tema che ha firmato, pesati per recenza.", "Bills and other acts on the topic they signed, weighted by recency.")], [.15, TT("Professione", "Profession"), TT("Affinità tra il suo lavoro fuori dall'Aula e il tema.", "Affinity between their work outside Parliament and the topic.")], [.10, TT("Formazione", "Education"), TT("Affinità tra i suoi titoli di studio e il tema.", "Affinity between their degrees and the topic.")], [.05, TT("Ruolo istituzionale", "Institutional role"), TT("Incarichi in corso, per esempio in Governo o in commissione.", "Current offices, for example in government or on a committee.")]];
  CH.pesi = null;
  // il bottone dei pesi nella casella della domanda resta acceso finché ci sono pesi personalizzati
  const segnaPesi = () => B.$$("[data-pesi-prima]").forEach((b) => b.setAttribute("aria-pressed", String(!!CH.pesi)));
  const rifai = (tt) => { if (!tt) return; B.chiudiPannello(); CH.chiedi(tt.querySelector(".turno__dom").textContent); };
  function pannelloPesi(tt) {
    const cr = CRIT_P(), base = (CH.pesi || cr.map((c) => c[0])).slice(), w = base.slice();
    const uguali = (a, b) => a.every((x, i) => Math.abs(x - b[i]) < .005);
    const html = () => `<p class="pesi-nota">${TT("Sei criteri, una somma pesata; i pesi fanno sempre 100%. Con pesi diversi può cambiare la voce scelta per un gruppo, e con lei citazioni e risposta.", "Six criteria, one weighted sum; the weights always add up to 100%. Different weights can change the voice chosen for a group, and with it the quotes and the answer.")}</p>${cr.map(([, t, d], i) => `<div class="peso-r"><div><b>${e(t)}</b>${B.info(d)}</div><input type="range" min="0" max="100" step="1" value="${Math.round(w[i] * 100)}" data-peso="${i}" aria-label="${e(t)}"><span>${Math.round(w[i] * 100)}%</span></div>`).join("")}
      <div class="pesi-az"><button class="bt-mini" data-ripristina>${TT("Ripristina i pesi del paper", "Reset to the paper's weights")}</button><button class="bt-pieno" data-rifai disabled data-tip="${TT("Rilancia la domanda. Conta come una domanda nel limite orario.", "Asks the question again. Counts as one question in the hourly limit.")}">${TT("Rifai con questi pesi", "Redo with these weights")}</button></div>`;
    B.pannello(TT("Criteri e pesi", "Criteria and weights"), html());
    const pan = document.getElementById("pannello");
    const stato = () => { const b = pan.querySelector("[data-rifai]"); if (b) b.disabled = uguali(w, base); };
    if (!tt) { const b = pan.querySelector("[data-rifai]"); b.textContent = TT("Usa questi pesi", "Use these weights"); b.dataset.tip = TT("Valgono per le prossime domande di confronto fra i gruppi", "They apply to the next questions comparing the groups"); }
    pan.oninput = (ev) => { const r = ev.target.closest("[data-peso]"); if (!r) return; B.ribilancia(w, +r.dataset.peso, r.value / 100).forEach((x, k) => { w[k] = x; }); pan.querySelectorAll("[data-peso]").forEach((q, k) => { if (q !== r) q.value = Math.round(w[k] * 100); q.nextElementSibling.textContent = `${Math.round(w[k] * 100)}%`; }); stato(); };
    pan.onclick = (ev) => {
      if (ev.target.closest("[data-ripristina]")) { cr.forEach((c, i) => { w[i] = c[0]; }); pan.querySelectorAll("[data-peso]").forEach((r, i) => { r.value = Math.round(w[i] * 100); r.nextElementSibling.textContent = `${r.value}%`; }); stato(); return; }
      if (ev.target.closest("[data-rifai]")) { CH.pesi = w.some((x) => x > 0) && !uguali(w, cr.map((c) => c[0])) ? w.slice() : null; pan.oninput = pan.onclick = null; segnaPesi(); if (tt) rifai(tt); else B.chiudiPannello(); }
    };
  }

  /* ---------- cronologia (nel browser) e condivisione (istantanea sul server) ---------- */
  const CHIAVE_STORIA = "parliamentrag-chat";
  const leggiStoria = () => { try { return JSON.parse(localStorage.getItem(CHIAVE_STORIA) || "[]"); } catch { return []; } };
  const nuovoId = () => Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
  CH.idChat = null;
  const CHIAVE_APERTA = "parliamentrag-aperta";
  function aperta(v) {
    try { if (v === undefined) return JSON.parse(sessionStorage.getItem(CHIAVE_APERTA) || "null"); if (v === null) sessionStorage.removeItem(CHIAVE_APERTA); else sessionStorage.setItem(CHIAVE_APERTA, JSON.stringify({ ...(aperta() || {}), ...v })); } catch { return null; }
  }
  addEventListener("pagehide", () => { if (document.body.dataset.vista === "conversazione" && CH.idChat) aperta({ y: Math.round(scrollY) }); });
  const turni = () => B.$$("#conversazione .turno").map((x) => ({ q: x.querySelector(".turno__dom").textContent, html: x.outerHTML.replace(/ class="corre"/g, "") }));
  function salva() {
    if (!CH.idChat) return;
    const tt = turni(); if (!tt.length) return;
    let xs = leggiStoria().filter((x) => x.id !== CH.idChat);
    xs.unshift({ id: CH.idChat, titolo: tt[0].q, agg: new Date().toISOString(), turni: tt });
    xs = xs.slice(0, 20);
    for (;;) { try { localStorage.setItem(CHIAVE_STORIA, JSON.stringify(xs)); break; } catch { if (xs.length <= 1) break; xs.pop(); } }
  }
  CH.nuova = () => { aperta(null); CH.proponi(null); CH.idChat = null; CH.pesi = null; segnaPesi(); storia.length = 0; delete CH.ultimaPersona; $("#conversazione").innerHTML = ""; location.hash = "#/"; };
  CH.apriStoria = (id) => {
    const x = leggiStoria().find((y) => y.id === id); if (!x) return;
    CH.idChat = x.id; CH.pesi = null; segnaPesi(); storia.length = 0; x.turni.forEach((tt) => storia.push({ role: "user", content: tt.q }));
    $("#conversazione").innerHTML = x.turni.map((tt) => tt.html).join("");
    document.body.dataset.vista = "conversazione"; history.replaceState(null, "", "#/chiedi"); B.chiudiPannello(); window.scrollTo(0, 0);
    aperta({ id: x.id, attesa: null });
  };
  // ricaricando la pagina si resta nella conversazione: si riapre dalla cronologia, nel punto lasciato;
  // una domanda rimasta a metà si rifà
  CH.riprendi = () => {
    const a = aperta(); if (!a) return false;
    const c = leggiStoria().find((y) => y.id === a.id);
    if (c) { CH.apriStoria(a.id); if (a.y) requestAnimationFrame(() => window.scrollTo(0, a.y)); }
    if (a.attesa && !(c && c.turni.some((tt) => tt.q === a.attesa))) { CH.idChat = a.id; CH.chiedi(a.attesa); return true; }
    return !!c;
  };
  CH.mostraStoria = () => {
    const xs = leggiStoria();
    B.pannello(TT("Le tue chat", "Your chats"), `<button class="bt bt--primario" data-nuova-chat>${B.ico("piu")}${TT("Nuova chat", "New chat")}</button>
      ${xs.length ? `<ul class="storia">${xs.map((x) => `<li><button data-apri-chat="${e(x.id)}"><b>${e(B.taglia(x.titolo, 90))}</b><small>${B.data(x.agg)} · ${x.turni.length} ${x.turni.length === 1 ? TT("domanda", "question") : TT("domande", "questions")}</small></button><button class="ic-a" data-cancella-chat="${e(x.id)}" aria-label="${TT("Cancella", "Delete")}" data-tip="${TT("Cancella", "Delete")}">${B.ico("cestino")}</button></li>`).join("")}</ul>` : `<p style="color:var(--t3)">${TT("Ancora nessuna chat.", "No chats yet.")}</p>`}`);
    $("#pannello-tipo").insertAdjacentHTML("beforeend", " " + B.info(TT("L'elenco delle chat resta in questo browser e lo cancelli quando vuoi. Per correggere gli errori salviamo domande e risposte, senza il tuo indirizzo IP: non scrivere dati personali.", "The list of chats stays in this browser and you can delete it whenever you like. To fix errors we keep questions and answers, without your IP address: do not write personal data.")));
    // quante domande restano nell'ultima ora: una riga discreta sotto «Nuova chat»
    fetch("/api/uso").then((r) => (r.ok ? r.json() : null)).then((u) => {
      const b = $("#pannello-corpo [data-nuova-chat]"); if (!u || !b || !u.limit) return;
      const min = Math.max(1, Math.ceil(u.resets_in / 60)), pieno = u.used >= u.limit;
      const ora = '<svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>';
      const resto = Math.max(0, u.limit - u.used);
      const quante = resto === 0 ? TT("Nessuna domanda rimanente", "No questions left") : resto === 1 ? TT("1 domanda rimanente", "1 question left") : TT(`${resto} domande rimanenti`, `${resto} questions left`);
      const giu = `${quante}. ${TT(`Si resetta tra ${min} ${min === 1 ? "minuto" : "minuti"}.`, `Resets in ${min} ${min === 1 ? "minute" : "minutes"}.`)}`;
      b.insertAdjacentHTML("afterend", `<div class="uso${pieno ? " uso--pieno" : ""}" role="status"><div class="uso__testa">${TT("Domande di quest'ora", "Questions this hour")}<span>${u.used}<em> / ${u.limit}</em></span></div><div class="uso__barra"><i style="width:${u.used ? Math.min(100, (100 * u.used) / u.limit) : 0}%"></i></div><small>${ora}${giu}</small></div>`);
    }).catch(() => { /* senza il conteggio il pannello funziona lo stesso */ });
  };
  const spunta = (bt, tip) => {
    if (!bt._ico) bt._ico = bt.innerHTML, bt._tip = bt.dataset.tip;
    clearTimeout(bt._t); bt.innerHTML = B.ico("ok"); bt.classList.add("copiato"); bt.dataset.tip = tip; bt.setAttribute("aria-label", tip);
    bt._t = setTimeout(() => { bt.innerHTML = bt._ico; bt.classList.remove("copiato"); bt.dataset.tip = bt._tip; bt.setAttribute("aria-label", bt._tip); }, 2200);
  };
  async function condividi(bt) {
    const tt = turni(); if (!tt.length) return;
    bt.dataset.tip = TT("Creo il link…", "Creating the link…");
    try {
      const r = await fetch("/api/condividi", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ titolo: tt[0].q, lingua: window.LANG, turni: tt }) });
      const { id } = await r.json(); const url = `${location.origin}/#/c/${id}`;
      // copiato: l'icona diventa una spunta verde; il pannello col link serve solo se gli appunti non sono disponibili
      let copiato = false;
      if (navigator.clipboard) copiato = await navigator.clipboard.writeText(url).then(() => true, () => false);
      if (copiato) { spunta(bt, TT("Link copiato", "Link copied")); return; }
      bt.dataset.tip = TT("Condividi", "Share");
      B.pannello(TT("Link alla conversazione", "Link to the conversation"), `<p>${TT("Chi ha il link vede questa conversazione così com'è ora. Il link è già negli appunti.", "Anyone with the link sees this conversation as it is now. The link is already on your clipboard.")}</p><div class="endpoint" translate="no"><code>${e(url)}</code><button class="ic-a endpoint__copia" data-copia-testo="${e(url)}" aria-label="${TT("Copia", "Copy")}" data-tip="${TT("Copia", "Copy")}">${B.ico("copia")}</button></div>`);
    } catch (err) { bt.dataset.tip = TT("Non riesco a creare il link", "I can't create the link"); }
  }
  CH.apriCondivisa = async (id) => {
    document.body.dataset.vista = "conversazione"; const box = $("#conversazione");
    box.innerHTML = `<div class="carica" role="status"><span class="vh">${TT("Apro la conversazione", "Opening the conversation")}</span><i></i><i></i><i></i></div>`;
    try {
      const r = await fetch(`/dati/condivisi/${encodeURIComponent(id)}.json`); if (!r.ok) throw new Error(TT("Conversazione non trovata", "Conversation not found"));
      const x = await r.json();
      box.innerHTML = `<div class="condivisa">${B.ico("condividi")}<span>${TT("Conversazione condivisa", "Shared conversation")} · ${B.data(x.creata)}</span><button class="bt-mini" data-nuova-chat>${TT("Fai una domanda nuova", "Ask a new question")}</button></div>` + x.turni.map((tt) => tt.html).join("");
      CH.idChat = null; storia.length = 0; x.turni.forEach((tt) => storia.push({ role: "user", content: tt.q }));
    } catch (err) { box.innerHTML = `<div class="errore">${e(err.message)}</div>`; }
  };

  /* ---------- eventi ---------- */
  document.addEventListener("click", (ev) => {
    const f = ev.target.closest("[data-fonte]");
    if (f) { const li = document.getElementById("f-" + f.dataset.fonte); if (li) { li.scrollIntoView({ block: "center" }); li.setAttribute("data-acceso", ""); setTimeout(() => li.removeAttribute("data-acceso"), 1800); } return; }
    const v = ev.target.closest("[data-voto-i]");
    if (v) { const b = v.closest(".blocco"); B.$$("[data-voto-i]", b).forEach((x) => x.setAttribute("aria-pressed", x === v)); CH.aulaVoto(b.querySelector(".aula-box"), b._voti[+v.dataset.votoI]); return; }
    const g = ev.target.closest("[data-chiedi-cl]");
    if (g) { const tt = g.closest(".turno"); const it = CH.intento(g.dataset.chiediCl); it.conGoverno = g.dataset.gov === "1"; classifica(tt._t, it, tt.querySelector(".prosa")); return; }
    const ne = ev.target.closest("[data-elenco]");
    if (ne) { ev.preventDefault(); const tt = ne.dataset.turno ? document.getElementById(`turno-${ne.dataset.turno}`) : null; if (tt && tt._stat) CH.statAperta = tt._stat; if (CH.statAperta) elencoTema(CH.statAperta, ne.dataset.elenco, ne.dataset.chi); return; }
    const sl = ev.target.closest("[data-salta]"); if (sl) { ev.preventDefault(); const x = document.getElementById(sl.dataset.salta); if (x) { x.scrollIntoView({ behavior: "smooth", block: "start" }); x.classList.add("acceso"); setTimeout(() => x.classList.remove("acceso"), 1500); } return; }
    if (ev.target.closest("[data-pesi-prima]")) { pannelloPesi(null); return; }
    const pv = ev.target.closest("[data-pesi-voci]"); if (pv) { pannelloPesi(pv.closest(".turno")); return; }
    const pp = ev.target.closest("[data-pesi-paper]"); if (pp) { CH.pesi = null; segnaPesi(); rifai(pp.closest(".turno")); return; }
    const es = ev.target.closest("[data-esperto]"); if (es && CH._esperti[es.dataset.esperto]) { const x = CH._esperti[es.dataset.esperto]; B.criteri(x, x._pesi || undefined); return; }
    const cd = ev.target.closest("[data-condividi]"); if (cd) { condividi(cd); return; }
    if (ev.target.closest("[data-nuova-chat]")) { B.chiudiPannello(); CH.nuova(); return; }
    const ac = ev.target.closest("[data-apri-chat]"); if (ac) { CH.apriStoria(ac.dataset.apriChat); return; }
    const cc = ev.target.closest("[data-cancella-chat]"); if (cc) { try { localStorage.setItem(CHIAVE_STORIA, JSON.stringify(leggiStoria().filter((x) => x.id !== cc.dataset.cancellaChat))); } catch { /* niente */ } CH.mostraStoria(); return; }
    const c = ev.target.closest("[data-copia]");
    if (c) { const tx = document.querySelector(`#turno-${c.dataset.copia} .prosa`); navigator.clipboard && navigator.clipboard.writeText(tx ? tx.innerText : ""); spunta(c, TT("Copiata", "Copied")); return; }
    const sg = ev.target.closest("[data-segnala]"); if (sg) { segnala(sg.closest(".turno")); return; }
    // utile / non utile: si può cambiare idea, e un secondo clic sullo stesso toglie la scelta
    const u = ev.target.closest("[data-utile]"); if (u) { const gia = u.classList.contains("fatto"); u.parentNode.querySelectorAll("[data-utile]").forEach((x) => { x.classList.remove("fatto"); x.setAttribute("aria-pressed", "false"); x.dataset.tip = x.getAttribute("aria-label"); }); if (!gia) { u.classList.add("fatto"); u.setAttribute("aria-pressed", "true"); u.dataset.tip = TT("Grazie", "Thanks"); } salva(); }
  });
  /* ---------- barra della conversazione: un punto per domanda, una linea per risposta ---------- */
  {
    const conv = $("#conversazione");
    const rail = document.createElement("nav"); rail.className = "conv-rail"; rail.setAttribute("aria-label", TT("Domande di questa chat", "Questions in this chat"));
    document.body.appendChild(rail);
    // bottoni e non link: un indirizzo #turno-N verrebbe letto dal router come una pagina e porterebbe alla home
    const disegna = () => {
      const turni = B.$$(".turno", conv);
      rail.hidden = turni.length < 2;
      rail.innerHTML = turni.map((t) => { const q = (t.querySelector(".turno__dom") || {}).textContent || ""; return `<button type="button" class="conv-rail__q" data-vai-turno="${t.id}" aria-label="${e(q)}" data-tip="${e(B.taglia(q, 70))}"></button><span class="conv-rail__a" aria-hidden="true"></span>`; }).join("");
      segna();
    };
    // la domanda corrente è l'ultima il cui inizio è salito sopra il 40% della finestra: una sola alla volta
    const segna = () => {
      const turni = B.$$(".turno", conv); if (!turni.length) return;
      let cur = turni[0]; turni.forEach((t) => { if (t.getBoundingClientRect().top < innerHeight * .4) cur = t; });
      B.$$("[data-vai-turno]", rail).forEach((x) => x.toggleAttribute("aria-current", x.dataset.vaiTurno === cur.id));
    };
    new MutationObserver(disegna).observe(conv, { childList: true });
    let rf = 0; addEventListener("scroll", () => { cancelAnimationFrame(rf); rf = requestAnimationFrame(segna); }, { passive: true });
    rail.addEventListener("click", (ev) => { const x = ev.target.closest("[data-vai-turno]"); if (!x) return; const t = document.getElementById(x.dataset.vaiTurno); if (t) t.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" }); });
    disegna();
  }
})();

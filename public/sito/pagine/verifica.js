(function () {
  "use strict";
  var D = window.DATI;
  var CIT = D.tema.citazioni;
  var API = "/api/verifica";
  var SPUNTA = window.ICONE.spunta, CROCE = window.ICONE.croce;
  var FORSE = '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><circle cx="8" cy="8" r="6.6"/><path d="M5.5 8h5"/></svg>';
  var EN = window.LINGUA === "en";
  var esc = window.esc, numero = window.numero, dataIt = window.dataLunga;
  /* Le sigle e i nomi dei gruppi restano italiani; il Governo si scrive nella lingua della pagina */
  var sigla = function (g) { return EN && g === "Governo" ? "Government" : g; };

  /* I nomi con cui il verificatore riconosce i gruppi vengono dal verificatore
     stesso (VOICES in Fascicoli, via /api/verifica/nomi): nessuna copia qui. */
  var NOMI_API = "/api/verifica/nomi";

  /* Formato JSON verificabile, versione 1 */
  var SCHEMA_V1 = "https://w3id.org/parliamentrag/verify/v1";
  var P = "http://dati.camera.it/ocd/persona.rdf/";
  /* Esempio scritto da noi: tre citazioni vere, la terza con una parola
     cambiata («tenuti» al posto di «obbligati»). */
  var ESEMPIO_V1 = {
    schema: SCHEMA_V1,
    system: { name: EN ? "Example" : "Esempio" },
    question: EN ? "What do the groups think about the minimum wage?" : "Cosa pensano i gruppi del salario minimo?",
    data_version: "2026-10-16",
    claims: [
      { speaker: P + "p305688", group: "http://dati.camera.it/ocd/gruppoParlamentare.rdf/gr4133",
        speech: "leg19_sed16_tit00040.sub00020.int00180",
        quote: "la prima risoluzione su questo tema è stata presentata dal sottoscritto",
        link: "https://www.camera.it/leg19/410?idSeduta=0016&tipo=stenografico#sed0016.stenografico.tit00040.sub00020.int00180" },
      { speaker: P + "p307436", group: "http://dati.camera.it/ocd/componenteGruppoMisto.rdf/cgm4139",
        speech: "leg19_sed690_tit00090.int00090",
        quote: "siccome secondo noi è una legge antidemocratica, plebiscitaria",
        link: "https://www.camera.it/leg19/410?idSeduta=0690&tipo=stenografico#sed0690.stenografico.tit00090.int00090" },
      { speaker: "gov_durigon_claudio", government: true,
        speech: "leg19_sed15_tit00070.sub00020.int00020",
        quote: "per gli Stati che, invece, non sono tenuti ad introdurre un salario minimo legale",
        link: "https://www.camera.it/leg19/410?idSeduta=0015&tipo=stenografico#sed0015.stenografico.tit00070.sub00020.int00020" }
    ]
  };

  /* Il testo incollato è una risposta nel formato v1? */
  function rispostaV1(testo) {
    var t = testo.trim();
    if (t.charAt(0) !== "{") return null;
    try {
      var o = JSON.parse(t);
      return o && o.schema === SCHEMA_V1 ? o : null;
    } catch (e) {
      return null;
    }
  }

  function norm(s) { return String(s || "").replace(/[’‘ʼ`´]/g, "'").replace(/\s+/g, " ").trim(); }
  function parole(s) { return norm(s).split(" ").filter(Boolean); }

  /* LCS sulle parole, come nella pagina iniziale */
  function allinea(a, b) {
    var n = a.length, m = b.length, t = [], i, j;
    for (i = 0; i <= n; i++) t.push(new Array(m + 1).fill(0));
    for (i = n - 1; i >= 0; i--) for (j = m - 1; j >= 0; j--)
      t[i][j] = a[i] === b[j] ? t[i + 1][j + 1] + 1 : Math.max(t[i + 1][j], t[i][j + 1]);
    var r = []; i = 0; j = 0;
    while (i < n && j < m) {
      if (a[i] === b[j]) { r.push({ w: b[j], s: "ok" }); i++; j++; }
      else if (t[i + 1][j] >= t[i][j + 1]) { r.push({ w: a[i], s: "no" }); i++; }
      else { r.push({ w: b[j], s: "nuovo" }); j++; }
    }
    while (i < n) r.push({ w: a[i++], s: "no" });
    while (j < m) r.push({ w: b[j++], s: "nuovo" });
    /* La citazione può essere una parte dell'intervento: togliamo le parole
       del resoconto prima della prima coincidenza e dopo l'ultima */
    var primo = -1, ultimo = -1, uguali = 0;
    r.forEach(function (x, k) { if (x.s !== "no") { if (primo < 0) primo = k; ultimo = k; } if (x.s === "ok") uguali++; });
    if (!uguali) return { r: r, uguali: 0 };
    var tagliato = r.filter(function (x, k) { return !(x.s === "no" && (k < primo || k > ultimo)); });
    return { r: tagliato, uguali: uguali };
  }

  /* ---------- Interfaccia ---------- */
  var area = document.getElementById("risposta");
  var domanda = document.getElementById("domanda");
  var esito = document.getElementById("esito");
  var stato = document.getElementById("stato");
  var msg = document.getElementById("msg");
  var conta = document.getElementById("conta");
  var bottone = document.getElementById("verifica");

  /* Esempio scritto da noi: due citazioni esatte, una con una parola cambiata
     («lavoratori» al posto di «sindacati»). Alcuni gruppi non compaiono. */
  function q(g) { return CIT.filter(function (x) { return x.group === g; })[0]; }
  var ESEMPIO = EN
    ? "The Chamber is divided on the minimum wage. The opposition wants a threshold set by law; the majority and the Government rely on collective bargaining.\n\n" +
      "Brothers of Italy is against it. Marcello Coppo: «" + q("FdI").quote + "»\n\n" +
      "The PD links the proposal to Article 36 of the Constitution. Maria Cecilia Guerra: «" + q("PD").quote + "».\n\n" +
      "Forza Italia fears effects on collective bargaining. Chiara Tenerini: «" + q("FI").quote.replace("dei sindacati", "dei lavoratori") + "».\n\n" +
      "The Lega points out how many workers are already covered by collective agreements. M5S, AVS and Azione support a legal threshold. For the Government the matter belongs to the social partners."
    : "Sul salario minimo la Camera è divisa. Le opposizioni chiedono una soglia fissata per legge; la maggioranza e il Governo puntano sulla contrattazione collettiva.\n\n" +
    "Fratelli d'Italia è contraria. Per Marcello Coppo: «" + q("FdI").quote + "»\n\n" +
    "Il PD lega la proposta all'articolo 36 della Costituzione. Maria Cecilia Guerra: «" + q("PD").quote + "».\n\n" +
    "Forza Italia teme effetti sulla contrattazione. Chiara Tenerini: «" + q("FI").quote.replace("dei sindacati", "dei lavoratori") + "».\n\n" +
    "La Lega ricorda quanti lavoratori sono già coperti dai contratti collettivi. M5S, AVS e Azione sostengono una soglia legale. Per il Governo la materia spetta alle parti sociali.";

  function contaParole() {
    var n = area.value.trim() ? area.value.trim().split(/\s+/).length : 0;
    conta.textContent = EN ? (n === 1 ? "1 word" : numero(n) + " words") : (n === 1 ? "1 parola" : numero(n) + " parole");
  }
  area.addEventListener("input", function () { contaParole(); msg.textContent = ""; });
  [area, domanda].forEach(function (el) {
    el.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); verifica(); }
    });
  });
  document.getElementById("esempio").addEventListener("click", function () {
    area.value = ESEMPIO;
    domanda.value = EN ? "What do the groups think about the minimum wage?" : "Cosa pensano i gruppi del salario minimo?";
    contaParole();
    msg.removeAttribute("data-tipo");
    msg.textContent = EN ? "Example inserted. It contains three quotes: one has a changed word." : "Esempio inserito. Contiene tre citazioni: una ha una parola cambiata.";
    bottone.focus();
  });
  document.getElementById("esempio-json").addEventListener("click", function () {
    area.value = JSON.stringify(ESEMPIO_V1, null, 2);
    domanda.value = "";
    contaParole();
    msg.removeAttribute("data-tipo");
    msg.textContent = EN ? "JSON example inserted. It contains three quotes: one has a changed word." : "Esempio JSON inserito. Contiene tre citazioni: una ha una parola cambiata.";
    bottone.focus();
  });
  var vuoto = esito.innerHTML;
  document.getElementById("svuota").addEventListener("click", function () {
    area.value = "";
    domanda.value = "";
    contaParole();
    msg.textContent = "";
    esito.innerHTML = vuoto;
    stato.textContent = EN ? "Waiting" : "In attesa";
    stato.style.color = "";
    area.focus();
  });
  document.getElementById("modulo").addEventListener("submit", function (e) { e.preventDefault(); verifica(); });

  function voce(nome, e, extra) {
    var icona = e === "ok" ? SPUNTA : e === "no" ? CROCE : FORSE;
    return '<span class="sigillo__voce" data-esito="' + e + '">' + icona + nome + (extra ? " <b>" + extra + "</b>" : "") + "</span>";
  }
  var ESITO = { pass: "ok", fail: "no", na: "nd" };

  var inCorso = false;
  function verifica() {
    var testo = area.value;
    if (!testo.trim()) {
      msg.dataset.tipo = "errore";
      msg.textContent = EN ? "Paste an answer before checking, or use the example." : "Incolla una risposta prima di verificare, oppure usa l'esempio.";
      area.focus();
      return;
    }
    if (inCorso) return;
    var v1 = rispostaV1(testo);
    if (!v1 && testo.trim().charAt(0) === "{" && /"schema"\s*:/.test(testo)) {
      msg.dataset.tipo = "errore";
      msg.textContent = EN ? "This looks like JSON, but it is not a valid answer in the v1 format: check the schema field and the commas." : "Sembra JSON, ma non è una risposta valida nel formato v1: controlla il campo schema e le virgole.";
      return;
    }
    if (v1) return verificaV1(v1);
    inCorso = true;
    bottone.disabled = true;
    msg.textContent = "";
    esito.setAttribute("aria-busy", "true");
    stato.textContent = EN ? "Checking" : "Controllo in corso";
    stato.style.color = "";
    esito.innerHTML = '<div class="attesa"><span>' + (EN ? "Searching the whole legislature and computing authority on the topic. It can take up to a minute…" : "Cerco in tutta la legislatura e calcolo l'autorevolezza sul tema. Può volerci fino a un minuto…") + '</span><span class="attesa__riga"><i></i></span></div>';
    fetch(API, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ answer: testo, topic: domanda.value.trim() || null })
    }).then(function (r) {
      if (r.status === 429) throw new Error(EN ? "Too many checks from this connection: try again in an hour." : "Troppe verifiche da questa connessione: riprova tra un'ora.");
      if (!r.ok) throw new Error(EN ? "The verifier is not answering right now. Try again in a minute." : "Il verificatore non risponde in questo momento. Riprova tra un minuto.");
      return r.json();
    }).then(function (rapporto) {
      mostra(testo, rapporto);
    }).catch(function (err) {
      esito.innerHTML = vuoto;
      stato.textContent = EN ? "Not checked" : "Non verificata";
      msg.dataset.tipo = "errore";
      msg.textContent = err.message;
    }).then(function () {
      inCorso = false;
      bottone.disabled = false;
      esito.setAttribute("aria-busy", "false");
    });
  }

  /* ---------- Formato v1: solo citazioni ---------- */
  function verificaV1(risposta) {
    inCorso = true;
    bottone.disabled = true;
    msg.textContent = "";
    esito.setAttribute("aria-busy", "true");
    stato.textContent = EN ? "Checking" : "Controllo in corso";
    stato.style.color = "";
    esito.innerHTML = '<div class="attesa"><span>' + (EN ? "Checking each quote against the record…" : "Controllo ogni citazione sul resoconto…") + '</span><span class="attesa__riga"><i></i></span></div>';
    fetch(API, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ v1: risposta })
    }).then(function (r) {
      if (r.status === 429) throw new Error(EN ? "Too many checks from this connection: try again in an hour." : "Troppe verifiche da questa connessione: riprova tra un'ora.");
      if (r.status === 422) return r.json().then(function (j) {
        var e = (j && j.errors) || [];
        throw new Error((EN ? "The JSON does not follow the v1 format: " : "Il JSON non segue il formato v1: ") + e.slice(0, 3).join("; ") + (e.length > 3 ? "…" : ""));
      });
      if (r.status === 413) throw new Error(EN ? "The answer is too long to check here." : "La risposta è troppo lunga per controllarla qui.");
      if (!r.ok) throw new Error(EN ? "The verifier is not answering right now. Try again in a minute." : "Il verificatore non risponde in questo momento. Riprova tra un minuto.");
      return r.json();
    }).then(function (out) {
      mostraV1(out.report);
    }).catch(function (err) {
      esito.innerHTML = vuoto;
      stato.textContent = EN ? "Not checked" : "Non verificata";
      msg.dataset.tipo = "errore";
      msg.textContent = err.message;
    }).then(function () {
      inCorso = false;
      bottone.disabled = false;
      esito.setAttribute("aria-busy", "false");
    });
  }

  var ESITI_V1 = EN ? {
    esatta: ["Matches", "the record, word for word"],
    esatta_dopo_normalizzazione: ["Matches", "with an allowed difference"],
    non_trovata: ["Not found", "the words are not in the speech"],
    parole_di_terzi: ["Someone else's words", "the speaker is quoting another person"],
    oratore_errato: ["Wrong speaker", "someone else gives this speech"],
    gruppo_errato: ["Wrong group", "not the speaker's group on that date"],
    link_errato: ["Wrong link", "it does not lead to the record of that sitting"],
    intervento_inesistente: ["Speech not found", "no speech with this id in the data"]
  } : {
    esatta: ["Coincide", "con il resoconto, parola per parola"],
    esatta_dopo_normalizzazione: ["Coincide", "con una differenza ammessa"],
    non_trovata: ["Non trovata", "le parole non sono nell'intervento"],
    parole_di_terzi: ["Parole di altri", "l'oratore sta citando un'altra persona"],
    oratore_errato: ["Oratore sbagliato", "l'intervento è di un'altra persona"],
    gruppo_errato: ["Gruppo sbagliato", "non è il gruppo di chi parla, a quella data"],
    link_errato: ["Link sbagliato", "non porta al resoconto di quella seduta"],
    intervento_inesistente: ["Intervento inesistente", "nei dati non c'è un intervento con questo ID"]
  };
  var NORMALIZZAZIONI = EN ? { whitespace: "extra spaces", first_letter_case: "first letter case", typographic_apostrophe: "typographic apostrophes" }
    : { whitespace: "spazi in più", first_letter_case: "maiuscola iniziale", typographic_apostrophe: "apostrofi tipografici" };
  var CONTROLLI = EN
    ? [["speech", "speech"], ["text", "text"], ["own_words", "own words"], ["speaker", "speaker"], ["group", "group"], ["link", "link"]]
    : [["speech", "intervento"], ["text", "testo"], ["own_words", "parole proprie"], ["speaker", "oratore"], ["group", "gruppo"], ["link", "link"]];
  var STATI = { ok: "✓", fail: "✗", not_verifiable: "?", not_checked: "–" };

  function mostraV1(R) {
    var Q = R.quotes, D = R.data;
    var eC = !Q.total ? "nd" : Q.exact === Q.total ? "ok" : "no";
    var h = '<div class="sigillo"><span class="sigillo__da">' + (EN ? "Verification" : "Verifica") + "</span>" +
      voce(EN ? "All groups" : "Tutti i gruppi", "nd", EN ? "not in v1" : "non in v1") +
      voce(EN ? "Authoritative voices" : "Voci autorevoli", "nd", EN ? "not in v1" : "non in v1") +
      voce(EN ? "Exact quotes" : "Citazioni esatte", eC, Q.total ? Q.exact + "/" + Q.total : "–") + "</div>";
    var sbagliate = Q.total - Q.exact;
    h += '<p class="riassunto">' + (EN
      ? (!Q.total ? "The answer has no quotes to check." : !sbagliate ? "Every quote matches the record, the speaker, the group and the link." : sbagliate + " of " + Q.total + (sbagliate === 1 ? " quote does" : " quotes do") + " not pass.")
      : (!Q.total ? "La risposta non ha citazioni da controllare." : !sbagliate ? "Ogni citazione coincide con il resoconto, con chi parla, con il gruppo e con il link." : (sbagliate === 1 ? "Una citazione su " + Q.total + " non passa." : sbagliate + " citazioni su " + Q.total + " non passano."))) + "</p>";
    h += '<section class="prova" aria-labelledby="p-v1"><div class="prova__testa"><h3 class="titolo-4" id="p-v1"><span>03</span>' + (EN ? "Exact quotes" : "Citazioni esatte") + "</h3>" +
      '<span class="prova__conto" data-esito="' + eC + '">' + Q.exact + (EN ? " of " : " su ") + Q.total + "</span></div>";
    h += '<div class="citate">' + Q.items.map(schedaV1).join("") + "</div>";
    var dati = (EN ? "Data: " : "Dati: ") + (D.source === "graph" ? (EN ? "ParliamentRAG graph, sittings up to " : "grafo di ParliamentRAG, sedute fino al ") + esc(D.version ? dataIt(D.version) : "–") : esc(D.dataset || "") + " " + esc(D.version || ""));
    h += '<p class="brevi">' + dati + " · " + (EN ? "verifier " : "verificatore ") + esc(R.verifier.version) + " · " +
      (EN ? "the answer says it used the data of " : "la risposta dichiara i dati del ") + esc(R.answer.data_version) + ".</p>";
    h += "<p>" + (EN ? "Groups and authority are not checked in this format yet: they come in the next phases of the plan." : "Gruppi e autorevolezza in questo formato non si controllano ancora: arrivano nelle prossime fasi del piano.") + "</p>";
    h += "</section>";
    esito.innerHTML = h;
    stato.textContent = !Q.total ? (EN ? "No quotes" : "Nessuna citazione") : (EN ? Q.exact + " of " + Q.total + " exact" : Q.exact + " su " + Q.total + " esatte");
    stato.style.color = eC === "no" ? "var(--errore)" : "";
  }

  function schedaV1(v) {
    var ok = v.outcome === "esatta" || v.outcome === "esatta_dopo_normalizzazione";
    var e = ESITI_V1[v.outcome] || [v.outcome, ""];
    var sotto = e[1];
    if (v.outcome === "esatta_dopo_normalizzazione") sotto = v.normalizations.map(function (n) { return NORMALIZZAZIONI[n] || n; }).join(", ");
    var f = v.found || {};
    var chiParla = f.speaker_name ? "<strong>" + esc(f.speaker_name) + "</strong>" + (f.date ? ", " + dataIt(f.date) : "") : "";
    var link = v.link ? ' <a class="bollino" href="' + esc(v.link) + '" rel="noopener">' + SPUNTA + (EN ? "Link in the answer" : "Link della risposta") + "</a>" : "";
    var controlli = '<p class="controlli">' + CONTROLLI.map(function (c) {
      var st = v.checks[c[0]];
      return '<span data-c="' + (st === "fail" ? "no" : "si") + '">' + STATI[st] + " " + c[1] + "</span>";
    }).join("") + "</p>";
    return '<article class="citata" data-esito="' + (ok ? "ok" : "no") + '"><p class="citata__esito">' + (ok ? SPUNTA : CROCE) +
      esc(e[0]) + " <span>" + esc(sotto) + "</span></p>" +
      '<blockquote class="cit cit--piccola"><p class="cit__testo" lang="it">' + esc(norm(v.quote)) + "</p></blockquote>" +
      '<p class="chi-dice">#' + v.index + " · " + esc(v.speech || "") + (chiParla ? " · " + chiParla : "") + link + "</p>" + controlli + "</article>";
  }

  function chi(s) {
    return "<strong>" + esc(s.name) + "</strong>, " + esc(sigla(s.group)) + (s.date ? ", " + dataIt(s.date) : "") +
      (s.url ? ' <a class="bollino" href="' + esc(s.url) + '" rel="noopener">' + SPUNTA + (EN ? "Record" : "Resoconto") + "</a>" : "");
  }

  function mostra(testo, R) {
    var G = R.groups, A = R.authority, C = R.quotes, S = R.summary;
    var eG = ESITO[S.groups], eA = ESITO[S.authority], eC = ESITO[S.quotes];
    var autorevoli = A.voices.filter(function (v) { return v.authoritative; }).length;

    var h = '<div class="sigillo"><span class="sigillo__da">' + (EN ? "Verification" : "Verifica") + "</span>" +
      voce(EN ? "All groups" : "Tutti i gruppi", eG, G.named + "/" + G.total) +
      voce(EN ? "Authoritative voices" : "Voci autorevoli", eA, A.voices.length ? autorevoli + "/" + A.voices.length : "–") +
      voce(EN ? "Exact quotes" : "Citazioni esatte", eC, C.total ? C.exact + "/" + C.total : "–") + "</div>";

    var mancanti = G.items.filter(function (g) { return g.status === "missing"; });
    var frasi = [];
    if (EN) {
      frasi.push(mancanti.length ? mancanti.length + (mancanti.length === 1 ? " voice is" : " voices are") + " missing out of " + G.total + "." : "Every group, Mixed Group component and the Government are there.");
      frasi.push(!C.total ? "There are no quotes to check." : C.exact === C.total && eC === "ok" ? "The quotes match the record." : (C.total - C.exact) + " of " + C.total + (C.total - C.exact === 1 ? " quote does" : " quotes do") + " not match the record or the speaker.");
    } else {
      frasi.push(mancanti.length ? "Mancano " + mancanti.length + (mancanti.length === 1 ? " voce" : " voci") + " su " + G.total + "." : "Ci sono tutti i gruppi, le componenti del Misto e il Governo.");
      frasi.push(!C.total ? "Non ci sono citazioni da controllare." : C.exact === C.total && eC === "ok" ? "Le citazioni coincidono con il resoconto." : (C.total - C.exact === 1 ? "Una citazione su " + C.total + " non coincide" : (C.total - C.exact) + " citazioni su " + C.total + " non coincidono") + " con il resoconto o con chi parla.");
    }
    h += '<p class="riassunto">' + frasi.join(" ") + "</p>";

    /* 01 Gruppi */
    h += '<section class="prova" data-entra style="--ritardo:80ms" aria-labelledby="p-a"><div class="prova__testa"><h3 class="titolo-4" id="p-a"><span>01</span>' + (EN ? "All groups" : "Tutti i gruppi") + "</h3>" +
      '<span class="prova__conto" data-esito="' + eG + '">' + G.named + (EN ? " of " : " su ") + G.total + (EN ? " present" : " presenti") + "</span></div>";
    h += '<ul class="appello">' + G.items.map(function (g) {
      var c = g.status !== "missing";
      var come = g.status === "quoted" ? '<span title="' + esc(g.quoted_by.join(", ")) + '">' + (EN ? "quoted" : "citato") + "</span>" : g.named_as ? "«" + esc(g.named_as) + "»" : (EN ? "absent" : "assente");
      return '<li data-c="' + (c ? "si" : "no") + '">' + (c ? SPUNTA : CROCE) +
        '<span class="appello__nome"><span class="sigla">' + esc(sigla(g.key)) + "</span> " + esc(EN && g.key === "Governo" ? "Government" : g.label) + "</span>" +
        '<span class="appello__come">' + come + "</span></li>";
    }).join("") + "</ul>";
    h += mancanti.length
      ? (EN ? "<p>I cannot find " + mancanti.map(function (g) { return esc(sigla(g.key)); }).join(", ").replace(/\.$/, "") + ". A complete answer names them, or says that they did not speak on the topic.</p>"
            : "<p>Non trovo " + mancanti.map(function (g) { return esc(g.key); }).join(", ").replace(/\.$/, "") + ". Una risposta completa li nomina, o dice che sul tema non hanno parlato.</p>")
      : (EN ? "<p>Every voice is named or quoted at least once.</p>" : "<p>Ogni voce è nominata o citata almeno una volta.</p>");
    (G.mismatches || []).forEach(function (m) {
      h += '<p class="chi-dice">' + (EN
        ? "The answer writes " + esc(m.name) + " (" + esc(m.group_written) + "), but they belong to " + esc(sigla(m.voice || m.group)) + "."
        : "La risposta scrive " + esc(m.name) + " (" + esc(m.group_written) + "), ma è di " + esc(m.voice || m.group) + ".") + "</p>";
    });
    h += "</section>";

    /* 02 Voci autorevoli */
    var tema = A.topic_source === "question"
      ? (EN ? "Topic: the question, «" : "Tema: la domanda, «") + esc(A.topic) + "»."
      : (EN ? "No question given: the topic comes from the first lines of the answer." : "Senza domanda: il tema viene dalle prime righe della risposta.");
    h += '<section class="prova" data-entra style="--ritardo:200ms" aria-labelledby="p-c"><div class="prova__testa"><h3 class="titolo-4" id="p-c"><span>02</span>' + (EN ? "Authoritative voices" : "Voci autorevoli") + "</h3>" +
      '<span class="prova__conto" data-esito="' + eA + '">' + (A.voices.length ? autorevoli + (EN ? " of " : " su ") + A.voices.length + (EN ? " authoritative" : " autorevoli") : (EN ? "no exact quotes" : "nessuna citazione esatta")) + "</span></div>";
    if (!A.available) {
      h += "<p>" + (EN ? "Authority on the topic could not be computed right now: try again in a minute." : "In questo momento non riesco a calcolare l'autorevolezza sul tema: riprova tra un minuto.") + "</p>";
    } else if (!A.voices.length) {
      h += "<p>" + (EN ? "Authority is checked on the deputies and members of the Government quoted or named in the answer. This answer has none." : "L'autorevolezza si controlla sui deputati e sui membri del Governo citati o nominati nella risposta. Questa risposta non ne ha.") + "</p>";
    } else {
      h += '<ul class="appello">' + A.voices.map(function (v) {
        var ok = v.authoritative;
        var perche = v.role === "governo" ? (EN ? "Government" : "Governo")
          : v.role === "relatore" ? (EN ? "rapporteur" : "relatore")
          : v.rank ? v.rank + (EN ? (v.rank === 1 ? "st" : v.rank === 2 ? "nd" : v.rank === 3 ? "rd" : "th") + " of " : "° su ") + v.group_size
          : (EN ? "not ranked" : "senza punteggio");
        return '<li data-c="' + (ok ? "si" : "no") + '">' + (ok ? SPUNTA : CROCE) +
          '<span class="appello__nome">' + esc(v.name) + ' <span class="sigla">' + esc(sigla(v.voice || v.group)) + "</span>" +
          (v.source === "named" ? ' <span class="nota">' + (EN ? "named" : "nominato") + "</span>" : "") + "</span>" +
          '<span class="appello__come">' + esc(perche) + "</span></li>";
      }).join("") + "</ul>";
      h += "<p>" + (EN ? "A voice is authoritative if it speaks for the Government, is the rapporteur of the bill or is among the top five of its group on the topic: the number is the rank within the group. " : "Una voce è autorevole se parla per il Governo, è relatore del provvedimento o è tra i primi cinque del suo gruppo sul tema: il numero è la posizione nel gruppo. ") + tema + "</p>";
    }
    h += "</section>";

    /* 03 Citazioni */
    h += '<section class="prova" data-entra style="--ritardo:320ms" aria-labelledby="p-b"><div class="prova__testa"><h3 class="titolo-4" id="p-b"><span>03</span>' + (EN ? "Exact quotes" : "Citazioni esatte") + "</h3>" +
      '<span class="prova__conto" data-esito="' + eC + '">' + (C.total ? (EN ? C.exact + " of " + C.total + " match" : C.exact + " su " + C.total + " coincidono") : (EN ? "no quotes" : "nessuna citazione")) + "</span></div>";
    if (!C.total) {
      h += EN ? "<p>I found no text between «…» or \"…\" at least four words long.</p>" : "<p>Non ho trovato testo tra «…» o tra \"…\" lungo almeno quattro parole.</p>";
    } else {
      h += '<div class="citate">' + C.items.map(scheda).join("") + "</div>";
    }
    if (C.short.length) {
      h += '<p class="brevi">' + (EN ? "In quotation marks but too short to be quotes: " : "Tra virgolette ma troppo brevi per essere citazioni: ") + C.short.map(function (s) { return "«" + esc(s) + "»"; }).join(", ") + ".</p>";
    }
    h += "</section>";

    esito.innerHTML = h;
    var tot = [eG, eA, eC];
    var passate = tot.filter(function (x) { return x === "ok"; }).length;
    var nd = tot.filter(function (x) { return x === "nd"; }).length;
    stato.textContent = (EN ? passate + " of 3 passed" : passate + " su 3 superate") + (nd ? (EN ? " · " + nd + " not checkable" : " · " + nd + " non verificabil" + (nd === 1 ? "e" : "i")) : "");
    stato.style.color = tot.indexOf("no") >= 0 ? "var(--errore)" : "";
  }

  function scheda(c) {
    var s = c.speech;
    var testo = '<blockquote class="cit cit--piccola"><p class="cit__testo" lang="it">' + esc(norm(c.text)) + "</p></blockquote>";
    var nonAttribuita = s && !c.attributed ? '<p class="chi-dice">' + (EN
      ? "The words are in the record, but " + esc(s.name) + "'s surname does not appear near the quote: check who the answer attributes it to."
      : "Le parole sono nel resoconto, ma il cognome di " + esc(s.name) + " non compare vicino alla citazione: controlla a chi la attribuisce la risposta.") + "</p>" : "";
    if (c.status === "exact") {
      var ok = c.attributed;
      return '<article class="citata" data-esito="' + (ok ? "ok" : "no") + '"><p class="citata__esito">' + (ok ? SPUNTA : CROCE) +
        (ok ? (EN ? "Matches <span>the record, word for word</span></p>" : "Coincide <span>con il resoconto, parola per parola</span></p>")
            : (EN ? "Speaker not named <span>near the quote</span></p>" : "Chi parla non è indicato <span>vicino alla citazione</span></p>")) +
        testo + '<p class="chi-dice">' + chi(s) + "</p>" + nonAttribuita + "</article>";
    }
    if (c.status === "omissions") {
      return '<article class="citata" data-esito="no"><p class="citata__esito">' + CROCE + (EN ? "Skips words <span>the pieces are in the record, in order, but the quote leaves out what is between them</span></p>" : "Salta delle parole <span>i pezzi sono nel resoconto, in ordine, ma la citazione toglie quello che c'è in mezzo</span></p>") +
        testo + '<p class="chi-dice">' + chi(s) + "</p>" + nonAttribuita + "</article>";
    }
    if (c.status === "modified") {
      var al = allinea(parole(c.passage), parole(c.text));
      var diverse = al.r.filter(function (x) { return x.s !== "ok"; });
      var nuove = diverse.filter(function (x) { return x.s === "nuovo"; }).length;
      var tolte = diverse.length - nuove;
      var quanto = [];
      if (EN) {
        if (nuove) quanto.push(nuove === 1 ? "1 word that the record does not have" : nuove + " words that the record does not have");
        if (tolte) quanto.push(tolte === 1 ? "1 word of the record missing" : tolte + " words of the record missing");
      } else {
        if (nuove) quanto.push(nuove === 1 ? "1 parola che il resoconto non ha" : nuove + " parole che il resoconto non ha");
        if (tolte) quanto.push(tolte === 1 ? "1 parola del resoconto che manca" : tolte + " parole del resoconto che mancano");
      }
      return '<article class="citata" data-esito="no"><p class="citata__esito">' + CROCE + (EN ? "Does not match <span>" : "Non coincide <span>") + quanto.join(", ") + "</span></p>" +
        '<p class="diff" lang="it">«' + al.r.map(function (x) { return '<span data-s="' + x.s + '">' + esc(x.w) + "</span>"; }).join(" ") + "»</p>" +
        '<p class="diff-legenda">' + (EN ? "<span>underlined: matches</span><span><mark>highlighted</mark>: only in the answer</span><span><s>struck through</s>: only in the record</span>" : "<span>sottolineato: coincide</span><span><mark>evidenziato</mark>: solo nella risposta</span><span><s>barrato</s>: solo nel resoconto</span>") + "</p>" +
        '<p class="chi-dice">' + (EN ? "The closest passage: " : "Il passo più vicino: ") + chi(s) + "</p></article>";
    }
    return '<article class="citata" data-esito="no"><p class="citata__esito">' + CROCE + (EN ? "Not found <span>in any floor speech of the 19th legislature</span></p>" : "Non trovata <span>in nessun intervento in Aula della XIX legislatura</span></p>") +
      testo + '<p class="chi-dice">' + (EN ? "It may come from an interview, a press release or the Senate, which this check does not cover. If it is presented as said in the Chamber, it is not in the record." : "Può venire da un'intervista, da un comunicato o dal Senato, che questo controllo non copre. Se è presentata come detta alla Camera, nel resoconto non c'è.") + "</p></article>";
  }

  /* Tabella dei nomi, letta dal verificatore */
  var alias = document.getElementById("alias");
  function rigaNome(v) {
    var nome = v.kind === "government" ? (EN ? "Government" : "Governo") : v.label;
    if (v.chamber === "senato") nome = /\)$/.test(nome) ? nome.replace(/\)$/, EN ? ", Senate)" : ", Senato)") : nome + (EN ? " (Senate)" : " (Senato)");
    return "<tr><td>" + esc(nome) + '</td><td class="mono">' + esc(v.abbreviations.length ? v.abbreviations.join(", ") : "–") +
      "</td><td>" + esc(v.names.join(", ")) + "</td></tr>";
  }
  fetch(NOMI_API).then(function (r) {
    if (!r.ok) throw new Error();
    return r.json();
  }).then(function (j) {
    alias.innerHTML = j.voices.map(rigaNome).join("");
  }).catch(function () {
    alias.innerHTML = '<tr><td colspan="3">' + (EN ? "The list is not available right now: try again later." : "L'elenco non è disponibile in questo momento: riprova più tardi.") + "</td></tr>";
  });

  contaParole();
  window.osservaComparse();
})();

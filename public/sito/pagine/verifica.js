(function () {
  "use strict";
  var D = window.DATI;
  var CIT = D.tema.citazioni;
  var SPUNTA = window.ICONE.spunta, CROCE = window.ICONE.croce;
  var FORSE = '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><circle cx="8" cy="8" r="6.6"/><path d="M5.5 8h5"/></svg>';
  var ridotto = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var EN = window.LINGUA === "en";
  var esc = window.esc, numero = window.numero, dataIt = window.dataLunga;
  /* Le sigle e i nomi dei gruppi restano italiani; il Governo si scrive nella lingua della pagina */
  var sigla = function (g) { return EN && g === "Governo" ? "Government" : g; };
  var nomeGruppo = function (q) { return EN && q.group === "Governo" ? "Government" : q.groupName; };

  /* ---------- Gruppi del tema e nomi con cui li riconosciamo ----------
   * Le sigle valgono solo in maiuscolo come le scriviamo (FI, Lega, Azione),
   * così «lega la proposta» o «un'azione» non contano. I nomi estesi valgono
   * con qualsiasi maiuscola. */
  var GRUPPI = [
    { k: "FdI", nome: "Fratelli d'Italia", sigle: ["FdI", "FDI"], nomi: ["Fratelli d'Italia"] },
    { k: "PD", nome: "Partito Democratico", sigle: ["PD", "Pd"], nomi: ["Partito Democratico", "Italia Democratica e Progressista"] },
    { k: "Lega", nome: "Lega - Salvini Premier", sigle: ["Lega"], nomi: ["Lega Salvini", "Salvini Premier"] },
    { k: "M5S", nome: "Movimento 5 Stelle", sigle: ["M5S"], nomi: ["Movimento 5 Stelle", "Movimento Cinque Stelle", "5 Stelle", "Cinque Stelle"] },
    { k: "FI", nome: "Forza Italia", sigle: ["FI"], nomi: ["Forza Italia"] },
    { k: "AVS", nome: "Alleanza Verdi e Sinistra", sigle: ["AVS"], nomi: ["Alleanza Verdi e Sinistra", "Verdi e Sinistra"] },
    { k: "Azione", nome: "Azione - PER", sigle: ["Azione", "AZ"], nomi: ["Popolari Europeisti Riformatori"] },
    { k: "IV", nome: "Italia Viva - Casa Riformista", sigle: ["IV"], nomi: ["Italia Viva", "Casa Riformista"] },
    { k: "NM", nome: "Noi Moderati", sigle: ["NM"], nomi: ["Noi Moderati", "MAIE", "Centro Popolare"] },
    { k: "+Europa", nome: "+Europa (Misto)", sigle: ["+Europa"], nomi: ["Più Europa", "+ Europa"] },
    { k: "Governo", nome: "Governo", sigle: [], nomi: ["Governo", "Esecutivo", "ministro", "ministra", "sottosegretario", "sottosegretaria"] }
  ];

  if (EN) {
    /* Chi scrive in inglese usa spesso i nomi tradotti */
    /* Come le sigle, «League» e «Action» valgono solo con la maiuscola */
    var SIGLE_EN = { Lega: ["League"], Azione: ["Action"] };
    var NOMI_EN = {
      FdI: ["Brothers of Italy"], PD: ["Democratic Party"], M5S: ["Five Star Movement", "Five Stars"],
      FI: ["Forward Italy", "Go Italy"], AVS: ["Greens and Left Alliance", "Green and Left Alliance"],
      IV: ["Italy Alive"], NM: ["Us Moderates"], "+Europa": ["More Europe"], Governo: ["Government", "minister", "undersecretary"]
    };
    GRUPPI.forEach(function (g) {
      g.sigle = g.sigle.concat(SIGLE_EN[g.k] || []);
      g.nomi = g.nomi.concat(NOMI_EN[g.k] || []);
      if (g.k === "Governo") g.nome = "Government";
    });
  }

  function apostrofi(s) { return s.replace(/[’‘ʼ`´]/g, "'"); }
  function regexEsc(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); }
  /* Confini di parola che funzionano anche con «+Europa» e con le lettere accentate */
  function cerca(testo, alias, maiuscole) {
    var re = new RegExp("(^|[^\\p{L}\\p{N}+])(" + regexEsc(apostrofi(alias)) + ")(?=$|[^\\p{L}\\p{N}])", maiuscole ? "u" : "iu");
    var m = re.exec(testo);
    return m ? m[2] : null;
  }
  function trovaGruppi(testo) {
    testo = apostrofi(testo);
    return GRUPPI.map(function (g) {
      var trovato = null;
      g.sigle.some(function (a) { trovato = cerca(testo, a, true); return trovato; });
      if (!trovato) g.nomi.some(function (a) { trovato = cerca(testo, a, false); return trovato; });
      return { g: g, come: trovato };
    });
  }

  /* ---------- Citazioni: estrazione e confronto ---------- */
  function norm(s) {
    return apostrofi(s).replace(/\s+/g, " ").trim();
  }
  function bordi(s) {
    return s.replace(/^[\s.,;:…]+|[\s.,;:…]+$/g, "");
  }
  function parole(s) { return norm(s).split(" ").filter(Boolean); }
  function estrai(testo) {
    var re = /«([^«»]+)»|“([^“”]+)”|"([^"]+)"/g, out = [], m;
    while ((m = re.exec(testo))) out.push({ t: m[1] || m[2] || m[3], da: m.index, a: m.index + m[0].length });
    return out;
  }
  /* Una citazione può saltare un pezzo con «…» o «[...]»: ogni frammento va trovato, in ordine */
  function coincide(frase, nota) {
    var pezzi = norm(frase).split(/\s*(?:\[\s*(?:…|\.\.\.)\s*\]|…|\.\.\.)\s*/).map(bordi).filter(Boolean);
    if (!pezzi.length) return false;
    var dove = 0, n = norm(nota);
    return pezzi.every(function (p) {
      var i = n.indexOf(p, dove);
      if (i < 0) {
        /* la prima lettera può cambiare maiuscola se la citazione inizia a metà frase */
        var alt = p.charAt(0) === p.charAt(0).toUpperCase() ? p.charAt(0).toLowerCase() + p.slice(1) : p.charAt(0).toUpperCase() + p.slice(1);
        i = n.indexOf(alt, dove);
      }
      if (i < 0) return false;
      dove = i + p.length;
      return true;
    });
  }
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
  function piuVicina(frase) {
    var b = parole(bordi(frase)), meglio = null;
    CIT.forEach(function (q) {
      var al = allinea(parole(q.quote), b);
      var quota = b.length ? al.uguali / b.length : 0;
      if (!meglio || quota > meglio.quota) meglio = { q: q, al: al, quota: quota };
    });
    return meglio;
  }
  /* Il cognome di chi parla compare vicino alla citazione? */
  function attribuita(testo, c, q) {
    var cognome = q.name.split(" ").slice(-1)[0];
    var intorno = testo.slice(Math.max(0, c.da - 180), Math.min(testo.length, c.a + 80));
    return new RegExp("(^|[^\\p{L}])" + regexEsc(cognome) + "(?=$|[^\\p{L}])", "iu").test(intorno);
  }

  /* ---------- Interfaccia ---------- */
  var area = document.getElementById("risposta");
  var esito = document.getElementById("esito");
  var stato = document.getElementById("stato");
  var msg = document.getElementById("msg");
  var conta = document.getElementById("conta");

  /* Esempio scritto da noi: due citazioni esatte, una con una parola cambiata
     («lavoratori» al posto di «sindacati»). IV, NM e +Europa non compaiono. */
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
  area.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); verifica(); }
  });
  document.getElementById("esempio").addEventListener("click", function () {
    area.value = ESEMPIO;
    contaParole();
    msg.removeAttribute("data-tipo");
    msg.textContent = EN ? "Example inserted. It contains three quotes: one has a changed word." : "Esempio inserito. Contiene tre citazioni: una ha una parola cambiata.";
    document.getElementById("verifica").focus();
  });
  document.getElementById("svuota").addEventListener("click", function () {
    area.value = "";
    contaParole();
    msg.textContent = "";
    esito.innerHTML = vuoto;
    stato.textContent = EN ? "Waiting" : "In attesa";
    stato.style.color = "";
    area.focus();
  });
  var vuoto = esito.innerHTML;
  document.getElementById("modulo").addEventListener("submit", function (e) { e.preventDefault(); verifica(); });

  function voce(nome, esito, extra) {
    var icona = esito === "ok" ? SPUNTA : esito === "no" ? CROCE : FORSE;
    return '<span class="sigillo__voce" data-esito="' + esito + '">' + icona + nome + (extra ? " <b>" + extra + "</b>" : "") + "</span>";
  }

  function verifica() {
    var testo = area.value;
    if (!testo.trim()) {
      msg.dataset.tipo = "errore";
      msg.textContent = EN ? "Paste an answer before checking, or use the example." : "Incolla una risposta prima di verificare, oppure usa l'esempio.";
      area.focus();
      return;
    }
    msg.textContent = "";
    esito.setAttribute("aria-busy", "true");
    stato.textContent = EN ? "Checking" : "Controllo in corso";
    stato.style.color = "";
    esito.innerHTML = '<div class="attesa"><span>' + (EN ? "Comparing with the local corpus…" : "Confronto con il corpus locale…") + '</span><span class="attesa__riga"><i></i></span></div>';
    setTimeout(function () { mostra(testo); }, ridotto ? 0 : 650);
  }

  function mostra(testo) {
    /* (a) Gruppi */
    var gruppi = trovaGruppi(testo);
    var presenti = gruppi.filter(function (x) { return x.come; });
    var mancanti = gruppi.filter(function (x) { return !x.come; });
    var esitoG = mancanti.length ? "no" : "ok";

    /* (b) Citazioni */
    var tutte = estrai(testo);
    var brevi = [], citazioni = [];
    tutte.forEach(function (c) { (parole(c.t).length < 4 ? brevi : citazioni).push(c); });
    citazioni.forEach(function (c) {
      var nota = CIT.filter(function (q) { return coincide(c.t, q.quote); })[0];
      if (nota) { c.esito = "ok"; c.q = nota; c.attr = attribuita(testo, c, nota); return; }
      var v = piuVicina(c.t);
      if (v && v.quota >= 0.5) { c.esito = "no"; c.q = v.q; c.al = v.al; c.attr = attribuita(testo, c, v.q); }
      else c.esito = "nd";
    });
    var ok = citazioni.filter(function (c) { return c.esito === "ok"; }).length;
    var no = citazioni.filter(function (c) { return c.esito === "no"; }).length;
    var nd = citazioni.length - ok - no;
    var esitoC = no ? "no" : citazioni.length && !nd ? "ok" : "nd";

    /* Sigillo e riassunto */
    var h = '<div class="sigillo">' + '<span class="sigillo__da">' + (EN ? "Preview" : "Anteprima") + "</span>" +
      voce(EN ? "All groups" : "Tutti i gruppi", esitoG, presenti.length + "/" + gruppi.length) +
      voce(EN ? "Authoritative voices" : "Voci autorevoli", "nd", EN ? "n/c" : "n.v.") +
      voce(EN ? "Exact quotes" : "Citazioni esatte", esitoC, citazioni.length ? ok + "/" + citazioni.length : "–") + "</div>";
    var frasi = [];
    if (EN) {
      frasi.push(mancanti.length ? mancanti.length + (mancanti.length === 1 ? " voice is" : " voices are") + " missing out of " + gruppi.length + "." : "All the groups of the topic and the Government are there.");
      if (no) frasi.push(no === 1 ? "One quote does not match the record." : no + " quotes do not match the record.");
      else if (citazioni.length && !nd) frasi.push("The quotes match the record.");
      else if (!citazioni.length) frasi.push("There are no quotes to check.");
      if (nd) frasi.push(nd === 1 ? "One quote is not in the local corpus." : nd + " quotes are not in the local corpus.");
    } else {
    frasi.push(mancanti.length ? "Mancano " + mancanti.length + (mancanti.length === 1 ? " voce" : " voci") + " su " + gruppi.length + "." : "Ci sono tutti i gruppi del tema e il Governo.");
    if (no) frasi.push(no === 1 ? "Una citazione non coincide con il resoconto." : no + " citazioni non coincidono con il resoconto.");
    else if (citazioni.length && !nd) frasi.push("Le citazioni coincidono con il resoconto.");
    else if (!citazioni.length) frasi.push("Non ci sono citazioni da controllare.");
    if (nd) frasi.push(nd === 1 ? "Una citazione non è nel corpus locale." : nd + " citazioni non sono nel corpus locale.");
    }
    h += '<p class="riassunto">' + frasi.join(" ") + "</p>";

    /* Blocco (a) */
    h += '<section class="prova" data-entra style="--ritardo:80ms" aria-labelledby="p-a"><div class="prova__testa"><h3 class="titolo-4" id="p-a"><span>01</span>' + (EN ? "All groups" : "Tutti i gruppi") + "</h3>" +
      '<span class="prova__conto" data-esito="' + esitoG + '">' + presenti.length + (EN ? " of " : " su ") + gruppi.length + (EN ? " named" : " nominati") + "</span></div>";
    h += '<ul class="appello">' + gruppi.map(function (x) {
      return '<li data-c="' + (x.come ? "si" : "no") + '">' + (x.come ? SPUNTA : CROCE) +
        '<span class="appello__nome"><span class="sigla">' + esc(sigla(x.g.k)) + "</span> " + esc(x.g.nome) + "</span>" +
        '<span class="appello__come">' + (x.come ? "«" + esc(x.come) + "»" : (EN ? "absent" : "assente")) + "</span></li>";
    }).join("") + "</ul>";
    h += mancanti.length
      ? (EN
        ? "<p>I cannot find " + mancanti.map(function (x) { return esc(sigla(x.g.k)); }).join(", ") + ". A complete answer names them, or says that they did not speak on the topic.</p>"
        : "<p>Non trovo " + mancanti.map(function (x) { return esc(x.g.k); }).join(", ") + ". Una risposta completa li nomina, o dice che sul tema non hanno parlato.</p>")
      : (EN ? "<p>Every group of the topic and the Government are named at least once.</p>" : "<p>Ogni gruppo del tema e il Governo sono nominati almeno una volta.</p>");
    h += "</section>";

    var citati = [];
    citazioni.forEach(function (c) { if (c.q && citati.indexOf(c.q) < 0) citati.push(c.q); });
    /* Blocco (c) */
    h += '<section class="prova" data-entra style="--ritardo:200ms" aria-labelledby="p-c"><div class="prova__testa"><h3 class="titolo-4" id="p-c"><span>02</span>' + (EN ? "Authoritative voices" : "Voci autorevoli") + "</h3>" +
      '<span class="prova__conto">' + (EN ? "not checkable in this preview" : "non verificabile in questa anteprima") + "</span></div>" +
      (EN
        ? "<p>To say whether the people quoted are authoritative voices on the topic we need the scores computed for the question. This page does not have them, so we give no result.</p>" +
          '<div class="futuro"><strong>The public verifier</strong><ol>' +
          "<li>will recognise who is quoted and for which group;</li>" +
          "<li>will compute authority on the topic with the six criteria and the public weights;</li>" +
          "<li>will check that for each group the speaker is a rapporteur, a member of the Government or one of the top five.</li></ol>"
        : "<p>Per dire se chi è citato è una voce autorevole sul tema servono i punteggi calcolati per la domanda. In questa pagina non li abbiamo, quindi non diamo un esito.</p>" +
          '<div class="futuro"><strong>Il verificatore pubblico</strong><ol>' +
          "<li>riconoscerà chi è citato e per quale gruppo;</li>" +
          "<li>calcolerà l'autorevolezza sul tema con i sei criteri e i pesi pubblici;</li>" +
          "<li>controllerà che per ogni gruppo parli un relatore, un membro del Governo o uno dei primi cinque.</li></ol>") +
      (citati.length ? '<div class="citati"><span class="nota">' + (EN ? "Quoted in this answer:" : "Citati in questa risposta:") + "</span>" + citati.map(function (q) { return '<span class="sigla">' + esc(q.name) + " · " + esc(sigla(q.group)) + "</span>"; }).join("") + "</div>" : "") +
      "</div></section>";

    /* Blocco (b) */
    h += '<section class="prova" data-entra style="--ritardo:320ms" aria-labelledby="p-b"><div class="prova__testa"><h3 class="titolo-4" id="p-b"><span>03</span>' + (EN ? "Exact quotes" : "Citazioni esatte") + "</h3>" +
      '<span class="prova__conto" data-esito="' + esitoC + '">' + (citazioni.length ? (EN ? ok + " of " + citazioni.length + " match" : ok + " su " + citazioni.length + " coincidono") : (EN ? "no quotes" : "nessuna citazione")) + "</span></div>";
    if (!citazioni.length) {
      h += EN ? "<p>I found no text between «…» or \"…\" at least four words long.</p>" : "<p>Non ho trovato testo tra «…» o tra \"…\" lungo almeno quattro parole.</p>";
    } else {
      h += '<div class="citate">' + citazioni.map(scheda).join("") + "</div>";
    }
    if (brevi.length) {
      h += '<p class="brevi">' + (EN ? "In quotation marks but too short to be quotes: " : "Tra virgolette ma troppo brevi per essere citazioni: ") + brevi.map(function (c) { return "«" + esc(c.t) + "»"; }).join(", ") + ".</p>";
    }
    h += "</section>";

    esito.innerHTML = h;
    esito.setAttribute("aria-busy", "false");
    var tot = [esitoG, "nd", esitoC];
    var passate = tot.filter(function (x) { return x === "ok"; }).length;
    stato.textContent = EN ? passate + " of 3 passed · 1 not checkable" : passate + " su 3 superate · 1 non verificabile";
    stato.style.color = tot.indexOf("no") >= 0 ? "var(--errore)" : "";
  }

  function scheda(c) {
    var q = c.q;
    var fonte = q ? '<p class="chi-dice">' + (c.esito === "ok" ? "" : (EN ? "The closest known quote: " : "La più vicina tra quelle note: ")) +
      "<strong>" + esc(q.name) + "</strong>, " + esc(nomeGruppo(q)) + ", " + dataIt(q.date) +
      ' <a class="bollino" href="' + esc(q.url) + '" rel="noopener">' + SPUNTA + (EN ? "Record" : "Resoconto") + "</a></p>" : "";
    var nomeVicino = q ? (c.attr ? "" : '<p class="chi-dice">' + (EN ? esc(q.name) + "'s surname does not appear near the quote: check who it is attributed to." : "Il cognome di " + esc(q.name) + " non compare vicino alla citazione: controlla a chi è attribuita.") + "</p>") : "";
    if (c.esito === "ok") {
      return '<article class="citata" data-esito="ok"><p class="citata__esito">' + SPUNTA + (EN ? "Matches <span>the record, word for word</span></p>" : "Coincide <span>con il resoconto, parola per parola</span></p>") +
        '<blockquote class="cit cit--piccola"><p class="cit__testo" lang="it">' + esc(bordi(norm(c.t))) + "</p></blockquote>" + fonte + nomeVicino + "</article>";
    }
    if (c.esito === "no") {
      var diverse = c.al.r.filter(function (x) { return x.s !== "ok"; });
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
        '<p class="diff" lang="it">«' + c.al.r.map(function (x) { return '<span data-s="' + x.s + '">' + esc(x.w) + "</span>"; }).join(" ") + "»</p>" +
        '<p class="diff-legenda">' + (EN ? "<span>underlined: matches</span><span><mark>highlighted</mark>: only in the answer</span><span><s>struck through</s>: only in the record</span>" : "<span>sottolineato: coincide</span><span><mark>evidenziato</mark>: solo nella risposta</span><span><s>barrato</s>: solo nel resoconto</span>") + "</p>" +
        fonte + "</article>";
    }
    return '<article class="citata" data-esito="nd"><p class="citata__esito">' + FORSE + (EN ? "Not found <span>in the local corpus of 11 quotes</span></p>" : "Non trovata <span>nel corpus locale di 11 citazioni</span></p>") +
      '<blockquote class="cit cit--piccola"><p class="cit__testo" lang="it">' + esc(bordi(norm(c.t))) + "</p></blockquote>" +
      '<p class="chi-dice">' + (EN ? "This does not mean it is false. The public verifier will search for it in all the speeches of the legislature." : "Non vuol dire che sia falsa. Il verificatore pubblico la cercherà in tutti gli interventi della legislatura.") + "</p></article>";
  }

  document.getElementById("alias").innerHTML = GRUPPI.map(function (g) {
    return "<tr><td>" + esc(g.nome) + '</td><td class="mono">' + (g.sigle.map(esc).join(", ") || "–") + "</td><td>" + g.nomi.map(esc).join(", ") + "</td></tr>";
  }).join("");

  contaParole();
  window.osservaComparse();
})();

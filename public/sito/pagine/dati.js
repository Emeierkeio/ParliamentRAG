(function () {
  "use strict";
  var S = window.DATI.stats;
  var EN = window.LINGUA === "en";
  var esc = window.esc, numero = window.numero, dataIt = window.dataLunga;

  /* ---------- Frontespizio e registro: l'HTML ha la fotografia del build, qui i valori vivi ---------- */
  document.querySelectorAll("[data-data-agg], #data-agg").forEach(function (el) { el.textContent = dataIt(S.last_update); });
  /* Camera e Senato restano separati: data-c dice di quale ramo è il numero */
  var C = S.by_chamber || {};
  function perRamo(c, k) { return C[c] && C[c][k]; }
  document.querySelectorAll("#registro [data-k]").forEach(function (el) {
    var v = el.dataset.c ? perRamo(el.dataset.c, el.dataset.k) : S[el.dataset.k];
    if (typeof v === "number") el.textContent = numero(v);
  });
  document.getElementById("triple-n").textContent = numero(S.triples);

  /* ---------- § 3 Note e righe del Turtle, collegate nei due sensi ---------- */
  var note = document.querySelectorAll("#note li");
  var blocchi = document.querySelectorAll("#ttl .blocco");
  function accendi(n) {
    note.forEach(function (li) { if (li.dataset.n === n) li.setAttribute("data-attiva", ""); else li.removeAttribute("data-attiva"); });
    blocchi.forEach(function (b) { if (b.dataset.n === n) b.setAttribute("data-attiva", ""); else b.removeAttribute("data-attiva"); });
  }
  note.forEach(function (li) {
    li.addEventListener("mouseenter", function () { accendi(li.dataset.n); });
    li.addEventListener("focus", function () { accendi(li.dataset.n); });
  });
  blocchi.forEach(function (b) {
    b.addEventListener("mouseenter", function () { accendi(b.dataset.n); });
  });
  document.getElementById("note").addEventListener("mouseleave", function () { accendi("5"); });
  accendi("5");

  /* ---------- § 4 Schema: nodi disegnati a mano, archi con il loro nome ---------- */
  function ramo(k) {
    var a = perRamo("camera", k), b = perRamo("senato", k);
    return typeof a === "number" && typeof b === "number" ? { camera: a, senato: b } : null;
  }
  var NODI = EN ? {
    deputato: { t: "MP", x: 360, y: 200, w: 112, classe: ["foaf:Person", "ocd:deputato", "osr:Senatore"], n: ramo("people"), nl: "deputies and senators, replacements included", d: "A person, with their mandate. The address is the one of the official profile on the Chamber's or the Senate's site." },
    appartenenza: { t: "Membership", x: 190, y: 96, w: 128, classe: ["org:Membership"], d: "Links a person to a group or a committee, with a start date and, when there is one, an end date. A change of group produces a new membership." },
    gruppo: { t: "Group", x: 70, y: 200, w: 96, classe: ["org:Organization", "ocd:gruppoParlamentare"], d: "A parliamentary group. The components of the Mixed Group are organisations of their own, so +Europa stays +Europa." },
    intervento: { t: "Speech", x: 540, y: 96, w: 116, classe: ["pr:Speech"], n: ramo("speeches"), nl: "speeches on the floor", d: "What a deputy or a senator said on the floor, with the full text of the verbatim record." },
    seduta: { t: "Sitting", x: 660, y: 200, w: 92, classe: ["pr:Session", "pr:Debate"], n: ramo("sessions"), nl: "sittings", d: "A sitting of the Chamber or the Senate, divided into debates. Every speech belongs to a debate of a sitting." },
    atto: { t: "Act", x: 190, y: 306, w: 80, classe: ["ocd:atto"], n: ramo("acts"), nl: "parliamentary acts", d: "A bill, motion, resolution, order of the day, question or document, with its signatories. Bills also have their rapporteurs; motions and resolutions their subject; orders of the day the bill they were tabled on and their outcome." },
    tema: { t: "Topic", x: 60, y: 380, w: 92, classe: ["skos:Concept"], n: S.eurovoc_concepts, nl: "EuroVoc topics linked to the acts", d: "A concept of EuroVoc, the European Union's thesaurus with labels in 24 languages, or of TESEO, the Senate's thesaurus for its bills." },
    voto: { t: "Vote", x: 540, y: 306, w: 80, classe: ["ocd:voto"], n: ramo("individual_votes"), nl: "individual votes, in a separate file", d: "A deputy's or a senator's vote in a roll call: in favour, against, abstained." },
    votazione: { t: "Roll call", x: 660, y: 380, w: 108, classe: ["ocd:votazione"], n: ramo("votes"), nl: "electronic votes", d: "An electronic vote on the floor, with the outcome and the act or amendment being voted on." },
    emendamento: { t: "Amendment", x: 400, y: 380, w: 116, classe: ["pr:Amendment"], d: "A proposed change to the text of an act, in committee or on the floor, with its full text, signatories, article and outcome. The outcome says where it comes from: published by the Chamber or the Senate, or taken from the floor vote on the amendment. A sub-amendment points to the amendment it changes; one filed again in another venue points to the first." },
    documento: { t: "Document", x: 680, y: 268, w: 104, classe: ["ocd:atto", "pr:ParliamentaryDocument"], d: "A parliamentary document (Doc.), such as the DEF or an inquiry proposal, debated or voted in one house. It is an act too, with rapporteurs, roll calls and the official PDFs. The DEF and the other Government documents reach the Chamber and the Senate under the same number: a joint examination links the two, kept apart from the path of a law." },
    testo: { t: "Text", x: 110, y: 520, w: 80, classe: ["pr:TextVersion"], d: "A version of the text of a Chamber bill: as introduced, as reported by the committee, as a consolidated text. Each one links to the official document." },
    percorso: { t: "Legislative process", x: 300, y: 520, w: 184, classe: ["pr:LegislativeProcess"], d: "The path of a bill between the Chamber and the Senate. Each reading is an act of its own, with its own number: C.2822, then S.1971, then C.2822-B. The readings are in order and each points to the next." },
    legge: { t: "Law", x: 540, y: 520, w: 80, classe: ["eli:LegalResource"], d: "The law published in the Official Gazette, with its number, date and the ELI address on Normattiva. You get here from the process that passed it." }
  } : {
    deputato: { t: "Parlamentare", x: 360, y: 200, w: 132, classe: ["foaf:Person", "ocd:deputato", "osr:Senatore"], n: ramo("people"), nl: "deputati e senatori, subentrati compresi", d: "Una persona, con il suo mandato. L'indirizzo è quello della scheda ufficiale della Camera o del Senato." },
    appartenenza: { t: "Appartenenza", x: 190, y: 96, w: 128, classe: ["org:Membership"], d: "Lega una persona a un gruppo o a una commissione, con data di inizio e, se c'è, di fine. Un cambio di gruppo produce una nuova appartenenza." },
    gruppo: { t: "Gruppo", x: 70, y: 200, w: 96, classe: ["org:Organization", "ocd:gruppoParlamentare"], d: "Un gruppo parlamentare. Le componenti del Gruppo Misto sono organizzazioni a sé, così +Europa resta +Europa." },
    intervento: { t: "Intervento", x: 540, y: 96, w: 116, classe: ["pr:Speech"], n: ramo("speeches"), nl: "interventi in Aula", d: "Quello che un deputato o un senatore ha detto in Aula, con il testo integrale del resoconto stenografico." },
    seduta: { t: "Seduta", x: 660, y: 200, w: 92, classe: ["pr:Session", "pr:Debate"], n: ramo("sessions"), nl: "sedute", d: "Una seduta della Camera o del Senato, divisa in dibattiti. Ogni intervento sta in un dibattito di una seduta." },
    atto: { t: "Atto", x: 190, y: 306, w: 80, classe: ["ocd:atto"], n: ramo("acts"), nl: "atti parlamentari", d: "Un progetto di legge, una mozione, una risoluzione, un ordine del giorno, un'interrogazione o un documento, con i firmatari. I progetti di legge hanno anche i relatori; mozioni e risoluzioni l'oggetto; gli ordini del giorno il progetto su cui sono stati presentati e l'esito." },
    tema: { t: "Tema", x: 60, y: 380, w: 92, classe: ["skos:Concept"], n: S.eurovoc_concepts, nl: "temi EuroVoc collegati agli atti", d: "Un concetto di EuroVoc, il thesaurus dell'Unione europea con le etichette in 24 lingue, o di TESEO, il thesaurus del Senato per i suoi disegni di legge." },
    voto: { t: "Voto", x: 540, y: 306, w: 80, classe: ["ocd:voto"], n: ramo("individual_votes"), nl: "voti individuali, in un file a parte", d: "Il voto di un deputato o di un senatore in una votazione: favorevole, contrario, astenuto." },
    votazione: { t: "Votazione", x: 660, y: 380, w: 108, classe: ["ocd:votazione"], n: ramo("votes"), nl: "votazioni elettroniche", d: "Una votazione elettronica dell'Aula, con l'esito e l'atto o l'emendamento su cui si vota." },
    emendamento: { t: "Emendamento", x: 400, y: 380, w: 128, classe: ["pr:Amendment"], d: "Una proposta di modifica al testo di un atto, in commissione o in Aula, con il testo integrale, i firmatari, l'articolo e l'esito. L'esito dice da dove viene: pubblicato dalla Camera o dal Senato, oppure ricavato dal voto d'Aula sull'emendamento. Un subemendamento rimanda all'emendamento che modifica; uno ripresentato in un'altra sede rimanda al primo." },
    documento: { t: "Documento", x: 680, y: 268, w: 112, classe: ["ocd:atto", "pr:ParliamentaryDocument"], d: "Un documento parlamentare (Doc.), come il DEF o una proposta di inchiesta, discusso o votato in un ramo. È anche un atto, con relatori, votazioni e i PDF ufficiali. Il DEF e gli altri documenti del Governo arrivano a Camera e Senato con lo stesso numero: un esame comune li tiene insieme, distinto dal percorso di una legge." },
    testo: { t: "Testo", x: 110, y: 520, w: 80, classe: ["pr:TextVersion"], d: "Una versione del testo di un progetto di legge della Camera: quello presentato, quello approvato in commissione, il testo unificato. Ognuna rimanda al documento ufficiale." },
    percorso: { t: "Percorso", x: 300, y: 520, w: 104, classe: ["pr:LegislativeProcess"], d: "Il cammino di un progetto di legge tra Camera e Senato. Ogni lettura è un atto a sé, con il suo numero: C.2822, poi S.1971, poi C.2822-B. Le letture sono in ordine e ognuna rimanda alla successiva." },
    legge: { t: "Legge", x: 540, y: 520, w: 80, classe: ["eli:LegalResource"], d: "La legge pubblicata in Gazzetta Ufficiale, con numero, data e l'indirizzo ELI di Normattiva. Ci si arriva dal percorso che l'ha approvata." }
  };
  var ARCHI = EN ? [
    ["appartenenza", "deputato", "member"],
    ["appartenenza", "gruppo", "organisation"],
    ["intervento", "deputato", "spoken by"],
    ["intervento", "seduta", "in the sitting"],
    ["atto", "deputato", "signed by"],
    ["atto", "deputato", "rapporteur"],
    ["atto", "tema", "topic"],
    ["voto", "deputato", "cast by"],
    ["voto", "votazione", "in the roll call"],
    ["votazione", "atto", "on the act"],
    ["emendamento", "atto", "amends"],
    ["emendamento", "deputato", "signed by"],
    ["votazione", "emendamento", "on the amendment"],
    ["documento", "deputato", "rapporteur"],
    ["votazione", "documento", "on the document"],
    ["atto", "testo", "version"],
    ["atto", "percorso", "reading of"],
    ["percorso", "legge", "became"]
  ] : [
    ["appartenenza", "deputato", "membro"],
    ["appartenenza", "gruppo", "organizzazione"],
    ["intervento", "deputato", "detto da"],
    ["intervento", "seduta", "nella seduta"],
    ["atto", "deputato", "firmato da"],
    ["atto", "deputato", "relatore"],
    ["atto", "tema", "tema"],
    ["voto", "deputato", "espresso da"],
    ["voto", "votazione", "nella votazione"],
    ["votazione", "atto", "sull'atto"],
    ["emendamento", "atto", "modifica"],
    ["emendamento", "deputato", "firmato da"],
    ["votazione", "emendamento", "sull'emendamento"],
    ["documento", "deputato", "relatore"],
    ["votazione", "documento", "sul documento"],
    ["atto", "testo", "versione"],
    ["atto", "percorso", "lettura di"],
    ["percorso", "legge", "diventa"]
  ];
  var svg = document.getElementById("schema-svg");
  var h = '<defs><marker id="pt" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M1 1l6 3-6 3" fill="none" stroke="context-stroke" stroke-width="1.3"/></marker></defs>';
  /* Punto sul bordo del rettangolo del nodo, nella direzione dell'altro nodo */
  function bordo(n, verso) {
    var dx = verso.x - n.x, dy = verso.y - n.y, hw = n.w / 2 + 4, hh = 20;
    var s = Math.min(hw / Math.abs(dx || 1e-6), hh / Math.abs(dy || 1e-6));
    return { x: n.x + dx * s, y: n.y + dy * s };
  }
  /* Due relazioni tra gli stessi nodi (firmato da, relatore) condividono la freccia */
  var tratti = [], perCoppia = {};
  ARCHI.forEach(function (a) {
    var k = a[0] + ">" + a[1];
    if (perCoppia[k]) perCoppia[k][2] += " · " + a[2];
    else tratti.push(perCoppia[k] = [a[0], a[1], a[2]]);
  });
  tratti.forEach(function (a) {
    var A = NODI[a[0]], B = NODI[a[1]], p = bordo(A, B), q = bordo(B, A);
    var d, lx, ly;
    if (a[0] === "votazione" && a[1] === "atto") {
      /* passa sotto l'emendamento, per non attraversare il centro */
      d = "M" + (A.x - A.w / 2 - 4) + "," + A.y + " C 520,460 330,460 " + (B.x + B.w / 2 + 4) + "," + B.y;
      lx = 424; ly = 452;
    } else {
      d = "M" + p.x.toFixed(1) + "," + p.y.toFixed(1) + " L" + q.x.toFixed(1) + "," + q.y.toFixed(1);
      lx = (p.x + q.x) / 2; ly = (p.y + q.y) / 2 - 8;
    }
    h += '<path class="arco" data-a="' + a[0] + '" data-b="' + a[1] + '" d="' + d + '" marker-end="url(#pt)"/>';
    h += '<text class="arco-l" data-a="' + a[0] + '" data-b="' + a[1] + '" x="' + lx.toFixed(1) + '" y="' + ly.toFixed(1) + '" text-anchor="middle" style="paint-order:stroke;stroke:var(--foglio);stroke-width:5px;stroke-linejoin:round">' + a[2] + "</text>";
  });
  Object.keys(NODI).forEach(function (k) {
    var n = NODI[k];
    h += '<g class="nodo" data-k="' + k + '"' + (k === "deputato" ? " data-centro" : "") + ' tabindex="0" role="button" aria-label="' + n.t + '">' +
      '<rect x="' + (n.x - n.w / 2) + '" y="' + (n.y - 17) + '" width="' + n.w + '" height="34" rx="17"/>' +
      '<text x="' + n.x + '" y="' + (n.y + 4.5) + '" text-anchor="middle">' + n.t + "</text></g>";
  });
  svg.setAttribute("viewBox", "0 62 740 482");
  svg.innerHTML = h;

  var schema = document.getElementById("schema");
  var desc = document.getElementById("schema-desc");
  function scegli(k) {
    var n = NODI[k];
    schema.setAttribute("data-scelto", k);
    var vicini = {};
    svg.querySelectorAll(".arco, .arco-l").forEach(function (e) {
      var on = e.dataset.a === k || e.dataset.b === k;
      if (on) { e.setAttribute("data-on", ""); vicini[e.dataset.a] = vicini[e.dataset.b] = true; } else e.removeAttribute("data-on");
    });
    svg.querySelectorAll(".nodo").forEach(function (g) {
      if (g.dataset.k === k) g.setAttribute("data-attivo", ""); else g.removeAttribute("data-attivo");
      if (vicini[g.dataset.k]) g.setAttribute("data-vicino", ""); else g.removeAttribute("data-vicino");
    });
    var collegati = ARCHI.filter(function (a) { return a[0] === k || a[1] === k; }).map(function (a) {
      return "<li>" + esc(NODI[a[0]].t) + ' <span class="mono">→ ' + esc(a[2]) + " →</span> " + esc(NODI[a[1]].t) + "</li>";
    });
    desc.innerHTML =
      '<p class="etichetta">' + (EN ? "Node" : "Nodo") + '</p><h3 class="titolo-3">' + esc(n.t) + "</h3><p>" + esc(n.d) + "</p>" +
      (n.classe.length ? '<div class="classe">' + n.classe.map(function (c) { return '<span class="sigla">' + esc(c) + "</span>"; }).join("") + "</div>" : "") +
      '<ul class="relazioni">' + collegati.join("") + "</ul>" +
      (n.n ? '<p class="quanti">' + quanti(n.n) + esc(n.nl) + (EN ? ", as of " : ", al ") + dataIt(S.last_update) + "</p>" : "");
  }
  function quanti(v) {
    if (typeof v === "number") return "<b>" + numero(v) + "</b>";
    return (EN ? "Chamber " : "Camera ") + "<b>" + numero(v.camera) + "</b> · " + (EN ? "Senate " : "Senato ") + "<b>" + numero(v.senato) + "</b><br>";
  }
  svg.addEventListener("mouseover", function (e) { var g = e.target.closest(".nodo"); if (g) scegli(g.dataset.k); });
  svg.addEventListener("click", function (e) { var g = e.target.closest(".nodo"); if (g) scegli(g.dataset.k); });
  svg.addEventListener("focusin", function (e) { var g = e.target.closest(".nodo"); if (g) scegli(g.dataset.k); });
  svg.addEventListener("keydown", function (e) {
    var g = e.target.closest(".nodo");
    if (g && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); scegli(g.dataset.k); }
  });
  scegli("deputato");

  window.osservaComparse();
})();

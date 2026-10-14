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
    deputato: { t: "Deputy", x: 360, y: 200, w: 112, classe: ["foaf:Person", "ocd:deputato"], n: ramo("people"), nl: "deputies and senators, replacements included", d: "A person, with their mandate. The address is the one of the Chamber's official profile." },
    appartenenza: { t: "Membership", x: 190, y: 96, w: 128, classe: ["org:Membership"], d: "Links a person to a group or a committee, with a start date and, when there is one, an end date. A change of group produces a new membership." },
    gruppo: { t: "Group", x: 70, y: 200, w: 96, classe: ["org:Organization", "ocd:gruppoParlamentare"], d: "A parliamentary group. The components of the Mixed Group are organisations of their own, so +Europa stays +Europa." },
    intervento: { t: "Speech", x: 540, y: 96, w: 116, classe: [], n: ramo("speeches"), nl: "speeches on the floor", d: "What a deputy said in the Chamber, with the full text of the verbatim record." },
    seduta: { t: "Sitting", x: 660, y: 200, w: 92, classe: [], n: ramo("sessions"), nl: "sittings", d: "A sitting of the Chamber, divided into debates. Every speech belongs to a debate of a sitting." },
    atto: { t: "Act", x: 190, y: 306, w: 80, classe: ["ocd:atto"], n: ramo("acts"), nl: "parliamentary acts", d: "A parliamentary act, with its signatories. Acts signed on the topic are one of the six authority criteria." },
    tema: { t: "EuroVoc topic", x: 70, y: 380, w: 124, classe: ["skos:Concept"], n: S.eurovoc_concepts, nl: "EuroVoc topics linked to the acts", d: "A concept of the European Union's EuroVoc thesaurus, with labels in 24 languages." },
    voto: { t: "Vote", x: 540, y: 306, w: 80, classe: ["ocd:voto"], n: ramo("individual_votes"), nl: "individual votes, in a separate file", d: "A deputy's vote in a roll call: in favour, against, abstained." },
    votazione: { t: "Roll call", x: 660, y: 380, w: 108, classe: ["ocd:votazione"], n: ramo("votes"), nl: "electronic votes", d: "An electronic vote of the Chamber, with the outcome and the act being voted on." }
  } : {
    deputato: { t: "Deputato", x: 360, y: 200, w: 112, classe: ["foaf:Person", "ocd:deputato"], n: ramo("people"), nl: "deputati e senatori, subentrati compresi", d: "Una persona, con il suo mandato. L'indirizzo è quello della scheda ufficiale della Camera." },
    appartenenza: { t: "Appartenenza", x: 190, y: 96, w: 128, classe: ["org:Membership"], d: "Lega una persona a un gruppo o a una commissione, con data di inizio e, se c'è, di fine. Un cambio di gruppo produce una nuova appartenenza." },
    gruppo: { t: "Gruppo", x: 70, y: 200, w: 96, classe: ["org:Organization", "ocd:gruppoParlamentare"], d: "Un gruppo parlamentare. Le componenti del Gruppo Misto sono organizzazioni a sé, così +Europa resta +Europa." },
    intervento: { t: "Intervento", x: 540, y: 96, w: 116, classe: [], n: ramo("speeches"), nl: "interventi in Aula", d: "Quello che un deputato ha detto in Aula, con il testo integrale del resoconto stenografico." },
    seduta: { t: "Seduta", x: 660, y: 200, w: 92, classe: [], n: ramo("sessions"), nl: "sedute", d: "Una seduta dell'Aula, divisa in dibattiti. Ogni intervento sta in un dibattito di una seduta." },
    atto: { t: "Atto", x: 190, y: 306, w: 80, classe: ["ocd:atto"], n: ramo("acts"), nl: "atti parlamentari", d: "Un atto parlamentare, con i suoi firmatari. Gli atti firmati sul tema sono uno dei sei criteri di autorevolezza." },
    tema: { t: "Tema EuroVoc", x: 70, y: 380, w: 124, classe: ["skos:Concept"], n: S.eurovoc_concepts, nl: "temi EuroVoc collegati agli atti", d: "Un concetto del thesaurus EuroVoc dell'Unione europea, con le etichette in 24 lingue." },
    voto: { t: "Voto", x: 540, y: 306, w: 80, classe: ["ocd:voto"], n: ramo("individual_votes"), nl: "voti individuali, in un file a parte", d: "Il voto di un deputato in una votazione: favorevole, contrario, astenuto." },
    votazione: { t: "Votazione", x: 660, y: 380, w: 108, classe: ["ocd:votazione"], n: ramo("votes"), nl: "votazioni elettroniche", d: "Una votazione elettronica dell'Aula, con l'esito e l'atto su cui si vota." }
  };
  var ARCHI = EN ? [
    ["appartenenza", "deputato", "member"],
    ["appartenenza", "gruppo", "organisation"],
    ["intervento", "deputato", "spoken by"],
    ["intervento", "seduta", "in the sitting"],
    ["atto", "deputato", "signed by"],
    ["atto", "tema", "topic"],
    ["voto", "deputato", "cast by"],
    ["voto", "votazione", "in the roll call"],
    ["votazione", "atto", "on the act"]
  ] : [
    ["appartenenza", "deputato", "membro"],
    ["appartenenza", "gruppo", "organizzazione"],
    ["intervento", "deputato", "detto da"],
    ["intervento", "seduta", "nella seduta"],
    ["atto", "deputato", "firmato da"],
    ["atto", "tema", "tema"],
    ["voto", "deputato", "espresso da"],
    ["voto", "votazione", "nella votazione"],
    ["votazione", "atto", "sull'atto"]
  ];
  var svg = document.getElementById("schema-svg");
  var h = '<defs><marker id="pt" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M1 1l6 3-6 3" fill="none" stroke="context-stroke" stroke-width="1.3"/></marker></defs>';
  /* Punto sul bordo del rettangolo del nodo, nella direzione dell'altro nodo */
  function bordo(n, verso) {
    var dx = verso.x - n.x, dy = verso.y - n.y, hw = n.w / 2 + 4, hh = 20;
    var s = Math.min(hw / Math.abs(dx || 1e-6), hh / Math.abs(dy || 1e-6));
    return { x: n.x + dx * s, y: n.y + dy * s };
  }
  ARCHI.forEach(function (a) {
    var A = NODI[a[0]], B = NODI[a[1]], p = bordo(A, B), q = bordo(B, A);
    var d, lx, ly;
    if (a[0] === "votazione") {
      /* passa sotto, per non attraversare il centro */
      d = "M" + (A.x - A.w / 2 - 4) + "," + A.y + " C 520,420 330,420 " + (B.x + B.w / 2 + 4) + "," + B.y;
      lx = 430; ly = 404;
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
  svg.setAttribute("viewBox", "0 62 720 362");
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

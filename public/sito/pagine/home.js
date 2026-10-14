/* Pagina iniziale: campione con le citazioni a rotazione, Aula vera, confronto parola per parola, numeri del grafo */
(function () {
  "use strict";
  var D = window.DATI, A = window.AULA;
  var EN = window.LINGUA === "en";
  var SPUNTA = window.ICONE.spunta, CROCE = window.ICONE.croce;
  var esc = window.esc, numero = window.numero, dataLunga = window.dataLunga;
  var T = EN
    ? {
        verbale: "Official record",
        stato: "3 guarantees out of 3",
        evidenziati: "Highlighted seats: ",
        misto: "the 3 seats of the +Europa component of the Mixed Group",
        governo: "the Government benches, in front of the hemicycle",
        coincide: "<strong>It matches the record.</strong> <span>The quote stays, with the link to sitting 510.</span>",
        nonCoincide: function (n) { return "<strong>It does not match: " + n + (n === 1 ? " word differs" : " words differ") + ".</strong> <span>The quote is removed from the answer.</span>"; },
        inCorso: "Comparing…"
      }
    : {
        verbale: "Verbale ufficiale",
        stato: "3 garanzie su 3",
        evidenziati: "Seggi evidenziati: ",
        misto: "i 3 seggi della componente +Europa del Gruppo Misto",
        governo: "i banchi del Governo, davanti all'emiciclo",
        coincide: "<strong>Coincide con il resoconto.</strong> <span>La citazione resta, con il link alla seduta 510.</span>",
        nonCoincide: function (n) { return "<strong>Non coincide: " + n + (n === 1 ? " parola diversa" : " parole diverse") + ".</strong> <span>La citazione viene tolta dalla risposta.</span>"; },
        inCorso: "Confronto in corso…"
      };
  /* Le sigle restano quelle italiane; in inglese cambia solo il Governo */
  function nomeGruppo(q) { return EN && q.group === "Governo" ? "Government" : q.groupName; }

  /* ---------- Campione in apertura: i controlli si accendono uno alla volta ---------- */
  var ordine = ["FdI", "PD", "Lega", "M5S", "FI", "AVS", "Azione", "IV", "NM", "+Europa", "Governo"];
  /* Sigle, citazioni, seggi, gruppi e numeri arrivano già scritti nell'HTML (src/sito/dinamici.ts) */
  var box = document.getElementById("campione-gruppi");
  var sigle = box.querySelectorAll(".sigla");
  var voci = document.querySelectorAll("#campione-sigillo .sigillo__voce");
  var stato = document.getElementById("campione-stato");
  var ridotto = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  function accendi() {
    sigle.forEach(function (s, i) {
      setTimeout(function () { s.setAttribute("data-ok", ""); }, ridotto ? 0 : 500 + i * 70);
    });
    voci.forEach(function (v, i) {
      setTimeout(function () { v.setAttribute("data-ok", ""); }, ridotto ? 0 : 1400 + i * 380);
    });
    setTimeout(function () { stato.textContent = T.stato; stato.style.color = "var(--verificato)"; }, ridotto ? 0 : 2600);
  }
  accendi();

  /* Una citazione verificata per ogni gruppo, a rotazione; clic su una sigla per sceglierla */
  var citazioni = document.querySelectorAll("#campione-voci .cit");
  var corrente = -1, giro = null, fermo = false;
  function mostra(i) {
    corrente = (i + ordine.length) % ordine.length;
    citazioni.forEach(function (c, k) { if (k === corrente) c.setAttribute("data-on", ""); else c.removeAttribute("data-on"); });
    sigle.forEach(function (b, k) { b.setAttribute("aria-pressed", k === corrente ? "true" : "false"); });
  }
  function avvia() {
    clearInterval(giro);
    if (ridotto) return;
    giro = setInterval(function () { if (!fermo && !document.hidden) mostra(corrente + 1); }, 6000);
  }
  box.addEventListener("click", function (e) {
    var b = e.target.closest("button.sigla");
    if (!b) return;
    mostra(+b.dataset.i);
    avvia();
  });
  var campione = document.querySelector(".campione");
  campione.addEventListener("mouseenter", function () { fermo = true; });
  campione.addEventListener("mouseleave", function () { fermo = false; });
  campione.addEventListener("focusin", function () { fermo = true; });
  campione.addEventListener("focusout", function () { fermo = false; });
  mostra(0);
  avvia();

  /* ---------- 01: Aula vera, seggi per gruppo ---------- */
  var svg = document.getElementById("aula");
  var NS = "http://www.w3.org/2000/svg";
  /* Se l'HTML non ha i seggi (aula.js letto male al build), li disegna qui */
  if (!svg.querySelector("circle")) {
    A.seats.forEach(function (s) {
      var c = document.createElementNS(NS, "circle");
      c.setAttribute("cx", s.x);
      c.setAttribute("cy", s.y);
      c.setAttribute("r", 17);
      c.setAttribute("data-g", s.g || "");
      c.setAttribute("data-k", s.k);
      if (s.c) c.setAttribute("data-c", s.c);
      svg.appendChild(c);
    });
  }

  var cit = {};
  D.tema.citazioni.forEach(function (q) { cit[q.group] = q; });
  /* Seggi del gruppo: +Europa siede nel Misto, il Governo ai banchi del Governo */
  var gruppi = [
    { k: "AVS", seggi: "AVS" }, { k: "M5S", seggi: "M5S" }, { k: "PD", seggi: "PD" }, { k: "Azione", seggi: "Azione" },
    { k: "IV", seggi: "IV" }, { k: "+Europa", seggi: "Misto", componente: "+Europa", nota: T.misto }, { k: "NM", seggi: "NM" },
    { k: "FI", seggi: "FI" }, { k: "Lega", seggi: "Lega" }, { k: "FdI", seggi: "FdI" }, { k: "Governo", seggi: null, banchi: "g", nota: T.governo }
  ];
  var lista = document.getElementById("gruppi");
  var voce = document.getElementById("gruppo-voce");

  function scegli(k) {
    var g = gruppi.filter(function (x) { return x.k === k; })[0];
    lista.querySelectorAll("button").forEach(function (b) { b.setAttribute("aria-pressed", b.dataset.k === k ? "true" : "false"); });
    svg.setAttribute("data-scelto", k);
    svg.querySelectorAll("circle").forEach(function (c) {
      /* Governo: solo i suoi banchi. +Europa: solo i seggi della componente, non tutto il Misto */
      var on = g.banchi ? c.getAttribute("data-k") === g.banchi
        : g.componente ? c.getAttribute("data-g") === g.seggi && c.getAttribute("data-c") === g.componente
        : c.getAttribute("data-g") === g.seggi;
      if (on) c.setAttribute("data-on", ""); else c.removeAttribute("data-on");
    });
    var q = cit[k];
    voce.innerHTML =
      '<blockquote class="cit cit--piccola" style="margin-top:var(--s-3)"><p class="cit__testo" lang="it">' + esc(q.quote) + "</p>" +
      '<footer class="cit__fonte"><span class="cit__chi">' + esc(q.name) + "</span><span>" + esc(nomeGruppo(q)) + "</span><span>" + dataLunga(q.date) + "</span>" +
      '<a class="bollino" href="' + q.url + '" rel="noopener">' + SPUNTA + T.verbale + "</a></footer></blockquote>" +
      (g.nota ? '<p class="nota" style="margin-top:var(--s-2);padding-left:var(--s-5)">' + T.evidenziati + g.nota + ".</p>" : "");
  }
  lista.addEventListener("click", function (e) {
    var b = e.target.closest("button");
    if (b) scegli(b.dataset.k);
  });
  scegli("PD");

  /* ---------- 03: confronto parola per parola ---------- */
  var ORIGINALE = "Siamo contrari all'idea di un salario minimo legale, fissato per legge, che rischia di diventare un tetto e non certo un pavimento per le retribuzioni.";
  var input = document.getElementById("confronto-input");
  var out = document.getElementById("confronto-parole");
  var esito = document.getElementById("confronto-esito");
  function parole(s) { return s.trim().split(/\s+/).filter(Boolean); }

  /* LCS sulle parole: abbastanza per citazioni di qualche decina di parole */
  function confronta(a, b) {
    var n = a.length, m = b.length, t = [];
    for (var i = 0; i <= n; i++) { t.push(new Array(m + 1).fill(0)); }
    for (i = n - 1; i >= 0; i--) for (var j = m - 1; j >= 0; j--)
      t[i][j] = a[i] === b[j] ? t[i + 1][j + 1] + 1 : Math.max(t[i + 1][j], t[i][j + 1]);
    var r = []; i = 0; j = 0;
    while (i < n && j < m) {
      if (a[i] === b[j]) { r.push({ w: b[j], s: "ok" }); i++; j++; }
      else if (t[i + 1][j] >= t[i][j + 1]) { r.push({ w: a[i], s: "no" }); i++; }
      else { r.push({ w: b[j], s: "nuovo" }); j++; }
    }
    while (i < n) r.push({ w: a[i++], s: "no" });
    while (j < m) r.push({ w: b[j++], s: "nuovo" });
    return r;
  }
  var timer;
  function aggiorna(anima) {
    clearTimeout(timer);
    var r = confronta(parole(ORIGINALE), parole(input.value));
    var diverse = r.filter(function (x) { return x.s !== "ok"; }).length;
    out.innerHTML = r.map(function (x) { return '<span data-s="' + (anima ? "" : x.s) + '" data-fin="' + x.s + '">' + esc(x.w) + "</span>"; }).join(" ");
    var span = out.querySelectorAll("span");
    var fine = function () {
      if (diverse === 0) {
        esito.setAttribute("data-esito", "ok");
        esito.innerHTML = SPUNTA + T.coincide;
      } else {
        esito.setAttribute("data-esito", "no");
        esito.innerHTML = CROCE + T.nonCoincide(diverse);
      }
    };
    if (anima && !ridotto) {
      esito.removeAttribute("data-esito");
      esito.innerHTML = '<span class="mono">' + T.inCorso + "</span>";
      span.forEach(function (s, i) { timer = setTimeout(function () { s.setAttribute("data-s", s.dataset.fin); if (i === span.length - 1) fine(); }, 40 * i); });
    } else {
      span.forEach(function (s) { s.setAttribute("data-s", s.dataset.fin); });
      fine();
    }
  }
  input.addEventListener("input", function () { aggiorna(false); });
  document.getElementById("confronto-ripristina").addEventListener("click", function () { input.value = ORIGINALE; aggiorna(true); });
  var avviato = false;
  new IntersectionObserver(function (v, io) {
    if (v[0].isIntersecting && !avviato) { avviato = true; aggiorna(true); io.disconnect(); }
  }, { threshold: 0.4 }).observe(out);
  aggiorna(false);

  /* ---------- Numeri del grafo: l'HTML ha la fotografia del build, qui i valori vivi ---------- */
  var S = D.stats;
  document.getElementById("data-agg").textContent = dataLunga(S.last_update);
  document.querySelectorAll("#numeri [data-k]").forEach(function (el) {
    var c = el.dataset.c;
    var v = c ? S.by_chamber && S.by_chamber[c] && S.by_chamber[c][el.dataset.k] : S[el.dataset.k];
    if (typeof v === "number") el.textContent = numero(v);
  });
})();

(function () {
  "use strict";
  var EN = window.LINGUA === "en";
  var esc = window.esc;
  var NESSUNA = EN ? "No question selected." : "Nessuna domanda scelta.";

  /* ---------- Schede: endpoint remoto / Claude Code, con frecce da tastiera ---------- */
  var lista = document.querySelector('[role="tablist"]');
  var schede = Array.prototype.slice.call(lista.querySelectorAll('[role="tab"]'));
  function apri(t) {
    schede.forEach(function (s) {
      var on = s === t;
      s.setAttribute("aria-selected", on ? "true" : "false");
      s.tabIndex = on ? 0 : -1;
      document.getElementById(s.getAttribute("aria-controls")).hidden = !on;
    });
  }
  lista.addEventListener("click", function (e) {
    var t = e.target.closest('[role="tab"]');
    if (t) apri(t);
  });
  lista.addEventListener("keydown", function (e) {
    var i = schede.indexOf(document.activeElement);
    if (i < 0) return;
    var j = e.key === "ArrowRight" ? i + 1 : e.key === "ArrowLeft" ? i - 1 : e.key === "Home" ? 0 : e.key === "End" ? schede.length - 1 : null;
    if (j === null) return;
    e.preventDefault();
    var t = schede[(j + schede.length) % schede.length];
    apri(t);
    t.focus();
  });

  /* ---------- Domande d'esempio: accendono gli strumenti che servono ---------- */
  var esempi = document.getElementById("esempi");
  var strumenti = document.getElementById("strumenti");
  var percorso = document.getElementById("percorso");
  esempi.addEventListener("click", function (e) {
    var b = e.target.closest(".esempio");
    if (!b) return;
    var gia = b.getAttribute("aria-pressed") === "true";
    esempi.querySelectorAll(".esempio").forEach(function (x) { x.setAttribute("aria-pressed", "false"); });
    strumenti.querySelectorAll(".strumento").forEach(function (s) { s.removeAttribute("data-on"); });
    if (gia) {
      strumenti.removeAttribute("data-attivi");
      percorso.textContent = NESSUNA;
      return;
    }
    b.setAttribute("aria-pressed", "true");
    var nomi = b.dataset.strumenti.split(" ");
    strumenti.setAttribute("data-attivi", "");
    nomi.forEach(function (n) {
      var s = strumenti.querySelector('[data-s="' + n + '"]');
      if (s) s.setAttribute("data-on", "");
    });
    percorso.innerHTML = (EN ? "Likely tools, in order: " : "Strumenti probabili, in ordine: ") + nomi.map(function (n) { return "<code>" + esc(n) + "</code>"; }).join(" → ") + ".";
  });
})();

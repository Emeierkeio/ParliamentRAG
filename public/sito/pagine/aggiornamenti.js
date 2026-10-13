(function () {
  "use strict";
  var EN = window.LINGUA === "en";
  var TUTTI = EN ? "October 2026" : "Ottobre 2026";

  /* ---------- Filtro per tipo ---------- */
  var filtro = document.getElementById("filtro");
  var notizie = document.querySelectorAll("#cronaca .notizia");
  var vuota = document.getElementById("vuota");
  var conteggio = document.getElementById("conteggio");
  filtro.addEventListener("click", function (e) {
    var b = e.target.closest("button");
    if (!b) return;
    var tipo = b.dataset.tipo;
    filtro.querySelectorAll("button").forEach(function (x) {
      var on = x === b;
      x.setAttribute("aria-pressed", on ? "true" : "false");
      x.setAttribute("aria-selected", on ? "true" : "false");
    });
    var n = 0;
    notizie.forEach(function (el) {
      var mostra = !tipo || el.dataset.tipo === tipo;
      if (mostra) { el.removeAttribute("data-nascosta"); el.setAttribute("data-visto", "true"); n++; }
      else el.setAttribute("data-nascosta", "");
    });
    vuota.hidden = n > 0;
    conteggio.textContent = tipo ? b.textContent + " · " + n + (EN ? (n === 1 ? " item" : " items") : (n === 1 ? " voce" : " voci")) : TUTTI;
  });
})();

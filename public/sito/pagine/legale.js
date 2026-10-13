(function () {
  "use strict";

  /* ---------- Indice: segna la sezione che stai leggendo ---------- */
  var voci = {};
  document.querySelectorAll("#indice a").forEach(function (a) { voci[a.getAttribute("href").slice(1)] = a; });
  var sezioni = Array.prototype.slice.call(document.querySelectorAll(".articolo-legale"));
  var attesa = false;
  function segna() {
    attesa = false;
    /* Corrente = l'ultima sezione il cui titolo è salito sopra un terzo dello schermo */
    var soglia = window.innerHeight / 3, corrente = null;
    sezioni.forEach(function (s) { if (s.getBoundingClientRect().top <= soglia) corrente = s.id; });
    /* In fondo alla pagina l'ultima sezione può non salire fin lassù */
    if (corrente && window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 2) corrente = sezioni[sezioni.length - 1].id;
    Object.keys(voci).forEach(function (k) {
      if (k === corrente) voci[k].setAttribute("aria-current", "true");
      else voci[k].removeAttribute("aria-current");
    });
  }
  window.addEventListener("scroll", function () {
    if (!attesa) { attesa = true; requestAnimationFrame(segna); }
  }, { passive: true });
  segna();
})();

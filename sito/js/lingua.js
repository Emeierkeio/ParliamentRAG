/* Italiano e inglese. L'interfaccia nasce in italiano; in inglese un osservatore traduce testi e attributi
   con il dizionario di lingua-en.js. Dati, nomi, testi di legge e citazioni restano nell'originale. */
(function () {
  const chiave = "parliamentrag-lingua";
  const daUrl = new URLSearchParams(location.search).get("lang");
  let L = daUrl || (() => { try { return localStorage.getItem(chiave); } catch { return null; } })() || ((navigator.language || "it").toLowerCase().startsWith("it") ? "it" : "en");
  if (L !== "en") L = "it";
  window.LANG = L;
  document.documentElement.lang = L;
  // testo nelle due lingue, per le frasi costruite dal codice
  window.TT = (it, en) => (L === "en" ? en : it);
  // cambia lingua e ricarica: con solo l'ancora diversa il browser non ricaricherebbe la pagina
  window.cambiaLingua = (x) => { try { localStorage.setItem(chiave, x); } catch { /* resta la lingua del browser */ } const u = new URL(location.href); u.searchParams.set("lang", x); history.replaceState(null, "", u.toString()); location.reload(); };
  // traduzione di una frase intera, per le domande precompilate e gli esempi
  window.TR = (s) => { if (L !== "en" || !window.LINGUA_EN || !s) return s; const k = s.replace(/\s+/g, " ").trim(); if (Object.prototype.hasOwnProperty.call(window.LINGUA_EN.testi, k)) return window.LINGUA_EN.testi[k]; for (const [re, f] of window.LINGUA_EN.modelli) { const m = re.exec(k); if (m) return typeof f === "function" ? f(m) : f; } return s; };
  if (L !== "en") return;

  const SALTA = '[translate="no"],script,style,.prosa,.estratto,q,.cit,blockquote,pre,code,.mono,.call,.kg-n,.kg-e,.cl-nome,.persona h4,.em-testo,.em-testo-em,.em-comma,.em-mod,.em-titolo-lungo,.lista li>.meta+span,.lista li>.meta+a,.oggi b,.marchio,#kg-svg';
  const ATTR = ["placeholder", "aria-label", "data-tip", "title"];
  const norm = (s) => s.replace(/\s+/g, " ").trim();
  const traduci = (s) => {
    const D = window.LINGUA_EN; if (!D) return null;
    const k = norm(s); if (!k) return null;
    if (Object.prototype.hasOwnProperty.call(D.testi, k)) return D.testi[k];
    for (const [re, f] of D.modelli) { const m = re.exec(k); if (m) return typeof f === "function" ? f(m) : f; }
    return null;
  };
  // ricorda cosa ha scritto, così non ritraduce le proprie modifiche
  const scritto = new WeakMap(), scrittoA = new WeakMap();
  const testo = (n) => {
    if (!n.parentElement || n.parentElement.closest(SALTA)) return;
    if (scritto.get(n) === n.nodeValue) return;
    const t = traduci(n.nodeValue); if (t == null || t === norm(n.nodeValue)) return;
    const lead = n.nodeValue.match(/^\s*/)[0], coda = n.nodeValue.match(/\s*$/)[0];
    const nuovo = lead + t + coda; scritto.set(n, nuovo); n.nodeValue = nuovo;
  };
  const attributi = (el) => { if (!el.getAttribute || (el.closest && el.closest('[translate="no"]'))) return; let m = scrittoA.get(el); ATTR.forEach((a) => { const v = el.getAttribute(a); if (!v || (m && m[a] === v)) return; const t = traduci(v); if (t != null && t !== v) { if (!m) scrittoA.set(el, (m = {})); m[a] = t; el.setAttribute(a, t); } }); };
  const passa = (radice) => {
    if (radice.nodeType === 3) return testo(radice);
    if (radice.nodeType !== 1) return;
    attributi(radice);
    radice.querySelectorAll("[placeholder],[aria-label],[data-tip],[title]").forEach(attributi);
    const w = document.createTreeWalker(radice, NodeFilter.SHOW_TEXT); let n; while ((n = w.nextNode())) testo(n);
  };
  const avvia = () => {
    passa(document.body); document.documentElement.classList.remove("trad-attesa"); document.title = traduci(document.title) || document.title;
    new MutationObserver((ms) => ms.forEach((m) => {
      if (m.type === "characterData") testo(m.target);
      else if (m.type === "attributes") attributi(m.target);
      else m.addedNodes.forEach(passa);
    })).observe(document.body, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ATTR });
    new MutationObserver(() => { const t = traduci(document.title); if (t && t !== document.title) document.title = t; }).observe(document.querySelector("title"), { childList: true });
  };
  document.readyState === "loading" ? document.addEventListener("DOMContentLoaded", avvia) : avvia();
})();

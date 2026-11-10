/* Avvio: percorsi, scelta grafica, menu, palette, eventi comuni. */
(function () {
  const { $, esc: e } = B;
  const radice = document.documentElement;

  /* ---------- scelta grafica ---------- */
  const CHIAVE = "parliamentrag-scelta";
  // due temi: chiaro e scuro; i valori salvati prima si convertono (notte e netto diventano scuro)
  const tono = (v) => (v === "scuro" || v === "notte" || v === "netto" ? "scuro" : "chiaro");
  const imposta = (v) => {
    const t = tono(v);
    // chiaro: lo stile chiaro di sempre; scuro: lo stile netto rovesciato in nero
    radice.dataset.scelta = t === "scuro" ? "netto" : "chiaro";
    if (t === "scuro") radice.dataset.tono = "scuro"; else delete radice.dataset.tono;
    if (!telefono) try { localStorage.setItem(CHIAVE, t); } catch (err) { /* navigazione privata */ }
    const tb = $("#tema-btn"), ic = $(`#tema-ico [data-scelta-btn="${t === "scuro" ? "chiaro" : "notte"}"]`);
    if (tb && ic) { tb.innerHTML = ic.innerHTML; tb.dataset.tip = t === "scuro" ? TT("Passa al tema chiaro", "Switch to light theme") : TT("Passa al tema scuro", "Switch to dark theme"); tb.setAttribute("aria-label", tb.dataset.tip); }
    if (window.HOME && HOME.ridisegna) HOME.ridisegna();
  };
  // da telefono il tono segue il dispositivo e non c'è un pulsante per cambiarlo
  const telefono = matchMedia("(max-width: 760px)").matches, scuro = matchMedia("(prefers-color-scheme: dark)");
  let iniziale = scuro.matches ? "scuro" : "chiaro"; try { iniziale = localStorage.getItem(CHIAVE) || iniziale; } catch (err) { /* */ }
  if (telefono) { iniziale = scuro.matches ? "scuro" : "chiaro"; scuro.addEventListener("change", () => imposta(scuro.matches ? "scuro" : "chiaro")); }
  const daUrl = new URLSearchParams(location.search).get("scelta"); if (daUrl) iniziale = daUrl;
  imposta(iniziale);
  document.addEventListener("click", (ev) => { if (!ev.target.closest("#tema-btn")) return; imposta(radice.dataset.tono === "scuro" ? "chiaro" : "scuro"); });

  /* ---------- indice a puntini della home ---------- */
  // porta il titolo della sezione appena sotto la testata, non il bordo della sezione
  function vaiSezione(s, liscio = true) {
    const alto = ($(".testata") || {}).offsetHeight || 72;
    const y = s.getBoundingClientRect().top + window.scrollY - alto;
    if (liscio && B.scorriA && B.scorriA(y)) return;
    window.scrollTo({ top: y, behavior: liscio && !matchMedia("(prefers-reduced-motion: reduce)").matches ? "smooth" : "auto" });
  }
  document.addEventListener("click", (ev) => { if (ev.target.closest("[data-casa]")) { ev.preventDefault(); if (!(B.scorriA && B.scorriA(0))) window.scrollTo({ top: 0, behavior: "smooth" }); history.replaceState(null, "", "#/"); return; } });
  new IntersectionObserver(([x]) => { const c = $("[data-casa]"); if (c) c.toggleAttribute("aria-current", x.isIntersecting); document.body.toggleAttribute("data-su-eroe", x.isIntersecting); if (x.isIntersecting) punti.forEach((p) => p.removeAttribute("aria-current")); }, { rootMargin: "-30% 0px -60% 0px" }).observe($(".eroe"));
  document.addEventListener("click", (ev) => { const p = ev.target.closest("[data-punto]"); if (!p) return; ev.preventDefault(); const s = document.getElementById(p.dataset.punto); if (s) { vaiSezione(s); history.replaceState(null, "", `#${p.dataset.punto}`); } });
  const punti = B.$$("[data-punto]");
  const osserva = new IntersectionObserver((xs) => xs.forEach((x) => { if (x.isIntersecting) punti.forEach((p) => p.toggleAttribute("aria-current", p.dataset.punto === x.target.id)); }), { rootMargin: "-30% 0px -60% 0px" });
  punti.forEach((p) => { const s = document.getElementById(p.dataset.punto); if (s) osserva.observe(s); });

  /* ---------- home: salto animato a una sezione dai punti a destra ---------- */
  {
    const fermo = matchMedia("(prefers-reduced-motion: reduce)"), largo = matchMedia("(min-width: 761px)");
    let corsa = 0;
    const attivo = () => !document.body.dataset.vista && !fermo.matches && largo.matches;
    // animazione propria: curva morbida e durata fissa, più regolare dello scorrimento «smooth» del browser
    let rf = 0;
    const curva = (x) => x < .5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2;
    const anima = (dest) => {
      cancelAnimationFrame(rf);
      const da = scrollY, d = dest - da, dur = Math.min(820, 520 + Math.abs(d) * .12), t0 = performance.now();
      corsa = Date.now() + dur + 60;
      document.documentElement.classList.add("scorre");
      const passoA = (ora) => { const x = Math.min(1, (ora - t0) / dur); window.scrollTo(0, da + d * curva(x)); if (x < 1) rf = requestAnimationFrame(passoA); else { corsa = 0; document.documentElement.classList.remove("scorre"); } };
      rf = requestAnimationFrame(passoA);
    };
    B.scorriA = (y) => { if (!attivo()) return false; anima(Math.max(0, Math.min(y, document.documentElement.scrollHeight - innerHeight))); return true; };
    // se l'utente scorre mentre l'animazione corre, l'animazione si ferma e comanda lui
    const ferma = () => { if (!corsa) return; cancelAnimationFrame(rf); corsa = 0; document.documentElement.classList.remove("scorre"); };
    ["wheel", "touchstart", "keydown"].forEach((t) => addEventListener(t, ferma, { passive: true }));
    // rotella, trackpad e tastiera restano allo scorrimento del browser (2/11): intercettarli faceva saltare due sezioni
    // o nessuna con l'inerzia del trackpad. L'animazione propria resta solo per i punti a destra e per il ritorno in cima.
  }

  // larghezza della spiegazione nei titoli di sezione: tutto lo spazio a destra della «i»
  document.addEventListener("mouseover", (ev) => { const i = ev.target.closest && ev.target.closest(".sez h2 .info"); if (!i) return; const w = Math.min(1040, innerWidth - i.getBoundingClientRect().right - 110); i.style.setProperty("--tip-w", `${Math.max(280, w)}px`); });

  /* ---------- giostra degli strumenti ---------- */
  const gs = $("#griglia-str"); if (gs) gs.scrollLeft = 0;
  // il nastro che scorre da solo si sposta con B.giostra (home.js); con il movimento ridotto il contenitore scorre normalmente
  document.addEventListener("click", (ev) => { const b = ev.target.closest("[data-giostra]"); if (!b) return; if (B.giostra && B.giostra(+b.dataset.giostra)) return; const g = $("#griglia-str"), card = g.querySelector("a"); g.scrollBy({ left: (+b.dataset.giostra) * ((card ? card.offsetWidth : 300) + 14), behavior: "smooth" }); });

  /* ---------- newsletter (nel prototipo non invia: la lista è quella vera) ---------- */
  { const f = $("#news-f"); if (f) f.addEventListener("submit", (ev) => { ev.preventDefault(); const m = $("#news-m"), em = $("#news-e").value.trim();
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(em)) { m.textContent = TT("Scrivi un indirizzo email valido.", "Enter a valid email address."); return; }
    if (!$("#news-c").checked) { m.textContent = TT("Per iscriverti serve il consenso.", "Consent is required to subscribe."); return; }
    m.textContent = TT("Prototipo locale: l'iscrizione non viene inviata. Sul sito pubblico arriverebbe una mail di conferma.", "Local prototype: the subscription is not sent. On the public site you would get a confirmation email."); }); }

  /* ---------- cronologia ---------- */
  document.addEventListener("click", (ev) => { if (ev.target.closest("#apri-storia")) CH.mostraStoria(); });

  /* ---------- lingua ---------- */
  if (window.LANG === "en") B.$$("[data-en]").forEach((x) => { x.href = x.dataset.en; });
  { const lb = $("#lingua-btn"), altra = window.LANG === "en" ? "it" : "en"; lb.textContent = altra.toUpperCase(); lb.dataset.tip = altra === "en" ? "English" : "Italiano"; lb.setAttribute("aria-label", lb.dataset.tip); lb.addEventListener("click", () => cambiaLingua(altra)); }

  /* ---------- ambito e invio ---------- */
  let ambito = "Parlamento";
  const invia = (ta) => { if (CH.inCorso) return; let q = ta.value.trim(); if (!q) return; ta.value = ""; ta.style.height = ""; if (ambito !== "Parlamento" && !/camera|senato/i.test(q)) q += ` (solo ${ambito === "Camera" ? "alla Camera" : "al Senato"})`; const ctx = ta.id === "q-conv" && !$("#ctx").hidden ? CH.contesto : null; CH.chiedi(q, ctx); CH.imposta(null); setTimeout(() => $("#q-conv").focus(), 50); };
  // contesto della pagina nella barra in basso
  CH.imposta = (c) => { CH.contesto = c; $("#ctx").hidden = !c; $("#ctx-t").textContent = c ? c.etichetta : ""; $("#q-conv").placeholder = c ? `Chiedi qualcosa su ${c.etichetta}` : CH.esempio ? TT(`Per esempio: ${CH.esempio}`, `For example: ${CH.esempio}`) : document.body.dataset.vista === "conversazione" ? "Continua: «e il Senato?», «chi ha votato contro?», un nome, una data…" : "Chiedi al Parlamento"; };
  // nella conversazione il campo propone come esempio una delle domande successive suggerite dall'ultima risposta
  CH.proponi = (q) => { CH.esempio = q || null; if (!CH.contesto) CH.imposta(null); };
  $("#ctx-x").addEventListener("click", () => CH.imposta(null));
  // in home la barra compare quando la chat grande esce dallo schermo
  new IntersectionObserver(([x]) => document.body.toggleAttribute("data-barra", !x.isIntersecting)).observe($("#f-eroe"));
  // la barra si toglie quando arriva il footer
  new IntersectionObserver(([x]) => document.body.toggleAttribute("data-piede", x.isIntersecting), { rootMargin: "0px 0px -40px 0px" }).observe($(".piede"));
  // copia un testo (per esempio l'indirizzo del server MCP)
  document.addEventListener("click", (ev) => { const c = ev.target.closest("[data-copia-testo]"); if (!c) return; navigator.clipboard && navigator.clipboard.writeText(c.dataset.copiaTesto); c.dataset.tip = TT("Copiato", "Copied"); c.classList.add("fatto"); setTimeout(() => { c.dataset.tip = TT("Copia l'indirizzo", "Copy the address"); c.classList.remove("fatto"); }, 1600); });
  B.$$("form.chat").forEach((f) => {
    const ta = f.querySelector("textarea");
    f.addEventListener("submit", (ev) => { ev.preventDefault(); invia(ta); });
    ta.addEventListener("keydown", (ev) => { if (ev.key === "Enter" && !ev.shiftKey) { ev.preventDefault(); invia(ta); } });
    ta.addEventListener("input", () => { ta.style.height = "auto"; ta.style.height = Math.min(ta.scrollHeight, 220) + "px"; });
  });
  document.addEventListener("click", (ev) => { const b = ev.target.closest(".ambito button"); if (!b) return; ambito = b.textContent.trim(); B.$$(".ambito button").forEach((x) => x.setAttribute("aria-pressed", x.textContent.trim() === ambito)); });

  /* ---------- privacy e termini, in locale ---------- */
  let LEG = null;
  async function legale(tipo, sezione) {
    const pag = $("#pagina"); document.body.dataset.vista = "strumento"; window.scrollTo(0, 0);
    pag.innerHTML = `<div class="carica" role="status"><i></i><i></i><i></i></div>`;
    if (!LEG) LEG = await fetch("/dati/legale.json").then((r) => r.json());
    const d = LEG[window.LANG === "en" ? "en" : "it"][tipo], ancora = (s) => B.norm(s).replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
    const collega = (t) => e(t).replace(/([\w.+-]+@[\w-]+\.[\w.]+[a-z])|\b((?:www\.)[\w-]+(?:\.[\w-]+)+(?:\/[\w/-]*)?|dati\.(?:camera|senato)\.it)/g, (m, em, web) => em ? `<a href="mailto:${em}">${em}</a>` : `<a href="https://${web}" target="_blank" rel="noopener">${web}</a>`);
    // prefisso: gli id della home (#newsletter, #metodo…) non devono ripetersi, né prenderne lo stile
    const sez = d.sections.map((s, i) => ({ ...s, a: "leg-" + (s.id || ancora(s.h)), n: String(i + 1).padStart(2, "0") }));
    const altro = tipo === "privacy" ? ["termini", TT("Termini d'uso", "Terms of use")] : ["privacy", TT("Informativa sulla privacy", "Privacy notice")];
    CH.imposta({ etichetta: d.title, testo: d.title });
    document.title = "ParliamentRAG";
    pag.innerHTML = `<div class="legale" translate="no"><nav class="briciole"><a href="#/">ParliamentRAG</a><span>/</span><b>${e(d.title)}</b></nav>
      <h1>${e(d.title)}</h1><p class="legale__agg">${e(d.updated)}</p>
      <div class="legale__corpo"><nav class="legale__indice" aria-label="${TT("Indice", "Contents")}"><ol>${sez.map((s) => `<li><a href="#/legale/${tipo}#${s.a}" data-salta-leg="${s.a}"><span>${s.n}</span>${e(s.h)}</a></li>`).join("")}</ol><a class="legale__altro" href="#/legale/${altro[0]}">${e(altro[1])} →</a></nav>
      <article>${sez.map((s) => `<section id="${s.a}"><h2><span>${s.n}</span>${e(s.h)}</h2>${s.p.map((x) => `<p>${collega(x)}</p>`).join("")}</section>`).join("")}</article></div></div>`;
    if (sezione) saltaLegale(sezione, "auto");
  }
  // le voci dell'indice portano a #/legale/<tipo>#<sezione>: il clic scorre senza ridisegnare, il link copiato apre la sezione
  const saltaLegale = (id, modo) => { const s = document.getElementById(id); if (s) window.scrollTo({ top: s.getBoundingClientRect().top + scrollY - 96, behavior: modo }); };
  document.addEventListener("click", (ev) => { const l = ev.target.closest("[data-salta-leg]"); if (!l) return; ev.preventDefault(); history.replaceState(null, "", l.getAttribute("href")); saltaLegale(l.dataset.saltaLeg, "smooth"); });

  /* ---------- mobile: si entra dalla chat, si torna alla chat ---------- */
  // da telefono il sito è una chat: gli strumenti si aprono dai link delle risposte e la freccia riporta alla conversazione, nel punto lasciato
  let daChat = false, yChat = 0;
  const ind = $("#indietro-m");
  if (ind) ind.addEventListener("click", () => { if (daChat) history.back(); else { history.pushState(null, "", "#/"); rotta(); window.scrollTo(0, 0); } });

  /* ---------- percorsi ---------- */
  function rotta() {
    const h = location.hash || "#/";
    const prima = document.body.dataset.vista;
    if (prima === "conversazione") yChat = scrollY;
    if (h.startsWith("#/strumenti")) { if (prima === "conversazione") daChat = true; else if (!prima) daChat = false; }
    else if (h.startsWith("#/chiedi") && prima === "strumento" && daChat) { daChat = false; requestAnimationFrame(() => window.scrollTo(0, yChat)); }
    const [percorso, qs] = h.slice(1).split("?");
    const p = percorso.split("/").filter(Boolean);
    $("#menu-str").hidden = true; delete document.body.dataset.menu;
    B.$$(".nav [data-nav]").forEach((a) => a.toggleAttribute("aria-current", (p[0] || "home") === a.dataset.nav));
    if (p[0] === "c" && p[1]) { CH.apriCondivisa(p[1]); return; }
    // ancora di una sezione della home (#strumenti, #metodo…): torna alla home e scorri lì
    if (!h.startsWith("#/") && h.length > 1) { delete document.body.dataset.vista; CH.imposta(null); const s = document.getElementById(h.slice(1)); if (s) requestAnimationFrame(() => vaiSezione(s, false)); return; }
    if (p[0] === "legale") { legale((p[1] || "").split("#")[0] === "termini" ? "termini" : "privacy", (location.hash.split("#")[2] || "")); return; }
    // la pagina «Dati» non esiste più: i dati e il server MCP stanno nella sezione della home
    if (p[0] === "strumenti" && p[1] === "dati") { history.replaceState(null, "", "#dati"); rotta(); return; }
    if (p[0] === "strumenti") { ST.apri(p[1] || "gruppi", p[2], new URLSearchParams(qs || "").get("q") || ""); return; }
    if (p[0] === "chiedi") { if ($("#conversazione").children.length) { document.body.dataset.vista = "conversazione"; CH.imposta(null); return; } const q = new URLSearchParams(qs || "").get("q"); if (q) { CH.chiedi(q); return; } if (CH.riprendi()) return; }
    if (h.startsWith("#/") || h === "#") { if (document.body.dataset.vista) window.scrollTo(0, 0); delete document.body.dataset.vista; CH.imposta(null); document.title = "ParliamentRAG"; if (window.HOME && HOME.ridisegna) HOME.ridisegna(); }
  }
  addEventListener("hashchange", rotta);
  // ricaricando si riparte dall'inizio della home, non dal punto lasciato
  if ("scrollRestoration" in history) history.scrollRestoration = "manual";
  if (!location.hash || location.hash === "#/" || location.hash === "#/chiedi") window.scrollTo(0, 0);
  // il logo riporta sempre all'inizio della home
  document.addEventListener("click", (ev) => { if (!ev.target.closest(".testata .marchio")) return; ev.preventDefault(); B.chiudiPannello && B.chiudiPannello();
    if (document.body.dataset.vista || location.hash.length > 2) { history.pushState(null, "", "#/"); rotta(); window.scrollTo(0, 0); } else window.scrollTo({ top: 0, behavior: "smooth" }); });

  /* ---------- clic comuni ---------- */
  document.addEventListener("click", (ev) => {
    const c = ev.target.closest("[data-chiedi]"); if (c) { ev.preventDefault(); B.chiudiPannello(); CH.chiedi(TR(c.dataset.chiedi)); return; }
    const v = ev.target.closest("[data-vai]"); if (v && !ev.target.closest("a[href]")) { ev.preventDefault(); location.hash = v.dataset.vai; return; }
    const s = ev.target.closest("circle[data-seggio]"); if (s) { location.hash = `#/strumenti/deputato/${s.dataset.seggio}`; return; }
    const sn = ev.target.closest("circle[data-sen-id]"); if (sn && sn.dataset.senId) { location.hash = `#/strumenti/senatore/${sn.dataset.senId}`; return; }
    const m = ev.target.closest("#apri-menu-str"); if (m) { const u = $("#menu-str"); u.hidden = !u.hidden; m.setAttribute("aria-expanded", !u.hidden); return; }
    if (!ev.target.closest(".menu-str")) $("#menu-str").hidden = true;
    if (ev.target.closest("#menu-m")) { document.body.toggleAttribute("data-menu"); return; }
    const sa = ev.target.closest("[data-salta]"); if (sa) { ev.preventDefault(); const t = document.querySelector(sa.getAttribute("href")); if (t) t.scrollIntoView({ block: "start" }); }
    const an = ev.target.closest('a[href^="#"]:not([href^="#/"])'); if (an && an.getAttribute("href").length > 1 && document.body.dataset.vista && !sa) { ev.preventDefault(); history.pushState(null, "", "#/"); delete document.body.dataset.vista; setTimeout(() => { const t = document.querySelector(an.getAttribute("href")); if (t) t.scrollIntoView(); }, 30); }
  });
  $("#pannello-chiudi").addEventListener("click", B.chiudiPannello);
  document.addEventListener("keydown", (ev) => { if (ev.key !== "Escape") return; const pan = $("#pannello").hasAttribute("data-aperto"), menu = !$("#menu-str").hidden; if (!pan && !menu) return; ev.preventDefault(); if (pan) B.chiudiPannello(); $("#menu-str").hidden = true; });
  const tip = $("#tip");
  document.addEventListener("mouseover", (ev) => {
    const sn = ev.target.closest && ev.target.closest("circle[data-senatore]");
    if (sn) { tip.textContent = `${sn.dataset.senatore} · ${sn.dataset.gruppo}${sn.dataset.esito ? " · " + (B.VOTO[sn.dataset.esito] || sn.dataset.esito) : ""}`; tip.hidden = false; tip.style.left = ev.clientX + 12 + "px"; tip.style.top = ev.clientY + 12 + "px"; return; }
    const s = ev.target.closest && ev.target.closest("circle[data-seggio]");
    if (!s) { tip.hidden = true; return; }
    const p = B.persona(s.dataset.seggio); if (!p) return;
    tip.textContent = `${p.n} · ${p.sigla}${s.dataset.esito ? " · " + (B.VOTO[s.dataset.esito] || s.dataset.esito) : ""}`;
    tip.hidden = false; tip.style.left = ev.clientX + 12 + "px"; tip.style.top = ev.clientY + 12 + "px";
  });

  /* ---------- palette ⌘K ---------- */
  const velo = $("#palette"), inp = $("#pal-q"), lista = $("#pal-lista");
  let voci = [], sel = 0;
  const disegna = () => {
    const q = inp.value.trim(), n = B.norm(q); voci = []; let h = "";
    const add = (gruppo, xs) => { if (!xs.length) return; h += `<li class="pal__gt" role="presentation">${TR(gruppo)}</li>`; xs.forEach((x) => { if (x.k === true) x.k = voci.filter((y) => y.k).length + 1; voci.push(x); h += `<li role="option" id="pv-${voci.length - 1}" class="pal__v${x.chiedi ? " pal__v--chiedi" : ""}" data-n="${voci.length - 1}"><span class="pal__i">${B.ico(x.i || (x.chiedi ? "chiedi" : "freccia"))}</span><span class="pal__n">${e(x.n)}</span>${x.s ? `<span class="pal__s">${e(x.s)}</span>` : ""}${x.k ? `<kbd>${x.k}</kbd>` : ""}</li>`; }); };
    if (q) add("Chiedi", [{ n: `Chiedi: «${q}»`, s: "risposta con tutti gli strumenti", chiedi: q }, { n: `Cerca negli atti e negli interventi: «${q}»`, s: "strumento Ricerca", vai: `#/strumenti/atti?q=${encodeURIComponent(q)}` }]);
    if (q) add("Strumenti", ST.ELENCO.filter((x) => B.norm(x.t + " " + x.d).includes(n)).map((x) => ({ n: x.t, s: x.b, i: x.i, vai: `#/strumenti/${x.k}` })));
    else [...new Set(ST.ELENCO.map((x) => x.a))].forEach((ar) => add(ar, ST.ELENCO.filter((x) => x.a === ar).map((x) => ({ n: x.t, s: x.b, i: x.i, vai: `#/strumenti/${x.k}`, k: true }))));
    if (q.length > 1) {
      add("Deputati", B.persone().filter((p) => B.norm(p.n).includes(n)).slice(0, 6).map((p) => ({ n: p.n, s: B.NOMI[p.sigla] || p.sigla, vai: `#/strumenti/deputato/${p.id}` })));
      add("Gruppi", B.gruppiCamera().filter((g) => B.norm(g.sigla + " " + B.NOMI[g.sigla]).includes(n)).map((g) => ({ n: B.NOMI[g.sigla] || g.sigla, s: `${g.seggi} seggi`, chiedi: `Come ha votato ${B.NOMI[g.sigla] || g.sigla} nelle ultime votazioni importanti?` })));
    }
    lista.innerHTML = h || `<li class="pal__gt">Scrivi un nome, un tema, uno strumento</li>`; sel = q ? 0 : -1; segna();
  };
  const segna = () => B.$$(".pal__v", lista).forEach((li) => { const on = +li.dataset.n === sel; li.setAttribute("aria-selected", on); if (on) { inp.setAttribute("aria-activedescendant", li.id); li.scrollIntoView({ block: "nearest" }); } }); if (sel < 0) inp.removeAttribute("aria-activedescendant");
  const scegli = (i) => { const x = voci[i]; if (!x) return; chiudi(); if (x.chiedi) CH.chiedi(TR(x.chiedi)); else location.hash = x.vai; };
  const apri = () => { velo.hidden = false; inp.value = ""; disegna(); inp.focus(); };
  const chiudi = () => { velo.hidden = true; };
  inp.addEventListener("input", disegna);
  inp.addEventListener("keydown", (ev) => { if (ev.key === "ArrowDown") { sel = Math.min(sel + 1, voci.length - 1); segna(); ev.preventDefault(); } if (ev.key === "ArrowUp") { sel = Math.max(sel - 1, 0); segna(); ev.preventDefault(); } if (ev.key === "Enter") scegli(sel); if (ev.key === "Escape") { ev.preventDefault(); ev.stopPropagation(); chiudi(); } if (!inp.value && /^[1-9]$/.test(ev.key)) { const i = voci.findIndex((x) => x.k === +ev.key); if (i >= 0) { ev.preventDefault(); scegli(i); } } });
  lista.addEventListener("click", (ev) => { const li = ev.target.closest(".pal__v"); if (li) scegli(+li.dataset.n); });
  velo.addEventListener("click", (ev) => { if (ev.target === velo) chiudi(); });
  document.addEventListener("keydown", (ev) => { if ((ev.metaKey || ev.ctrlKey) && ev.key.toLowerCase() === "k") { ev.preventDefault(); velo.hidden ? apri() : chiudi(); } });
  const cb = $("#cerca-btn"); if (cb) cb.addEventListener("click", apri);
  // l'icona Strumenti apre il pannello di comandi
  document.addEventListener("click", (ev) => { if (ev.target.closest("#apri-menu-str")) { ev.preventDefault(); ev.stopImmediatePropagation(); $("#menu-str").hidden = true; apri(); } }, true);

  /* ---------- avvio ---------- */
  const aree = [...new Set(ST.ELENCO.map((x) => x.a))];
  $("#menu-str").innerHTML = aree.map((a) => `<li class="area"><p>${e(a)}</p>${ST.ELENCO.filter((x) => x.a === a).map((x) => `<a href="#/strumenti/${x.k}">${B.ico(x.i)}<b>${e(x.t)}</b><span>${e(x.b)}</span></a>`).join("")}</li>`).join("")
    + `<li class="piede"><a href="#/">Non sai quale usare? Chiedi: la risposta li usa tutti.</a><a href="#strumenti">Tutti gli strumenti</a></li>`;
  // le liste lunghe degli strumenti vanno a pagine appena compaiono
  new MutationObserver(() => B.pagine($("#pagina"))).observe($("#pagina"), { childList: true, subtree: true });
  HOME.prepara();
  rotta();
})();

/* barra «Chiedi»: scorrendo giù lascia il posto a un bottone tondo, risalendo o toccando il bottone torna.
   Resta aperta se l'utente ci sta scrivendo. */
(function () {
  const q = document.getElementById("q-conv"), fab = document.getElementById("chat-fab");
  if (!q || !fab) return;
  let y0 = window.scrollY;
  // nella conversazione sotto c'è il piè di pagina: conta la fine dell'ultima risposta, non quella della pagina
  const fineChat = () => { if (document.body.dataset.vista !== "conversazione") return false; const t = [...document.querySelectorAll("#conversazione .turno")].pop(); return !!t && t.getBoundingClientRect().bottom <= innerHeight - 40; };
  // la risposta cresce senza che l'utente scorra: si ricontrolla quando cambia l'altezza della chat
  const conv = document.getElementById("conversazione");
  if (conv && window.ResizeObserver) new ResizeObserver(() => { if (fineChat()) stretta(false); }).observe(conv);
  const stretta = (si) => {
    if (si && (document.activeElement === q || q.value.trim())) return;
    document.body.toggleAttribute("data-barra-stretta", si);
    fab.tabIndex = si ? 0 : -1;
  };
  window.addEventListener("scroll", () => {
    const y = window.scrollY, d = y - y0;
    // alla fine della chat (o della pagina) la barra resta aperta, pronta per un'altra domanda
    const inFondo = fineChat() || y + innerHeight >= document.documentElement.scrollHeight - 160;
    if (inFondo) { stretta(false); y0 = y; return; }
    if (Math.abs(d) < 12) return;
    stretta(d > 0 && y > 160); y0 = y;
  }, { passive: true });
  fab.addEventListener("click", () => { stretta(false); q.focus({ preventScroll: true }); });
  q.addEventListener("focus", () => stretta(false));
})();

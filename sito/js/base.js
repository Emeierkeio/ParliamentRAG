/* Strumenti comuni del prototipo. Nessuna libreria esterna. */
(function () {
  const B = (window.B = {});
  const $ = (B.$ = (s, r = document) => r.querySelector(s));
  B.$$ = (s, r = document) => [...r.querySelectorAll(s)];
  B.esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const e = B.esc;
  B.num = (n) => (n == null ? "—" : Number(n).toLocaleString(EN ? "en-GB" : "it-IT", { useGrouping: "always" }));
  const EN = window.LANG === "en";
  const MESI = EN ? ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"] : ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"];
  const MESI_L = EN ? ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"] : ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"];
  B.data = (iso) => { if (!iso) return ""; const [a, m, g] = String(iso).slice(0, 10).split("-"); return `${+g} ${MESI[+m - 1]} ${a}`; };
  B.dataLunga = (iso) => { if (!iso) return ""; const [a, m, g] = String(iso).slice(0, 10).split("-"); return `${+g} ${MESI_L[+m - 1]} ${a}`; };
  B.ramo = (r) => (r === "senato" ? "Senato" : "Camera");
  B.taglia = (s, n) => { s = String(s || ""); return s.length > n ? s.slice(0, n - 1).replace(/\s+\S*$/, "") + "…" : s; };
  B.norm = (s) => String(s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
  B.frase = (s) => { s = String(s || ""); const m = s.replace(/[^A-Za-zÀ-ÿ]/g, ""); if (!m || (s.match(/[A-ZÀ-Ý]/g) || []).length / m.length < 0.6) return s; const t = s.toLowerCase(); return t.charAt(0).toUpperCase() + t.slice(1); };
  B.nome = (s) => String(s || "").toLowerCase().replace(/(^|[\s'’-])(\p{L})/gu, (m, a, b) => a + b.toUpperCase());

  /* ---------- servizi ---------- */
  B.mcp = async (strumento, argomenti = {}) => {
    const r = await fetch(`/api/mcp/${strumento}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(argomenti) });
    const j = await r.json();
    if (!r.ok) throw new Error(j.errore || "Il servizio non risponde.");
    return j;
  };

  /* ---------- gruppi ---------- */
  const REGOLE = [[/FRATELLI/i, "FdI"], [/PARTITO DEMOCRATICO/i, "PD"], [/^LEGA/i, "Lega"], [/FORZA ITALIA/i, "FI"],
    [/MOVIMENTO 5|MoVimento 5/i, "M5S"], [/ALLEANZA VERDI/i, "AVS"], [/AZIONE/i, "Azione"], [/ITALIA VIVA/i, "IV"],
    [/NOI MODERATI|Civici/i, "NM"], [/Autonomie/i, "Aut"], [/\+Europa/i, "+Europa"], [/Futuro Nazionale|^FNV?$/i, "FNV"],
    [/Minoranze|Min\.?\s*ling/i, "MinLing"], [/Sud chiama|^SCN$/i, "SCN"], [/PSI/i, "PSI"], [/Governo/i, "Governo"], [/MISTO/i, "Misto"]];
  B.NOMI = { FdI: "Fratelli d'Italia", PD: "Partito Democratico", Lega: "Lega", FI: "Forza Italia", M5S: "Movimento 5 Stelle",
    AVS: "Alleanza Verdi e Sinistra", Azione: "Azione", IV: "Italia Viva", NM: "Noi Moderati", Aut: "Per le Autonomie",
    "+Europa": "+Europa (Misto)", FNV: "Futuro Nazionale Vannacci (Misto)", MinLing: "Minoranze linguistiche (Misto)",
    SCN: "Sud chiama Nord (Misto)", PSI: "Avanti PSI (Misto)", Misto: "Misto, non iscritti", Governo: "Governo" };
  B.sigla = (s, comp) => { const t = comp || s || ""; if (B.NOMI[t]) return t; for (const [r, k] of REGOLE) if (r.test(t)) return k; return "Misto"; };
  B.ORDINE = ["AVS", "M5S", "PD", "Azione", "IV", "+Europa", "MinLing", "SCN", "FNV", "Misto", "Aut", "NM", "FI", "Lega", "FdI", "Governo"];
  B.serie = () => (document.documentElement.dataset.tono === "scuro" ? "scuro" : "chiaro");
  B.col = (sig) => COLORI[B.serie()][sig] || COLORI[B.serie()].Misto;
  B.colVoto = (v) => { const t = COLORI.voto[B.serie()]; return { favor: t.favorevole, against: t.contrario, abstain: t.astenuto }[v] || t["non votante"]; };
  B.VOTO = { favor: "Favorevole", against: "Contrario", abstain: "Astenuto", absent: "Assente", secret: "Voto segreto" };
  // il gruppo si scrive sempre per esteso
  B.sig = (sig) => `<span class="sig"><i style="background:${B.col(sig)}"></i>${e(B.NOMI[sig] || sig)}</span>`;
  B.barra = (f, a, s, x = 0) => { const t = f + a + s + x || 1; return `<div class="barra-v" role="img" aria-label="${f} favorevoli, ${a} contrari, ${s} astenuti"><span style="width:${f / t * 100}%;background:${B.colVoto("favor")}"></span><span style="width:${a / t * 100}%;background:${B.colVoto("against")}"></span><span style="width:${s / t * 100}%;background:${B.colVoto("abstain")}"></span></div>`; };
  // voto di un gruppo: favorevoli da sinistra, contrari da destra, astenuti al centro; lo spazio vuoto sono gli assenti
  B.barraLati = (f, a, s, x = 0) => { const t = f + a + s + x || 1, p = (n) => `${n / t * 100}%`;
    return `<div class="barra-l" role="img" aria-label="${f} ${TT("favorevoli", "in favour")}, ${s} ${TT("astenuti", "abstained")}, ${a} ${TT("contrari", "against")}"><span style="left:0;width:${p(f)};background:${B.colVoto("favor")}"></span><span style="left:50%;transform:translateX(-50%);width:${p(s)};background:${B.colVoto("abstain")}"></span><span style="right:0;width:${p(a)};background:${B.colVoto("against")}"></span></div>`; };
  // pesi che sommano sempre a 100: chi si muove prende il suo valore, gli altri si dividono il resto in proporzione
  B.ribilancia = (w, i, v) => {
    v = Math.max(0, Math.min(1, v)); const resto = 1 - v, altri = w.reduce((s, x, k) => s + (k === i ? 0 : x), 0), n = w.length - 1;
    const out = w.map((x, k) => (k === i ? v : altri > 0 ? (x / altri) * resto : resto / n));
    // percentuali intere che sommano esattamente a 100 (resti più grandi)
    const c = out.map((x) => x * 100), base = c.map(Math.floor); let manca = 100 - base.reduce((a, b) => a + b, 0);
    c.map((x, k) => [x - base[k], k]).sort((a, b) => b[0] - a[0]).forEach(([, k]) => { if (manca > 0) { base[k]++; manca--; } });
    return base.map((x) => x / 100);
  };
  B.esito = (v) => (v.kind === "quorum_check" ? [TT("Numero legale", "Quorum check"), "neutro"] : /^approv/.test(v.outcome) ? [TT("Approvata", "Passed"), "ok"] : v.outcome === "rejected" ? [TT("Respinta", "Rejected"), "no"] : ["—", "neutro"]);

  /* ---------- Aula: seggi reali della Camera ---------- */
  const COMP = { FNV: "FNV", "Min. Ling.": "MinLing", "+Europa": "+Europa", SCN: "SCN" };
  B.siglaSeggio = (s) => (s.g === "Misto" ? COMP[s.c] || "Misto" : s.g);
  B.seggi = () => (window.AULA ? AULA.seats.filter((s) => s.k === "d") : []);
  B.persone = () => B.seggi().filter((s) => s.id).map((s) => ({ id: s.id, n: s.n, sigla: B.siglaSeggio(s), v: s.v, x: s.x, y: s.y }));
  B.persona = (id) => B.persone().find((p) => p.id === String(id));
  // i senatori, quando B.caricaSenato ha letto l'elenco: stessa forma dei deputati, con senato vero
  B.senatori = () => (B.SEN ? Object.values(B.SEN.perId).map((x) => ({ id: x.id, n: x.name, sigla: x.component || x.group, senato: true })) : []);
  B.perNome = (nome) => { const n = B.norm(nome); return B.persone().find((p) => B.norm(p.n) === n); };
  B.gruppiCamera = () => { const m = {}; B.persone().forEach((p) => { m[p.sigla] = (m[p.sigla] || 0) + 1; }); return B.ORDINE.filter((g) => m[g]).map((g) => ({ sigla: g, seggi: m[g] })); };
  B.foto = (id) => `https://documenti.camera.it/_dati/leg19/schededeputatinuovosito/fotoDefinitivo/big/d${id}.jpg`;
  B.fotoHtml = (p) => `<span class="foto"><img src="${B.foto(p.id)}" alt="" loading="lazy" onerror="this.replaceWith(document.createTextNode('${e(p.n.split(" ").map((x) => x[0]).slice(0, 2).join(""))}'))"></span>`;
  /* voti individuali (get_vote_details) → id del seggio: codice camera.it, altrimenti nome */
  B.votiSeggi = (individuali) => {
    const ids = new Set(B.persone().map((p) => p.id)), m = {};
    (individuali || []).forEach((x) => {
      const k = /persona\.rdf\/p(\d+)/.exec(x.id || "");
      let id = k && ids.has(k[1]) ? k[1] : null;
      if (!id) { const p = B.perNome(`${x.first_name} ${x.last_name}`); if (p) id = p.id; }
      if (id) m[id] = x.outcome;
    });
    return m;
  };
  B.emiciclo = (o = {}) => {
    const r = o.r || 16, vuoto = B.serie() === "scuro" ? "rgba(255,255,255,.10)" : "rgba(20,22,29,.10)";
    const c = B.seggi().map((s) => {
      let f = vuoto, esito = "";
      if (s.id) {
        if (o.voti) { esito = o.voti[s.id] || ""; f = esito ? B.colVoto(esito) : vuoto; }
        else f = B.col(B.siglaSeggio(s));
        if (o.filtra && !o.filtra(s)) { f = B.col(B.siglaSeggio(s)); s._spento = true; }
      }
      const acceso = o.evidenzia && s.id === String(o.evidenzia);
      const sp = s._spento; delete s._spento; return `<circle cx="${s.x}" cy="${s.y}" r="${acceso ? r * 2 : r}" fill="${f}"${sp ? ' opacity=".18"' : ""} style="--w:${(((s.x - 80) / 2400) * 0.6).toFixed(3)}s"${acceso ? ' stroke="currentColor" stroke-width="8"' : ""}${s.id ? ` data-seggio="${s.id}" data-esito="${esito}"` : ""}/>`;
    }).join("");
    return `<svg class="emi" viewBox="0 0 2552 1760" role="img" aria-label="${e(o.etichetta || "Aula della Camera, seggi reali")}">${c}</svg>`;
  };
  B.legendaVoto = () => `<div class="legenda">${["favor", "against", "abstain", "absent"].map((k) => `<span><b style="color:${B.colVoto(k)}">●</b> ${B.VOTO[k].toLowerCase()}</span>`).join("")}<span>${matchMedia("(max-width: 760px)").matches ? "tocca un seggio: chi è e come ha votato" : "clic su un seggio: chi è e come ha votato"}</span></div>`;

  /* ---------- icone (tratto 1,7, 24×24) ---------- */
  const I = { scarica: '<path d="M12 4v11M7 10l5 5 5-5M5 20h14"/>', legge: '<path d="M12 4v16M6 20h12M5 8h14"/><path d="m5 8-2.5 6a2.5 2.5 0 0 0 5 0zM19 8l-2.5 6a2.5 2.5 0 0 0 5 0z"/>', sx: '<path d="M15 6l-6 6 6 6"/>', dx: '<path d="m9 6 6 6-6 6"/>', cerca: '<circle cx="11" cy="11" r="6.5"/><path d="m20 20-4.2-4.2"/>', voto: '<rect x="4" y="4" width="16" height="16" rx="3"/><path d="m8.5 12.5 2.5 2.5 5-6"/>',
    sed: '<rect x="4" y="5" width="16" height="15" rx="2"/><path d="M4 10h16M9 3v4M15 3v4"/>', cal: '<rect x="4" y="5" width="16" height="15" rx="2"/><path d="M4 10h16M9 3v4M15 3v4M8 14h2M12 14h2M16 14h0M8 17h2"/>', aula: '<path d="M4 18a8 8 0 0 1 16 0M8 18a4 4 0 0 1 8 0"/>',
    pers: '<circle cx="12" cy="8" r="3.5"/><path d="M5 20a7 7 0 0 1 14 0"/>', scudo: '<path d="M12 3 5 6v5c0 4.5 3 8 7 10 4-2 7-5.5 7-10V6z"/><path d="m9 12 2 2 4-4"/>',
    atto: '<path d="M7 3h7l4 4v14H7z"/><path d="M14 3v4h4"/>', gruppi: '<circle cx="7" cy="12" r="3"/><circle cx="17" cy="12" r="3"/>',
    emend: '<path d="M7 3h7l4 4v14H7z"/><path d="M10 13h5M12.5 10.5v5"/>', bilancia: '<path d="M12 4v16M5 20h14M6 8h12M6 8l-3 6h6zM18 8l-3 6h6z"/>',
    dati: '<ellipse cx="12" cy="6" rx="7" ry="3"/><path d="M5 6v12c0 1.7 3.1 3 7 3s7-1.3 7-3V6M5 12c0 1.7 3.1 3 7 3s7-1.3 7-3"/>',
    ok: '<path d="m5 12.5 4.5 4.5L19 7.5"/>', ripristina: '<path d="M4 12a8 8 0 1 0 2.4-5.7L4 8.6"/><path d="M4 4v4.6h4.6"/>', traduci: '<path d="M4 5h8M8 3v2M5.5 9c1.4 2.7 3.6 4.6 6.5 5.6M11 5c-.9 4-3.3 7.2-7 9"/><path d="m13 21 4-9 4 9M14.4 18h5.2"/>', giu: '<path d="m6 9 6 6 6-6"/>', piu: '<path d="M12 5v14M5 12h14"/>', menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
    chiedi: '<path d="M5 5h14v10H9l-4 4z"/>', impost: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>', chiudi: '<path d="M6 6l12 12M18 6 6 18"/>', cestino: '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>', condividi: '<circle cx="18" cy="5" r="2.5"/><circle cx="6" cy="12" r="2.5"/><circle cx="18" cy="19" r="2.5"/><path d="m8.2 10.8 7.6-4.4M8.2 13.2l7.6 4.4"/>', storia: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>', esterno: '<path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>', info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5v.5"/>', copia: '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V5a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3"/>', su: '<path d="M7 11v9H4v-9zM7 11l4-7c1.5 0 2.5 1 2 3l-1 3h6a2 2 0 0 1 2 2.3l-1.2 6A2 2 0 0 1 16.8 20H7"/>', giuP: '<path d="M17 13V4h3v9zM17 13l-4 7c-1.5 0-2.5-1-2-3l1-3H6a2 2 0 0 1-2-2.3l1.2-6A2 2 0 0 1 7.2 4H17"/>', segnala: '<path d="M5 21V4M5 4h11l-2 4 2 4H5"/>', freccia: '<path d="M5 12h14M13 6l6 6-6 6"/>' };
  // spiegazione dietro una «i», link come icona
  // anagrafica da dati.camera.it: nascita, età, elezione
  B.anagrafica = async (id) => { const r = await fetch(`/dati/anagrafica/${encodeURIComponent(id)}.json`); if (!r.ok) throw new Error("dati.camera.it non risponde"); const d = await r.json();
    const ymd = (x) => x && /^\d{8}$/.test(x) ? `${x.slice(0, 4)}-${x.slice(4, 6)}-${x.slice(6, 8)}` : x || null;
    const nascita = ymd(d.nascita), luogo = (/nato a ([^,]+)|nata a ([^,]+)/i.exec(d.nascitaL || "") || []).slice(1).find(Boolean);
    let eta = null; if (nascita) { const n = new Date(nascita), o = new Date(); eta = o.getFullYear() - n.getFullYear() - (o < new Date(o.getFullYear(), n.getMonth(), n.getDate()) ? 1 : 0); }
    const titolo = (s) => s ? s.toLowerCase().replace(/(^|[\s(-])([a-zà-ý])/g, (m, a, b) => a + b.toUpperCase()) : s;
    return { nascita, eta, luogo: titolo(luogo), inizio: ymd(d.inizio), convalida: d.convalida || null, circ: titolo(d.circ), coll: d.coll ? d.coll.replace(/^(.*?) - /, (m, a) => titolo(a) + " – ") : null, tipo: d.tipo, elezione: ymd(d.data), fonte: d.fonte }; };
  // ogni fonte apre prima una pagina di ParliamentRAG; da lì «Raggiungi la fonte»
  B.interno = (url, titolo, extra = {}) => {
    const u = String(url || ""), t = String(titolo || "");
    let m = /\b(\d\/\d{4,6})\b/.exec(t); if (m) return `#/strumenti/atto/camera-${m[1].replace("/", "~")}?t=${encodeURIComponent(t)}&u=${encodeURIComponent(u)}`;
    m = /idDocumento=([\w-]+)/.exec(u); if (m && /camera\.it/.test(u)) return `#/strumenti/atto/camera-${m[1]}?t=${encodeURIComponent(t)}`;
    m = /^\s*S\.\s*(\d+[\w-]*)/.exec(t) || /\(S\.\s*(\d+)\)/.exec(t); if (m && /senato\.it/.test(u)) return `#/strumenti/atto/senato-${m[1]}?t=${encodeURIComponent(t)}&u=${encodeURIComponent(u)}`;
    m = /^\s*C\.\s*(\d+[\w-]*)/.exec(t); if (m && /camera\.it/.test(u)) return `#/strumenti/atto/camera-${m[1]}?t=${encodeURIComponent(t)}`;
    m = /idSeduta=0*(\d+)/.exec(u); if (m && /camera\.it/.test(u)) return `#/strumenti/seduta/leg19_sed${m[1]}`;
    const q = new URLSearchParams({ u, t, ...extra }); return `#/strumenti/fonte?${q.toString()}`;
  };
  // il resoconto ufficiale con la frase evidenziata dal browser (#:~:text=inizio,fine); senza link, la pagina interna
  B.allaFonte = (url, frase) => {
    const u = String(url || ""); if (!/^https?:/.test(u)) return null;
    const p = String(frase || "").replace(/[«»"“”]/g, "").split(/\s+/).filter(Boolean);
    if (p.length < 4) return u;
    const enc = (xs) => encodeURIComponent(xs.join(" ")).replace(/-/g, "%2D").replace(/,/g, "%2C");
    const b = u.split(":~:")[0]; return `${b}${b.includes("#") ? "" : "#"}:~:text=${p.length > 12 ? `${enc(p.slice(0, 6))},${enc(p.slice(-5))}` : enc(p)}`;
  };
  // emiciclo del Senato dai voti individuali: un punto per senatore, gruppi da sinistra a destra
  // Senato: pianta reale dei posti (senato.it, «Dove siedono i senatori»)
  B.caricaSenato = async () => {
    if (B.SEN) return B.SEN;
    const [p, s] = await Promise.all([fetch("/dati/senato/seats.json").then((r) => r.json()), fetch("/dati/senatori.json").then((r) => r.json())]);
    const perPosto = {}, perId = {}; s.deputies.forEach((x) => { perId[x.id] = x; if (x.seat != null) perPosto[x.seat] = x; });
    B.SEN = { pianta: p, perPosto, perId }; return B.SEN;
  };
  B.emicicloSenato = (iv, etichetta, perGruppo, solo) => {
    const S = B.SEN; if (!S) return "";
    const voti = {}; (iv || []).forEach((x) => { const id = x.sid || ((/(?:senatore\/|^)(\d+)$/.exec(x.senato_id || x.id || "") || [])[1]); if (id) voti[id] = x.outcome; });
    const [, , W, H] = S.pianta.plan.viewBox, r = S.pianta.plan.seatRadius;
    const c = S.pianta.seats.map((st) => {
      const x = S.perPosto[st.posto], g = x ? B.sigla(x.group) : "", fuori = solo && g !== solo;
      if (!x) return `<circle cx="${st.cx}" cy="${st.cy}" r="${r}" fill="none" stroke="var(--bordo2)" stroke-width="1"/>`;
      const v = voti[x.id], col = perGruppo ? B.col(g) : v && v !== "absent" ? B.colVoto(v) : null;
      return `<circle data-sen-id="${e(x.id)}" data-senatore="${e(x.name)}" data-gruppo="${e(g)}" data-esito="${e(perGruppo ? "" : v || "")}" cx="${st.cx}" cy="${st.cy}" r="${r}" fill="${col || "none"}" stroke="${col || "var(--t3)"}" stroke-width="1.2"${fuori ? ' opacity=".18"' : ""}/>`;
    }).join("");
    return `<svg class="emiciclo emi-sen" viewBox="0 0 ${W} ${S.pianta.plan.separatorY + 10}" role="img" aria-label="${e(etichetta || "")}">${c}</svg>`;
  };

  // sigla con il nome intero del gruppo
  B.sigLungo = (sig) => `<span class="sig sig--lungo"><i style="background:${B.col(sig)}"></i>${e(B.NOMI[sig] || sig)}</span>`;
  // dettaglio dei sei criteri di autorevolezza di un parlamentare
  // ramo di una voce del fascicolo: i deputati hanno l'id della Camera, i senatori si riconoscono dal nome
  B.ramoDi = (x) => {
    const id = (/p(\d+)$/.exec(x.id || "") || [])[1]; if (id && B.persona(id)) return "camera";
    const nome = B.norm(`${x.first_name || ""} ${x.last_name || ""}`);
    if (/sen/i.test(x.id || "") || (B.SEN && Object.values(B.SEN.perId).some((s) => B.norm(s.name) === nome || B.norm(s.registryName || "") === nome))) return "senato";
    return id ? "camera" : null;
  };
  B.carica = (x) => ({ camera: TT("Camera dei deputati", "Chamber of Deputies"), senato: TT("Senato della Repubblica", "Senate") })[B.ramoDi(x)] || "";
  B.criteri = (x, pesi) => {
    const C = [["speeches", TT("Interventi in Aula", "Floor speeches"), .25], ["committee", TT("Commissione", "Committee"), .25], ["acts", TT("Atti firmati", "Signed acts"), .20], ["profession", TT("Professione", "Profession"), .15], ["education", TT("Formazione", "Education"), .10], ["role", TT("Ruolo istituzionale", "Institutional role"), .05]];
    const b = x.score_breakdown || {}, id = (/p(\d+)$/.exec(x.id || "") || [])[1], nome = B.nome(`${x.first_name} ${x.last_name}`), g = B.sigla(x.group);
    const p = id ? (B.persona(id) || { id, n: nome, sigla: g }) : null, senato = B.ramoDi(x) === "senato";
    const sid = (/senatore\/(\d+)$/.exec(x.id || "") || [])[1];
    B.pannello(TT("Autorevolezza", "Authority"), `<div class="crit-testa">${p ? B.fotoHtml(p) : sid ? `<span class="foto"><img src="/dati/foto/senatori/${sid}.jpg" alt="" onerror="this.remove()"></span>` : ""}<div><b>${e(nome)}</b><span class="ramo-v">${B.carica(x)}</span>${B.sigLungo(g)}<span class="crit-tot">${Number(x.authority_score).toFixed(2)}</span></div></div>
      <ul class="crit">${C.map(([k, t, w], i) => { const v = b[k] || 0, peso = pesi ? pesi[i] : w;
        // professione e formazione: senza il dato il criterio non conta; con il dato, 0 vuol dire sotto la mediana dei parlamentari su questo tema
        const manca = (k === "profession" || k === "education") && !x[k];
        const nota = manca ? (senato ? TT("dato non pubblicato dal Senato", "not published by the Senate") : TT("dato non disponibile", "no data")) : (k === "profession" || k === "education") && v === 0 ? TT(`peso ${Math.round(peso * 100)}% · sotto la mediana su questo tema`, `weight ${Math.round(peso * 100)}% · below the median on this topic`) : `${TT("peso", "weight")} ${Math.round(peso * 100)}% · ${TT("contributo", "contribution")} ${(v * peso).toFixed(3)}`;
        return `<li${manca ? ' class="crit--off"' : ""}><div><b>${t}</b><small>${nota}</small></div><span class="crit-barra"><i style="width:${manca ? 0 : (v * 100).toFixed(0)}%"></i></span><span class="crit-v">${manca ? "—" : v.toFixed(2)}</span></li>`; }).join("")}</ul>
      ${[x.committee && `<p class="crit-nota"><b>${TT("Commissione", "Committee")}</b> ${e(B.frase(x.committee))}</p>`, x.profession && `<p class="crit-nota"><b>${TT("Professione", "Profession")}</b> ${e(x.profession)}</p>`, x.education && `<p class="crit-nota"><b>${TT("Formazione", "Education")}</b> ${e(x.education)}</p>`].filter(Boolean).join("")}
      ${id ? `<a class="bt bt--primario" href="#/strumenti/deputato/${id}" style="margin-top:16px">${B.ico("pers")}${TT("Apri la scheda", "Open the profile")}</a>` : ""}`);
  };
  B.entita = (s) => { const t = document.createElement("textarea"); t.innerHTML = s; return t.value; };
  // in inglese i testi ufficiali (titoli di votazioni, atti, sedute) si traducono dopo il disegno; si marcano con data-tr
  const IN_ATTESA = new Set();
  B.traduci = () => {
    if (window.LANG !== "en") return;
    clearTimeout(B._trT); B._trT = setTimeout(async () => {
      const els = [...document.querySelectorAll("[data-tr]:not([data-tr-fatto])")].filter((x) => !IN_ATTESA.has(x)); if (!els.length) return;
      els.forEach((x) => IN_ATTESA.add(x));
      const testi = els.map((x) => x.textContent.trim());
      try { const r = await fetch("/api/traduci", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ testi }) }); const { tradotti } = await r.json();
        els.forEach((x, i) => { if (tradotti[i] && tradotti[i] !== testi[i]) { x.title = testi[i]; x.textContent = tradotti[i]; } x.setAttribute("data-tr-fatto", ""); IN_ATTESA.delete(x); });
      } catch { els.forEach((x) => IN_ATTESA.delete(x)); }
    }, 150);
  };
  if (window.LANG === "en") document.addEventListener("DOMContentLoaded", () => new MutationObserver(() => { if (document.querySelector("[data-tr]:not([data-tr-fatto])")) B.traduci(); }).observe(document.body, { childList: true, subtree: true }));
  B.info = (t) => `<span class="info" tabindex="0" role="note" aria-label="${B.esc(t)}" data-tip="${B.esc(t)}">${B.ico("info")}</span>`;
  B.link = (href, etichetta, ico) => { const fuori = /^https?:/.test(href); return `<a class="ic-a" href="${B.esc(href)}" aria-label="${B.esc(etichetta)}" data-tip="${B.esc(etichetta)}"${fuori ? ' target="_blank" rel="noopener"' : ""}>${B.ico(ico || (fuori ? "esterno" : "freccia"))}</a>`; };
  // liste lunghe a pagine (ul[data-per]): così un blocco resta alto quanto quello accanto
  B.pagine = (root) => root.querySelectorAll("ul[data-per]:not([data-pag])").forEach((ul) => {
    const per = +ul.dataset.per, li = [...ul.children], n = Math.ceil(li.length / per);
    ul.dataset.pag = "0"; if (n < 2) return;
    const nav = document.createElement("nav"); nav.className = "pag"; nav.setAttribute("aria-label", TT("Pagine", "Pages"));
    nav.innerHTML = `<button type="button" class="ic-a" data-pag="-1" aria-label="${TT("Precedenti", "Previous")}">${B.ico("sx")}</button><span aria-live="polite"></span><button type="button" class="ic-a" data-pag="1" aria-label="${TT("Successivi", "Next")}">${B.ico("dx")}</button>`;
    const vai = (k) => { ul.dataset.pag = k; li.forEach((x, i) => { x.hidden = Math.floor(i / per) !== k; }); nav.querySelector("span").textContent = `${k + 1} / ${n}`; nav.querySelector('[data-pag="-1"]').disabled = k === 0; nav.querySelector('[data-pag="1"]').disabled = k === n - 1; };
    nav.addEventListener("click", (ev) => { const b = ev.target.closest("[data-pag]"); if (b) vai(Math.min(n - 1, Math.max(0, +ul.dataset.pag + +b.dataset.pag))); });
    ul.after(nav); vai(0);
  });
  B.ico = (n) => `<svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${I[n] || I.chiedi}</svg>`;

  /* ---------- pannello laterale e suggerimento ---------- */
  B.pannello = (tipo, html) => {
    const p = $("#pannello"); $("#pannello-tipo").textContent = tipo; $("#pannello-corpo").innerHTML = html;
    p.setAttribute("data-aperto", ""); p.setAttribute("aria-hidden", "false"); B._daFocus = document.activeElement; $("#pannello-chiudi").focus();
  };
  B.chiudiPannello = () => { const p = $("#pannello"); p.removeAttribute("data-aperto"); p.setAttribute("aria-hidden", "true"); if (B._daFocus) B._daFocus.focus(); };
  B.scheda = (id, esito, titoloVoto) => {
    const p = B.persona(id); if (!p) return;
    B.pannello("Deputato · Camera", `<div style="display:flex;gap:14px;align-items:center">${B.fotoHtml(p)}<div><b class="titolo" style="font-size:26px;display:block;line-height:1.1">${e(p.n)}</b>${B.sig(p.sigla)} <span style="color:var(--t3);font-size:14px">${e(B.NOMI[p.sigla] || "")}</span></div></div>
      ${titoloVoto ? `<p class="meta" style="margin:0">${e(titoloVoto)}</p><div class="sig" style="font-size:16px"><i style="background:${B.colVoto(esito)};border-radius:50%;width:12px;height:12px"></i>${esito ? B.VOTO[esito] || esito : "non registrato"}</div>` : ""}
      ${B.link(`#/strumenti/deputato/${p.id}`, "Apri la scheda")}<button class="bt bt--linea" data-chiedi="Cosa ha detto ${e(p.n)} in Aula di recente?">Chiedi cosa ha detto</button>`);
  };
})();

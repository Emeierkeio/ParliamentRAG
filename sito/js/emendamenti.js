/* Emendamenti: una legge con il suo iter, il testo comma per comma e gli emendamenti che lo toccano.
   Dati di Camera e Senato dal database, in sola lettura. */
(function () {
  const e = B.esc, $ = B.$;
  const ELETTORALE = "legge-elettorale";
  const APPROVATI = "approvati";
  const cache = new Map();
  let indice = null;

  /* ---------- dati ---------- */
  const leggi = async (url) => {
    if (cache.has(url)) return cache.get(url);
    const p = fetch(url).then((r) => (r.ok ? r.json() : Promise.reject(new Error(r.status === 404 ? "Questa legge non è nei dati." : "Il servizio non risponde."))));
    cache.set(url, p);
    p.catch(() => cache.delete(url));
    return p;
  };
  const urlLegge = (slug) => (slug === ELETTORALE ? "/dati/emendamenti/legge-elettorale.json" : `/dati/emendamenti/leggi/${encodeURIComponent(slug)}.json`);

  /* ---------- stato nell'indirizzo ---------- */
  const CHIAVI = { fase: "fase", art: "art", comma: "comma", lettera: "lettera", em: "em", esito: "esito", gruppo: "gruppo", pan: "pan" };
  const leggiStato = () => { const q = new URLSearchParams((location.hash.split("?")[1]) || ""); const s = {}; Object.keys(CHIAVI).forEach((k) => { s[k] = q.get(k) || null; }); return s; };
  const scriviStato = (slug, s) => {
    const q = new URLSearchParams(); Object.keys(CHIAVI).forEach((k) => { if (s[k]) q.set(k, s[k]); });
    const qs = q.toString();
    history.replaceState(null, "", `#/strumenti/emendamenti/${encodeURIComponent(slug)}${qs ? "?" + qs : ""}`);
  };

  /* ---------- formati ---------- */
  const MESI = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"];
  const data = (d) => { if (!d) return ""; const x = String(d).replace(/-/g, ""); return `${+x.slice(6, 8)} ${MESI[+x.slice(4, 6) - 1]} ${x.slice(0, 4)}`; };
  let senzaEsito = false; // nessun esito pubblicato nella lista: niente filtri e niente etichetta ripetuta su ogni riga
  const ESITI = { approvato: "Approvato", respinto: "Respinto", inammissibile: "Inammissibile", precluso: "Precluso", ritirato: "Ritirato", improcedibile: "Improcedibile", "trasformato in odg": "Trasformato in odg", "vedi altro testo": "Riformulato", altro: "Altro esito" };
  const SPIEGA = { inammissibile: "La presidenza lo ha dichiarato inammissibile: non è stato votato.", precluso: "Non è stato votato: un voto precedente aveva già deciso lo stesso punto.", ritirato: "I firmatari lo hanno ritirato prima del voto.", improcedibile: "La presidenza lo ha dichiarato improcedibile, di solito per mancanza di copertura dei costi.", "trasformato in odg": "I firmatari lo hanno trasformato in un ordine del giorno.", "vedi altro testo": "I firmatari lo hanno riscritto: l'esito sta sul testo nuovo.", altro: "La fonte riporta un esito diverso dai soliti." };
  const esito = (a) => (a.outcome ? ESITI[a.outcome] || a.outcome : "Esito non pubblicato");
  const spiega = (a) => { const aula = /aula|assemblea|terza/.test(a.stage); if (a.outcome === "approvato") return `${aula ? "L'Aula" : "La commissione"} lo ha approvato.`; if (a.outcome === "respinto") return `${aula ? "L'Aula" : "La commissione"} lo ha respinto.`; return a.outcome ? SPIEGA[a.outcome] || "" : "La fonte non ha ancora pubblicato l'esito."; };
  const classeEsito = (a) => (a.outcome === "approvato" ? "ok" : a.outcome === "respinto" ? "no" : "neutro");
  const TIPI = { emendamento: "Emendamento", subEmendamento: "Subemendamento", articoloAggiuntivo: "Articolo aggiuntivo" };
  const gruppoEtichetta = (g) => (g === "Misto" ? "Misto, componente non nei dati" : g);
  const chip = (g) => (g ? `<span class="em-g" title="${e(gruppoEtichetta(g))}"><i style="background:${B.col(B.sigla(g))}"></i>${e(g)}</span>` : "");
  const confronta = (x, y) => {
    const p = (n) => String(n).split(/[./]/).map((v) => (/^\d+$/.test(v) ? Number(v) : v));
    const a = p(x), b = p(y);
    for (let i = 0; i < Math.max(a.length, b.length); i++) {
      if (a[i] === undefined) return -1; if (b[i] === undefined) return 1; if (a[i] === b[i]) continue;
      if (typeof a[i] === "number" && typeof b[i] === "number") return a[i] - b[i];
      return String(a[i]).localeCompare(String(b[i]));
    }
    return 0;
  };
  const dove = (a) => [a.article && /^\d/.test(a.article) ? `Art. ${a.article}` : "Fuori articolato", a.comma && `comma ${a.comma}`, a.letter && `lettera ${a.letter})`].filter(Boolean).join(", ");
  const nEm = (n) => `${B.num(n)} ${n === 1 ? "emendamento" : "emendamenti"}`;

  /* ---------- scheletri di caricamento ---------- */
  const righe = (n, cl = "") => Array.from({ length: n }, (_, i) => `<span class="skel skel--riga ${cl}" style="width:${[92, 78, 85, 64, 88, 70][i % 6]}%"></span>`).join("");
  const scheletroElenco = () => `<div class="em-skel" aria-busy="true"><span class="vh" role="status">Carico l'elenco delle leggi</span><span class="skel skel--campo"></span>${Array.from({ length: 8 }, () => `<div class="em-skel__riga"><span class="skel" style="width:90px;height:14px"></span><span class="skel" style="flex:1;height:14px"></span><span class="skel" style="width:60px;height:14px"></span></div>`).join("")}</div>`;
  const scheletroLettore = () => `<div class="em-skel" aria-busy="true"><span class="vh" role="status">Carico il testo della legge e gli emendamenti</span>
    <span class="skel" style="width:120px;height:13px"></span><span class="skel" style="width:60%;height:26px;margin-top:10px"></span>
    <div class="em-skel__fasi">${Array.from({ length: 5 }, () => `<span class="skel" style="height:54px"></span>`).join("")}</div>
    <div class="em-griglia"><div class="em-skel__col">${righe(9)}</div><div class="em-skel__col em-skel__testo">${righe(14)}</div><div class="em-skel__col">${righe(10)}</div></div></div>`;

  /* ---------- elenco delle leggi ---------- */
  async function elenco(box) {
    box.insertAdjacentHTML("beforeend", `<div id="em-corpo">${scheletroElenco()}</div>`);
    try { indice = indice || (await leggi("/dati/emendamenti/leggi/index.json")); }
    catch (err) { $("#em-corpo").innerHTML = `<div class="errore">Non riesco a leggere l'elenco delle leggi: ${e(err.message)}</div>`; return; }
    const temi = [...new Set(indice.flatMap((x) => x.temi || []))].sort();
    $("#em-corpo").innerHTML = `
      <div class="em-filtri"><label class="vh" for="em-q">Cerca una legge</label><input id="em-q" placeholder="Cerca per titolo o numero, per esempio «S. 1689» o «caregiver»">
        <label class="vh" for="em-tema">Tema</label><select id="em-tema"><option value="">Tutti i temi</option>${temi.map((t) => `<option>${e(t)}</option>`).join("")}</select>
        <label class="vh" for="em-stato">Stato</label><select id="em-stato"><option value="">Ogni stato</option><option value="legge">Diventate legge</option><option value="esame">In esame</option></select>
        <label class="vh" for="em-ord">Ordine</label><select id="em-ord"><option value="em">Più emendamenti</option><option value="data">Più recenti</option></select></div>
      ${ST.avvio(TT("Ogni legge con il suo iter, il testo comma per comma e gli emendamenti che lo toccano, con il voto e l'esito.", "Every bill with its path, the text clause by clause and the amendments to it, with vote and outcome."), ["legge elettorale", "bilancio", "autonomia", "S. 1689"], "em-q")}
      <a class="em-evidenza" href="#/strumenti/emendamenti/${ELETTORALE}">
        <span class="em-num">C. 2822 · S. 1971 · C. 2822-B</span>
        <b>Legge elettorale</b>
        <span>Disposizioni in materia di elezioni della Camera dei deputati e del Senato della Repubblica. Il testo in ogni fase, le modifiche tra una fase e l'altra e gli emendamenti presentati in commissione e in Aula, alla Camera e al Senato.</span>
        <span class="em-evidenza__vai">Apri la legge</span>
      </a>
      <p class="em-conta" id="em-conta"></p>
      <div class="em-tab" role="table" aria-label="Leggi con emendamenti"><div class="em-tab__testa" role="row"><span role="columnheader">Numero</span><span role="columnheader">Titolo</span><span role="columnheader">Iter</span><span role="columnheader" class="dx">Emendamenti</span></div><div id="em-righe"></div></div>
      <button class="bt bt--linea" id="em-altre" hidden>Mostra altre leggi</button>
      <p class="em-nota">Dati di Camera e Senato, XIX legislatura. ${B.num(indice.length)} leggi con almeno un emendamento.</p>`;
    let quante = 40;
    const filtra = () => {
      const q = B.norm($("#em-q").value.trim()), tema = $("#em-tema").value, stato = $("#em-stato").value, ord = $("#em-ord").value;
      let xs = indice.filter((x) => (!q || B.norm(`${x.title} ${x.numbers.join(" ")} ${x.numbers.join(" ").replace(/\.\s*/g, ".")}`).includes(q)) && (!tema || (x.temi || []).includes(tema)) && (!stato || (stato === "legge" ? /legge|definitiv/i.test(x.stato) : !/legge|definitiv/i.test(x.stato))));
      xs = xs.sort(ord === "data" ? (a, b) => String(b.ultimo || "").localeCompare(String(a.ultimo || "")) : (a, b) => b.amendments - a.amendments);
      $("#em-conta").textContent = `${B.num(xs.length)} leggi`;
      $("#em-righe").innerHTML = xs.slice(0, quante).map((x) => `<a class="em-riga" role="row" href="#/strumenti/emendamenti/${encodeURIComponent(x.slug)}">
        <span class="em-num" role="cell">${e(x.numbers.join(" · "))}</span>
        <span role="cell"><b>${e(B.taglia(x.title, 150))}</b><small>${e([statoLeggibile(x.stato), (x.temi || [])[0], x.commissione && `${x.commissione.nome} ${x.commissione.ramo === "S" ? "Senato" : "Camera"}`].filter(Boolean).join(" · "))}</small></span>
        <span role="cell" class="em-iter-mini">${(x.iter || []).filter((t) => t.label !== "Presentata").map((t) => `<i class="${t.c === "S" ? "s" : "c"}${t.label === "Legge" ? " l" : ""}" title="${e(`${t.c === "S" ? "Senato" : "Camera"}, ${t.label.toLowerCase()}, ${data(t.date)}`)}"></i>`).join("")}</span>
        <span role="cell" class="dx em-cifra">${B.num(x.amendments)}</span></a>`).join("") || `<p class="em-vuoto">Nessuna legge con questi filtri.</p>`;
      $("#em-altre").hidden = xs.length <= quante;
    };
    ["#em-q", "#em-tema", "#em-stato", "#em-ord"].forEach((s) => $(s).addEventListener("input", () => { quante = 40; filtra(); }));
    $("#em-altre").addEventListener("click", () => { quante += 60; filtra(); });
    filtra();
  }
  const statoLeggibile = (s) => ({ "appr. definit. Legge": "Legge", "esame in comm.": "In commissione", approvato: "Approvata in un ramo", "appr. con modificaz": "Approvata con modifiche", "concluso l'esame": "Esame concluso", "appr. in t.u.": "Approvata in testo unificato", respinto: "Respinta", "in relazione": "In relazione", "all'esame assemblea": "In Aula", assorbito: "Assorbita", "approvato definitivamente": "Legge", "rinviato ass.->comm.": "Rinviata in commissione" }[s] || s);

  /* ---------- fasi dell'iter ---------- */
  function fasi(L) {
    if (L.steps && L.steps.length) {
      const raw = L.steps;
      return raw.map((s, i) => {
        const version = s.version || (raw.slice(i + 1).find((x) => x.version) || {}).version || (raw.slice(0, i).reverse().find((x) => x.version) || {}).version || "";
        const prev = raw[i - 1], cambia = s.changesFrom && prev && prev.version && prev.version !== s.version;
        return { ...s, version, changesFrom: cambia ? s.changesFrom : null, changesLabel: cambia ? `Cambiato in ${prev.label.charAt(0).toLowerCase()}${prev.label.slice(1)} (${prev.chamber})` : null };
      });
    }
    const has = (id) => L.versions.some((v) => v.id === id);
    const prima = (st) => { const d = L.amendments.filter((a) => a.stage === st && a.date).map((a) => String(a.date).replace(/-/g, "")).sort(); return d[0] || null; };
    const fin = L.events.find((x) => /definitiv/i.test(x.label));
    return [
      { id: "camera-commissione", chamber: "Camera", label: "Commissione", date: prima("camera-commissione"), version: "presentato", stage: "camera-commissione", changesFrom: null },
      { id: "camera-aula", chamber: "Camera", label: "Aula", date: prima("camera-aula"), version: "commissione", stage: "camera-aula", changesFrom: "commissione", changesLabel: "Cambiato in commissione" },
      { id: "senato-commissione", chamber: "Senato", label: "Commissione", date: prima("senato-commissione"), version: "camera1", stage: "senato-commissione", changesFrom: "camera1", changesLabel: "Cambiato nell'Aula della Camera" },
      { id: "senato-aula", chamber: "Senato", label: "Aula", date: prima("senato-aula"), version: "camera1", stage: "senato-aula", changesFrom: "camera1", changesLabel: "Cambiato nell'Aula della Camera" },
      { id: "legge", chamber: "Legge", label: "Testo definitivo", date: fin ? fin.date : null, version: "senato", stage: APPROVATI, changesFrom: "senato", changesLabel: "Cambiato al Senato" },
    ].filter((s) => has(s.version));
  }

  /* ---------- cosa farebbe un emendamento al testo (formule semplici) ---------- */
  function effetto(a, art) {
    if (!a || !art || !a.text) return null;
    // «Sostituire l'articolo con il seguente» / «Sostituire gli articoli da 1 a 3 con i seguenti»: il testo di oggi barrato, sotto quello nuovo
    const sost = /^\s*sostituire (?:l'articolo(?: (\d+[\w-]*))?|gli articoli da (\d+) a (\d+)) con (?:il seguente|i seguenti)\s*:?/i.exec(a.text);
    if (sost) {
      const n = parseInt(art.num, 10), da = sost[2] ? +sost[2] : null, a2 = sost[3] ? +sost[3] : null;
      const tocca = da != null ? n >= da && n <= a2 : (sost[1] || a.article) === art.num;
      if (!tocca) return null;
      // il nuovo testo di questo articolo: da «Art. N» al prossimo «Art.» a inizio riga
      const resto = a.text.slice(sost[0].length), pezzi = resto.split(/\n(?=\s*["“]?\s*Art\.\s*\d+\s*\n)/);
      // solo i titoli d'articolo da soli su una riga: «Art. 1-bis.» dentro il testo è una norma citata, non un articolo nuovo
      const mio = da == null ? resto : pezzi.find((x) => new RegExp(`^\\s*["“]?\\s*Art\\.\\s*${n}\\s*\\n`).test(x));
      const righe = (mio || "").split("\n").map((x) => x.trim().replace(/^["«“]|["»”]\.?$/g, "")).filter(Boolean).filter((x, i) => !(i === 0 && /^Art\.\s*\d/.test(x)));
      return { articolo: true, comma: (art.commi[0] || {}).num, blocchi: new Map(), nuovo: righe, intervallo: da != null ? `${da}-${a2}` : null };
    }
    if (a.article !== art.num) return null;
    // «Sopprimere l'articolo»: tutto l'articolo barrato
    if (/^\s*sopprimere l'articolo\.?\s*$/i.test(a.text)) return { articolo: true, comma: (art.commi[0] || {}).num, blocchi: new Map() };
    if (!a.comma) return null;
    const c = art.commi.find((x) => x.num === a.comma); if (!c) return null;
    const t = a.text.split(/\n|Conseguentemente/)[0];
    const segni = (testo) => {
      let m;
      if ((m = /sostituire (?:la parola|le parole):?\s*«([^»]+)»\s*con (?:la seguente|le seguenti):?\s*«([^»]+)»/i.exec(testo))) return { trova: m[1], con: m[2] };
      if ((m = /sopprimere (?:la parola|le parole):?\s*«([^»]+)»/i.exec(testo))) return { trova: m[1], con: "" };
      if ((m = /dopo (?:la parola|le parole):?\s*«([^»]+)»\s*(?:aggiungere|inserire)(?:, in fine,)? (?:la seguente|le seguenti):?\s*«([^»]+)»/i.exec(testo))) return { dopo: m[1], con: m[2] };
      if ((m = /aggiungere,? in fine,? (?:la seguente|le seguenti)(?: parol[ae])?:?\s*«([^»]+)»/i.exec(testo))) return { fine: m[1] };
      if (/^\s*(?:Al comma \d+[^,]*,\s*)?sopprimerl[oa]\.?\s*$/i.test(testo) || /sopprimere il comma/i.test(testo)) return { tutto: true };
      // la Camera pubblica spesso il testo senza virgolette: «la parola» è una parola sola, «le parole» arrivano fino al verbo che segue
      const fino = (x) => x.trim().replace(/[.;]\s*$/, "");
      if ((m = /sostituire la parola:?\s+([^\s,;:]+)\s+con (?:la seguente|le seguenti):?\s+(.+)$/i.exec(testo))) return { trova: m[1], con: fino(m[2]) };
      if ((m = /sostituire le parole:?\s+(.+?)\s+con (?:la seguente|le seguenti):?\s+(.+)$/i.exec(testo))) return { trova: m[1], con: fino(m[2]) };
      if ((m = /dopo la parola:?\s+([^\s,;:]+)\s+(?:aggiungere|inserire)(?:,? in fine,?)? (?:la seguente|le seguenti)(?: parol[ae])?:?\s+(.+)$/i.exec(testo))) return { dopo: m[1], con: fino(m[2]) };
      if ((m = /dopo le parole:?\s+(.+?)\s+(?:aggiungere|inserire)(?:,? in fine,?)? (?:la seguente|le seguenti)(?: parol[ae])?:?\s+(.+)$/i.exec(testo))) return { dopo: m[1], con: fino(m[2]) };
      if ((m = /sopprimere la parola:?\s+([^\s,;:]+)\.?\s*$/i.exec(testo))) return { trova: m[1], con: "" };
      if ((m = /sopprimere le parole:?\s+(.+)$/i.exec(testo))) return { trova: fino(m[1]), con: "" };
      if ((m = /aggiungere,? in fine,? (?:la seguente|le seguenti)(?: parol[ae])?:?\s+(.+)$/i.exec(testo))) return { fine: fino(m[1]) };
      return null;
    };
    const op = segni(t); if (!op) return null;
    const blocchi = c.blocks.map((b) => b.text);
    let i = 0;
    if (a.letter) { const k = c.blocks.findIndex((b) => b.kind === "point" && (b.label || "").replace(/[)\s]/g, "") === a.letter); if (k >= 0) i = k; }
    const out = new Map();
    if (op.tutto) { c.blocks.forEach((_, k) => { if (!a.letter || k === i) out.set(k, "via"); }); return { comma: c.num, blocchi: out }; }
    const cerca = (trova) => { const idx = a.letter ? [i] : blocchi.map((_, k) => k); for (const k of idx) { const p = blocchi[k].indexOf(trova); if (p >= 0) return [k, p]; } return null; };
    if (op.fine) { const k = a.letter ? i : blocchi.length - 1; out.set(k, [["eq", blocchi[k]], ["ins", " " + op.fine]]); return { comma: c.num, blocchi: out }; }
    const trova = op.trova || op.dopo; const pos = cerca(trova); if (!pos) return null;
    const [k, p] = pos, s = blocchi[k];
    out.set(k, op.dopo ? [["eq", s.slice(0, p + trova.length)], ["ins", " " + op.con], ["eq", s.slice(p + trova.length)]] : [["eq", s.slice(0, p)], ["del", trova], ...(op.con ? [["ins", op.con]] : []), ["eq", s.slice(p + trova.length)]]);
    return { comma: c.num, blocchi: out };
  }
  const segmenti = (seg) => seg.map(([k, t]) => (k === "eq" ? e(t) : `<${k === "ins" ? "ins" : "del"}>${e(t)}</${k === "ins" ? "ins" : "del"}>`)).join(" ").replace(/\s+([,.;:])/g, "$1");

  /* ---------- lettore ---------- */
  async function lettore(box, slug) {
    box.insertAdjacentHTML("beforeend", `<div id="em-corpo">${scheletroLettore()}</div>`);
    let L;
    try { L = await leggi(urlLegge(slug)); }
    catch (err) { $("#em-corpo").innerHTML = `<div class="errore">${e(err.message)} ${B.link("#/strumenti/emendamenti", "Torna all\'elenco")}</div>`; return; }
    if (!$("#em-corpo")) return; // l'utente ha cambiato pagina
    const P = fasi(L);
    const perId = new Map(L.amendments.map((a) => [a.id, a]));
    const figli = new Map(); L.amendments.forEach((a) => { if (a.parent) figli.set(a.parent, [...(figli.get(a.parent) || []), a]); });
    const nomeFase = new Map(L.stages.map((s) => [s.id, s.label]));
    const conta = new Map(P.map((s) => [s.id, L.amendments.filter((a) => (s.stage === APPROVATI ? a.outcome === "approvato" : a.stage === s.stage) && !a.parent).length]));
    const maggioranza = new Set(L.majority || []);
    let st = leggiStato();
    if (st.em && perId.has(st.em) && !st.fase) { const a = perId.get(st.em), f = P.find((x) => x.stage === a.stage); st = { ...st, fase: f && f.id, art: a.article, comma: a.comma, lettera: a.letter }; }
    const ultimaConEm = [...P].reverse().find((s) => s.stage !== APPROVATI && conta.get(s.id));
    const titolo = L.bill.short || L.bill.title;
    const ultimo = [...L.events].reverse().find((x) => x.result);

    $("#em-corpo").innerHTML = `<div class="em-testa">
        <div><p class="em-num">${e(L.bill.numbers.join(" · "))}</p><h2 class="em-titolo-lungo">${e(B.taglia(L.bill.title, 220))}</h2>
        <p class="em-sotto">${L.bill.proponents ? (() => { const pf = L.bill.proponents.split(/,\s*/).filter(Boolean); return `<span title="${e(pf.join(", "))}">Prima firma: ${e(pf[0])}${pf.length > 1 ? ` e altri ${pf.length - 1}` : ""}</span> · `; })() : ""}${B.num(L.amendments.length)} emendamenti</p></div>
        ${ultimo ? votoFinale(ultimo) : ""}</div>
      <nav class="em-fasi" aria-label="Fasi dell'iter" id="em-fasi"></nav>
      <details class="em-iter"><summary>Iter: ${B.num(L.events.length)} passaggi</summary><ol>${L.events.map((x) => `<li><span class="em-cifra">${data(x.date)}</span><b>${e(x.label)}</b>${x.detail ? `<span>${e(x.detail)}</span>` : ""}${x.result ? `<span class="em-cifra">${B.num(x.result.in_favor)} sì · ${B.num(x.result.against)} no${x.result.abstained ? ` · ${B.num(x.result.abstained)} astenuti` : ""}</span>` : ""}${x.url || (x.result && x.result.url) ? `${B.link(x.url || x.result.url, "Apri la fonte")}` : ""}</li>`).join("")}</ol></details>
      <div class="em-griglia"><nav class="em-art" id="em-art" aria-label="Articoli"></nav><article class="em-testo" id="em-testo" aria-live="polite"></article><aside class="em-pan" id="em-pan" aria-live="polite"></aside></div>
      <p class="em-nota">Dati di Camera e Senato. Gli esiti in commissione sono pubblicati solo in parte, e i pareri del relatore e del Governo non sono nei dati aperti. L'anteprima sul testo funziona con le formule più comuni: sostituire, sopprimere, aggiungere dopo una parola o in fine.</p>`;

    const disegna = () => {
      const fase = P.find((s) => s.id === st.fase) || ultimaConEm || P[P.length - 1];
      const ver = L.versions.find((v) => v.id === fase.version) || L.versions[L.versions.length - 1];
      const art = ver.articles.find((a) => a.num === st.art) || ver.articles[0];
      const ems = L.amendments.filter((a) => (fase.stage === APPROVATI ? a.outcome === "approvato" : a.stage === fase.stage)).sort((x, y) => confronta(x.number, y.number));
      const cont = new Map(); const add = (k) => cont.set(k, (cont.get(k) || 0) + 1);
      ems.forEach((a) => { if (!a.article || a.parent) return; add(`${a.article}|*`); if (a.comma) add(`${a.article}|${a.comma}`); if (a.comma && a.letter) add(`${a.article}|${a.comma}|${a.letter}`); });
      const modifiche = L.changes.filter((c) => fase.changesFrom && c.version === fase.changesFrom);
      const modArt = new Set(modifiche.map((c) => c.article));
      const modComma = new Map(modifiche.filter((c) => c.article === art.num).map((c) => [c.comma, c]));
      const cur = st.em ? perId.get(st.em) : null;
      // leggi grandi: i testi arrivano tagliati, quello intero si chiede per articolo quando si apre un emendamento
      if (cur && cur.cut) {
        const u = `/dati/emendamenti/leggi/${encodeURIComponent(slug)}/testi/${encodeURIComponent(cur.article || "_")}.json`;
        leggi(u).then((m) => { L.amendments.forEach((a) => { if (m[a.id] != null) { a.text = m[a.id]; a.cut = false; } }); if ($("#em-corpo")) disegna(); }).catch(() => {});
      }
      const eff = cur && !cur.cut ? effetto(cur, art) : null;
      scriviStato(slug, st);
      CH.imposta({ etichetta: cur ? `em. ${cur.number}, ${titolo}` : titolo, testo: `Emendamenti di ${L.bill.numbers.join(", ")} «${L.bill.title}», fase ${fase.chamber} ${fase.label}, articolo ${art.num}${st.comma ? `, comma ${st.comma}` : ""}${cur ? `; emendamento ${cur.number} (${esito(cur)}): ${B.taglia(cur.text || "", 300)}` : ""}` });

      $("#em-fasi").innerHTML = P.map((s) => `<button data-fase="${e(s.id)}" aria-pressed="${s.id === fase.id}"><b><span class="em-fasi__ramo">${e(s.chamber)}</span> ${e(s.label)}</b><span class="em-cifra">${s.date ? data(s.date) : "data non nei dati"} · ${s.stage === APPROVATI ? `${B.num(conta.get(s.id))} approvati` : B.num(conta.get(s.id) || 0)}</span></button>`).join("");

      const iA = ver.articles.indexOf(art), aPrima = ver.articles[iA - 1], aDopo = ver.articles[iA + 1];
      $("#em-art").innerHTML = `<button class="em-art__fr" ${aPrima ? `data-art="${e(aPrima.num)}"` : "disabled"} aria-label="Articolo precedente">‹</button>
        <label class="vh" for="em-art-sel">Articolo</label><select id="em-art-sel">${ver.articles.map((a) => { const n = cont.get(`${a.num}|*`) || 0; return `<option value="${e(a.num)}"${a.num === art.num ? " selected" : ""}>Art. ${e(a.num)}${a.heading ? ` · ${e(B.taglia(a.heading, 60))}` : ""}${n ? ` · ${B.num(n)} em.` : ""}${modArt.has(a.num) ? " · cambiato" : ""}</option>`; }).join("")}</select>
        <button class="em-art__fr" ${aDopo ? `data-art="${e(aDopo.num)}"` : "disabled"} aria-label="Articolo successivo">›</button>
        <span class="em-sotto">${iA + 1} di ${ver.articles.length}</span>`;

      const nArt = cont.get(`${art.num}|*`) || 0;
      $("#em-testo").innerHTML = `<header class="em-testo__testa"><div><h3>Articolo ${e(art.num)}</h3>${art.heading ? `<p>${e(art.heading)}</p>` : ""}</div><span class="em-sotto">${e(ver.label)}${ver.date ? `, ${data(ver.date)}` : ""}</span></header>
        ${!eff && fase.changesLabel && modifiche.length && modComma.size ? `<p class="em-legenda"><ins>parole aggiunte</ins> <del>parole tolte</del> ${e(fase.changesLabel)}: ${B.num(modComma.size)} ${modComma.size === 1 ? "comma" : "commi"} di questo articolo.</p>` : ""}
        ${eff ? `<p class="em-legenda em-legenda--anteprima">${cur.outcome === "approvato" ? `Con l'em. ${e(cur.number)}, approvato` : `Se fosse stato approvato l'em. ${e(cur.number)} (${e(esito(cur).toLowerCase())})`}. <button class="em-link" data-em="">Togli l'anteprima</button></p>` : ""}
        ${nArt ? `<button class="em-tutto" aria-pressed="${!!st.pan && !st.comma}">${st.pan && !st.comma ? "Emendamenti dell'articolo" : "Vedi gli emendamenti dell'articolo"} <span class="em-cifra">${B.num(nArt)}</span></button> <span class="em-sotto">oppure scegli un comma</span>` : `<p class="em-sotto em-nessuno">Nessun emendamento su questo articolo</p>`}
        ${art.commi.map((c) => {
          const n = cont.get(`${art.num}|${c.num}`) || 0, mod = eff ? null : modComma.get(c.num), att = st.comma === c.num, ant = eff && eff.articolo ? new Map(c.blocks.map((_, k) => [k, "via"])) : eff && eff.comma === c.num ? eff.blocchi : null;
          const corpo = mod && !ant ? `<p>${segmenti(mod.diff)}</p>${mod.amendments && mod.amendments.length ? `<p class="em-da">Da ${mod.amendments.map((id) => perId.get(id)).filter(Boolean).map((a) => `<button class="em-link" data-em="${e(a.id)}">em. ${e(a.number)}</button>`).join(", ")}</p>` : ""}`
            : c.blocks.map((b, k) => {
              const lett = b.kind === "point" && b.depth === 0 ? (b.label || "").replace(/[)\s]/g, "") : "";
              const nl = lett ? cont.get(`${art.num}|${c.num}|${lett}`) || 0 : 0;
              const x = ant && ant.get(k);
              const testo = x === "via" ? `<del>${e(b.text)}</del>` : x ? segmenti(x) : e(b.text);
              const etich = b.label ? `<span class="em-lab">${e(b.label)}</span>` : "";
              if (lett && nl) return `<p class="em-lett${att && st.lettera === lett ? " att" : ""}" style="margin-left:${b.depth * 18}px"><button data-comma="${e(c.num)}" data-lettera="${e(lett)}">${etich}${testo}</button> <span class="em-n" title="${nEm(nl)} su questa lettera">${nl}</span></p>`;
              return `<p style="margin-left:${b.depth * 18}px">${etich}${testo}</p>`;
            }).join("");
          return `<section class="em-comma${att ? " att" : ""}${mod ? " mod" : ""}" id="em-c-${e(c.num)}"><button class="em-comma__n" data-comma="${e(c.num)}" aria-pressed="${att}" aria-label="Comma ${e(c.num)}: ${nEm(n)}"><span>${e(c.num)}.</span>${n ? `<span class="em-n">${n}</span>` : ""}</button><div class="em-comma__t">${corpo}</div></section>`;
        }).join("")}
        ${eff && eff.articolo && eff.nuovo ? `<section class="em-comma em-nuovo"><div class="em-comma__t"><p class="em-nuovo__tit">${eff.nuovo.length ? `Il testo che l'em. ${e(cur.number)} mette al posto dell'articolo` : `L'em. ${e(cur.number)} sostituisce questo articolo, ma il nuovo testo non si legge nei dati`}</p>${eff.nuovo.map((x) => `<p><ins>${e(x)}</ins></p>`).join("")}</div></section>` : ""}
        <div class="em-scorri">${(() => { const i = ver.articles.indexOf(art), p = ver.articles[i - 1], s = ver.articles[i + 1]; return `${p ? `<button data-art="${e(p.num)}">Art. ${e(p.num)}</button>` : "<span></span>"}${s ? `<button data-art="${e(s.num)}">Art. ${e(s.num)}</button>` : ""}`; })()}</div>`;

      const aperto = !!(cur || st.comma || st.pan);
      $("#em-pan").hidden = false; $("#em-pan").classList.toggle("em-pan--riepilogo", !aperto); $(".em-griglia").classList.toggle("con-pan", aperto);
      $("#em-pan").innerHTML = aperto ? `<button class="em-chiudi" data-chiudi-pan aria-label="Chiudi il pannello">×</button>${cur ? dettaglio(cur) : elencoEm()}` : riepilogo();

      // senza scelta: quanti emendamenti, su quali commi, presentati da chi; ogni riga apre l'elenco
      function riepilogo() {
        const xs = ems.filter((a) => !a.parent && a.article === art.num);
        if (!xs.length) return `<header class="em-pan__testa"><h3>Art. ${e(art.num)}</h3><span class="em-sotto">Nessun emendamento su questo articolo in questa fase.</span></header>`;
        const commi = art.commi.map((c) => [c.num, cont.get(`${art.num}|${c.num}`) || 0]).filter(([, n]) => n).sort((a, b) => b[1] - a[1]).slice(0, 6);
        const gr = {}; xs.forEach((a) => { const g = (a.signers.find((x) => x.first) || a.signers[0] || {}).group || "nd"; gr[g] = (gr[g] || 0) + 1; });
        const gruppi = Object.entries(gr).sort((a, b) => b[1] - a[1]).slice(0, 5), mx = Math.max(1, ...commi.map((c) => c[1]));
        return `<header class="em-pan__testa"><h3>Art. ${e(art.num)}</h3><span class="em-sotto">${nEm(xs.length)} · ${e(fase.chamber)}, ${e(fase.label.toLowerCase())}</span></header>
          ${commi.length ? `<section><h4>Commi più emendati</h4><ul class="em-rie">${commi.map(([c, n]) => `<li><button data-comma="${e(c)}"><span>Comma ${e(c)}</span><span class="em-barretta"><i style="width:${(n / mx) * 100}%"></i></span><span class="em-cifra">${B.num(n)}</span></button></li>`).join("")}</ul></section>` : ""}
          <section><h4>Chi li ha presentati</h4><ul class="em-rie">${gruppi.map(([g, n]) => `<li><button data-gruppo="${e(g === "nd" ? "" : g)}" data-apri-lista><span>${g === "nd" ? "Non indicato" : chip(g)}</span><span class="em-barretta"><i style="width:${(n / xs.length) * 100}%;background:${g === "nd" ? "var(--t3)" : B.col(B.sigla(g))}"></i></span><span class="em-cifra">${B.num(n)}</span></button></li>`).join("")}</ul></section>
          <button class="em-tutto em-tutto--pieno">Vedi tutti gli emendamenti</button>`;
      }
      if (eff) { const el = $(`#em-c-${CSS.escape(eff.comma)}`); if (el) el.scrollIntoView({ block: "nearest" }); }

      function elencoEm() {
        let xs = ems.filter((a) => !a.parent && (a.article === art.num || (!a.article && fase.stage !== APPROVATI && false)) && (!st.comma || a.comma === st.comma) && (!st.lettera || a.letter === st.lettera));
        const tutti = xs;
        if (st.esito) xs = xs.filter((a) => (st.esito === "nd" ? !a.outcome : a.outcome === st.esito));
        if (st.gruppo) xs = xs.filter((a) => a.signers.some((s) => s.group === st.gruppo));
        const gr = {}; tutti.forEach((a) => { const f = (a.signers.find((s) => s.first) || a.signers[0] || {}).group || "nd"; gr[f] = gr[f] || { p: 0, a: 0 }; gr[f].p++; if (a.outcome === "approvato") gr[f].a++; });
        const gruppi = Object.entries(gr).sort((a, b) => b[1].p - a[1].p), max = Math.max(1, ...gruppi.map((g) => g[1].p));
        const esiti = {}; tutti.forEach((a) => { const k = a.outcome || "nd"; esiti[k] = (esiti[k] || 0) + 1; });
        senzaEsito = Object.keys(esiti).length === 1 && esiti.nd > 0;
        const dove2 = `Art. ${art.num}${st.comma ? `, comma ${st.comma}` : ""}${st.lettera ? `, lettera ${st.lettera})` : ""}`;
        return `<header class="em-pan__testa"><h3>${e(dove2)}</h3><span class="em-sotto">${tutti.length ? `${nEm(tutti.length)} · ` : ""}${e(fase.chamber)}, ${e(fase.label.toLowerCase())}</span></header>
          ${tutti.length ? `<section class="em-gr"><h4>Chi li ha presentati <small class="em-sotto">gruppo di chi firma per primo</small></h4><table><thead><tr><th>Gruppo</th><th></th><th class="dx">Presentati</th><th class="dx">Approvati</th></tr></thead><tbody>${gruppi.map(([g, v]) => `<tr><td>${g === "nd" ? "Non indicato" : chip(g)}${maggioranza.has(g) ? `<small title="Gruppo di maggioranza"> magg.</small>` : ""}</td><td><span class="em-barretta"><i style="width:${(v.p / max) * 100}%;background:${g === "nd" ? "var(--t3)" : B.col(B.sigla(g))}"></i></span></td><td class="dx em-cifra">${B.num(v.p)}</td><td class="dx em-cifra">${B.num(v.a)}</td></tr>`).join("")}</tbody></table></section>
          ${senzaEsito ? `<p class="em-sotto em-nd">${/^S/.test(fase.chamber) ? "Il Senato" : "La Camera"} non ha ancora pubblicato l'esito di questi emendamenti.</p>` : `<div class="em-chip-f" role="group" aria-label="Filtra per esito"><button data-esito="" aria-pressed="${!st.esito}">Tutti</button>${Object.entries(esiti).sort((a, b) => b[1] - a[1]).map(([k, n]) => `<button data-esito="${e(k)}" aria-pressed="${st.esito === k}">${k === "nd" ? "Esito non pubblicato" : e(ESITI[k] || k)} <span class="em-cifra">${n}</span></button>`).join("")}</div>`}
          ${st.gruppo ? `<p class="em-sotto">Firmati anche da ${chip(st.gruppo)} <button class="em-link" data-gruppo="">togli il filtro</button></p>` : ""}
          <ul class="em-lista">${xs.slice(0, 200).map((a) => voce(a)).join("")}</ul>${xs.length > 200 ? `<p class="em-sotto">Primi 200 di ${B.num(xs.length)}. Scegli un comma per restringere.</p>` : ""}`
          : `<p class="em-vuoto">${fase.stage === APPROVATI ? "Nessun emendamento approvato su questo articolo." : "Nessun emendamento su questo punto in questa fase."}</p>`}`;
      }
      function voce(a) {
        const f = a.signers.find((s) => s.first) || a.signers[0];
        return `<li><button data-em="${e(a.id)}"><span class="em-voce__r1"><span class="em-num">${e(a.number)}</span>${senzaEsito ? "" : `<span class="em-esito em-esito--${classeEsito(a)}">${e(esito(a))}</span>`}</span>
          <span class="em-voce__r2">${f ? `${chip(f.group)} ${e(B.nome(f.name))}${a.signers.length > 1 ? ` <span class="em-sotto">e altri ${a.signers.length - 1}</span>` : ""}` : `<span class="em-sotto">Firmatari non nei dati</span>`}</span>
          <span class="em-voce__t">${e(B.taglia((a.text || "").replace(/\s+/g, " "), 150))}</span>${figli.get(a.id) ? `<span class="em-sotto">${figli.get(a.id).length} subemendamenti</span>` : ""}</button></li>`;
      }
      function dettaglio(a) {
        const mod = L.changes.filter((c) => (c.amendments || []).includes(a.id));
        const sub = (figli.get(a.id) || []).sort((x, y) => confronta(x.number, y.number));
        const ident = (a.identical || []).map((id) => perId.get(id)).filter(Boolean);
        const padre = a.parent && perId.get(a.parent), ripreso = a.resubmission_of && perId.get(a.resubmission_of);
        const v = a.vote;
        const votoUrl = v && /^camera_leg19_sed\d+_v\d+$/.test(v.id || "") ? `#/strumenti/voto/${v.id}` : null;
        return `<button class="em-indietro" data-em="">Torna agli emendamenti di Art. ${e(art.num)}</button>
          <header class="em-pan__testa"><h3><span class="em-num">${e(a.number)}</span> ${e(TIPI[a.kind] || a.kind || "Emendamento")}</h3><span class="em-sotto">${e(nomeFase.get(a.stage) || a.stage)}${a.date ? ` · ${data(a.date)}` : ""}</span></header>
          <div class="em-esito-box em-esito-box--${classeEsito(a)}"><b>${e(esito(a))}</b><span>${e(spiega(a))}</span></div>
          <section><h4>Cosa modifica</h4><p><b>${e(dove(a))}</b> <button class="em-link" data-punto="${e(a.article || "")}|${e(a.comma || "")}|${e(a.letter || "")}">vedi nel testo</button></p><p class="em-sotto">${eff && cur === a ? "Nel testo a sinistra: le parole tolte barrate, quelle nuove evidenziate." : "Per questa formula non c'è l'anteprima sul testo."}</p>
          ${mod.length ? `<div class="em-mod"><p class="em-sotto">Nel testo successivo ha portato ${mod.length === 1 ? "questa modifica" : `${mod.length} modifiche`}:</p>${mod.map((c) => `<p><b>Art. ${e(c.article)}, comma ${e(c.comma)}</b>${c.kind === "nuovo" ? " (comma nuovo)" : ""}<br>${segmenti(c.diff)}</p>`).join("")}</div>` : ""}</section>
          <section><h4>Firmatari <span class="em-cifra">${a.signers.length}</span></h4>${(() => { const pf = a.signers.find((x) => x.first) || a.signers[0], altri = a.signers.filter((x) => x !== pf);
            const riga = (x) => `<li>${chip(x.group)} <span>${e(B.nome(x.name))}</span>${x.first ? `<small>prima firma</small>` : ""}${x.group ? `<button class="em-link" data-gruppo="${e(x.group)}" title="Emendamenti firmati da ${e(x.group)}">filtra</button>` : ""}</li>`;
            return pf ? `<ul class="em-firme">${riga(pf)}</ul>${altri.length ? `<details><summary>e altri ${altri.length}</summary><ul class="em-firme">${altri.map(riga).join("")}</ul></details>` : ""}` : `<p class="em-sotto">Firmatari non nei dati.</p>`; })()}</section>
          ${v ? `<section><h4>Votazione${v.date ? ` del ${data(v.date)}` : ""}</h4><div class="em-voto"><span class="em-cifra"><b>${B.num(v.in_favor)}</b> sì</span><span class="em-cifra"><b>${B.num(v.against)}</b> no</span><span class="em-cifra"><b>${B.num(v.abstained)}</b> astenuti</span></div>${B.barra(v.in_favor, v.against, v.abstained)}
            ${v.secret ? `<p class="em-sotto">Voto segreto: i voti dei singoli e dei gruppi non sono pubblici.</p>` : ""}
            ${v.by_group && v.by_group.length ? `<table class="em-vg"><thead><tr><th>Gruppo</th><th class="dx">Sì</th><th class="dx">No</th><th class="dx">Ast.</th></tr></thead><tbody>${v.by_group.map((g) => `<tr><td>${chip(g.group)}</td><td class="dx em-cifra">${g.favor}</td><td class="dx em-cifra">${g.against}</td><td class="dx em-cifra">${g.abstain}</td></tr>`).join("")}</tbody></table>` : ""}
            <p class="em-azioni">${votoUrl ? `${B.link(votoUrl, "Apri la votazione con l'Aula")}` : ""}${v.url ? `${B.link(v.url, "Apri il resoconto")}` : ""}</p></section>` : ""}
          <section><details class="em-det-testo"${eff && cur === a ? "" : " open"}><summary><h4>Testo dell'emendamento</h4></summary><div class="em-testo-em">${e(a.text || "Testo non nei dati.")}${a.cut ? "…" : ""}</div>${a.cut ? `<p class="em-sotto" role="status">${TT("Carico il testo intero…", "Loading the full text…")}</p>` : ""}${a.text_presented && a.text_presented !== a.text ? `<details><summary>Testo come presentato</summary><div class="em-testo-em">${e(a.text_presented)}</div></details>` : ""}</details></section>
          ${padre || ripreso || sub.length || ident.length ? `<section><h4>Collegati</h4><ul class="em-coll">
            ${padre ? `<li>Subemendamento di <button class="em-link" data-em="${e(padre.id)}">${e(padre.number)}</button></li>` : ""}
            ${ripreso ? `<li>Ripresenta in Aula <button class="em-link" data-em="${e(ripreso.id)}">${e(ripreso.number)}</button>, ${e((nomeFase.get(ripreso.stage) || "").toLowerCase())}</li>` : ""}
            ${ident.length ? `<li>Testo identico a ${ident.map((x) => `<button class="em-link" data-em="${e(x.id)}">${e(x.number)}</button> ${chip((x.signers.find((s) => s.first) || x.signers[0] || {}).group)}`).join(", ")}</li>` : ""}
            ${sub.length ? `<li>${sub.length} subemendamenti: ${sub.slice(0, 30).map((x) => `<button class="em-link" data-em="${e(x.id)}">${e(x.number)}</button>`).join(", ")}${sub.length > 30 ? "…" : ""}</li>` : ""}</ul></section>` : ""}
          ${a.source ? `<p class="em-azioni">${B.link(a.source, "Apri la fonte ufficiale")}</p>` : ""}`;
      }
    };

    const corpo = $("#em-corpo");
    corpo.addEventListener("click", (ev) => {
      const b = ev.target.closest("button"); if (!b || !corpo.contains(b)) return;
      if (b.dataset.chiudiPan !== undefined) st = { ...st, comma: null, lettera: null, em: null, pan: null, esito: null, gruppo: null };
      else if (b.classList.contains("em-tutto")) st = { ...st, comma: null, lettera: null, em: null, pan: st.pan && !st.comma ? null : "art" };
      else if (b.dataset.fase !== undefined) st = { ...st, fase: b.dataset.fase, comma: null, lettera: null, em: null, esito: null, gruppo: null };
      else if (b.dataset.art !== undefined) { st = { ...st, art: b.dataset.art, comma: null, lettera: null, em: null, pan: null }; $("#em-testo").scrollTop = 0; }
      else if (b.dataset.punto !== undefined) { const [ar, co, le] = b.dataset.punto.split("|"); st = { ...st, art: ar || st.art, comma: co || null, lettera: le || null }; disegna(); const el = co && $(`#em-c-${CSS.escape(co)}`); if (el) el.scrollIntoView({ behavior: "smooth", block: "center" }); return; }
      else if (b.dataset.em !== undefined) {
        const a = b.dataset.em ? perId.get(b.dataset.em) : null;
        if (a) { const f = P.find((x) => x.stage === a.stage); st = { ...st, em: a.id, fase: (f && f.id) || st.fase, art: a.article || st.art, comma: a.comma, lettera: a.letter }; }
        else st = { ...st, em: null, pan: st.comma ? st.pan : "art" };
        disegna(); $("#em-pan").scrollTop = 0; if (innerWidth < 900) $("#em-pan").scrollIntoView({ behavior: "smooth", block: "start" }); return;
      }
      else if (b.dataset.comma !== undefined) st = { ...st, comma: b.dataset.comma || null, lettera: b.dataset.lettera || null, em: null };
      else if (b.dataset.esito !== undefined) st = { ...st, esito: b.dataset.esito || null };
      else if (b.dataset.gruppo !== undefined) st = { ...st, gruppo: b.dataset.gruppo || null, em: null, pan: b.dataset.apriLista !== undefined ? "art" : st.pan };
      else return;
      disegna();
    });
    corpo.addEventListener("change", (ev) => { if (ev.target.id === "em-art-sel") { st = { ...st, art: ev.target.value, comma: null, lettera: null, em: null, pan: null }; disegna(); } });
    disegna();
  }

  function votoFinale(x) {
    const r = x.result, ok = /^approv/i.test(r.outcome || x.label || "");
    return `<div class="em-finale"><span class="em-sotto">${e(x.label)}, ${data(x.date)}</span><b class="em-cifra">${B.num(r.in_favor)} sì · ${B.num(r.against)} no</b><span class="em-esito em-esito--${ok ? "ok" : "no"}">${ok ? "Approvata" : "Respinta"}</span></div>`;
  }

  /* ---------- ingresso ---------- */
  function apri(box, arg, testa) {
    const slug = arg ? String(arg) : "";
    if (!slug) { box.innerHTML = testa("emendamenti", null, "Ogni legge con il suo iter, il testo comma per comma e gli emendamenti che lo toccano."); elenco(box); return; }
    const voce = slug === ELETTORALE ? { title: "Legge elettorale" } : (indice || []).find((x) => x.slug === slug);
    box.innerHTML = testa("emendamenti", voce ? B.taglia(voce.title, 110) : "Emendamenti", null);
    lettore(box, slug).then(() => { const h = box.querySelector("h1"); const L = cache.get(urlLegge(slug)); if (h && L && !voce) L.then((x) => { h.textContent = B.taglia(x.bill.short || x.bill.title, 110); }); });
  }

  window.EM = { apri };
})();

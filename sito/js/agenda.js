/* Agenda del Parlamento: sedute d'Aula, commissioni, termini per gli emendamenti, progetti di legge, voti finali e leggi,
   in un calendario per mese o per settimana. In ogni giorno solo titoli brevi; il clic apre il dettaglio in una finestra.
   Interroga lo strumento pubblico get_parliament_agenda (api/strumenti/agenda.py). */
(function () {
  const e = B.esc, $ = B.$;
  const TIPI = [
    ["termini", TT("Termini emendamenti", "Amendment deadlines")],
    ["aula", TT("Aula", "Floor")],
    ["voti", TT("Voti finali", "Final votes")],
    ["leggi", TT("Leggi", "Laws")],
    ["atti", TT("Progetti di legge", "Bills filed")],
    ["commissioni", TT("Commissioni", "Committees")],
  ];
  const GIORNI = TT("lun mar mer gio ven sab dom", "Mon Tue Wed Thu Fri Sat Sun").split(" ");
  const MESI = TT("gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre",
    "January February March April May June July August September October November December").split(" ");
  const MASSIMO = 4;                       // titoli visibili in una casella del mese; gli altri dietro «+N»
  const cache = new Map();
  const st = { vista: "mese", inizio: null, ramo: "both", attivi: new Set(TIPI.map((t) => t[0])), dati: null };

  // date locali, mai in UTC: «2026-11-09» è il 9 novembre ovunque sia chi guarda
  const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  const daIso = (s) => { const [a, m, g] = s.split("-").map(Number); return new Date(a, m - 1, g); };
  const piu = (d, n) => new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);
  const lunedi = (d) => piu(d, -((d.getDay() + 6) % 7));
  const oggi = () => iso(new Date());
  const giornoLungo = (s) => { const d = daIso(s); return `${GIORNI[(d.getDay() + 6) % 7]} ${d.getDate()} ${MESI[d.getMonth()]} ${d.getFullYear()}`; };
  const ramo = (r) => (r === "senato" ? TT("Senato", "Senate") : TT("Camera", "Chamber"));
  // in Aula i primi punti sono spesso di servizio: si mostra il primo di merito
  const SERVIZIO = /^(missioni|comunicazioni|preavviso|annunzi|ordine del giorno della prossima|trasmissione|modifica nella composizione|sull'ordine dei lavori|in morte|commemorazione|sui lavori|calendario dei lavori|dimissioni|congedi)/i;
  const merito = (xs) => (xs || []).filter((t) => !SERVIZIO.test(t));
  // i titoli della fonte portano tag HTML («<em>(approvato dal Senato)</em>»), virgolette e il numero ripetuto in coda
  const pulito = (t) => String(t || "").replace(/<[^>]+>/g, "").replace(/^S\.\s*\d+\.?\s*-\s*/, "").replace(/\s*\(\d+[\w-]*\)\s*$/, "")
    .replace(/["“”]/g, "").replace(/\s+/g, " ").trim();
  // la scheda del sito per l'atto del termine: dall'uri (it:camera:19:ac:3120) o dal riferimento della fonte (ddl:2074)
  function scheda(t) {
    const r = (t.act || "").match(/:(ac|ddl):([\w-]+)$/) || (t.act_refs || []).map((x) => x.match(/^(ac|ddl):([\w-]+)$/)).find(Boolean);
    if (!r) return null;
    const titolo = [atto(t), pulito(t.act_title)].filter(Boolean).join(" · ");
    return `#/strumenti/atto/${r[1] === "ac" ? "camera" : "senato"}-${r[2]}?t=${encodeURIComponent(titolo)}${t.act_url ? `&u=${encodeURIComponent(t.act_url)}` : ""}`;
  }

  function intervallo() {
    if (st.vista === "settimana") return [st.inizio, piu(st.inizio, 6)];
    const primo = new Date(st.inizio.getFullYear(), st.inizio.getMonth(), 1), ultimo = new Date(st.inizio.getFullYear(), st.inizio.getMonth() + 1, 0);
    return [lunedi(primo), piu(lunedi(ultimo), 6)];
  }

  async function leggi(da, a) {
    const k = `${iso(da)}|${iso(a)}|${st.ramo}`;
    if (!cache.has(k)) cache.set(k, B.mcp("get_parliament_agenda", { start_date: iso(da), end_date: iso(a), chamber: st.ramo }).then((r) => {
      if (r.errore) throw new Error((r.testi || [])[0] || "errore");
      return r.dati;
    }).catch((err) => { cache.delete(k); throw err; }));
    return cache.get(k);
  }

  /* ---------- gli eventi di un giorno, con il titolo breve ---------- */
  const atto = (t) => t.act_number ? `${t.chamber === "senato" ? "S." : "C."} ${t.act_number}` : (t.act_refs || []).map((r) => r.replace(/^ac:/, "C. ").replace(/^ddl:/, "S. ")).slice(0, 2).join(", ");
  const TIPO_T = { "emendamenti": TT("emendamenti", "amendments"), "subemendamenti": TT("subemendamenti", "sub-amendments"),
    "emendamenti e ordini del giorno": TT("emendamenti e ordini del giorno", "amendments and agenda motions"),
    "riesame delle inammissibilità": TT("richieste di riesame", "requests for review"), "segnalazione degli emendamenti": TT("emendamenti segnalati", "flagged amendments") };

  function eventi(g) {
    const on = (k) => st.attivi.has(k) && (g[k] || []).length;
    const xs = [];
    if (on("termini")) g.termini.forEach((t) => xs.push({ tipo: "termini", ora: t.due_time, x: t, off: t.superseded,
      titolo: `${TT("Termine", "Deadline")} ${atto(t) || TIPO_T[t.kind] || ""}` }));
    if (on("aula")) g.aula.forEach((s) => xs.push({ tipo: "aula", ora: s.start_time, x: s,
      titolo: `${TT("Aula", "Floor")} ${ramo(s.chamber)}${s.status === "planned" ? ` · ${TT("prevista", "planned")}` : ""}` }));
    if (on("voti")) g.voti.forEach((v) => xs.push({ tipo: "voti", x: v, esito: v.approved ? "ok" : "no", titolo: `${TT("Voto finale", "Final vote")}: ${pulito(v.act_title || v.title)}` }));
    if (on("leggi")) g.leggi.forEach((l) => xs.push({ tipo: "leggi", x: l, titolo: `${TT("Legge", "Law")} ${l.law_number ? `n. ${l.law_number}` : ""} · ${pulito(l.title)}` }));
    if (on("atti")) xs.push({ tipo: "atti", x: g.atti, titolo: `${g.atti.length} ${g.atti.length === 1 ? TT("progetto di legge", "bill") : TT("progetti di legge", "bills")}` });
    if (on("commissioni")) xs.push({ tipo: "commissioni", x: g.commissioni, titolo: `${g.commissioni.length} ${g.commissioni.length === 1 ? TT("commissione", "committee") : TT("commissioni", "committees")}` });
    const peso = { termini: 0, aula: 1, voti: 2, leggi: 3, atti: 4, commissioni: 5 };
    return xs.sort((a, b) => peso[a.tipo] - peso[b.tipo] || String(a.ora || "99").localeCompare(String(b.ora || "99")));
  }

  /* ---------- il dettaglio di un evento ---------- */
  function dettaglio(ev) {
    const x = ev.x;
    if (ev.tipo === "termini") {
      const passato = x.due_date < oggi() || x.event === "expired";
      return `<p class="ag-d__tipo ag-t--termini">${TT("Termine per", "Deadline for")} ${e(TIPO_T[x.kind] || x.kind)}</p>
        <h3>${e([atto(x), x.act_title && pulito(x.act_title)].filter(Boolean).join(" · ") || TT("Atto non indicato", "Act not stated"))}</h3>
        <dl class="ag-d__dati"><dt>${TT("Scade", "Due")}</dt><dd>${e(giornoLungo(x.due_date))}${x.due_time ? `, ${TT("ore", "at")} ${e(x.due_time)}` : ""}${x.superseded ? ` <span class="ag-pill ag-pill--off">${TT("spostato più tardi", "moved later")}</span>` : passato ? ` <span class="ag-pill ag-pill--off">${TT("scaduto", "expired")}</span>` : ""}</dd>
        <dt>${TT("Dove", "Where")}</dt><dd>${ramo(x.chamber)} · ${e((x.bodies || [x.body_name]).filter(Boolean).join(", "))}</dd>
        ${x.presented ? `<dt>${TT("Proposte", "Proposals")}</dt><dd>${x.presented} ${TT("presentate", "filed")}</dd>` : ""}</dl>
        <blockquote class="ag-d__fonte">«${e(x.sentence)}»</blockquote>
        <p class="ag-nota">${TT("Sommario della seduta del", "Summary record of the sitting of")} ${B.data(x.sitting_date)}${x.mentions > 1 ? `, ${TT("ricordato in", "mentioned in")} ${x.mentions} ${TT("sedute", "sittings")}` : ""}.</p>
        ${scheda(x) || x.act_url ? `<div class="ag-d__azioni">${scheda(x) ? `<a class="bt bt--primario ag-d__vai" href="${e(scheda(x))}">${TT("Apri il provvedimento", "Open the bill")}</a>` : ""}${x.act_url ? `<a class="bt bt--linea ag-d__vai" href="${e(x.act_url)}" target="_blank" rel="noopener">${B.ico("esterno")}${x.chamber === "senato" ? TT("Scheda sul sito del Senato", "Page on the Senate website") : TT("Scheda sul sito della Camera", "Page on the Chamber website")}</a>` : ""}</div>` : ""}`;
    }
    if (ev.tipo === "aula") {
      const temi = merito(x.items);
      return `<p class="ag-d__tipo ag-t--aula">${TT("Aula", "Floor")} ${ramo(x.chamber)} · ${TT("seduta", "sitting")} ${x.number}${x.status === "planned" ? ` <span class="ag-pill">${TT("prevista", "planned")}</span>` : ""}</p>
        <h3>${x.start_time ? `${TT("Ore", "At")} ${e(x.start_time)}` : e(giornoLungo(x.date))}${x.votes ? ` · ${x.votes} ${TT("votazioni", "votes")}` : ""}</h3>
        ${temi.length ? `<ul class="ag-d__lista">${temi.map((t) => `<li>${e(B.taglia(t, 220))}</li>`).join("")}</ul>` : `<p class="ag-nota">${TT("Comunicazioni e adempimenti", "Announcements and formalities")}</p>`}
        ${x.items_total > temi.length && x.items_total > (x.items || []).length ? `<p class="ag-nota">${TT("e altri argomenti", "and more items")}</p>` : ""}
        ${x.session_id && x.status !== "planned" ? `<a class="bt bt--linea ag-d__vai" href="#/strumenti/seduta/${e(x.session_id)}">${TT("Apri la seduta", "Open the sitting")}</a>` : ""}`;
    }
    if (ev.tipo === "voti") return `<p class="ag-d__tipo ag-t--voti">${TT("Voto finale", "Final vote")} · ${ramo(x.chamber)} <span class="ag-pill ag-pill--${x.approved ? "ok" : "no"}">${x.approved ? TT("approvato", "passed") : TT("respinto", "rejected")}</span></p>
        <h3>${e(pulito(x.act_title || x.title))}</h3>
        <dl class="ag-d__dati"><dt>${TT("Sì", "Yes")}</dt><dd>${x.favor ?? "–"}</dd><dt>No</dt><dd>${x.against ?? "–"}</dd>${x.abstain ? `<dt>${TT("Astenuti", "Abstained")}</dt><dd>${x.abstain}</dd>` : ""}${x.confidence ? `<dt>${TT("Fiducia", "Confidence")}</dt><dd>${TT("sì", "yes")}</dd>` : ""}</dl>
        ${x.vote_id ? `<a class="bt bt--linea ag-d__vai" href="#/strumenti/voto/${e(x.vote_id)}">${TT("Apri la votazione", "Open the vote")}</a>` : ""}`;
    if (ev.tipo === "leggi") return `<p class="ag-d__tipo ag-t--leggi">${TT("Legge", "Law")}${x.law_number ? ` n. ${e(x.law_number)}` : ""}</p><h3>${e(pulito(x.title))}</h3>`;
    if (ev.tipo === "atti") return `<p class="ag-d__tipo ag-t--atti">${x.length} ${TT("progetti di legge presentati", "bills filed")}</p>
        <ul class="ag-d__lista">${x.map((a) => `<li><b>${ramo(a.chamber).charAt(0)}. ${e(a.number)}</b> ${a.card_url ? `<a href="${e(a.card_url)}" target="_blank" rel="noopener">${e(B.taglia(a.title || "", 160))}</a>` : e(B.taglia(a.title || "", 160))}${a.initiative ? ` <small>${e(a.initiative)}</small>` : ""}</li>`).join("")}</ul>`;
    return `<p class="ag-d__tipo ag-t--commissioni">${x.length} ${TT("organi riuniti", "committees met")}</p>
        <ul class="ag-d__lista">${x.map((c) => `<li><b>${ramo(c.chamber)}</b> · ${e(c.body_name || "")}${c.sittings > 1 ? ` <small>× ${c.sittings}</small>` : ""}${(c.items || []).length ? `<br><small>${e(c.items.slice(0, 3).map((t) => B.taglia(t, 90)).join(" · "))}</small>` : ""}</li>`).join("")}</ul>`;
  }

  /* ---------- la griglia ---------- */
  let indice = [];                          // gli eventi disegnati, per il clic
  const chip = (ev) => { indice.push(ev); return `<button type="button" class="ag-ev ag-t--${ev.tipo}${ev.off ? " ag-ev--off" : ""}${ev.esito ? ` ag-ev--${ev.esito}` : ""}" data-ev="${indice.length - 1}" title="${e(ev.titolo)}"><i aria-hidden="true"></i>${ev.ora ? `<time>${e(ev.ora)}</time>` : ""}<span>${e(ev.titolo)}</span></button>`; };

  function griglia(dati) {
    const [da, a] = intervallo(), m = st.inizio.getMonth(), sett = st.vista === "settimana";
    indice = [];
    let celle = GIORNI.map((g) => `<div class="ag-cal__testa" aria-hidden="true">${g}</div>`).join("");
    for (let d = da; d <= a; d = piu(d, 1)) {
      const k = iso(d), evs = eventi((dati.days || {})[k] || {}), fuori = !sett && d.getMonth() !== m;
      const visti = sett ? evs : evs.slice(0, evs.length > MASSIMO ? MASSIMO - 1 : MASSIMO), altri = evs.length - visti.length;
      celle += `<div class="ag-cella${fuori ? " ag-cella--fuori" : ""}${k === oggi() ? " ag-cella--oggi" : ""}${(d.getDay() + 6) % 7 > 4 ? " ag-cella--festa" : ""}">
        <button type="button" class="ag-cella__n" data-giorno="${k}" aria-label="${e(giornoLungo(k))}: ${evs.length} ${TT("eventi", "events")}">${d.getDate()}${d.getDate() === 1 && !sett ? `<span class="ag-mese1"> ${MESI[d.getMonth()].slice(0, 3)}</span>` : ""}</button>
        <div class="ag-cella__ev">${visti.map(chip).join("")}${altri > 0 ? `<button type="button" class="ag-altri" data-giorno="${k}">+${altri} ${TT("altri", "more")}</button>` : ""}</div>
        <div class="ag-cella__punti" aria-hidden="true">${[...new Set(evs.map((x) => x.tipo))].map((t) => `<i class="ag-t--${t}"></i>`).join("")}</div></div>`;
    }
    return `<div class="ag-cal ag-cal--${st.vista}">${celle}</div>`;
  }

  /* ---------- la finestra del dettaglio ---------- */
  function apri(html, titolo) {
    let d = $("#ag-dlg");
    if (!d) {
      document.body.insertAdjacentHTML("beforeend", `<dialog id="ag-dlg" class="ag-dlg" aria-labelledby="ag-dlg-t"><div class="ag-dlg__testa"><p id="ag-dlg-t"></p><button type="button" class="ic-a" data-chiudi aria-label="${TT("Chiudi", "Close")}" data-tip="${TT("Chiudi", "Close")}"><svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18"/></svg></button></div><div class="ag-dlg__corpo"></div></dialog>`);
      d = $("#ag-dlg");
      d.addEventListener("click", (ev) => {
        if (ev.target === d || ev.target.closest("[data-chiudi]")) { d.close(); return; }
        const x = ev.target.closest("[data-ev]"); if (x) { const k = +x.dataset.ev; apri(dettaglio(indice[k]), giornoLungo(x.dataset.giorno || "")); }
        if (ev.target.closest("a[href^='#']")) d.close();
      });
    }
    d.querySelector("#ag-dlg-t").textContent = titolo;
    d.querySelector(".ag-dlg__corpo").innerHTML = html;
    if (!d.open) d.showModal();
  }
  // il giorno intero: tutti gli eventi, ciascuno apribile
  function giorno(k) {
    const evs = eventi((st.dati.days || {})[k] || {});
    const html = evs.length ? `<ul class="ag-giorno">${evs.map((ev) => { indice.push(ev); return `<li><button type="button" class="ag-ev ag-ev--lungo ag-t--${ev.tipo}${ev.off ? " ag-ev--off" : ""}" data-ev="${indice.length - 1}" data-giorno="${k}"><i aria-hidden="true"></i>${ev.ora ? `<time>${e(ev.ora)}</time>` : ""}<span>${e(ev.titolo)}</span>${B.ico("dx")}</button></li>`; }).join("")}</ul>`
      : `<p class="ag-nota">${TT("Niente in calendario", "Nothing scheduled")}</p>`;
    apri(html, giornoLungo(k));
  }

  function titoloPeriodo() {
    const [da, a] = intervallo();
    if (st.vista === "mese") return `${MESI[st.inizio.getMonth()]} ${st.inizio.getFullYear()}`;
    return da.getMonth() === a.getMonth() ? `${da.getDate()}–${a.getDate()} ${MESI[a.getMonth()]} ${a.getFullYear()}` : `${da.getDate()} ${MESI[da.getMonth()].slice(0, 3)} – ${a.getDate()} ${MESI[a.getMonth()].slice(0, 3)} ${a.getFullYear()}`;
  }

  async function disegna() {
    const box = $("#ag-corpo"); if (!box) return;
    $("#ag-periodo").textContent = titoloPeriodo();
    box.setAttribute("aria-busy", "true");
    const [da, a] = intervallo();
    try {
      st.dati = await leggi(da, a);
      box.innerHTML = griglia(st.dati);
      const c = st.dati.counts || {};
      $("#ag-conto").textContent = TIPI.filter(([t]) => st.attivi.has(t) && c[t]).map(([t, n]) => `${c[t]} ${n.toLowerCase()}`).join(" · ") || TT("Niente in questo periodo con i filtri scelti.", "Nothing in this period with the chosen filters.");
    } catch (err) { box.innerHTML = ST.errore(err); }
    box.removeAttribute("aria-busy");
  }

  window.AGENDA = (box, arg) => {
    const base = /^\d{4}-\d{2}-\d{2}$/.test(arg || "") ? daIso(arg) : new Date();
    st.inizio = st.vista === "settimana" ? lunedi(base) : new Date(base.getFullYear(), base.getMonth(), 1);
    box.innerHTML = ST.testa("agenda", null, null, TT("Cosa scade questa settimana in Parlamento?", "What is due in Parliament this week?"))
      + ST.avvio(TT("Il calendario del Parlamento: sedute d'Aula, commissioni, termini per presentare gli emendamenti, progetti di legge, voti finali e leggi. Clicca un evento per il dettaglio.", "Parliament's calendar: floor sittings, committees, deadlines for amendments, bills, final votes and laws. Click an event for the details."), [], "")
      + `<div class="ag-barra">
          <div class="ag-nav"><button type="button" class="bt bt--linea ag-oggi" data-ag="0">${TT("Oggi", "Today")}</button><button type="button" class="ic-a" data-ag="-1" aria-label="${TT("Periodo precedente", "Previous period")}" data-tip="${TT("Precedente", "Previous")}">${B.ico("sx")}</button><button type="button" class="ic-a" data-ag="1" aria-label="${TT("Periodo successivo", "Next period")}" data-tip="${TT("Successivo", "Next")}">${B.ico("dx")}</button><h2 id="ag-periodo" aria-live="polite"></h2></div>
          <div class="ag-scelte"><label class="vh" for="ag-ramo">${TT("Ramo", "Chamber")}</label><select id="ag-ramo"><option value="both">${TT("Camera e Senato", "Chamber and Senate")}</option><option value="camera">Camera</option><option value="senato">Senato</option></select>
          <div class="ag-vista" role="group" aria-label="${TT("Vista", "View")}"><button type="button" data-vista="mese" aria-pressed="${st.vista === "mese"}">${TT("Mese", "Month")}</button><button type="button" data-vista="settimana" aria-pressed="${st.vista === "settimana"}">${TT("Settimana", "Week")}</button></div></div>
        </div>
        <div class="ag-tipi" role="group" aria-label="${TT("Cosa mostrare", "What to show")}">${TIPI.map(([k, n]) => `<button type="button" class="ag-tipo ag-t--${k}" data-tipo="${k}" aria-pressed="${st.attivi.has(k)}"><i></i>${e(n)}</button>`).join("")}<span class="ag-conto" id="ag-conto"></span></div>
        <div id="ag-corpo">${ST.carica(TT("Leggo l'agenda", "Loading the agenda"))}</div>
        <p class="ag-piede">${TT("Le sedute d'Aula previste vengono dall'ordine del giorno della Camera. I termini per gli emendamenti vengono dai sommari delle commissioni: si vedono dal giorno dopo la seduta in cui sono fissati, e mancano quelli decisi senza che il sommario li riporti.", "Planned floor sittings come from the Chamber's order of business. Amendment deadlines come from committee summary records: they appear the day after the sitting that sets them, and those the record does not report are missing.")}</p>`;
    $("#ag-ramo").value = st.ramo;
    box.querySelector(".ag-barra").addEventListener("click", (ev) => {
      const n = ev.target.closest("[data-ag]"), v = ev.target.closest("[data-vista]");
      if (n) {
        const k = +n.dataset.ag;
        if (k === 0) st.inizio = st.vista === "settimana" ? lunedi(new Date()) : new Date(new Date().getFullYear(), new Date().getMonth(), 1);
        else if (st.vista === "settimana") st.inizio = piu(st.inizio, 7 * k);
        else st.inizio = new Date(st.inizio.getFullYear(), st.inizio.getMonth() + k, 1);
      }
      if (v && v.dataset.vista !== st.vista) {
        st.vista = v.dataset.vista;
        box.querySelectorAll("[data-vista]").forEach((b) => b.setAttribute("aria-pressed", String(b === v)));
        const rif = st.vista === "settimana" ? (st.inizio.getMonth() === new Date().getMonth() ? new Date() : st.inizio) : st.inizio;
        st.inizio = st.vista === "settimana" ? lunedi(rif) : new Date(rif.getFullYear(), rif.getMonth(), 1);
      }
      if (n || v) disegna();
    });
    $("#ag-ramo").addEventListener("change", (ev) => { st.ramo = ev.target.value; disegna(); });
    box.querySelector(".ag-tipi").addEventListener("click", (ev) => {
      const b = ev.target.closest("[data-tipo]"); if (!b) return;
      const k = b.dataset.tipo;
      if (st.attivi.has(k) && st.attivi.size > 1) st.attivi.delete(k); else st.attivi.add(k);
      box.querySelectorAll("[data-tipo]").forEach((x) => x.setAttribute("aria-pressed", String(st.attivi.has(x.dataset.tipo))));
      disegna();
    });
    $("#ag-corpo").addEventListener("click", (ev) => {
      const x = ev.target.closest("[data-ev]");
      if (x) { const c = x.closest(".ag-cella"); apri(dettaglio(indice[+x.dataset.ev]), giornoLungo(c.querySelector("[data-giorno]").dataset.giorno)); return; }
      const g = ev.target.closest("[data-giorno]") || (matchMedia("(max-width: 640px)").matches && ev.target.closest(".ag-cella")?.querySelector("[data-giorno]"));
      if (g) giorno(g.dataset.giorno);
    });
    disegna();
  };
})();

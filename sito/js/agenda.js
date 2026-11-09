/* Agenda del Parlamento: sedute d'Aula, commissioni, termini per gli emendamenti, progetti di legge, voti finali e leggi,
   per settimana o per mese. Interroga lo strumento pubblico get_parliament_agenda (api/strumenti/agenda.py). */
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
  const cache = new Map();
  const st = { vista: "settimana", inizio: null, scelto: null, ramo: "both", attivi: new Set(TIPI.map((t) => t[0])) };

  // date locali, mai in UTC: «2026-11-09» è il 9 novembre ovunque sia chi guarda
  const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  const daIso = (s) => { const [a, m, g] = s.split("-").map(Number); return new Date(a, m - 1, g); };
  const piu = (d, n) => new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);
  const lunedi = (d) => piu(d, -((d.getDay() + 6) % 7));
  const oggi = () => iso(new Date());
  const giornoLungo = (s) => { const d = daIso(s); return `${GIORNI[(d.getDay() + 6) % 7]} ${d.getDate()} ${MESI[d.getMonth()]}`; };
  const ramo = (r) => (r === "senato" ? TT("Senato", "Senate") : TT("Camera", "Chamber"));
  // in Aula i primi punti sono spesso di servizio: si mostra il primo di merito
  const SERVIZIO = /^(missioni|comunicazioni|preavviso|annunzi|ordine del giorno della prossima|trasmissione|modifica nella composizione|sull'ordine dei lavori|in morte|commemorazione|sui lavori|calendario dei lavori|dimissioni|congedi)/i;
  const merito = (xs) => (xs || []).filter((t) => !SERVIZIO.test(t));

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

  /* ---------- una voce per tipo ---------- */
  const atto = (t) => t.act_number ? `${t.chamber === "senato" ? "S." : "C."} ${t.act_number}` : (t.act_refs || []).map((r) => r.replace(/^ac:/, "C. ").replace(/^ddl:/, "S. ")).slice(0, 2).join(", ");
  const TIPO_T = { "emendamenti": TT("emendamenti", "amendments"), "subemendamenti": TT("subemendamenti", "sub-amendments"),
    "emendamenti e ordini del giorno": TT("emendamenti e ordini del giorno", "amendments and agenda motions"),
    "riesame delle inammissibilità": TT("richieste di riesame", "requests for review"), "segnalazione degli emendamenti": TT("emendamenti segnalati", "flagged amendments") };
  function termine(t, i) {
    const passato = t.due_date < oggi() || t.event === "expired";
    const stato = t.superseded ? `<span class="ag-pill ag-pill--off">${TT("spostato", "moved")}</span>` : passato ? `<span class="ag-pill ag-pill--off">${TT("scaduto", "expired")}</span>` : "";
    return `<li class="ag-v ag-v--termini${t.superseded ? " ag-v--superato" : ""}"><button type="button" class="ag-apri" data-termine="${i}" aria-expanded="false">
      <span class="ag-v__ora">${t.due_time ? e(t.due_time) : TT("in giornata", "during the day")}</span>
      <b>${TT("Termine per", "Deadline for")} ${e(TIPO_T[t.kind] || t.kind)}${stato}</b>
      <span class="ag-v__t">${e([atto(t), t.act_title && B.taglia(t.act_title, 90)].filter(Boolean).join(" · ") || TT("Atto non indicato", "Act not stated"))}</span>
      <span class="ag-v__m">${ramo(t.chamber)} · ${e(t.body_name || "")}${t.presented ? ` · ${t.presented} ${TT("proposte presentate", "proposals filed")}` : ""}</span></button>
      <div class="ag-fonte" hidden><p>«${e(t.sentence)}»</p><p class="ag-nota">${TT("Sommario della seduta del", "Summary record of the sitting of")} ${B.data(t.sitting_date)}${t.mentions > 1 ? `, ${TT("ricordato in", "mentioned in")} ${t.mentions} ${TT("sedute", "sittings")}` : ""}. ${TT("Testo degli uffici, non parole di un parlamentare. Data letta da regole fisse e confermata da una seconda lettura.", "Written by the clerks, not words of a member. Date read by fixed rules and confirmed by a second reading.")}</p></div></li>`;
  }
  const aula = (s) => `<li class="ag-v ag-v--aula"><a href="#/strumenti/seduta/${e(s.session_id)}">
      <span class="ag-v__ora">${s.start_time ? e(s.start_time) : ""}</span>
      <b>${TT("Aula", "Floor")} ${ramo(s.chamber)} · ${TT("seduta", "sitting")} ${s.number}${s.status === "planned" ? `<span class="ag-pill">${TT("prevista", "planned")}</span>` : ""}</b>
      <span class="ag-v__t">${e(B.taglia(merito(s.items)[0] || TT("Comunicazioni e adempimenti", "Announcements and formalities"), 90))}</span>
      <span class="ag-v__m">${s.items_total > 1 ? `${s.items_total} ${TT("argomenti", "items")}` : ""}${s.items_total > 1 && s.votes ? " · " : ""}${s.votes ? `${s.votes} ${TT("votazioni", "votes")}` : ""}</span></a></li>`;
  const voto = (v) => `<li class="ag-v ag-v--voti"><a href="#/strumenti/voto/${e(v.vote_id)}">
      <b>${TT("Voto finale", "Final vote")} · ${ramo(v.chamber)}<span class="ag-pill ag-pill--${v.approved ? "ok" : "no"}">${v.approved ? TT("approvato", "passed") : TT("respinto", "rejected")}</span></b>
      <span class="ag-v__t">${e(B.taglia((v.act_title || v.title || "").replace(/^S\.\s*\d+\.?\s*-\s*/, "").replace(/^"|"$/g, ""), 90))}</span>
      <span class="ag-v__m">${v.favor ?? "–"} ${TT("sì", "yes")} · ${v.against ?? "–"} no${v.abstain ? ` · ${v.abstain} ${TT("astenuti", "abstained")}` : ""}${v.confidence ? ` · ${TT("fiducia", "confidence")}` : ""}</span></a></li>`;
  const legge = (l) => `<li class="ag-v ag-v--leggi"><span class="ag-v__blocco"><b>${TT("Legge", "Law")} ${l.law_number ? `n. ${e(l.law_number)}` : ""}</b><span class="ag-v__t">${e(B.taglia(l.title || "", 130))}</span></span></li>`;
  const gruppo = (k, xs, testo, riga) => `<li class="ag-v ag-v--${k}"><details><summary><b>${xs.length} ${testo}</b>${B.ico("dx")}</summary><ul class="ag-sotto">${xs.map(riga).join("")}</ul></details></li>`;
  const pdl = (a) => `<li><span>${ramo(a.chamber).charAt(0)}. ${e(a.number)}</span> ${a.card_url ? `<a href="${e(a.card_url)}" target="_blank" rel="noopener">${e(B.taglia(a.title || "", 110))}</a>` : e(B.taglia(a.title || "", 110))}${a.initiative ? ` <small>${e(a.initiative)}</small>` : ""}</li>`;
  const comm = (c) => `<li><span>${ramo(c.chamber)}</span> ${e(c.body_name || "")}${c.sittings > 1 ? ` <small>× ${c.sittings}</small>` : ""}${(c.seats || []).length ? ` <small>${e(c.seats.join(", ").toLowerCase())}</small>` : ""}</li>`;

  let termini = [];
  function giorno(d, g) {
    const parti = [];
    const on = (k) => st.attivi.has(k) && (g[k] || []).length;
    if (on("termini")) parti.push(...g.termini.map((t) => { termini.push(t); return termine(t, termini.length - 1); }));
    if (on("aula")) parti.push(...g.aula.map(aula));
    if (on("voti")) parti.push(...g.voti.map(voto));
    if (on("leggi")) parti.push(...g.leggi.map(legge));
    if (on("atti")) parti.push(gruppo("atti", g.atti, g.atti.length === 1 ? TT("progetto di legge presentato", "bill filed") : TT("progetti di legge presentati", "bills filed"), pdl));
    if (on("commissioni")) parti.push(gruppo("commissioni", g.commissioni, g.commissioni.length === 1 ? TT("organo riunito", "committee met") : TT("organi riuniti", "committees met"), comm));
    return parti;
  }

  function settimana(dati) {
    const [da] = intervallo();
    let html = "";
    for (let i = 0; i < 7; i++) {
      const d = iso(piu(da, i)), parti = giorno(d, (dati.days || {})[d] || {});
      html += `<section class="ag-g${d === oggi() ? " ag-g--oggi" : ""}${parti.length ? "" : " ag-g--vuoto"}" aria-label="${e(giornoLungo(d))}"><h3><span>${GIORNI[i]}</span> ${daIso(d).getDate()}${d === oggi() ? `<span class="ag-pill ag-pill--acc">${TT("oggi", "today")}</span>` : ""}</h3>${parti.length ? `<ul>${parti.join("")}</ul>` : `<p class="ag-niente">${TT("Niente in calendario", "Nothing scheduled")}</p>`}</section>`;
    }
    return `<div class="ag-sett">${html}</div>`;
  }

  function mese(dati) {
    const [da, a] = intervallo(), m = st.inizio.getMonth();
    let celle = GIORNI.map((g) => `<div class="ag-mese__testa" aria-hidden="true">${g}</div>`).join("");
    for (let d = da; d <= a; d = piu(d, 1)) {
      const k = iso(d), g = (dati.days || {})[k] || {};
      const conti = TIPI.filter(([t]) => st.attivi.has(t) && (g[t] || []).length).map(([t, n]) => `<span class="ag-c ag-c--${t}" title="${e(n)}"><i></i>${g[t].length}</span>`);
      celle += `<button type="button" class="ag-cella${d.getMonth() !== m ? " ag-cella--fuori" : ""}${k === oggi() ? " ag-cella--oggi" : ""}${k === st.scelto ? " ag-cella--scelta" : ""}" data-giorno="${k}" aria-label="${e(giornoLungo(k))}: ${conti.length ? e(TIPI.filter(([t]) => st.attivi.has(t) && (g[t] || []).length).map(([t, n]) => `${g[t].length} ${n}`).join(", ")) : TT("niente", "nothing")}"><span class="ag-cella__n">${d.getDate()}</span>${conti.join("")}</button>`;
    }
    const scelto = st.scelto && (dati.days || {})[st.scelto] ? giorno(st.scelto, dati.days[st.scelto]) : [];
    return `<div class="ag-mese">${celle}</div>${st.scelto ? `<section class="ag-g ag-g--dettaglio"><h3>${e(giornoLungo(st.scelto))}</h3>${scelto.length ? `<ul>${scelto.join("")}</ul>` : `<p class="ag-niente">${TT("Niente in calendario", "Nothing scheduled")}</p>`}</section>` : `<p class="ag-niente">${TT("Scegli un giorno per vedere il dettaglio.", "Pick a day to see the details.")}</p>`}`;
  }

  function titoloPeriodo() {
    const [da, a] = intervallo();
    if (st.vista === "mese") return `${MESI[st.inizio.getMonth()]} ${st.inizio.getFullYear()}`;
    return da.getMonth() === a.getMonth() ? `${da.getDate()}–${a.getDate()} ${MESI[a.getMonth()]} ${a.getFullYear()}` : `${da.getDate()} ${MESI[da.getMonth()]} – ${a.getDate()} ${MESI[a.getMonth()]} ${a.getFullYear()}`;
  }

  async function disegna() {
    const box = $("#ag-corpo"); if (!box) return;
    $("#ag-periodo").textContent = titoloPeriodo();
    box.setAttribute("aria-busy", "true");
    const [da, a] = intervallo();
    try {
      const dati = await leggi(da, a);
      termini = [];
      box.innerHTML = st.vista === "settimana" ? settimana(dati) : mese(dati);
      const c = dati.counts || {};
      $("#ag-conto").textContent = TIPI.filter(([t]) => st.attivi.has(t) && c[t]).map(([t, n]) => `${c[t]} ${n.toLowerCase()}`).join(" · ") || TT("Niente in questo periodo con i filtri scelti.", "Nothing in this period with the chosen filters.");
    } catch (err) { box.innerHTML = ST.errore(err); }
    box.removeAttribute("aria-busy");
  }

  window.AGENDA = (box, arg) => {
    const base = /^\d{4}-\d{2}-\d{2}$/.test(arg || "") ? daIso(arg) : new Date();
    st.inizio = lunedi(base); st.scelto = iso(base); st.vista = matchMedia("(max-width: 760px)").matches ? "settimana" : st.vista;
    box.innerHTML = ST.testa("agenda", null, null, TT("Cosa scade questa settimana in Parlamento?", "What is due in Parliament this week?"))
      + ST.avvio(TT("Il calendario del Parlamento: sedute d'Aula previste e tenute, commissioni, termini per presentare gli emendamenti, progetti di legge presentati, voti finali e leggi.", "Parliament's calendar: planned and held floor sittings, committees, deadlines for amendments, bills filed, final votes and laws."), [], "")
      + `<div class="ag-barra">
          <div class="ag-nav"><button type="button" class="ic-a" data-ag="-1" aria-label="${TT("Periodo precedente", "Previous period")}" data-tip="${TT("Precedente", "Previous")}">${B.ico("sx")}</button><button type="button" class="bt bt--linea ag-oggi" data-ag="0">${TT("Oggi", "Today")}</button><button type="button" class="ic-a" data-ag="1" aria-label="${TT("Periodo successivo", "Next period")}" data-tip="${TT("Successivo", "Next")}">${B.ico("dx")}</button><h2 id="ag-periodo" aria-live="polite"></h2></div>
          <div class="ag-scelte"><div class="ag-vista" role="group" aria-label="${TT("Vista", "View")}"><button type="button" data-vista="settimana" aria-pressed="${st.vista === "settimana"}">${TT("Settimana", "Week")}</button><button type="button" data-vista="mese" aria-pressed="${st.vista === "mese"}">${TT("Mese", "Month")}</button></div>
          <label class="vh" for="ag-ramo">${TT("Ramo", "Chamber")}</label><select id="ag-ramo"><option value="both">${TT("Camera e Senato", "Chamber and Senate")}</option><option value="camera">Camera</option><option value="senato">Senato</option></select></div>
        </div>
        <div class="ag-tipi" role="group" aria-label="${TT("Cosa mostrare", "What to show")}">${TIPI.map(([k, n]) => `<button type="button" class="ag-tipo ag-tipo--${k}" data-tipo="${k}" aria-pressed="${st.attivi.has(k)}"><i></i>${e(n)}</button>`).join("")}</div>
        <p class="ag-conto" id="ag-conto"></p>
        <div id="ag-corpo">${ST.carica(TT("Leggo l'agenda", "Loading the agenda"))}</div>
        <p class="ag-piede">${TT("Le sedute d'Aula previste vengono dall'ordine del giorno della Camera. I termini per gli emendamenti vengono dai sommari delle commissioni: si vedono dal giorno dopo la seduta in cui sono fissati, e mancano quelli decisi senza che il sommario li riporti.", "Planned floor sittings come from the Chamber's order of business. Amendment deadlines come from committee summary records: they appear the day after the sitting that sets them, and those the record does not report are missing.")}</p>`;
    $("#ag-ramo").value = st.ramo;
    box.querySelector(".ag-barra").addEventListener("click", (ev) => {
      const n = ev.target.closest("[data-ag]"), v = ev.target.closest("[data-vista]");
      if (n) {
        const k = +n.dataset.ag;
        if (k === 0) { st.inizio = lunedi(new Date()); st.scelto = oggi(); }
        else if (st.vista === "settimana") st.inizio = piu(st.inizio, 7 * k);
        else { st.inizio = new Date(st.inizio.getFullYear(), st.inizio.getMonth() + k, 1); st.scelto = null; }
      }
      if (v) {
        st.vista = v.dataset.vista;
        box.querySelectorAll("[data-vista]").forEach((b) => b.setAttribute("aria-pressed", String(b === v)));
        st.inizio = st.vista === "settimana" ? lunedi(st.scelto ? daIso(st.scelto) : st.inizio) : new Date((st.scelto ? daIso(st.scelto) : st.inizio).getFullYear(), (st.scelto ? daIso(st.scelto) : st.inizio).getMonth(), 1);
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
      const c = ev.target.closest("[data-giorno]");
      if (c) { st.scelto = c.dataset.giorno; disegna(); return; }
      const t = ev.target.closest("[data-termine]");
      if (t) { const f = t.parentElement.querySelector(".ag-fonte"), aperto = t.getAttribute("aria-expanded") === "true"; t.setAttribute("aria-expanded", String(!aperto)); f.hidden = aperto; }
    });
    disegna();
  };
})();

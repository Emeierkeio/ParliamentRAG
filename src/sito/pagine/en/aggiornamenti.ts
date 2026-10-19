import type { Contenuto } from "../../guscio";

const contenuto: Contenuto = {
  titolo: "Updates · ParliamentRAG",
  descrizione: "What changes in ParliamentRAG: papers, systems, public talks. With email updates.",
  html: String.raw`
  <!-- Apertura -->
  <section class="apertura">
    <div class="pagina apertura__griglia">
      <div>
        <p class="etichetta compare">Updates</p>
        <h1 class="titolo-1 compare" style="--ritardo:80ms">What changes in the project.</h1>
        <p class="attacco compare" style="--ritardo:160ms">Papers, new systems, public talks. In order, most recent first.</p>
      </div>
      <div class="compare" style="--ritardo:220ms">
        <div class="schede" role="group" aria-label="Filter by type" id="filtro">
          <button type="button" aria-pressed="true" aria-selected="true" data-tipo="">All</button>
          <button type="button" aria-pressed="false" aria-selected="false" data-tipo="pubblicazioni">Publications</button>
          <button type="button" aria-pressed="false" aria-selected="false" data-tipo="sistemi">Systems</button>
          <button type="button" aria-pressed="false" aria-selected="false" data-tipo="interventi">Talks</button>
        </div>
      </div>
    </div>
  </section>

  <!-- Cronaca -->
  <section class="sezione-stretta" style="padding-top:0">
    <div class="pagina">
      <div class="testata compare"><span class="testata__n">§ 1</span><p class="etichetta" style="padding-top:.55em" id="conteggio" aria-live="polite">October 2026</p></div>

      <ol class="cronaca" id="cronaca">
        <li class="notizia compare" data-tipo="pubblicazioni">
          <div class="notizia__quando">
            <time datetime="2026-10-25">25–29 Oct 2026</time>
            <span class="sigla">Publications</span>
          </div>
          <div class="notizia__corpo">
            <h2>Two papers accepted at ISWC 2026</h2>
            <p>The In-Use Track paper and the ParliamentRAG demo were accepted at the International Semantic Web Conference. We present them in Bari, from 25 to 29 October.</p>
            <div class="fila notizia__link">
              <a class="collegamento" href="/en/research">Read the papers and how to cite them</a>
              <a class="collegamento" href="https://iswc2026.semanticweb.org/#/program/acceptedpapers" rel="noopener">Conference programme <svg class="freccia-nord-est" width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3.5 8.5l5-5M4.5 3.5h4v4"/></svg></a>
            </div>
          </div>
        </li>

        <li class="notizia compare" data-tipo="sistemi">
          <div class="notizia__quando">
            <time datetime="2026-10-19">19 Oct 2026</time>
            <span class="sigla">Systems</span>
          </div>
          <div class="notizia__corpo">
            <h2>Amendments, documents and laws in the graph</h2>
            <p>The graph now holds the amendments of the Chamber and the Senate with their outcome, the documents voted on the floor, the orders of the day and the rapporteurs of the bills. When a bill becomes law, Fascicoli, Scranno, Stenografo and the connector show the published law, with a link to Normattiva.</p>
            <div class="fila notizia__link">
              <a class="collegamento" href="https://www.scranno.it">Open Scranno</a>
              <a class="collegamento" href="/en/data">See the data</a>
            </div>
          </div>
        </li>

        <li class="notizia compare" data-tipo="sistemi">
          <div class="notizia__quando">
            <time datetime="2026-10-16">16 Oct 2026</time>
            <span class="sigla">Systems</span>
          </div>
          <div class="notizia__corpo">
            <h2>The verifier is open</h2>
            <p>Paste the answer of an AI assistant and the verifier checks the three guarantees: all groups, authoritative voices, exact quotes. The same check is a tool of the connector. Quotes can also be checked on your own computer, with the open data.</p>
            <div class="fila notizia__link">
              <a class="collegamento" href="/en/verification">Try the verifier</a>
            </div>
          </div>
        </li>

        <li class="notizia compare" data-tipo="sistemi">
          <div class="notizia__quando">
            <time datetime="2026-10-14">14 Oct 2026</time>
            <span class="sigla">Systems</span>
          </div>
          <div class="notizia__corpo">
            <h2>The Senate is here</h2>
            <p>Fascicoli, Stenografo, Scranno, search and the connector for AI assistants now cover the Chamber and the Senate in the 19th legislature.</p>
            <div class="fila notizia__link">
              <a class="collegamento" href="https://www.fascicoli.it">Open Fascicoli</a>
              <a class="collegamento" href="/en/developers">Set up the connector</a>
            </div>
          </div>
        </li>

        <li class="notizia compare" data-tipo="sistemi">
          <div class="notizia__quando">
            <time datetime="2026-10-03">3 Oct 2026</time>
            <span class="sigla">Systems</span>
          </div>
          <div class="notizia__corpo">
            <h2>Fascicoli is online</h2>
            <p>Dossiers on a topic are now a system of their own, on fascicoli.it. For each topic you find the position of every group, the authoritative voices and the exact quotes.</p>
            <div class="fila notizia__link">
              <a class="collegamento" href="https://www.fascicoli.it">Open Fascicoli</a>
            </div>
          </div>
        </li>

        <li class="notizia compare" data-tipo="interventi">
          <div class="notizia__quando">
            <time datetime="2026-10-01">1 Oct 2026</time>
            <span class="sigla">Talks</span>
          </div>
          <div class="notizia__corpo">
            <h2>ParliamentRAG at Milano Digital Week</h2>
            <p>We presented the project at Milano Digital Week 2026, at the University of Milano-Bicocca.</p>
            <div class="fila notizia__link">
              <a class="collegamento" href="https://www.milanodigitalweek.com/event/parliamentrag-navigare-gli-atti-parlamentari-con-lia-affidabile" rel="noopener">Event page <svg class="freccia-nord-est" width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3.5 8.5l5-5M4.5 3.5h4v4"/></svg></a>
            </div>
          </div>
        </li>
      </ol>
      <p class="cronaca__vuota" id="vuota" hidden>No updates of this type, for now.</p>
    </div>
  </section>

  <!-- Iscrizione -->
  <section class="sezione-stretta" id="iscriviti" style="background:var(--carta-2);border-top:1px solid var(--filetto)">
    <div class="pagina iscriviti">
      <div class="compare">
        <h2 class="titolo-2">Get the updates by email.</h2>
        <p class="tenue" style="margin-top:var(--s-3);max-width:44ch">Few emails, when there is something to say. Unsubscribe in one click.</p>
        <ul class="iscriviti__regole">
          <li><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3.5 8.4l3 3 6-6.6"/></svg>You confirm the subscription from an email we send you.</li>
          <li><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3.5 8.4l3 3 6-6.6"/></svg>The address stays on Brevo. We do not link it to the questions you ask.</li>
        </ul>
      </div>
      <form class="compare" id="iscrizione" novalidate style="--ritardo:120ms">
        <label class="sr" for="email">Your email</label>
        <div class="campo">
          <input id="email" name="email" type="email" autocomplete="email" placeholder="name@example.com" required>
          <button class="btn btn--accento" type="submit">Subscribe</button>
        </div>
        <label class="spunta"><input type="checkbox" id="consenso"> <span>I have read the <a class="collegamento" href="/en/privacy#newsletter">privacy notice</a> and agree to receive updates about ParliamentRAG.</span></label>
        <p class="messaggio" id="iscrizione-msg" role="status"></p>
      </form>
    </div>
  </section>
`,
};

export default contenuto;

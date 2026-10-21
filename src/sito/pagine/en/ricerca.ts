import type { Contenuto } from "../../guscio";

const contenuto: Contenuto = {
  titolo: "Research · ParliamentRAG",
  descrizione: "ParliamentRAG's papers at ISWC 2026, the code with a DOI, the public talks and the project's funding.",
  html: String.raw`
  <!-- Apertura -->
  <section class="apertura">
    <div class="pagina">
      <p class="etichetta compare">Research · University of Milano-Bicocca</p>
      <h1 class="titolo-1 compare" style="--ritardo:80ms">The method is written, peer-reviewed and <em>citable</em>.</h1>
      <p class="attacco compare" style="--ritardo:160ms">ParliamentRAG is described in two papers accepted at ISWC 2026, in Bari from 25 to 29 October.</p>

    </div>
  </section>

  <!-- Articoli -->
  <section class="sezione-stretta" id="articoli" style="padding-top:0">
    <div class="pagina">
      <div class="testata compare"><span class="testata__n">§ 1</span><p class="etichetta" style="padding-top:.55em">Papers</p></div>

      <article class="lavoro compare" aria-labelledby="a1-t">
        <div class="lavoro__dove">
          <span class="sigla sigla--accento">ISWC 2026</span>
          <span class="etichetta">In-Use Track</span>
          <span class="mono">LNCS 17128, ch. 24</span>
          <span class="mono">Springer</span>
        </div>
        <div>
          <h2 class="lavoro__t" id="a1-t">Who Speaks Matters: Authority-Aware Multi-View RAG over Italian Parliamentary Proceedings</h2>
          <p class="lavoro__chi">Mirko Tritella, Riccardo Pozzi, Matteo Palmonari</p>
          <p class="lavoro__cosa">The paper that describes the method: how to choose the authoritative voices of each group and how to build an answer that includes them all.</p>
          <div class="fila lavoro__azioni">
            <a class="btn btn--accento btn--piccolo" href="https://emeierkeio.github.io/papers/who-speaks-matters-iswc2026.pdf" rel="noopener">PDF</a>
            <a class="btn btn--linea btn--piccolo" href="https://arxiv.org/abs/2608.13410" rel="noopener">arXiv</a>
            <a class="btn btn--linea btn--piccolo" href="https://doi.org/10.5281/zenodo.23173703" rel="noopener">Code</a>
            <a class="btn btn--linea btn--piccolo" href="https://orkg.org/papers/R1909763" rel="noopener">ORKG</a>
            <button class="btn btn--linea btn--piccolo" type="button" aria-expanded="false" aria-controls="cita-1" data-cita>Cite</button>
          </div>
          <p class="nota">DOI 10.1007/978-3-032-42029-9_24, active when the volume is out.</p>
          <div class="citazione-bib" id="cita-1" hidden>
            <div class="blocco-codice">
              <pre class="codice" id="bib-1">@inproceedings{tritella2026whospeaksmatters,
  author    = {Tritella, Mirko and Pozzi, Riccardo and Palmonari, Matteo},
  title     = {Who Speaks Matters: Authority-Aware Multi-View RAG over Italian Parliamentary Proceedings},
  booktitle = {Proceedings of the 25th International Semantic Web Conference (ISWC 2026), In-Use Track},
  series    = {Lecture Notes in Computer Science},
  volume    = {17128},
  publisher = {Springer},
  year      = {2026},
  doi       = {10.1007/978-3-032-42029-9_24}
}</pre>
              <button class="copia" type="button" data-copia="bib-1">Copy</button>
            </div>
            <p class="nota">BibTeX. If you write about the project, cite this paper.</p>
          </div>
        </div>
      </article>

      <article class="lavoro compare" aria-labelledby="a2-t">
        <div class="lavoro__dove">
          <span class="sigla sigla--accento">ISWC 2026</span>
          <span class="etichetta">Posters &amp; Demos</span>
        </div>
        <div>
          <h2 class="lavoro__t" id="a2-t">ParliamentRAG: An Authority-Aware Multi-View RAG System for Italian Parliamentary Proceedings</h2>
          <p class="lavoro__chi">Mirko Tritella, Riccardo Pozzi, Matteo Palmonari</p>
          <p class="lavoro__cosa">The system at work: the demo presented at the conference. In Bari we show it live on Fascicoli, with data from the Chamber and the Senate.</p>
          <div class="fila lavoro__azioni">
            <a class="btn btn--accento btn--piccolo" href="https://emeierkeio.github.io/papers/parliamentrag-demo-iswc2026.pdf" rel="noopener">PDF</a>
            <a class="btn btn--linea btn--piccolo" href="https://truthful-amazement-production.up.railway.app" rel="noopener">Demo <svg class="freccia-nord-est" width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3.5 8.5l5-5M4.5 3.5h4v4"/></svg></a>
            <a class="btn btn--linea btn--piccolo" href="https://www.fascicoli.it" rel="noopener">Fascicoli <svg class="freccia-nord-est" width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3.5 8.5l5-5M4.5 3.5h4v4"/></svg></a>
          </div>
        </div>
      </article>
    </div>
  </section>


  <!-- Conferenza e interventi -->
  <section class="sezione-stretta" id="interventi">
    <div class="pagina">
      <div class="testata compare"><span class="testata__n">§ 2</span><p class="etichetta" style="padding-top:.55em">Conference and talks</p></div>
      <div class="eventi">
        <article class="foglio foglio--pad evento compare">
          <span class="etichetta">Conference</span>
          <p class="evento__quando">25–29 October 2026</p>
          <p class="evento__dove"><strong>ISWC 2026, Bari</strong>25th International Semantic Web Conference. We present the In-Use paper and the demo.</p>
          <p class="evento__vai"><a class="collegamento" href="https://iswc2026.semanticweb.org/#/program/acceptedpapers" rel="noopener">Accepted papers in the programme</a></p>
        </article>
        <article class="foglio foglio--pad evento compare" style="--ritardo:100ms">
          <span class="etichetta">Talk</span>
          <p class="evento__quando">1 October 2026</p>
          <p class="evento__dove"><strong>Milano Digital Week 2026</strong>«ParliamentRAG», at the University of Milano-Bicocca.</p>
          <p class="evento__vai"><a class="collegamento" href="https://www.milanodigitalweek.com/event/parliamentrag-navigare-gli-atti-parlamentari-con-lia-affidabile" rel="noopener">Event page (in Italian)</a></p>
        </article>
      </div>
      <p class="nota compare" style="margin-top:var(--s-5)">To invite us to talk about the project, write to <a class="collegamento" href="mailto:contatti@parliamentrag.it">contatti@parliamentrag.it</a>.</p>
    </div>
  </section>

  <!-- Persone e sostegno -->
  <section class="sezione-stretta" id="persone">
    <div class="pagina">
      <div class="testata compare"><span class="testata__n">§ 3</span><p class="etichetta" style="padding-top:.55em">People and support</p></div>
      <div class="chi">
        <div class="compare">
          <h3>Authors</h3>
          <ul class="persone">
            <li>
              <span>Mirko Tritella</span>
              <span class="fila">
                <a class="collegamento" href="https://emeierkeio.github.io" rel="noopener">Website</a>
                <a class="collegamento" href="https://orcid.org/0009-0000-8611-8189" rel="noopener">ORCID</a>
                <a class="collegamento" href="https://github.com/Emeierkeio" rel="noopener">GitHub</a>
              </span>
            </li>
            <li>
              <span>Riccardo Pozzi</span>
              <span class="fila">
                <a class="collegamento" href="https://www.riccardopozzi.com/" rel="noopener">Website</a>
                <a class="collegamento" href="https://orcid.org/0000-0002-4954-3837" rel="noopener">ORCID</a>
                <a class="collegamento" href="https://github.com/rpo19" rel="noopener">GitHub</a>
              </span>
            </li>
            <li>
              <span>Matteo Palmonari</span>
              <span class="fila">
                <a class="collegamento" href="https://www.unimib.it/matteo-luigi-palmonari" rel="noopener">Website</a>
                <a class="collegamento" href="https://orcid.org/0000-0002-1801-5118" rel="noopener">ORCID</a>
              </span>
            </li>
          </ul>
          <p class="nota" style="margin-top:var(--s-3)">University of Milano-Bicocca.</p>
        </div>
        <div class="compare" style="--ritardo:100ms">
          <h3>Funding</h3>
          <p class="tenue" style="max-width:44ch">The project is supported by the EU Horizon Europe programme, grant 101189771 (DataPACT).</p>
          <p style="margin-top:var(--s-4)"><a class="riproduci__doi" style="margin-top:0" href="https://doi.org/10.3030/101189771" rel="noopener">doi.org/10.3030/101189771</a></p>
        </div>
      </div>
    </div>
  </section>

  <!-- Iscrizione -->
  <section class="sezione-stretta" style="background:var(--carta-2);border-top:1px solid var(--filetto)">
    <div class="pagina iscriviti">
      <div class="compare">
        <h2 class="titolo-2">New systems, new data, new papers.</h2>
        <p class="tenue" style="margin-top:var(--s-3);max-width:44ch">Few emails, when there is something to say. Unsubscribe in one click.</p>
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

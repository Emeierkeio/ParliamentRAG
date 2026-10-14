import type { Contenuto } from "../../guscio";

const contenuto: Contenuto = {
  titolo: "ParliamentRAG",
  descrizione: "Research project on AI for the debates of Italian institutions: three guarantees for every answer about Parliament, open data and a method to check them.",
  html: String.raw`
  <!-- Apertura -->
  <section class="apertura">
    <div class="pagina apertura__griglia">
      <div>
        <p class="etichetta compare">Research project · University of Milano-Bicocca</p>
        <h1 class="titolo-1 compare" style="--ritardo:80ms;font-size:clamp(2.5rem,1.3rem + 3.9vw,5rem);line-height:.98;letter-spacing:-.03em">Talking about Parliament needs <em>guarantees</em>.</h1>
        <p class="attacco compare" style="--ritardo:160ms">A parliamentary debate is reported correctly only if every party has a voice, if the people speaking know the topic and if the words in quotation marks were really said. ParliamentRAG checks these three guarantees in AI answers about the institutions, and applies them in free tools for anyone.</p>
        <div class="fila apertura__azioni compare" style="--ritardo:240ms">
          <a class="btn btn--accento" href="https://www.stenografo.it">Ask a question <svg class="freccia" width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 8h10M9 4l4 4-4 4"/></svg></a>
          <a class="btn btn--linea" href="#garanzie">The three guarantees</a>
        </div>
      </div>

      <figure class="foglio galleggia campione compare" style="--ritardo:200ms" aria-label="Example of a checked answer">
        <div class="campione__testa">
          <span class="etichetta">Example · real quotes</span>
          <span class="etichetta" id="campione-stato">Checking</span>
        </div>
        <div class="campione__corpo">
          <p class="campione__domanda">What do the parties say about the minimum wage?</p>
          <p class="campione__risposta">The opposition wants a threshold set by law; the majority relies on collective bargaining. On 5 December 2023 the Chamber rejected the Conte amendment with 149 votes against and 111 in favour.</p>
          <div class="campione__gruppi" id="campione-gruppi" aria-label="Groups considered">{{sigle}}</div>
          <div class="campione__voci" id="campione-voci" aria-live="polite">{{voci}}</div>
        </div>
        <div class="campione__piede">
          <div class="sigillo" id="campione-sigillo">
            <span class="sigillo__da">Check</span>
            <span class="sigillo__voce"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="8" cy="8" r="6.6"/><path d="M5.2 8.2l1.9 1.9 3.8-4"/></svg>All parties</span>
            <span class="sigillo__voce"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="8" cy="8" r="6.6"/><path d="M5.2 8.2l1.9 1.9 3.8-4"/></svg>Authoritative voices</span>
            <span class="sigillo__voce"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="8" cy="8" r="6.6"/><path d="M5.2 8.2l1.9 1.9 3.8-4"/></svg>Exact quotes</span>
          </div>
        </div>
      </figure>
    </div>
  </section>

  <!-- Il problema -->
  <section class="sezione-stretta">
    <div class="pagina">
      <div class="testata compare"><span class="testata__n">§ 1</span><p class="etichetta" style="padding-top:.55em">The problem</p></div>
      <div class="problema">
        <h2 class="titolo-2 compare">More and more people ask AI what is happening in Parliament.</h2>
        <div class="problema__testo compare" style="--ritardo:120ms">
          <p>An assistant can leave a group out, let someone who does not work on the topic speak for it, put words a member of Parliament never said into their mouth. <strong>Readers have no way to notice.</strong></p>
          <p>The data to check exists: the Chamber and the Senate publish records, acts and votes. What is missing is a method that says what to check and a tool that does it. ParliamentRAG works on both.</p>
        </div>
      </div>
    </div>
  </section>

  <!-- Le tre garanzie -->
  <section class="sezione-stretta" id="garanzie">
    <div class="pagina">
      <div class="testata compare"><span class="testata__n">§ 2</span><p class="etichetta" style="padding-top:.55em">Three guarantees for every answer</p></div>

      <article class="garanzia">
        <div class="compare">
          <p class="garanzia__n">01</p>
          <h3 class="titolo-2">All groups</h3>
          <p class="garanzia__testo">No group is silently left out. If a group has not spoken about the topic, the answer says so.</p>
          <p class="garanzia__come"><span class="etichetta">Try it</span>Pick a group: its seats light up in today's Chamber and you see what it said about the minimum wage, with the link to the record.</p>
        </div>
        <div class="aula-demo compare" style="--ritardo:120ms">
          <svg class="emiciclo" id="aula" data-scelto="PD" viewBox="0 0 2560 1760" role="img" aria-label="Seats of the Chamber at Montecitorio, 19th legislature">{{seggi}}</svg>
          <div class="gruppi-lista" id="gruppi" role="group" aria-label="Parliamentary groups">{{gruppi}}</div>
          <div class="gruppo-voce" id="gruppo-voce" aria-live="polite">{{voce}}</div>
        </div>
      </article>

      <article class="garanzia">
        <div class="compare">
          <p class="garanzia__n">02</p>
          <h3 class="titolo-2">Authoritative voices</h3>
          <p class="garanzia__testo">For each group, the person who speaks is someone who really works on the topic. We measure it with six criteria and public weights, computed again for every question.</p>
          <p class="garanzia__come"><span class="etichetta">Why the weights are public</span>They are an editorial choice, not a neutral measure. We publish them so that anyone can challenge them.</p>
        </div>
        <div class="pesi compare" style="--ritardo:120ms" aria-label="Weights of the six authority criteria">
          <div class="peso"><span class="peso__nome">Speeches on the floor<small>how much, and how recently, they spoke about the topic</small></span><span class="peso__barra"><i style="--w:100%;--ritardo:0ms"></i></span><span class="peso__v">0.25</span></div>
          <div class="peso"><span class="peso__nome">Committee<small>how close their committee is to the topic</small></span><span class="peso__barra"><i style="--w:100%;--ritardo:80ms"></i></span><span class="peso__v">0.25</span></div>
          <div class="peso"><span class="peso__nome">Signed acts<small>bills and acts on the topic, weighted by recency</small></span><span class="peso__barra"><i style="--w:80%;--ritardo:160ms"></i></span><span class="peso__v">0.20</span></div>
          <div class="peso"><span class="peso__nome">Profession<small>affinity between their work and the topic</small></span><span class="peso__barra"><i style="--w:60%;--ritardo:240ms"></i></span><span class="peso__v">0.15</span></div>
          <div class="peso"><span class="peso__nome">Education<small>affinity between their degrees and the topic</small></span><span class="peso__barra"><i style="--w:40%;--ritardo:320ms"></i></span><span class="peso__v">0.10</span></div>
          <div class="peso"><span class="peso__nome">Role<small>current institutional offices</small></span><span class="peso__barra"><i style="--w:20%;--ritardo:400ms"></i></span><span class="peso__v">0.05</span></div>
        </div>
      </article>

      <article class="garanzia">
        <div class="compare">
          <p class="garanzia__n">03</p>
          <h3 class="titolo-2">Exact quotes</h3>
          <p class="garanzia__testo">What is in quotation marks was said on the floor, by the person we attribute it to. We compare every quote with the record word for word: if it does not match, we remove it.</p>
          <p class="garanzia__come"><span class="etichetta">Try it</span>Change even a single word of the quote next to this text and see what happens.</p>
        </div>
        <div class="confronto compare" style="--ritardo:120ms">
          <p class="etichetta">Quote proposed by the model</p>
          <div class="campo campo--area">
            <textarea id="confronto-input" rows="3" spellcheck="false" lang="it" aria-label="Quote to compare">Siamo contrari all'idea di un salario minimo legale, fissato per legge, che rischia di diventare un tetto e non certo un pavimento per le retribuzioni.</textarea>
          </div>
          <p class="etichetta" style="margin-top:var(--s-3)">Compared with the record · Marcello Coppo, FdI, 14 July 2025</p>
          <p class="confronto__parole" id="confronto-parole" lang="it" aria-live="polite">{{parole}}</p>
          <div class="esito" id="confronto-esito" role="status" data-esito="ok">{{esito}}</div>
          <div class="fila">
            <button class="btn btn--linea btn--piccolo" type="button" id="confronto-ripristina">Reset</button>
            <a class="collegamento piccolo" href="https://www.camera.it/leg19/410?idSeduta=0510&tipo=stenografico#sed0510.stenografico.tit00040.sub00010.int00080" rel="noopener">Open the record of sitting 510</a>
          </div>
        </div>
      </article>
    </div>
  </section>

  <!-- Sistemi -->
  <section class="sezione-stretta" id="sistemi">
    <div class="pagina">
      <div class="testata compare"><span class="testata__n">§ 3</span><p class="etichetta" style="padding-top:.55em">Where we apply them</p></div>
      <h2 class="titolo-1 compare" style="margin-top:var(--s-6);max-width:16ch">Three free systems, one graph.</h2>
      <p class="attacco compare" style="margin-top:var(--s-4)">Each one does a single job and carries the seal of the three guarantees. No account needed.</p>

      <div class="sistemi">
        <a class="foglio sistema compare" href="https://www.stenografo.it">
          <span class="sistema__marchio"><svg viewBox="6 8.5 50.5 48" aria-hidden="true" focusable="false"><path d="M10 42C12 23 29 16 33.5 27C37 36 24 42 27.5 49.5C31 56.5 46 52 48.5 28" fill="none" stroke="currentColor" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/><circle cx="50" cy="15" r="6.6" fill="#167A68"/></svg></span>
          <span class="sistema__nome">Stenografo</span>
          <span class="sistema__cosa">Ask a question about a sitting, an act or a vote. You get a short answer, with the official record next to every sentence.</span>
          <span class="sistema__per">For people looking for a precise fact: journalists, research offices, citizens.</span>
          <span class="sistema__vai">Ask a question <svg class="freccia" width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 8h10M9 4l4 4-4 4"/></svg></span>
        </a>
        <a class="foglio sistema compare" style="--ritardo:100ms" href="https://www.fascicoli.it">
          <span class="sistema__marchio"><svg viewBox="-5.8 5.5 57.8 55" aria-hidden="true" focusable="false"><g transform="rotate(-30 28 32)"><path d="M14 14V44a14 14 0 0 0 28 0V18a7 7 0 0 0-14 0V40" fill="none" stroke="currentColor" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/><circle cx="14" cy="2" r="6.6" fill="#167A68"/></g></svg></span>
          <span class="sistema__nome">Fascicoli</span>
          <span class="sistema__cosa">Pick a topic. You get the position of every group, the most authoritative voices in each, the exact quotes and the related votes.</span>
          <span class="sistema__per">For people who need to understand a whole debate: researchers, analysts, newsrooms.</span>
          <span class="sistema__vai">Open a dossier <svg class="freccia" width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 8h10M9 4l4 4-4 4"/></svg></span>
        </a>
        <a class="foglio sistema compare" style="--ritardo:200ms" href="https://www.scranno.it">
          <span class="sistema__marchio"><svg viewBox="14.3 8.3 36.5 45.5" aria-hidden="true" focusable="false"><path d="M18 12C18 24 18 32 20 36C22 40 30 40 42 40C46 40 47 43 47 50M24 40V50" fill="none" stroke="currentColor" stroke-width="7.5" stroke-linecap="round" stroke-linejoin="round"/><circle cx="34" cy="24" r="6.4" fill="#167A68"/></svg></span>
          <span class="sistema__nome">Scranno</span>
          <span class="sistema__cosa">You enter the Chamber at Montecitorio. Every seat leads to the deputy who sits there and to their work: speeches, acts, votes.</span>
          <span class="sistema__per">For people who want to know who sits where, and how they voted.</span>
          <span class="sistema__vai">Enter the Chamber <svg class="freccia" width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 8h10M9 4l4 4-4 4"/></svg></span>
        </a>
      </div>
    </div>
  </section>

  <!-- Numeri -->
  <section class="sezione numeri">
    <div class="pagina">
      <div class="testata compare"><span class="testata__n">§ 4</span><p class="etichetta" style="padding-top:.55em">In the graph, as of <span id="data-agg">{{dataAgg}}</span></p></div>
      <h2 class="titolo-1 compare" style="margin-top:var(--s-6);max-width:18ch">The 19th legislature of the Chamber and the Senate, linked fact by fact.</h2>
      <div id="numeri">{{numeri}}</div>
      <div class="fila compare" style="margin-top:var(--s-7)">
        <a class="btn btn--linea" href="/en/data">Download the graph</a>
        <a class="btn btn--linea" href="/en/developers">Connect an AI assistant</a>
      </div>
      <p class="nota compare" style="margin-top:var(--s-4)">Sources: open data of the Chamber of Deputies and the Senate of the Republic, EuroVoc thesaurus. The graph is released under CC BY-SA 4.0.</p>
    </div>
  </section>

  <!-- Ricerca -->
  <section class="sezione-stretta">
    <div class="pagina">
      <div class="testata compare"><span class="testata__n">§ 5</span><p class="etichetta" style="padding-top:.55em">Research</p></div>
      <h2 class="titolo-2 compare" style="margin-top:var(--s-6)">Two papers at ISWC 2026, Bari, 25–29 October.</h2>
      <div class="articoli compare">
        <a class="articolo" href="https://emeierkeio.github.io/papers/who-speaks-matters-iswc2026.pdf" rel="noopener">
          <span class="etichetta">In-Use Track · LNCS 17128</span>
          <span><span class="articolo__t">Who Speaks Matters: Authority-Aware Multi-View Retrieval-Augmented Generation over Italian Parliamentary Proceedings</span><span class="articolo__a" style="display:block">M. Tritella, R. Pozzi, M. Palmonari</span></span>
          <span class="etichetta">PDF ↗</span>
        </a>
        <a class="articolo" href="https://emeierkeio.github.io/papers/parliamentrag-demo-iswc2026.pdf" rel="noopener">
          <span class="etichetta">Posters &amp; Demos</span>
          <span><span class="articolo__t">ParliamentRAG: An Authority-Aware Multi-View RAG System for Italian Parliamentary Proceedings</span><span class="articolo__a" style="display:block">M. Tritella, R. Pozzi, M. Palmonari</span></span>
          <span class="etichetta">PDF ↗</span>
        </a>
      </div>
      <p class="compare" style="margin-top:var(--s-5)"><a class="collegamento" href="/en/research">How to cite them, and the public talks</a></p>
    </div>
  </section>

  <!-- Cosa copre -->
  <section class="sezione-stretta">
    <div class="pagina">
      <div class="testata compare"><span class="testata__n">§ 6</span><p class="etichetta" style="padding-top:.55em">Before you use an answer</p></div>
      <div class="copre">
        <div class="compare">
          <h3>Covers</h3>
          <ul>
            <li><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3.5 8.4l3 3 6-6.6"/></svg>Chamber of Deputies and Senate of the Republic in the 19th legislature, from 13 October 2022</li>
            <li><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3.5 8.4l3 3 6-6.6"/></svg>Records of the plenary sittings, with the full text</li>
            <li><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3.5 8.4l3 3 6-6.6"/></svg>Acts and electronic votes, with the vote of every member of Parliament</li>
            <li><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3.5 8.4l3 3 6-6.6"/></svg>Updated after every new sitting</li>
          </ul>
        </div>
        <div class="compare presto" style="--ritardo:100ms">
          <h3>Coming soon</h3>
          <ul>
            <li><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" aria-hidden="true"><circle cx="8" cy="8" r="5.5"/></svg>Legislatures before the 19th</li>
          </ul>
        </div>
        <div class="compare" style="--ritardo:200ms">
          <h3>Found an error?</h3>
          <p class="piccolo tenue">Write to <a class="collegamento" href="mailto:contatti@parliamentrag.it">contatti@parliamentrag.it</a> with the link to the answer. We check it against the record and correct it.</p>
        </div>
      </div>

      <div style="margin-top:var(--s-8)">
        <h2 class="titolo-3 compare">Frequently asked questions</h2>
        <div class="compare" style="margin-top:var(--s-4);border-top:1px solid var(--filetto)">
          <details class="domanda"><summary>Is it an official service of Parliament?</summary><p class="domanda__r">No. It is an independent research project started at the University of Milano-Bicocca. It uses the open data the Chamber and the Senate publish on dati.camera.it and dati.senato.it, but it is not affiliated with Parliament and does not speak on its behalf.</p></details>
          <details class="domanda"><summary>Can I trust the quotes?</summary><p class="domanda__r">The words, yes: every quote is compared with the record and links to the source. The rest of the answer is written by an AI model, which can leave something out or make mistakes. When it matters, check the record.</p></details>
          <details class="domanda"><summary>Is it free?</summary><p class="domanda__r">Yes. Stenografo, Fascicoli and Scranno work without an account and without paying. The data can be downloaded freely.</p></details>
          <details class="domanda"><summary>Can I use an answer in an article?</summary><p class="domanda__r">Yes. Cite the official source linked next to every sentence, not the generated text. If you write about the project, the Research page has the BibTeX reference.</p></details>
          <details class="domanda"><summary>What do you do with my data?</summary><p class="domanda__r">This site needs no account and uses no analytics or advertising tools. If you subscribe to updates, your email stays on Brevo and we do not link it to the questions you ask. <a class="collegamento" href="/en/privacy">Read the privacy notice</a>.</p></details>
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

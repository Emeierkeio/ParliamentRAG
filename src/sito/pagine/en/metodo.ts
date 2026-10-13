import type { Contenuto } from "../../guscio";

const contenuto: Contenuto = {
  titolo: "Method · ParliamentRAG",
  descrizione: "How we check an answer about Parliament: the path of a question, the three guarantees, the authority weights, the compass and the limits.",
  html: String.raw`
  <!-- Apertura -->
  <section class="apertura">
    <div class="pagina">
      <p class="etichetta compare">Method</p>
      <h1 class="titolo-1 compare" style="--ritardo:80ms">How we check an <em>answer</em>.</h1>
      <p class="attacco compare" style="--ritardo:160ms">An AI model writes the answer. Before it reaches the reader, we check three things: that all the groups are there, that the people speaking work on the topic, that the words in quotation marks are the ones in the record.</p>
      <p class="nota compare" style="--ritardo:200ms;margin-top:var(--s-4)">The method has limits. You find them in <a class="collegamento" href="#limiti">§ 6</a>, before you use an answer.</p>

      <nav class="sommario compare" style="--ritardo:240ms" aria-label="The three guarantees">
        <a href="#gruppi"><span class="sommario__n">01</span><span class="sommario__t">All groups</span><span class="sommario__d">No group is left out without the answer saying so.</span></a>
        <a href="#autorevoli"><span class="sommario__n">02</span><span class="sommario__t">Authoritative voices</span><span class="sommario__d">For each group, the person speaking works on the topic, by public criteria.</span></a>
        <a href="#esatte"><span class="sommario__n">03</span><span class="sommario__t">Exact quotes</span><span class="sommario__d">In quotation marks, only words that match the record.</span></a>
      </nav>
    </div>
  </section>

  <div class="pagina impaginato">

    <!-- Indice: fisso sul desktop, elenco in testa sul telefono -->
    <aside class="indice" aria-label="On this page">
      <p class="etichetta">On this page</p>
      <ol id="indice">
        <li><a href="#percorso">The path</a></li>
        <li><a href="#gruppi">All groups</a></li>
        <li><a href="#autorevoli">Authoritative voices</a></li>
        <li><a href="#esatte">Exact quotes</a></li>
        <li><a href="#bussola">The compass</a></li>
        <li><a href="#limiti">Limits</a></li>
        <li><a href="#fonti">Sources</a></li>
      </ol>
    </aside>

    <div class="corpo">

      <!-- § 1 Il percorso di una domanda -->
      <section class="capitolo" id="percorso" aria-labelledby="t-percorso" style="padding-top:0">
        <div class="testata compare"><span class="testata__n">§ 1</span><p class="etichetta" style="padding-top:.55em">The path of a question</p></div>
        <h2 class="titolo-2 compare" id="t-percorso">From question to answer, in six steps.</h2>
        <p class="attacco compare">Each step takes the result of the one before. The last one is a check: if a quote does not pass, it does not reach the reader.</p>

        <ol class="condotto" id="condotto">
          <li class="passo">
            <span class="passo__nodo" aria-hidden="true">1</span>
            <div class="passo__corpo">
              <h3>Rewritten question</h3>
              <p>The question is rephrased and expanded with the terms the debate really uses.</p>
              <span class="passo__esce">out: the question and its synonyms</span>
            </div>
          </li>
          <li class="passo">
            <span class="passo__nodo" aria-hidden="true">2</span>
            <div class="passo__corpo">
              <h3>Search in the speeches</h3>
              <p>A hybrid search, by meaning and by words, finds the relevant floor speeches.</p>
              <span class="passo__esce">out: the candidate speeches</span>
            </div>
          </li>
          <li class="passo">
            <span class="passo__nodo" aria-hidden="true">3</span>
            <div class="passo__corpo">
              <h3>Authority</h3>
              <p>For every member of Parliament who appears, we compute how much they work on the topic of this question.</p>
              <span class="passo__esce">out: who speaks for each group</span>
            </div>
          </li>
          <li class="passo">
            <span class="passo__nodo" aria-hidden="true">4</span>
            <div class="passo__corpo">
              <h3>One section per group</h3>
              <p>The model writes a section for each group, using only that group's speeches.</p>
              <div class="ventaglio" id="ventaglio" aria-hidden="true"></div>
              <span class="passo__esce">out: one section per group</span>
            </div>
          </li>
          <li class="passo">
            <span class="passo__nodo" aria-hidden="true">5</span>
            <div class="passo__corpo">
              <h3>Integration</h3>
              <p>The sections become a single answer, with the points of agreement and disagreement.</p>
              <span class="passo__esce">out: the draft answer</span>
            </div>
          </li>
          <li class="passo">
            <span class="passo__nodo" aria-hidden="true">6</span>
            <div class="passo__corpo">
              <h3>Word-by-word check</h3>
              <p>Every quote is extracted by position from the original text and compared. If it does not match, we remove it.</p>
              <p class="parole-mini" aria-hidden="true" lang="it"><span style="--i:0">vogliamo</span> <span style="--i:1">rafforzarla</span></p>
              <span class="passo__esce">out: only quotes that match</span>
            </div>
          </li>
        </ol>

        <div class="quinte compare">
          <span class="etichetta">Behind the scenes</span>
          <p>In the research demo a panel shows the steps of each answer, how long each one took and which calls to the model it made. It is there for people who study the system and for anyone who wants to know where a sentence comes from.</p>
        </div>
      </section>

      <!-- § 2 Tutti i gruppi -->
      <section class="capitolo" id="gruppi" aria-labelledby="t-gruppi">
        <div class="testata compare"><span class="testata__n">§ 2</span><p class="etichetta" style="padding-top:.55em">First guarantee</p></div>
        <div class="garanzia__testa compare">
          <span class="garanzia__cifra" aria-hidden="true">01</span>
          <h2 class="titolo-2" id="t-gruppi">All groups</h2>
        </div>
        <p class="garanzia__dice compare">An answer about a debate reports the position of every group. If a group has not spoken about the topic, the answer says so.</p>

        <div class="tre-colonne compare">
          <div>
            <span class="etichetta">What it means</span>
            <p>An assistant that summarises a debate tends to follow whoever spoke the most. Small groups disappear without anyone noticing.</p>
            <p>This guarantee asks for an absence to be stated, not decided silently by the model.</p>
          </div>
          <div>
            <span class="etichetta">How we apply it</span>
            <ul>
              <li><strong>Fascicoli</strong> gives every group its own section, even when it spoke little.</li>
              <li><strong>Stenografo</strong> answers specific questions: it quotes the majority, or the Government, together with the opposition. Never one side alone.</li>
              <li>The Mixed Group is attributed to its component: +Europa, not «the Mixed Group».</li>
            </ul>
          </div>
          <div>
            <span class="etichetta">How to check it</span>
            <p>Count the groups named in the answer and compare them with those sitting in the house. For each missing group, look for the sentence that explains why it is missing.</p>
            <p><a class="collegamento" href="/en/verification">Try the check on the Verification page</a></p>
          </div>
        </div>

        <p class="etichetta compare" style="margin-top:var(--s-6)">In the example topic, minimum wage: ten group voices and the Government</p>
        <div class="fila-voci compare" id="fila-voci"></div>
      </section>

      <!-- § 3 Voci autorevoli -->
      <section class="capitolo" id="autorevoli" aria-labelledby="t-autorevoli">
        <div class="testata compare"><span class="testata__n">§ 3</span><p class="etichetta" style="padding-top:.55em">Second guarantee</p></div>
        <div class="garanzia__testa compare">
          <span class="garanzia__cifra" aria-hidden="true">02</span>
          <h2 class="titolo-2" id="t-autorevoli">Authoritative voices</h2>
        </div>
        <p class="garanzia__dice compare">For each group, the person speaking works on the topic, according to our criteria. Not whoever spoke most often in general.</p>

        <div class="tre-colonne compare">
          <div>
            <span class="etichetta">What it means</span>
            <p>Authority is computed for every question. There is no global score: someone authoritative on health may not be on taxes.</p>
          </div>
          <div>
            <span class="etichetta">How we apply it</span>
            <ul>
              <li><strong>Stenografo</strong> quotes only rapporteurs, members of the Government and the top five of each group by authority.</li>
              <li>If these conditions cannot be met, it prefers to quote no speech at all.</li>
            </ul>
          </div>
          <div>
            <span class="etichetta">How to check it</span>
            <p>Criteria and weights are public. Anyone can recompute the ranking on the open data and compare it with the voices quoted.</p>
          </div>
        </div>

        <h3 class="titolo-3 compare" style="margin-top:var(--s-7)">Six criteria, one weighted sum</h3>
        <p class="compare tenue" style="margin-top:var(--s-3);max-width:60ch">Each criterion is worth between 0 and 1 and is measured against the question. A member's score is the sum of the six, each multiplied by its weight.</p>
        <div class="tabella-scorri compare tabella-pesi">
          <table class="tabella">
            <thead><tr><th scope="col">Criterion</th><th scope="col" class="num">Weight</th><th scope="col">What it measures</th></tr></thead>
            <tbody id="tabella-pesi"></tbody>
          </table>
        </div>

        <div class="riquadro">
          <div class="compare">
            <h3 class="titolo-4">Time matters</h3>
            <p class="tenue piccolo" style="margin-top:var(--s-2);max-width:48ch">Speeches and acts lose weight with age, with a half-life of 18 months (548 days). A speech from a year and a half ago is worth half of one from today.</p>
          </div>
          <figure class="decadimento compare" style="--ritardo:120ms" aria-label="Decay curve: weight 1 today, 0.5 at 18 months, 0.25 at 36 months">
            <p class="etichetta">Weight of a speech by its age</p>
            <svg id="decadimento" viewBox="0 0 520 210" role="img" aria-hidden="true"></svg>
          </figure>
        </div>

        <!-- Giocattolo: cambia la distribuzione dei pesi, non la classifica -->
        <div class="foglio giocattolo compare" id="giocattolo">
          <div class="giocattolo__testa">
            <span class="etichetta">Try it · move the weights</span>
            <button class="btn btn--linea btn--piccolo" type="button" id="pesi-ripristina">Reset the published weights</button>
          </div>
          <div class="giocattolo__corpo">
            <div>
              <div id="cursori"></div>
              <p class="somma" id="somma" aria-live="polite"></p>
            </div>
            <div class="barre">
              <div>
                <p class="etichetta">Published weights</p>
                <div class="barra-pila" id="barra-pubblicati" aria-hidden="true"></div>
              </div>
              <div>
                <p class="etichetta">Your weights, scaled to a sum of 1</p>
                <div class="barra-pila" id="barra-tuoi" aria-hidden="true"></div>
              </div>
              <div class="chiave" id="chiave"></div>
              <p class="scarti" id="scarti" aria-live="polite"></p>
              <p class="nota">Only the distribution of the weight changes here. We do not recompute the ranking of the members of Parliament: that would need the data of a real question.</p>
            </div>
          </div>
        </div>

        <p class="compare" style="margin-top:var(--s-5);max-width:62ch;color:var(--inchiostro-2)">The weights are an editorial choice. We publish them so that they can be read, discussed and challenged. A different choice produces different voices, and readers should know it.</p>
      </section>

      <!-- § 4 Citazioni esatte -->
      <section class="capitolo" id="esatte" aria-labelledby="t-esatte">
        <div class="testata compare"><span class="testata__n">§ 4</span><p class="etichetta" style="padding-top:.55em">Third guarantee</p></div>
        <div class="garanzia__testa compare">
          <span class="garanzia__cifra" aria-hidden="true">03</span>
          <h2 class="titolo-2" id="t-esatte">Exact quotes</h2>
        </div>
        <p class="garanzia__dice compare">What is in quotation marks was said on the floor, by the person we attribute it to, in those words.</p>

        <div class="tre-colonne compare">
          <div>
            <span class="etichetta">What it means</span>
            <p>A language model tends to paraphrase even when it uses quotation marks. One changed word can change the meaning of a sentence.</p>
          </div>
          <div>
            <span class="etichetta">How we apply it</span>
            <ul>
              <li>The model points to where the passage starts and ends. We take the text ourselves, by position, from the record.</li>
              <li>Then we compare it word for word. If it does not match, the quote is removed.</li>
            </ul>
          </div>
          <div>
            <span class="etichetta">How to check it</span>
            <p>Every quote links to the official record of the Chamber or the Senate. One click is enough.</p>
          </div>
        </div>

        <div class="provenienza">
          <blockquote class="cit compare" id="cit-esempio"></blockquote>
          <dl class="compare" style="--ritardo:120ms" id="cit-scheda"></dl>
        </div>

        <aside class="avvertenza compare" aria-labelledby="t-scelta">
          <h3 id="t-scelta">Exact does not mean neutral.</h3>
          <p>The words match, but the choice of passage stays with the system: which sentence, in which frame, next to which other one. A quote can be partial with respect to the whole speech. That is why the full context is always one click away, in the record.</p>
        </aside>
      </section>

      <!-- § 5 Bussola -->
      <section class="capitolo" id="bussola" aria-labelledby="t-bussola">
        <div class="testata compare"><span class="testata__n">§ 5</span><p class="etichetta" style="padding-top:.55em">The compass, in the research demo</p></div>
        <h2 class="titolo-2 compare" id="t-bussola">Where the groups stand, on that question.</h2>
        <p class="attacco compare">The compass describes what the groups argued on the floor on a precise question. It does not certify their political position.</p>

        <div class="bussola">
          <ol class="compare">
            <li><span>For each question the system proposes two thematic axes. For the minimum wage, for example, one could go from «by law» to «by contract».</span></li>
            <li><span>A language model reads each retrieved speech and gives it a position between −1 and +1 on each axis. If the speech takes no position, it gets none.</span></li>
            <li><span>A group's position is the average of its speeches that have a position.</span></li>
            <li><span>When there are few speeches, the average is pulled towards the centre: two sentences are not enough to place a group.</span></li>
          </ol>
          <figure class="piano compare" style="--ritardo:120ms">
            <svg viewBox="0 0 360 300" role="img" aria-labelledby="piano-t">
              <title id="piano-t">Diagram: speeches on two axes, group average and average pulled towards the centre</title>
              <g id="piano"></g>
            </svg>
            <figcaption class="nota" style="margin-top:var(--s-2)">Diagram, no real data. The grey dots are speeches by one group; the dashed circle is their average; the filled dot is the average pulled towards the centre because there are few speeches.</figcaption>
          </figure>
        </div>
      </section>

      <!-- § 6 Limiti -->
      <section class="capitolo" id="limiti" aria-labelledby="t-limiti">
        <div class="testata compare"><span class="testata__n">§ 6</span><p class="etichetta" style="padding-top:.55em">Limits</p></div>
        <div class="limiti compare">
          <h2 class="titolo-2" id="t-limiti">Before you use an answer, know this.</h2>
          <ol>
            <li><div><p>The generated text can contain errors or omissions.</p><p>The guarantees check groups, voices and quotes. The rest of the answer is written by a model.</p></div></li>
            <li><div><p>A relevant speech may not be retrieved.</p><p>The search finds a lot, not everything. An absence in the answer does not prove that nobody spoke about it on the floor.</p></div></li>
            <li><div><p>An exact quote is still a choice.</p><p>The system chooses the passage and the frame. The context is in the record.</p></div></li>
            <li><div><p>Authority depends on our weights.</p><p>With different weights, other people would speak. That is why we publish them.</p></div></li>
            <li><div><p>It is an independent project.</p><p>It is not affiliated with the Chamber of Deputies or the Senate of the Republic, which do not endorse it and are not responsible for it.</p></div></li>
            <li><div><p>When it matters, check the official record.</p><p>Every quote has the link. Use it.</p></div></li>
          </ol>
          <p class="limiti__piede">Found an error? Write to <a href="mailto:contatti@parliamentrag.it">contatti@parliamentrag.it</a> with the link to the answer.</p>
        </div>
      </section>

      <!-- § 7 Fonti -->
      <section class="capitolo" id="fonti" aria-labelledby="t-fonti">
        <div class="testata compare"><span class="testata__n">§ 7</span><p class="etichetta" style="padding-top:.55em">Sources</p></div>
        <h2 class="titolo-2 compare" id="t-fonti">The method in full.</h2>
        <div class="fonti compare">
          <a class="fonte" href="https://emeierkeio.github.io/papers/who-speaks-matters-iswc2026.pdf" rel="noopener">
            <span class="etichetta">Paper · ISWC 2026</span>
            <span><span class="fonte__t">Who Speaks Matters: Authority-Aware Multi-View Retrieval-Augmented Generation over Italian Parliamentary Proceedings</span><span class="fonte__d">M. Tritella, R. Pozzi, M. Palmonari. Pipeline, weights and evaluation.</span></span>
            <span class="etichetta">PDF ↗</span>
          </a>
          <a class="fonte" href="https://arxiv.org/abs/2608.13410" rel="noopener">
            <span class="etichetta">Preprint</span>
            <span><span class="fonte__t">arXiv 2608.13410</span><span class="fonte__d">The same research, in open access.</span></span>
            <span class="etichetta">arXiv ↗</span>
          </a>
          <a class="fonte" href="https://orkg.org/papers/R1909763" rel="noopener">
            <span class="etichetta">Structured record</span>
            <span><span class="fonte__t">Open Research Knowledge Graph</span><span class="fonte__d">Problem, method and results in a form you can compare with other work.</span></span>
            <span class="etichetta">ORKG ↗</span>
          </a>
          <a class="fonte" href="/en/verification">
            <span class="etichetta">On this site</span>
            <span><span class="fonte__t">Verification</span><span class="fonte__d">The public verifier of the three guarantees, under construction.</span></span>
            <span class="etichetta">→</span>
          </a>
          <a class="fonte" href="/en/data">
            <span class="etichetta">On this site</span>
            <span><span class="fonte__t">Data</span><span class="fonte__d">The graph the method works on, ready to download.</span></span>
            <span class="etichetta">→</span>
          </a>
        </div>
      </section>
    </div>
  </div>
`,
};

export default contenuto;

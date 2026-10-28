import type { Contenuto } from "../../guscio";

const contenuto: Contenuto = {
  titolo: "Data · ParliamentRAG",
  descrizione: "The graph of the 19th legislature of the Chamber and the Senate in RDF: members of Parliament, groups, acts, sittings, speeches and votes, under the CC BY-SA 4.0 licence.",
  html: String.raw`
  <!-- Apertura -->
  <section class="apertura">
    <div class="pagina apertura__griglia">
      <div>
        <p class="etichetta compare">Open data · CC BY-SA 4.0</p>
        <h1 class="titolo-1 compare" style="--ritardo:80ms">The graph, ready to <em>download</em>.</h1>
        <p class="attacco compare" style="--ritardo:160ms">The 19th legislature of the Chamber and the Senate as an RDF graph. Members of Parliament, groups, acts, sittings, speeches and votes, linked to each other and to EuroVoc topics. It is the same graph that Stenografo, Fascicoli and Scranno use.</p>
        <div class="fila apertura__azioni compare" style="--ritardo:240ms">
          <a class="btn btn--accento" href="#scarica">Download <svg class="freccia" width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 8h10M9 4l4 4-4 4"/></svg></a>
          <a class="btn btn--linea" href="#deputato">How it is built</a>
        </div>
      </div>
      <dl class="frontespizio compare" style="--ritardo:200ms" id="frontespizio">{{frontespizio}}</dl>
    </div>
  </section>

  <!-- § 1 Numeri -->
  <section class="sezione-stretta" style="padding-top:0">
    <div class="pagina">
      <div class="testata compare"><span class="testata__n">§ 1</span><p class="etichetta" style="padding-top:.55em">In the graph, as of <span id="data-agg">{{dataAgg}}</span></p></div>
      <div id="registro">{{registro}}</div>
      <p class="nota compare" style="margin-top:var(--s-4)">Sources: open data of the Chamber (dati.camera.it) and the Senate (dati.senato.it), EuroVoc thesaurus. The figures update with the graph, after every new sitting.</p>
    </div>
  </section>

  <!-- § 2 Tre idee -->
  <section class="sezione-stretta">
    <div class="pagina">
      <div class="testata compare"><span class="testata__n">§ 2</span><p class="etichetta" style="padding-top:.55em">How it is designed</p></div>
      <h2 class="titolo-2 compare" style="margin-top:var(--s-6);max-width:20ch">An open graph anyone can reuse.</h2>
      <div class="idee">
        <article class="idea compare">
          <span class="idea__n">01</span>
          <h3 class="titolo-3">Everything has an address</h3>
          <p>People, acts, sittings, speeches and votes have a stable URI. For people we use the official one: dati.camera.it for deputies, dati.senato.it for senators. Anyone who already has that data links it to ours without conversion tables.</p>
          <div class="idea__vista" aria-label="Example of an address">
            <span class="mono">http://dati.camera.it/ocd/persona.rdf/p308912</span>
            <span class="freccia-giu" aria-hidden="true">↓</span>
            <span>Gian Antonio Girelli, deputy</span>
          </div>
        </article>
        <article class="idea compare" style="--ritardo:100ms">
          <span class="idea__n">02</span>
          <h3 class="titolo-3">Shared vocabularies</h3>
          <p>We use vocabularies that already exist. A program that knows W3C ORG understands our groups; one that knows EuroVoc reads the topics of the acts in 24 languages.</p>
          <div class="idea__vista">
            <div class="vocabolari-mini"><span class="sigla">foaf</span><span class="sigla">org</span><span class="sigla">ocd</span><span class="sigla">skos</span><span class="sigla">prov</span><span class="sigla">eurovoc</span></div>
            <span class="nota">Our own namespace covers only what is missing: <span class="mono">w3id.org/parliamentrag/ontology#</span></span>
          </div>
        </article>
        <article class="idea compare" style="--ritardo:200ms">
          <span class="idea__n">03</span>
          <h3 class="titolo-3">Elementary facts</h3>
          <p>Every piece of information is a triple: subject, relation, object. Triples can be counted, filtered and joined with other data. The export has <span id="triple-n">{{triple}}</span>.</p>
          <div class="idea__vista" aria-label="Example of a triple">
            <div class="tripla"><span>membership</span><i aria-hidden="true">→</i><span>org:organization</span><i aria-hidden="true">→</i><span>group AZ</span>
              <em>subject</em><em></em><em>relation</em><em></em><em>object</em></div>
          </div>
        </article>
      </div>
    </div>
  </section>

  <!-- § 3 Un deputato nel grafo -->
  <section class="sezione-stretta" id="deputato" style="scroll-margin-top:72px">
    <div class="pagina">
      <div class="testata compare"><span class="testata__n">§ 3</span><p class="etichetta" style="padding-top:.55em">A deputy in the graph</p></div>
      <h2 class="titolo-2 compare" style="margin-top:var(--s-6);max-width:22ch">Gian Antonio Girelli, in the PD group since 18 October 2022.</h2>
      <p class="attacco compare" style="margin-top:var(--s-4);max-width:52ch">This is how he appears in the Turtle file. Hover over a note, or select it with the keyboard, to see the lines it refers to.</p>

      <div class="estratto">
        <div class="estratto__codice compare">
          <span class="estratto__titolo">Shortened excerpt, abbreviated URIs</span>
          <pre class="codice" id="ttl"><span class="blocco" data-n="1"><span class="k">@prefix</span> foaf: <span class="s">&lt;http://xmlns.com/foaf/0.1/&gt;</span> .
<span class="k">@prefix</span> org:  <span class="s">&lt;http://www.w3.org/ns/org#&gt;</span> .
<span class="k">@prefix</span> ocd:  <span class="s">&lt;http://dati.camera.it/ocd/&gt;</span> .
<span class="k">@prefix</span> skos: <span class="s">&lt;http://www.w3.org/2004/02/skos/core#&gt;</span> .
<span class="k">@prefix</span> pro:  <span class="s">&lt;https://w3id.org/parliamentrag/ontology#&gt;</span> .
<span class="k">@prefix</span> xsd:  <span class="s">&lt;http://www.w3.org/2001/XMLSchema#&gt;</span> .
<span class="k">@base</span>   <span class="s">&lt;https://w3id.org/parliamentrag/resource/&gt;</span> .
</span>
<span class="blocco" data-n="2"><span class="c"># The deputy: the address is the Chamber's</span>
<span class="m">&lt;http://dati.camera.it/ocd/persona.rdf/p308912&gt;</span>
</span><span class="blocco" data-n="3">    <span class="k">a</span> foaf:Person, ocd:deputato ;
</span><span class="blocco" data-n="2">    foaf:givenName  <span class="s">"GIAN ANTONIO"</span> ;
    foaf:familyName <span class="s">"GIRELLI"</span> .
</span>
<span class="blocco" data-n="4"><span class="c"># The group</span>
<span class="m">&lt;group/pd&gt;</span>
    <span class="k">a</span> org:Organization, ocd:gruppoParlamentare ;
    skos:altLabel <span class="s">"PD"</span> .
</span>
<span class="blocco" data-n="5"><span class="c"># The membership: a fact of its own, with its date</span>
<span class="m">&lt;membership/p308912_pd_2022-10-18&gt;</span>
    <span class="k">a</span> org:Membership ;
    org:member       <span class="m">&lt;http://dati.camera.it/ocd/persona.rdf/p308912&gt;</span> ;
    org:organization <span class="m">&lt;group/pd&gt;</span> ;
    pro:startDate    <span class="s">"2022-10-18"</span>^^xsd:date .</span></pre>
          <button class="copia" type="button" data-copia="ttl">Copy</button>
        </div>

        <ol class="note compare" style="--ritardo:120ms" id="note">
          <li tabindex="0" data-n="1"><div><strong>Prefixes</strong><p>Abbreviations of the vocabularies used. All except <span class="mono">pro:</span> already exist and are maintained by others.</p></div></li>
          <li tabindex="0" data-n="2"><div><strong>The person</strong><p>The URI is the one of the Chamber's official profile. For senators it is the one on dati.senato.it. The same address works in any other dataset that uses it.</p></div></li>
          <li tabindex="0" data-n="3"><div><strong>Two types at once</strong><p>A person for anyone using FOAF, and a deputy in the Chamber's open data vocabulary.</p></div></li>
          <li tabindex="0" data-n="4"><div><strong>The group</strong><p>An organisation in the W3C ORG sense, the same model used for parties, public bodies and companies.</p></div></li>
          <li tabindex="0" data-n="5"><div><strong>The membership</strong><p>Links person and group with a start date, and an end date when there is one. If a deputy changes group, a new membership is created: the history stays in the graph.</p></div></li>
        </ol>
      </div>
    </div>
  </section>

  <!-- § 4 Schema -->
  <section class="sezione-stretta">
    <div class="pagina">
      <div class="testata compare"><span class="testata__n">§ 4</span><p class="etichetta" style="padding-top:.55em">The schema</p></div>
      <h2 class="titolo-2 compare" style="margin-top:var(--s-6);max-width:22ch">Nine types of node, and how they fit together.</h2>
      <div class="schema" id="schema">
        <figure class="foglio schema__figura compare">
          <p class="etichetta" style="margin-bottom:var(--s-3)">Schema, not data · pick a node</p>
          <div class="schema__scorri">
            <svg viewBox="0 62 720 362" id="schema-svg" role="group" aria-label="Graph schema: nine types of node and the relations between them"></svg>
          </div>
        </figure>
        <div class="schema-desc compare" style="--ritardo:120ms" id="schema-desc" aria-live="polite"></div>
      </div>
    </div>
  </section>

  <!-- § 5 Vocabolari -->
  <section class="sezione-stretta">
    <div class="pagina">
      <div class="testata compare"><span class="testata__n">§ 5</span><p class="etichetta" style="padding-top:.55em">Vocabularies</p></div>
      <h2 class="titolo-2 compare" style="margin-top:var(--s-6);max-width:22ch">The graph uses existing standard vocabularies.</h2>
      <div class="tabella-scorri compare vocabolari">
        <table class="tabella">
          <thead><tr><th scope="col">In the graph</th><th scope="col">Vocabulary</th><th scope="col">What it allows</th></tr></thead>
          <tbody>
            <tr><td>Deputy</td><td class="mono">ocd:deputato, foaf:Person</td><td>The Chamber's own official record, reusable anywhere. For senators, the one on dati.senato.it.</td></tr>
            <tr><td>Parliamentary group, committee</td><td class="mono">org:Organization</td><td>The W3C model for organisations.</td></tr>
            <tr><td>Membership of a group</td><td class="mono">org:Membership</td><td>Start and end: changes of group stay on record.</td></tr>
            <tr><td>Topic of an act</td><td class="mono">EuroVoc, via SKOS</td><td>The same topics in 24 languages.</td></tr>
            <tr><td>Sitting, debate, speech</td><td>The international standard for parliamentary records</td><td>A structure other parliaments already use.</td></tr>
            <tr><td>Roll call and individual vote</td><td class="mono">ocd</td><td>The Chamber's open data vocabulary.</td></tr>
            <tr><td>Provenance</td><td class="mono">prov</td><td>Every build states when it was made and from which sources.</td></tr>
          </tbody>
        </table>
      </div>
      <p class="prefissi compare">
        <span><b>foaf</b>http://xmlns.com/foaf/0.1/</span>
        <span><b>org</b>http://www.w3.org/ns/org#</span>
        <span><b>ocd</b>http://dati.camera.it/ocd/</span>
        <span><b>pro</b>https://w3id.org/parliamentrag/ontology#</span>
      </p>
    </div>
  </section>

  <!-- § 6 Scarica -->
  <section class="sezione-stretta" id="scarica" style="background:var(--carta-2);border-top:1px solid var(--filetto);scroll-margin-top:64px">
    <div class="pagina">
      <div class="testata compare"><span class="testata__n">§ 6</span><p class="etichetta" style="padding-top:.55em">Download</p></div>
      <h2 class="titolo-2 compare" style="margin-top:var(--s-6);max-width:20ch">Where to download the data.</h2>

      <div class="scarica">
        <article class="foglio deposito compare">
          <div class="deposito__testa"><span class="etichetta">Zenodo · RDF</span><span class="sigla sigla--accento">DOI</span></div>
          <div class="deposito__corpo">
            <div class="file">
              <div><p class="file__nome">parliamentrag_kg.ttl</p><p class="file__cosa">The graph in Turtle: people, groups, committees, acts, EuroVoc topics, sittings, debates and speeches with the full text.</p></div>
              <span class="sigla">Turtle</span>
            </div>
            <div class="file">
              <div><p class="file__nome">Individual votes</p><p class="file__cosa">In a separate file, because it is the largest: the vote of every member of Parliament in every roll call.</p></div>
              <span class="sigla">RDF</span>
            </div>
          </div>
          <div class="deposito__piede">
            <span class="doi" id="doi">10.5281/zenodo.21560331</span>
            <button class="btn btn--linea btn--piccolo" type="button" data-copia="doi">Copy the DOI</button>
            <a class="btn btn--accento btn--piccolo" href="https://doi.org/10.5281/zenodo.21560331" rel="noopener">Open on Zenodo <svg class="freccia-nord-est" width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3.5 8.5l5-5M4.5 3.5h4v4"/></svg></a>
          </div>
        </article>

        <article class="foglio deposito compare" style="--ritardo:100ms">
          <div class="deposito__testa"><span class="etichetta">Hugging Face · tables</span></div>
          <div class="deposito__corpo">
            <div class="file">
              <div><p class="file__nome">emeierkeio/parliamentrag-leg19</p><p class="file__cosa">The data of the 19th legislature in table form, for people who work with pandas, R or a spreadsheet rather than RDF.</p></div>
              <span class="sigla">Tables</span>
            </div>
            <div class="file">
              <div><p class="file__nome">parliamentrag-iswc / build</p><p class="file__cosa">The code that builds the graph from the open data of the Chamber and the Senate. Anyone can rebuild it from scratch and compare.</p></div>
              <span class="sigla">Code</span>
            </div>
          </div>
          <div class="deposito__piede">
            <a class="btn btn--accento btn--piccolo" href="https://huggingface.co/datasets/emeierkeio/parliamentrag-leg19" rel="noopener">Open on Hugging Face <svg class="freccia-nord-est" width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3.5 8.5l5-5M4.5 3.5h4v4"/></svg></a>
            <a class="btn btn--linea btn--piccolo" href="https://github.com/Emeierkeio/parliamentrag-iswc/tree/main/build" rel="noopener">The pipeline on GitHub <svg class="freccia-nord-est" width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3.5 8.5l5-5M4.5 3.5h4v4"/></svg></a>
          </div>
        </article>
      </div>

      <div class="avvisi compare">
        <div>
          <h3>Licence</h3>
          <p>The data is released under the <a class="collegamento" href="https://creativecommons.org/licenses/by-sa/4.0/deed.en" rel="noopener">CC BY-SA 4.0</a> licence. You can copy, modify and redistribute it, commercially too, if you credit the source and use the same licence. The sources are the open data of the Chamber (CC BY-SA 4.0) and the Senate (<a class="collegamento" href="https://creativecommons.org/licenses/by/3.0/it/" rel="noopener">CC BY 3.0</a>).</p>
        </div>
        <div>
          <h3>Snapshots</h3>
          <p>On Zenodo we publish a snapshot at major milestones, not at every update. The graph used by the systems is more recent than the latest snapshot.</p>
        </div>
        <div>
          <h3>What is not included</h3>
          <p>The export does not contain the embeddings, users' conversations or summaries written by AI. Only public data and its relations.</p>
        </div>
      </div>
    </div>
  </section>

  <!-- § 7 Interrogalo -->
  <section class="sezione-stretta">
    <div class="pagina">
      <div class="testata compare"><span class="testata__n">§ 7</span><p class="etichetta" style="padding-top:.55em">Query it</p></div>
      <div class="interroga" style="margin-top:var(--s-6)">
      <div class="compare">
        <h2 class="titolo-2">You do not need to download it to use it.</h2>
        <p class="tenue" style="margin-top:var(--s-4);max-width:46ch">An MCP server exposes the graph to the AI assistants that support it. The assistant searches the speeches and the acts, opens a debate, reads a vote or the text of an amendment, and every result links to the record.</p>
        <a class="btn btn--linea" style="margin-top:var(--s-5)" href="/en/developers">Connect an assistant <svg class="freccia" width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 8h10M9 4l4 4-4 4"/></svg></a>
      </div>
      <ul class="strumenti compare" style="--ritardo:120ms" aria-label="Tools of the MCP server">
        <li><code>search_parliament</code><span>searches the floor speeches</span></li>
        <li><code>list_sessions</code><span>lists the sittings</span></li>
        <li><code>get_debate</code><span>opens a debate</span></li>
        <li><code>get_session_votes</code><span>the votes of a sitting</span></li>
        <li><code>get_vote_details</code><span>the vote by group and by member of Parliament</span></li>
        <li><code>get_vote_hemicycle</code><span>the hemicycle of a vote</span></li>
        <li><code>get_voted_text</code><span>the text put to the vote</span></li>
        <li><code>verify_answer</code><span>checks the three guarantees on an answer</span></li>
      </ul>
      </div>
    </div>
  </section>
`,
};

export default contenuto;

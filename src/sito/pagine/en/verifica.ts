import type { Contenuto } from "../../guscio";

const contenuto: Contenuto = {
  titolo: "Verification · ParliamentRAG",
  descrizione: "The public verifier of the three guarantees: paste the answer of an AI system and check groups, authoritative voices and quotes.",
  html: String.raw`
  <!-- Apertura -->
  <section class="apertura">
    <div class="pagina apertura__griglia">
      <div>
        <p class="etichetta compare">Verification</p>
        <h1 class="titolo-1 compare" style="--ritardo:80ms">One answer, <em>three</em> checks.</h1>
        <p class="attacco compare" style="--ritardo:160ms">Paste the answer you got from an AI system: the verifier checks whether it meets the three guarantees we require of our own systems.</p>
      </div>
      <div class="cantiere compare" style="--ritardo:240ms">
        <span class="etichetta cantiere__stato cantiere__stato--attivo"><i aria-hidden="true"></i>What it covers</span>
        <p>All the floor speeches of the Chamber and the Senate, 19th legislature, updated every night. Quotes go between «…» or "…".</p>
        <p><a class="collegamento" href="#come">Read how the verification works</a></p>
      </div>
    </div>
  </section>

  <!-- § 1 Prova -->
  <section class="sezione-stretta" style="padding-top:0" id="prova">
    <div class="pagina">
      <div class="testata compare"><span class="testata__n">§ 1</span><p class="etichetta" style="padding-top:.55em">Verification · Parliament, 19th legislature</p></div>

      <div class="banco">
        <form class="banco__input compare" id="modulo" novalidate>
          <label class="titolo-4" for="domanda">The question <span class="nota">optional</span></label>
          <div class="campo">
            <input id="domanda" type="text" maxlength="300" autocomplete="off" placeholder="For example: what do the groups think about the minimum wage?">
          </div>
          <label class="titolo-4" for="risposta">The answer to check</label>
          <div class="campo campo--area">
            <textarea id="risposta" rows="14" spellcheck="false" placeholder="Paste the answer an AI system gave you about a topic debated in Parliament. Quotes go between «…» or &quot;…&quot;."></textarea>
            <div class="banco__conta"><span id="conta">0 words</span><span class="scorciatoia">⌘/Ctrl + Enter to check</span></div>
          </div>
          <div class="banco__azioni">
            <button class="btn btn--accento" type="submit" id="verifica">Check</button>
            <button class="btn btn--linea btn--piccolo" type="button" id="esempio">Paste an example</button>
            <button class="btn btn--linea btn--piccolo" type="button" id="svuota">Clear</button>
          </div>
          <p class="messaggio" id="msg" role="status"></p>
          <p class="nota">Is your answer in the <a class="collegamento" href="https://github.com/Emeierkeio/ParliamentRAG/blob/main/schema/verifiable-answer.v1.json" rel="noopener">verifiable JSON format</a>? Paste it here: I check its quotes one by one, with the rules of the <a class="collegamento" href="https://github.com/Emeierkeio/ParliamentRAG/tree/main/verifica" rel="noopener">open verifier</a>. <button class="link-bottone" type="button" id="esempio-json">Paste a JSON example</button></p>
          <p class="nota">The text reaches our server only for the check: we do not store it or log it. The question goes to OpenAI to compute authority on the topic. <a class="collegamento" href="/en/privacy">Privacy</a></p>
        </form>

        <div class="foglio esito-box compare" style="--ritardo:120ms">
          <div class="esito-box__testa">
            <span class="etichetta">Result</span>
            <span class="etichetta" id="stato">Waiting</span>
          </div>
          <div class="esito-box__corpo" id="esito" aria-live="polite" aria-busy="false">
            <div class="vuoto">
              <div class="sigillo" aria-hidden="true">
                <span class="sigillo__da">Check</span>
                <span class="sigillo__voce" data-esito="nd">All groups</span>
                <span class="sigillo__voce" data-esito="nd">Authoritative voices</span>
                <span class="sigillo__voce" data-esito="nd">Exact quotes</span>
              </div>
              <p>Paste an answer, or use the example, and press Check. The result appears here, guarantee by guarantee.</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>

  <!-- § 2 Cosa controlla -->
  <section class="sezione-stretta" id="come">
    <div class="pagina">
      <div class="testata compare"><span class="testata__n">§ 2</span><p class="etichetta" style="padding-top:.55em">What it checks, and how</p></div>
      <h2 class="titolo-2 compare" style="margin-top:var(--s-6);max-width:22ch">Three checks across the whole 19th legislature.</h2>
      <p class="attacco compare" style="margin-top:var(--s-4);max-width:52ch">The same ones we apply to the answers of our own systems. The verifier uses no language model: with the same data, the same answer gets the same result.</p>
      <div class="tabella-scorri compare confronto-v">
        <table class="tabella">
          <thead><tr><th scope="col">Guarantee</th><th scope="col">What it checks</th><th scope="col">When it passes</th></tr></thead>
          <tbody>
            <tr>
              <td>All groups</td>
              <td data-l="What it checks">Looks in the text for the acronym or name of every group in office, of the Mixed Group components with deputies or senators and of the Government. A senator in the Mixed Group counts for their component, for example Cucchi for AVS. The list comes from the graph, not from a hand-written list.</td>
              <td data-l="When it passes">Every voice is named or quoted. A word identical to a name counts even if it is used in another sense.</td>
            </tr>
            <tr>
              <td>Exact quotes</td>
              <td data-l="What it checks">Looks for every text in quotation marks, four words or longer, in all the floor speeches. It shows who said it, when, and the link to the record.</td>
              <td data-l="When it passes">Every quote is a continuous stretch of one speech and the speaker's surname appears nearby. Only spaces, typographic apostrophes and the initial capital may differ; ellipses and skipped words may not.</td>
            </tr>
            <tr>
              <td>Authoritative voices</td>
              <td data-l="What it checks">For every member of Parliament or of the Government quoted or named (by full name, or by surname when there are no namesakes) it computes authority on the topic of the question, with the six public criteria and weights, and their rank among the members of their group who spoke on the topic. It flags a wrong group written next to a name.</td>
              <td data-l="When it passes">The speaker is a member of the Government, the rapporteur of the bill or one of the top five of their group among those who spoke on the topic (all of them, if fewer than five did). Without a question, the topic comes from the first lines of the answer.</td>
            </tr>
          </tbody>
        </table>
      </div>
      <details class="domanda alias compare">
        <summary>Names the verifier uses to recognise the groups</summary>
        <div class="tabella-scorri">
          <table class="tabella">
            <thead><tr><th scope="col">Voice</th><th scope="col">Acronyms, only as written</th><th scope="col">Names, any capitalisation</th></tr></thead>
            <tbody id="alias"></tbody>
          </table>
        </div>
      </details>
    </div>
  </section>

  <!-- § 3 Perché -->
  <section class="sezione-stretta" style="background:var(--carta-2);border-top:1px solid var(--filetto)">
    <div class="pagina">
      <div class="testata compare"><span class="testata__n">§ 3</span><p class="etichetta" style="padding-top:.55em">Why a verifier</p></div>
      <div class="perche">
        <h2 class="titolo-2 compare">The data is public. The guarantees, so far, are not.</h2>
        <div class="perche__testo compare" style="--ritardo:120ms">
          <p>The Chamber and the Senate publish records, acts and votes. Yet people who get an answer from an AI assistant have no simple way to know whether a group is missing or a quote has been altered.</p>
          <p><strong>A check that depends on whoever wrote the answer is not enough.</strong> That is why the verifier applies the same rules to every answer, ours included.</p>
          <p>The method is described above. The same check is the <code>verify_answer</code> tool of our <a class="collegamento" href="/en/developers#mcp">MCP server</a>. You can also check quotes on your own computer, with the open data: <code>pip install ./verifica</code> from the <a class="collegamento" href="https://github.com/Emeierkeio/ParliamentRAG" rel="noopener">repository</a>, then <code>parliamentrag-verifica answer.json</code>. If you have hard cases, answers that fool a check or ideas on what to measure, write to us.</p>
          <div class="fila" style="margin-top:var(--s-2)">
            <a class="btn btn--accento" href="#come">How the verification works</a>
            <a class="btn btn--linea" href="/en/method">How we apply the guarantees</a>
          </div>
          <p class="nota">Write to <a class="collegamento" href="mailto:contatti@parliamentrag.it">contatti@parliamentrag.it</a>.</p>
        </div>
      </div>
    </div>
  </section>
`,
};

export default contenuto;

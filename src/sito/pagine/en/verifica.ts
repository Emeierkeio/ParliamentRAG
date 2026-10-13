import type { Contenuto } from "../../guscio";

const contenuto: Contenuto = {
  titolo: "Verification · ParliamentRAG",
  descrizione: "The public verifier of the three guarantees, under construction: paste an answer about Parliament and check groups, voices and quotes.",
  html: String.raw`
  <!-- Apertura -->
  <section class="apertura">
    <div class="pagina apertura__griglia">
      <div>
        <p class="etichetta compare">Verification</p>
        <h1 class="titolo-1 compare" style="--ritardo:80ms">One answer, <em>three</em> checks.</h1>
        <p class="attacco compare" style="--ritardo:160ms">We are building a public verifier: you give it an answer about Parliament and it tells you whether it meets the three guarantees. It will work with answers from any system, ours included.</p>
      </div>
      <div class="cantiere compare" style="--ritardo:240ms">
        <span class="etichetta cantiere__stato"><i aria-hidden="true"></i>Under construction</span>
        <p>Below is a preview that runs in your browser. It works on a single topic, the minimum wage, and knows only the 11 verified quotes of the example.</p>
        <p><a class="collegamento" href="https://github.com/Emeierkeio/ParliamentRAG/blob/main/docs/piano-verifica.md" rel="noopener">Read the verification plan (in Italian)</a></p>
      </div>
    </div>
  </section>

  <!-- § 1 Prova -->
  <section class="sezione-stretta" style="padding-top:0" id="prova">
    <div class="pagina">
      <div class="testata compare"><span class="testata__n">§ 1</span><p class="etichetta" style="padding-top:.55em">Preview · minimum wage topic</p></div>

      <div class="banco">
        <form class="banco__input compare" id="modulo" novalidate>
          <label class="titolo-4" for="risposta">The answer to check</label>
          <div class="campo campo--area">
            <textarea id="risposta" rows="14" spellcheck="false" placeholder="Paste an answer about the minimum wage here. Quotes go between «…» or &quot;…&quot;."></textarea>
            <div class="banco__conta"><span id="conta">0 words</span><span class="scorciatoia">⌘/Ctrl + Enter to check</span></div>
          </div>
          <div class="banco__azioni">
            <button class="btn btn--accento" type="submit" id="verifica">Check</button>
            <button class="btn btn--linea btn--piccolo" type="button" id="esempio">Paste an example</button>
            <button class="btn btn--linea btn--piccolo" type="button" id="svuota">Clear</button>
          </div>
          <p class="messaggio" id="msg" role="status"></p>
          <p class="nota">The text stays in your browser: the preview does not send it to any server.</p>
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

  <!-- § 2 Anteprima e versione pubblica -->
  <section class="sezione-stretta">
    <div class="pagina">
      <div class="testata compare"><span class="testata__n">§ 2</span><p class="etichetta" style="padding-top:.55em">What it checks, and how</p></div>
      <h2 class="titolo-2 compare" style="margin-top:var(--s-6);max-width:22ch">The preview runs two checks out of three, on a small corpus.</h2>
      <p class="attacco compare" style="margin-top:var(--s-4);max-width:52ch">The public version will use the whole graph of the 19th legislature. Below, for each guarantee, what this page does today and what the verifier will do.</p>
      <div class="tabella-scorri compare confronto-v">
        <table class="tabella">
          <thead><tr><th scope="col">Guarantee</th><th scope="col">Preview, on this page</th><th scope="col">Public verifier</th></tr></thead>
          <tbody>
            <tr>
              <td>All groups</td>
              <td data-l="Preview">Looks in the text for the acronym or the name of each of the ten groups of the topic and of the Government. A word identical to a name counts as a mention even if it is used in another sense.</td>
              <td data-l="Public verifier">Compares the groups quoted with those in office on the date of the question, components of the Mixed Group included, and looks for the sentence that states a group is absent.</td>
            </tr>
            <tr>
              <td>Exact quotes</td>
              <td data-l="Preview">Extracts the text between «…» or "…", normalises spaces and apostrophes and compares it word for word with the 11 quotes of the example. Part of a quote also counts.</td>
              <td data-l="Public verifier">Looks for every quote in all the speeches in the Chamber, checks that the speaker is the one stated and returns the link to the record.</td>
            </tr>
            <tr>
              <td>Authoritative voices</td>
              <td data-l="Preview">Not checked. It needs the authority scores for the question, which we do not have here.</td>
              <td data-l="Public verifier">Computes authority on the topic with the six public criteria and checks that for each group the speaker is a rapporteur, a member of the Government or one of the top five.</td>
            </tr>
          </tbody>
        </table>
      </div>
      <details class="domanda alias compare">
        <summary>Names the preview uses to recognise the groups</summary>
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
          <p>The Chamber publishes records, acts and votes. Yet people who get an answer from an AI assistant have no simple way to know whether a group is missing or a quote has been altered.</p>
          <p><strong>A check that depends on whoever wrote the answer is not enough.</strong> That is why the verifier will be separate from our systems and will work with anyone's answers.</p>
          <p>The method is described in the verification plan. If you have hard cases, answers that fool a check or ideas on what to measure, write to us.</p>
          <div class="fila" style="margin-top:var(--s-2)">
            <a class="btn btn--accento" href="https://github.com/Emeierkeio/ParliamentRAG/blob/main/docs/piano-verifica.md" rel="noopener">The verification plan <svg class="freccia-nord-est" width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3.5 8.5l5-5M4.5 3.5h4v4"/></svg></a>
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

import type { Contenuto } from "../../guscio";

const contenuto: Contenuto = {
  titolo: "Developers · ParliamentRAG",
  descrizione: "MCP server to connect an AI assistant to the official data of the Chamber and the Senate, HTTP API on request and graph dumps with a DOI.",
  html: String.raw`
  <!-- Apertura -->
  <section class="apertura">
    <div class="pagina apertura__griglia">
      <div>
        <p class="etichetta compare">Developers</p>
        <h1 class="titolo-1 compare" style="--ritardo:80ms">Connect your AI assistant to the <em>records</em>.</h1>
        <p class="attacco compare" style="--ritardo:160ms">The ParliamentRAG MCP server gives your assistant the official records of the Chamber and the Senate: speeches, acts, sittings, votes. Every result links to the source.</p>
        <div class="fila clienti compare" style="--ritardo:220ms" aria-label="Compatible clients">
          <span class="sigla">Claude</span><span class="sigla">ChatGPT</span><span class="sigla">Cursor</span><span class="sigla">VS Code</span><span class="sigla">and other MCP clients</span>
        </div>
      </div>
      <div class="foglio galleggia indirizzo compare" style="--ritardo:200ms">
        <p class="etichetta">Remote server · nothing to install</p>
        <div class="indirizzo__url">
          <code id="url-mcp">https://mcp.parliamentrag.it/mcp</code>
          <button class="btn btn--linea btn--piccolo" type="button" data-copia="url-mcp">Copy</button>
        </div>
        <p class="nota">Add it as a remote MCP server in your client's settings. <a class="collegamento" href="https://github.com/Emeierkeio/ParliamentRAG/blob/main/docs/mcp.md" rel="noopener">Guide for each client</a>.</p>
      </div>
    </div>
  </section>

  <!-- MCP -->
  <section class="sezione-stretta" id="mcp" style="padding-top:0">
    <div class="pagina">
      <div class="testata compare"><span class="testata__n">§ 1</span><p class="etichetta" style="padding-top:.55em">MCP server</p></div>

      <div class="mcp">
        <div class="istruzioni compare">
          <h2 class="titolo-3">How to connect it</h2>
          <div class="schede" role="tablist" aria-label="Connection method">
            <button type="button" role="tab" id="tab-remoto" aria-controls="pan-remoto" aria-selected="true">Remote endpoint</button>
            <button type="button" role="tab" id="tab-claude" aria-controls="pan-claude" aria-selected="false" tabindex="-1">Claude Code</button>
          </div>

          <div role="tabpanel" id="pan-remoto" aria-labelledby="tab-remoto">
            <p>The server runs on our side. In your client, add a remote MCP server with this address.</p>
            <div class="blocco-codice">
              <pre class="codice codice--a-capo" id="cod-remoto">https://mcp.parliamentrag.it/mcp</pre>
              <button class="copia" type="button" data-copia="cod-remoto">Copy</button>
            </div>
            <p class="nota">Each client has its own menu. The steps for Claude, ChatGPT, Cursor and VS Code are in the <a class="collegamento" href="https://github.com/Emeierkeio/ParliamentRAG/blob/main/docs/mcp.md" rel="noopener">guide</a>.</p>
          </div>

          <div role="tabpanel" id="pan-claude" aria-labelledby="tab-claude" hidden>
            <p>To run it on your computer with Claude Code, run this command in the terminal.</p>
            <div class="blocco-codice">
              <pre class="codice codice--a-capo" id="cod-claude"><span class="k">claude</span> mcp add parliamentrag -- uvx --from <span class="s">"git+https://github.com/Emeierkeio/parliamentrag-iswc.git#subdirectory=mcp"</span> parliamentrag-mcp</pre>
              <button class="copia" type="button" data-copia="cod-claude">Copy</button>
            </div>
            <p class="nota">The command uses <span class="mono">uvx</span>: you need uv installed. The server code is in the <span class="mono">mcp</span> folder of the <a class="collegamento" href="https://github.com/Emeierkeio/parliamentrag-iswc/tree/main/mcp" rel="noopener">repository</a>.</p>
          </div>
        </div>

        <div class="compare" style="--ritardo:120ms">
          <h2 class="titolo-3">Seven tools</h2>
          <p class="tenue piccolo" style="margin-top:var(--s-2);margin-bottom:var(--s-4)">The assistant picks them on its own, based on the question.</p>
          <ol class="strumenti" id="strumenti">
            <li class="strumento" data-s="search_parliament"><code>search_parliament</code><span>Hybrid search over speeches and acts of the Chamber and the Senate.</span></li>
            <li class="strumento" data-s="list_sessions"><code>list_sessions</code><span>Sittings of the Chamber and the Senate, with summary and debates.</span></li>
            <li class="strumento" data-s="get_debate"><code>get_debate</code><span>A debate: summary, acts, speakers.</span></li>
            <li class="strumento" data-s="get_session_votes"><code>get_session_votes</code><span>The votes of a sitting.</span></li>
            <li class="strumento" data-s="get_vote_details"><code>get_vote_details</code><span>A vote: results by group and individual votes.</span></li>
            <li class="strumento" data-s="get_vote_hemicycle"><code>get_vote_hemicycle</code><span>The hemicycle of a vote, as an image.</span></li>
            <li class="strumento" data-s="get_voted_text"><code>get_voted_text</code><span>The text voted on: amendments, articles, motions.</span></li>
          </ol>
        </div>
      </div>

      <!-- Domande d'esempio -->
      <div class="esempi">
        <div class="compare">
          <p class="etichetta">Example questions</p>
          <h2 class="titolo-3" style="margin-top:var(--s-3)">What you can ask</h2>
          <p class="tenue piccolo" style="margin-top:var(--s-3);max-width:40ch">Pick a question: the tools the assistant would use to answer light up. We show no answers here: your assistant gives them, with the sources.</p>
        </div>
        <div class="compare" style="--ritardo:120ms">
          <div class="esempi__lista" id="esempi" role="group" aria-label="Example questions">
            <button class="esempio" type="button" aria-pressed="false" data-strumenti="list_sessions get_session_votes get_vote_details get_vote_hemicycle">Who voted against the confidence vote of 7 October? <svg class="freccia" width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 8h10M9 4l4 4-4 4"/></svg></button>
            <button class="esempio" type="button" aria-pressed="false" data-strumenti="search_parliament get_debate">What did the groups say in the Chamber about the minimum wage? <svg class="freccia" width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 8h10M9 4l4 4-4 4"/></svg></button>
            <button class="esempio" type="button" aria-pressed="false" data-strumenti="list_sessions get_session_votes get_voted_text">Which amendments did the Chamber vote on in the last sitting? <svg class="freccia" width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 8h10M9 4l4 4-4 4"/></svg></button>
          </div>
          <p class="percorso" id="percorso" aria-live="polite">No question selected.</p>
        </div>
      </div>
    </div>
  </section>

  <!-- API -->
  <section class="sezione-stretta" id="api">
    <div class="pagina">
      <div class="testata compare"><span class="testata__n">§ 2</span><p class="etichetta" style="padding-top:.55em">HTTP API · on request</p></div>
      <h2 class="titolo-2 compare" style="margin-top:var(--s-6);max-width:22ch">The same queries our systems use, in JSON.</h2>
      <div class="api">
        <ul class="offre compare">
          <li><strong>Search</strong>Hybrid search over floor speeches and acts.</li>
          <li><strong>Sittings and debates</strong>Summaries, acts discussed and speakers.</li>
          <li><strong>Votes</strong>Results by group and the vote of every member of Parliament.</li>
          <li><strong>Statistics</strong>Graph figures and the index of the open data.</li>
        </ul>
        <div class="token compare" style="--ritardo:120ms">
          <p class="etichetta">Why you need a token</p>
          <p>Every request has a computing cost. That is why access is personal: we give you a token and we know who each request belongs to.</p>
          <p>Write to us with who you are and what you want to build.</p>
          <div class="fila">
            <a class="btn btn--accento" href="mailto:contatti@parliamentrag.it?subject=ParliamentRAG%20API%20token%20request">Request a token</a>
          </div>
          <p class="nota">Or write to <span class="mono">contatti@parliamentrag.it</span>. What we keep from the requests is explained in the <a class="collegamento" href="/en/privacy">privacy notice</a>.</p>
        </div>
      </div>
    </div>
  </section>

  <!-- Dump -->
  <section class="sezione-stretta" id="dump">
    <div class="pagina">
      <div class="testata compare"><span class="testata__n">§ 3</span><p class="etichetta" style="padding-top:.55em">Dumps and datasets</p></div>
      <h2 class="titolo-2 compare" style="margin-top:var(--s-6);max-width:22ch">The whole graph, ready to download.</h2>
      <p class="tenue compare" style="margin-top:var(--s-3);max-width:52ch">If you need everything, not one question at a time, download the data. No token needed.</p>
      <div class="dump compare">
        <a class="dump__voce" href="/en/data">
          <span class="dump__nome">RDF Turtle</span>
          <span class="dump__cosa">The graph export, from the Data page.</span>
          <span class="dump__dove">parliamentrag.it/en/data</span>
        </a>
        <a class="dump__voce" href="https://doi.org/10.5281/zenodo.21560331" rel="noopener">
          <span class="dump__nome">Zenodo</span>
          <span class="dump__cosa">The archived dataset, with a DOI to cite.</span>
          <span class="dump__dove">doi.org/10.5281/zenodo.21560331</span>
        </a>
        <a class="dump__voce" href="https://huggingface.co/datasets/emeierkeio/parliamentrag-leg19" rel="noopener">
          <span class="dump__nome">Hugging Face</span>
          <span class="dump__cosa">The dataset of the Chamber, 19th legislature.</span>
          <span class="dump__dove">emeierkeio/parliamentrag-leg19</span>
        </a>
        <a class="dump__voce" href="https://github.com/Emeierkeio/parliamentrag-iswc/tree/main/build" rel="noopener">
          <span class="dump__nome">Pipeline</span>
          <span class="dump__cosa">The code that builds the graph from the open data.</span>
          <span class="dump__dove">parliamentrag-iswc/build</span>
        </a>
      </div>
    </div>
  </section>

  <!-- Licenza -->
  <section class="sezione-stretta" id="licenza">
    <div class="pagina">
      <div class="testata compare"><span class="testata__n">§ 4</span><p class="etichetta" style="padding-top:.55em">Licence</p></div>
      <div class="licenza">
        <h2 class="titolo-3 compare">The data stays the Chamber's and the Senate's, under their licences.</h2>
        <div class="prosa compare" style="--ritardo:120ms">
          <p>The data comes from the open data of the Chamber of Deputies, under the <a href="https://creativecommons.org/licenses/by-sa/4.0/deed.en" rel="noopener">CC BY-SA 4.0</a> licence, and of the Senate of the Republic, under the <a href="https://creativecommons.org/licenses/by/3.0/it/deed.en" rel="noopener">CC BY 3.0</a> licence. If you reuse it, credit the Chamber or the Senate as the source. For Chamber data, share derived work under the same licence.</p>
          <p>The rules for using the service are in the <a href="/en/terms">terms</a>. For automated access, ask for a token instead of downloading the pages.</p>
        </div>
      </div>
    </div>
  </section>
`,
};

export default contenuto;

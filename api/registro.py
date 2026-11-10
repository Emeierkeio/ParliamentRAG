"""Registro degli strumenti: nome, descrizione, parametri tipizzati (Pydantic) e la funzione su Postgres. Dallo stesso
registro nascono gli schemi per l'agente (function calling di OpenAI) e la lista del server MCP: uno strumento si
aggiunge qui una volta sola."""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

import psycopg
from pydantic import BaseModel, ConfigDict, Field

from .strumenti import agenda, atti, citazioni, conti, documenti, emendamenti, fatti, persone, ricerca, sedute, significato, soggetti, voti

Ramo = Literal["camera", "senato"]
Iniziativa = Field(None, description="categoria (governo, parlamentare, regione, cnel, popolare, mista) o parole del presentatore "
                                     "come le scrive la fonte («Regione Toscana», «Consiglio regionale della Lombardia»)")
SommaRami = Field(False, description="vero solo se la domanda chiede il totale dei due rami insieme; se no il conto si divide per ramo")


class Parametri(BaseModel):
    model_config = ConfigDict(extra="forbid")


@dataclass(frozen=True)
class Strumento:
    nome: str
    descrizione: str
    parametri: type[Parametri]
    esegui: Callable[[psycopg.Connection, Parametri], object]

    def schema(self) -> dict:
        s = self.parametri.model_json_schema()
        s.pop("title", None)
        for p in s.get("properties", {}).values():
            p.pop("title", None)
        return s


def _json(x) -> object:
    """Modelli Pydantic, liste e tuple (totale, elementi) in dati JSON semplici."""
    if isinstance(x, BaseModel):
        return x.model_dump(mode="json", exclude_none=True)
    if isinstance(x, tuple) and len(x) == 2 and isinstance(x[0], int):
        return {"total": x[0], "items": _json(x[1])}
    if isinstance(x, list):
        return [_json(y) for y in x]
    return x


class CercaPersone(Parametri):
    q: str | None = Field(None, description="nome o cognome, anche parziale")
    chamber: Ramo | None = Field(None, description="ramo; vuoto per Camera e Senato")
    group: str | None = Field(None, description="sigla o uri del gruppo; il Misto comprende le sue componenti")
    in_office: bool | None = Field(True, description="vero: solo chi è in carica oggi; falso: anche chi non lo è più (per le domande sul passato)")
    limit: int = Field(20, ge=1, le=100)


class Uri(Parametri):
    uri: str


class Articolo(Parametri):
    code: str = Field(description="codice della versione del testo, dal campo versions di atto")
    number: str | None = Field(None, description="numero dell'articolo («2», «3-bis»); senza, l'elenco degli articoli")


class Composizione(Parametri):
    chamber: Ramo
    date: dt.date | None = Field(None, description="la data; vuota per oggi")


class ElencoSedute(Parametri):
    chamber: Ramo | None = None
    body: str | None = Field(None, description="«aula», «commissioni» o l'uri di un organo")
    start: dt.date | None = None
    end: dt.date | None = None
    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0)


class Argomenti(Parametri):
    chamber: Ramo | None = None
    body: str | None = Field(None, description="organo: «aula», parte del nome («XIV Commissione», «Bilancio») o uri")
    seat: str | None = Field(None, description="sede, parte del nome: «SEDE LEGISLATIVA», «ATTI DELL'UNIONE EUROPEA», «SEDE REFERENTE»")
    stage: str | None = Field(None, description="fase del punto, parte del testo: «approvazione», «conclusione», «rinvio»")
    q: str | None = Field(None, description="parole del titolo del punto: «fine seduta», «question time», un atto")
    start: dt.date | None = None
    end: dt.date | None = None
    limit: int = Field(50, ge=1, le=100)
    offset: int = Field(0, ge=0)


class ContaSedute(Parametri):
    chamber: Ramo | None = None
    body: str | None = Field("aula", description="«aula» o l'uri di un organo")
    start: dt.date | None = None
    end: dt.date | None = None
    by_month: bool = False


class Seduta(Parametri):
    uri: str
    full_text: bool = Field(False, description="testo intero degli interventi; senza, i primi 150 caratteri (per il contenuto usa cerca_interventi)")


class ElencoVotazioni(Parametri):
    q: str | None = Field(None, description="parole del voto o dell'atto votato (titolo e testo); sintassi di ricerca web")
    chamber: Ramo | None = None
    act: str | None = Field(None, description="uri dell'atto votato")
    kind: str | None = Field(None, description="final, article, amendment, agenda_order, motion, resolution, confidence…")
    final: bool | None = Field(None, description="solo le votazioni finali")
    confidence: bool | None = Field(None, description="vero: solo le questioni di fiducia (alla Camera si votano sugli articoli)")
    start: dt.date | None = None
    end: dt.date | None = None
    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0)


class Votazione(Parametri):
    uri: str
    with_ballots: bool = Field(False, description="anche il voto di ogni parlamentare (lungo: solo per «chi ha votato…»)")


class CercaAtti(Parametri):
    q: str | None = Field(None, description="parole del titolo; sintassi di ricerca web: «\"frase\"», «-parola», «or»")
    chamber: Ramo | None = None
    kind: str | None = Field(None, description="bill, written_question, oral_question, interpellation, motion, resolution, agenda_order…")
    number: str | None = Field(None, description="numero dell'atto: 1695, 5-04321")
    signer: str | None = Field(None, description="uri di un firmatario")
    initiative: str | None = Iniziativa
    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0)


class CercaEmendamenti(Parametri):
    testo: str | None = Field(None, min_length=3, max_length=6000, description="un tema, una frase o il testo di una bozza di emendamento: "
                              "cerca per significato in tutta la legislatura, dal più vicino")
    q: str | None = Field(None, description="parole del testo dell'emendamento («\"frase esatta\"», «-parola», «or»)")
    act: str | None = Field(None, description="uri del progetto di legge; vuoto: tutta la legislatura")
    number: str | None = Field(None, description="numero dell'emendamento come lo scrive la fonte («1.1», «2.0.3», «Tab. 2.1»)")
    chamber: Ramo | None = None
    group: str | None = Field(None, description="nome, sigla o uri del gruppo di un firmatario alla data")
    signer: str | None = Field(None, description="uri di un firmatario")
    outcome: Literal[tuple(emendamenti.CODICI)] | None = Field(None, description="esito calcolato (vedi il campo esito dei risultati)")
    venue: Literal["committee", "assembly"] | None = Field(None, description="commissione o Aula")
    start: dt.date | None = None
    end: dt.date | None = None
    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0)


class TemaProposto(Parametri):
    nome: str = Field(min_length=2, max_length=80, description="il tema come lo capisce un utente («Sugar tax»)")
    parole: str = Field(min_length=2, max_length=200, description="le parole con cui il Parlamento ne parla, sintassi di ricerca: "
                        "«\"bevande edulcorate\" or \"sugar tax\"»")


class ProponiTemi(Parametri):
    soggetto: str = Field(min_length=2, max_length=120, description="l'azienda, l'associazione o l'ente chiesto dall'utente")
    temi: list[TemaProposto] = Field(min_length=1, max_length=8, description="i temi parlamentari che probabilmente lo riguardano")
    associazioni: list[str] = Field(default_factory=list, max_length=4, description="le sue associazioni di categoria, se ne ha")


class ChiediSettore(Parametri):
    soggetto: str = Field(min_length=2, max_length=120, description="l'azienda o l'ente di cui non si capisce il settore")


class Emendamento(Parametri):
    uri: str = Field(description="uri dell'emendamento (dai risultati di cerca_emendamenti)")


class CercaInterventi(Parametri):
    q: str = Field(min_length=2, max_length=200, description="parole da cercare nel testo; «\"frase esatta\"», «-parola», «or»")
    chamber: Ramo | None = None
    person: str | None = Field(None, description="uri di chi parla")
    start: dt.date | None = None
    end: dt.date | None = None
    include_summaries: bool = Field(True, description="anche i riassunti delle commissioni, che non si citano tra virgolette")
    captions: bool = Field(False, description="cerca nelle didascalie del resoconto (applausi, proteste, commenti, «si levano in piedi»…) "
                                              "invece che nel parlato: tutte le parole, anche parziali; l'estratto è il parlato che precede la didascalia")
    limit: int = Field(10, ge=1, le=50)
    offset: int = Field(0, ge=0)


class CercaPerSignificato(Parametri):
    testo: str = Field(min_length=3, max_length=500, description="il tema o la frase, in italiano, detto come lo direbbe un parlamentare")
    fonti: list[Literal["interventi", "atti", "documenti", "emendamenti"]] = Field(
        default_factory=lambda: ["interventi"], min_length=1, description="dove cercare; vuoto: gli interventi")
    ramo: Ramo | None = Field(None, description="ramo; vuoto per Camera e Senato")
    da: dt.date | None = Field(None, description="dal giorno (della seduta, dell'atto o del documento)")
    a: dt.date | None = Field(None, description="fino al giorno, incluso")
    quanti: int = Field(10, ge=1, le=30)


class Organo(Parametri):
    q: str | None = Field(None, description="nome o uri dell'organo: «X Commissione» (Camera, numeri romani), «8ª Commissione» o «8» (Senato), "
                                            "«Giunta per le elezioni», «affari sociali»; vuoto: le commissioni permanenti")
    chamber: Ramo | None = None
    date: dt.date | None = Field(None, description="la data delle cariche; vuota per oggi")
    titles: list[Literal["chair", "vice_chair", "secretary", "quaestor"]] | None = Field(None, description="solo queste cariche")


class FiltriVoti(Parametri):
    kind: str | None = Field(None, description="final, article, amendment, agenda_order, motion, resolution, confidence, other…")
    final: bool | None = Field(None, description="vero: solo le votazioni finali (vote.final)")
    approved: bool | None = Field(None, description="vero: approvate; falso: respinte")
    confidence: bool | None = Field(None, description="vero: solo le questioni di fiducia")
    act: str | None = Field(None, description="uri dell'atto votato")
    q: str | None = Field(None, description="parole del voto o dell'atto votato (titolo e testo)")
    start: dt.date | None = None
    end: dt.date | None = None


class ContaVotazioni(FiltriVoti):
    chamber: Ramo | None = None
    secret: bool | None = Field(None, description="vero: solo le segrete; falso: solo le palesi")
    group_by: list[Literal["ramo", "tipo", "esito", "anno", "mese", "finale", "segreta", "fiducia"]] = Field(default_factory=list)
    sum_chambers: bool = SommaRami
    limit: int = Field(100, ge=1, le=200)
    offset: int = Field(0, ge=0)


class VotoGruppi(FiltriVoti):
    chamber: Ramo
    groups: list[str] | None = Field(None, max_length=20, description="sigle, nomi o uri dei gruppi da mostrare; con due gruppi anche "
                                                                     "l'elenco delle votazioni in cui hanno preso posizioni diverse")
    person: str | None = Field(None, description="uri di un parlamentare: quanto ha votato come ciascun gruppo, diviso per il gruppo che aveva al voto")
    limit: int = Field(50, ge=1, le=200, description="righe dell'elenco delle posizioni diverse")
    offset: int = Field(0, ge=0)


class Presenze(Parametri):
    chamber: Ramo
    persons: list[str] | None = Field(None, max_length=50, description="uri dei parlamentari")
    group: str | None = Field(None, description="sigla, nome o uri del gruppo: le schede date da membri del gruppo")
    government: bool = Field(False, description="vero: chi ha avuto un incarico in un governo della legislatura durante il mandato")
    kind: str | None = None
    final: bool | None = None
    start: dt.date | None = None
    end: dt.date | None = None
    order_by: Literal["voted", "absent", "mission", "favor", "against", "abstain"] = "voted"
    limit: int = Field(50, ge=1, le=200)
    offset: int = Field(0, ge=0)


class ContaInterventi(Parametri):
    chamber: Ramo | None = None
    body: str | None = Field("aula", description="«aula», «commissioni», l'uri di un organo, o vuoto per tutto")
    phrase: str | None = Field(None, min_length=2, max_length=100, description="parola o frase esatta (parole intere, maiuscole "
                                                                               "indifferenti): conta gli interventi che la contengono e le occorrenze")
    person: str | None = Field(None, description="uri di chi parla")
    group: str | None = Field(None, description="sigla, nome o uri del gruppo di chi parla alla data")
    role: Literal["parlamentare", "governo", "presidenza", "relatore", "altro"] | None = None
    start: dt.date | None = None
    end: dt.date | None = None
    include_summaries: bool = Field(True, description="in commissione, anche i riassunti del resoconto sommario")
    words: bool = Field(False, description="conta anche le parole (più lento)")
    group_by: list[Literal["ramo", "sede", "organo", "anno", "mese", "persona", "gruppo", "ruolo", "schieramento"]] = Field(default_factory=list)
    order_by: Literal["interventi", "parole", "occorrenze"] = "interventi"
    sum_chambers: bool = SommaRami
    limit: int = Field(50, ge=1, le=200)
    offset: int = Field(0, ge=0)


class ContaReazioni(Parametri):
    chamber: Ramo | None = None
    kinds: list[Literal["applause", "protests", "comments", "noise", "laughter", "ironic_applause", "altercation", "interruption",
                        "action", "procedure", "other"]] | None = None
    body: str | None = Field("aula", description="«aula», «commissioni», l'uri di un organo, o vuoto per tutto")
    start: dt.date | None = None
    end: dt.date | None = None
    speaker: str | None = Field(None, description="uri di chi parla")
    speaker_group: str | None = Field(None, description="gruppo di chi parla")
    from_group: str | None = Field(None, description="gruppo che reagisce")
    speaker_role: Literal["parlamentare", "governo", "presidenza", "relatore", "altro"] | None = None
    contains: str | None = Field(None, description="testo dentro la didascalia, es. «in piedi»")
    group_by: list[Literal["ramo", "tipo", "anno", "mese", "gruppo_che_reagisce", "gruppo_oratore", "ruolo_oratore", "persona_oratore"]] = \
        Field(default_factory=list)
    sum_chambers: bool = SommaRami
    limit: int = Field(100, ge=1, le=200)
    offset: int = Field(0, ge=0)


class ContaAtti(Parametri):
    chamber: Ramo | None = None
    kind: str | None = Field(None, description="bill, written_question, oral_question, committee_question, interpellation, motion, resolution, agenda_order…")
    initiative: str | None = Iniziativa
    q: str | None = Field(None, description="parole del titolo")
    subject: str | None = Field(None, description="tema dei thesauri (EuroVoc), anche parte del nome: «sanit», «immigrazione»; "
                                                  "comprende i concetti più specifici")
    signer: str | None = Field(None, description="uri di un firmatario")
    first_signer: bool = Field(False, description="con signer: solo come primo firmatario")
    group: str | None = Field(None, description="gruppo del primo firmatario alla data")
    addressee: str | None = Field(None, description="ministero a cui sono rivolti (interrogazioni, interpellanze), parte del nome: «interno»")
    became_law: bool | None = Field(None, description="vero: solo gli atti diventati legge")
    start: dt.date | None = Field(None, description="presentati dal giorno")
    end: dt.date | None = None
    laws: bool = Field(False, description="vero: conta le leggi approvate una volta sola anche se l'atto è nei due rami "
                                          "(group_by: iniziativa, anno, mese, costituzionale, conversione_decreto)")
    group_by: list[Literal["ramo", "tipo", "iniziativa", "gruppo_primo_firmatario", "primo_firmatario", "anno", "mese", "legge",
                           "costituzionale", "conversione_decreto", "tema"]] = Field(
        default_factory=list, description="tema: i descrittori dei thesauri di ogni atto (un atto conta sotto ognuno dei suoi)")
    sum_chambers: bool = SommaRami
    limit: int = Field(100, ge=1, le=200)
    offset: int = Field(0, ge=0)


class ContaEmendamenti(Parametri):
    chamber: Ramo | None = None
    act: str | None = Field(None, description="uri del progetto di legge")
    outcome: str | None = None
    venue: str | None = Field(None, description="referente (commissione in sede referente, Camera), committee (commissione, Senato), "
                                                "assembly (Aula), legislativa, consultiva")
    group: str | None = Field(None, description="proposte con almeno un firmatario del gruppo")
    start: dt.date | None = None
    end: dt.date | None = None
    cross_group: bool = Field(False, description="vero: solo le proposte firmate da deputati o senatori di almeno due gruppi")
    group_by: list[Literal["ramo", "atto", "sede", "esito", "anno", "articolo", "tipo", "gruppo_primo_firmatario", "gruppo_firmatario",
                           "coppia_gruppi"]] = Field(default_factory=list, description="tipo: emendamento, articoloAggiuntivo, "
                           "subEmendamento; gruppo_primo_firmatario conta ogni proposta una volta, gruppo_firmatario una volta per gruppo")
    sum_chambers: bool = SommaRami
    limit: int = Field(100, ge=1, le=200)
    offset: int = Field(0, ge=0)


class CambiGruppo(Parametri):
    chamber: Ramo | None = None
    start: dt.date | None = None
    end: dt.date | None = None
    person: str | None = Field(None, description="uri di un parlamentare")
    group: str | None = Field(None, description="passaggi da o verso questo gruppo")
    components: bool = Field(False, description="vero: conta anche ingressi e uscite dalle componenti del Misto")
    limit: int = Field(100, ge=1, le=200)
    offset: int = Field(0, ge=0)


class Agenda(Parametri):
    start: dt.date = Field(description="primo giorno")
    end: dt.date | None = Field(None, description="ultimo giorno (al più 62 giorni dopo start); vuoto: solo start")
    chamber: Ramo | None = None
    types: list[Literal["aula", "commissioni", "termini", "atti", "voti", "leggi"]] | None = Field(
        None, description="quali eventi; vuoto: tutti. termini = scadenze per emendamenti, subemendamenti e ordini del giorno")


class FattiCommissioni(Parametri):
    kind: Literal["audizione", "parere", "interrogazione"] | None = Field(
        None, description="audizione: chi è stato sentito; parere: parere di una commissione su un atto; interrogazione: chi "
                          "risponde per il governo a un'interrogazione in commissione e la replica")
    act: str | None = Field(None, description="uri dell'atto (da cerca_atti) o riferimento come ac:3120, ddl:2074, aic:5-05944")
    subject: str | None = Field(None, description="parole del soggetto: l'ente o la persona audita, la commissione che dà il parere, chi risponde")
    body: str | None = Field(None, description="uri o parole del nome della commissione")
    chamber: Ramo | None = None
    outcome: str | None = Field(None, description="esito: favorevole, contrario, favorevole con condizioni, nulla osta, soddisfatto, insoddisfatto …")
    start: dt.date | None = None
    end: dt.date | None = None
    limit: int = Field(30, ge=1, le=100)
    offset: int = Field(0, ge=0)


class DocumentiAcquisiti(Parametri):
    uri: str | None = Field(None, description="uri di un documento (dall'elenco): ne legge il testo; senza uri si ha l'elenco")
    act: str | None = Field(None, description="uri dell'atto (da cerca_atti) o riferimento come ac:3120: i documenti depositati su quell'atto")
    author: str | None = Field(None, description="parole del nome di chi ha mandato il documento: «ANIA», «IVASS», «Confindustria»")
    body: str | None = Field(None, description="uri o nome della commissione: «X Commissione» (Camera, numeri romani)")
    kind: Literal["memoria", "contributo", "allegato", "dossier"] | None = Field(
        None, description="memoria: depositata in un'audizione; contributo: scritto mandato su un atto senza audizione; allegato: "
                          "del Bollettino; dossier: dei servizi studi. Vuoto: tutti")
    q: str | None = Field(None, description="parole nel titolo, nell'autore o nel nome dell'audizione")
    start: dt.date | None = None
    end: dt.date | None = None
    limit: int = Field(25, ge=1, le=50)
    offset: int = Field(0, ge=0, description="per l'elenco: la pagina dopo; con uri: il carattere da cui riprendere il testo")


def _documenti(c, p: DocumentiAcquisiti):
    if p.uri:
        return documenti.documento(c, p.uri, p.offset) or {"errore": "documento non trovato: prendi l'uri dall'elenco"}
    return documenti.documenti(c, p.act, p.author, p.body, p.kind, p.q, p.start, p.end, p.limit, p.offset)


class VerificaCitazioni(Parametri):
    text: str = Field(max_length=20000, description="la risposta con le citazioni tra «…»")


def _seduta(c, p: Seduta):
    s = sedute.seduta(c, p.uri)
    if s and not p.full_text:
        for i in s.items:
            for x in i.speeches:
                x.text = x.text[:150] + ("…" if len(x.text) > 150 else "")
                # le didascalie restano (applausi, proteste, «si levano in piedi»), senza i rinvii procedurali
                x.reactions = [r for r in x.reactions if r.kind != "procedure"]
    return s


def _cerca_persone(c, p: CercaPersone):
    tutte = persone.cerca_persone(c, p.q, p.chamber, p.group, p.in_office, 10_000)
    return len(tutte), tutte[:p.limit]


def _cerca_interventi(c, p: CercaInterventi):
    if p.captions:
        return ricerca.cerca_didascalie(c, p.q, p.chamber, p.person, p.start, p.end, p.limit, p.offset)
    trovati = ricerca.cerca_interventi(c, p.q, p.chamber, p.person, p.start, p.end, p.include_summaries, p.limit, p.offset)
    totale = len(trovati) + p.offset if len(trovati) < p.limit else ricerca.totale_interventi(
        c, p.q, p.chamber, p.person, p.start, p.end, p.include_summaries)
    return totale, trovati


STRUMENTI: list[Strumento] = [
    Strumento("cerca_persone", "Parlamentari della XIX legislatura per nome, ramo e gruppo, con il gruppo di oggi (il Misto per componente).",
              CercaPersone, _cerca_persone),
    Strumento("scheda_persona", "Scheda completa di una persona: anagrafica, mandati, gruppi, organi, cariche di governo, numero di interventi, voti, firme.",
              Uri, lambda c, p: persone.scheda_persona(c, p.uri)),
    Strumento("composizione", "Gruppi di un ramo alla data con il numero di membri; il Misto diviso per componente.",
              Composizione, lambda c, p: persone.composizione(c, p.chamber, p.date)),
    Strumento("elenco_sedute", "Sedute d'Aula e di commissione, dalla più recente.", ElencoSedute,
              lambda c, p: sedute.elenco_sedute(c, p.chamber, p.body, p.start, p.end, p.limit, p.offset)),
    Strumento("argomenti_sedute", "I punti all'ordine del giorno di Aula e commissioni (Bollettino) per organo, sede, fase e parole del "
              "titolo, con atti collegati (e leggi) e chi è intervenuto: «interventi di fine seduta», sede legislativa, atti UE.",
              Argomenti, lambda c, p: sedute.argomenti(c, p.chamber, p.body, p.seat, p.stage, p.q, p.start, p.end, p.limit, p.offset)),
    Strumento("conta_sedute", "CONTEGGIO. Quante sedute tenute e quante ore (dai video della Camera), per ramo e mese.",
              ContaSedute, lambda c, p: sedute.conta_sedute(c, p.chamber, p.body, p.start, p.end, p.by_month)),
    Strumento("seduta", "Una seduta: argomenti, atti discussi, interventi con chi parla, il suo gruppo e le didascalie del resoconto "
              "(reactions: applausi, proteste, «si levano in piedi»), votazioni.", Seduta, _seduta),
    Strumento("organo", "Commissioni, giunte e altri organi per nome, con presidente, vicepresidenti, segretari alla data (e il loro "
              "gruppo) e il numero dei membri.", Organo, lambda c, p: persone.organo(c, p.q, p.chamber, p.date, p.titles)),
    Strumento("elenco_votazioni", "Votazioni elettroniche, dalla più recente, per parole, ramo, atto, tipo e date.", ElencoVotazioni,
              lambda c, p: voti.elenco_votazioni(c, p.chamber, p.act, p.kind, p.start, p.end, p.final, p.limit, p.offset, p.confidence, p.q)),
    Strumento("votazione", "Una votazione: totali, esito, atto, voto di ogni gruppo (il Misto per componente) e, se chiesto, di ogni parlamentare. "
              "Un gruppo con split vero si è diviso: dillo con i numeri di ogni scelta, mai una posizione unica.",
              Votazione, lambda c, p: voti.votazione(c, p.uri, p.with_ballots)),
    Strumento("cerca_atti", "Progetti di legge, interrogazioni, mozioni e altri atti per parole del titolo, numero, tipo, firmatario o "
              "iniziativa (governo, parlamentare, regione, CNEL, popolare, o il presentatore: «Regione Toscana»).",
              CercaAtti, lambda c, p: atti.cerca_atti(c, p.q, p.chamber, p.kind, p.number, p.signer, p.limit, p.offset, p.initiative)),
    Strumento("atto", "Un atto: firmatari, iter, testi con il numero di articoli, votazioni, emendamenti per esito.",
              Uri, lambda c, p: atti.atto(c, p.uri)),
    Strumento("articolo", "Il testo di un articolo di una versione dell'atto (presentato, della commissione, approvato), o l'elenco degli articoli.",
              Articolo, lambda c, p: atti.articolo(c, p.code, p.number)),
    Strumento("cerca_emendamenti", "Emendamenti di tutta la legislatura o di un progetto di legge: per significato (un tema, una frase, il "
              "testo di una bozza: trova quelli simili già presentati), per parole o per filtri (gruppo, firmatario, esito, sede, ramo, "
              "periodo). Ognuno con firmatari e gruppi, l'esito in un elenco fisso e la fonte dell'esito.",
              CercaEmendamenti, lambda c, p: emendamenti.cerca(c, p.testo, p.q, p.act, p.chamber, p.group, p.signer, p.outcome, p.venue,
                                                             p.start, p.end, p.limit, p.offset, p.number)),
    Strumento("proponi_temi", "Per una domanda su un soggetto che non è un tema parlamentare (un'azienda, un marchio, un'associazione, "
              "un ente): proponi i temi parlamentari che lo riguardano e le sue associazioni di categoria; lo strumento li verifica "
              "sui dati e mostra all'utente una scelta con i numeri. Le proposte senza riscontro spariscono.",
              ProponiTemi, lambda c, p: soggetti.proponi(c, p.soggetto, [t.model_dump() for t in p.temi], p.associazioni)),
    Strumento("chiedi_settore", "Per un'azienda o un ente di cui dal nome non si capisce di cosa si occupa (es. «Rossi S.r.l.», «Gruppo "
              "Bianchi»), invece di proponi_temi: mostra all'utente una scelta per dire il settore; poi i temi arrivano da soli.",
              ChiediSettore, lambda c, p: {"soggetto": p.soggetto, "chiedi_settore": True}),
    Strumento("emendamento", "La scheda di un emendamento: testo intero, firmatari, esito con la fonte, voto dei gruppi in Aula, storia (lo "
              "stesso testo o quasi presentato in altri atti, con l'esito di ogni volta), interventi della seduta del voto che lo citano, "
              "pareri di governo e relatore letti nei sommari, termini per gli emendamenti dell'atto.",
              Emendamento, lambda c, p: emendamenti.scheda(c, p.uri) or {"errore": "emendamento non trovato"}),
    Strumento("cerca_interventi", "Interventi in Aula e in commissione che contengono le parole cercate, dal più recente, con un estratto; "
              "con captions, le didascalie del resoconto (applausi, proteste, chi si alza in piedi) con il parlato che le precede.",
              CercaInterventi, _cerca_interventi),
    Strumento("cerca_per_significato", "Brani di interventi, atti, documenti o emendamenti vicini per significato a un tema o a una frase, anche "
              "senza le stesse parole: per gli interventi chi parla, gruppo alla data (il Misto per componente), data, seduta e link al resoconto.",
              CercaPerSignificato, lambda c, p: significato.cerca(c, p.testo, p.fonti, p.ramo, p.da, p.a, p.quanti)),
    # conteggi: numeri, classifiche e matrici, ognuno con `counted` (che cosa si è contato)
    Strumento("conta_votazioni", "CONTEGGIO. Quante votazioni, per ramo, tipo, esito, anno, mese, finali, segrete, fiducia, atto o periodo.",
              ContaVotazioni, lambda c, p: conti.conta_votazioni(c, p.chamber, p.kind, p.final, p.secret, p.approved, p.confidence, p.act,
                                                                  p.q, p.start, p.end, p.group_by, p.sum_chambers, p.limit, p.offset)),
    Strumento("voto_gruppi", "CONTEGGIO. Come hanno votato i gruppi (il Misto per componente) su un insieme di votazioni palesi di un ramo: "
              "posizioni, coesione (indice di Hix-Noury-Roland), quota di voti compatti, matrice di accordo fra gruppi; con due gruppi le "
              "votazioni in cui si sono divisi; con una persona quanto ha votato come ciascun gruppo, prima e dopo un cambio di gruppo.",
              VotoGruppi, lambda c, p: conti.voto_gruppi(c, p.chamber, p.kind, p.final, p.approved, p.confidence, p.act, p.q, p.start,
                                                          p.end, p.groups, p.person, p.limit, p.offset)),
    Strumento("presenze", "CONTEGGIO. Per ogni parlamentare: votazioni a cui ha partecipato, favorevoli, contrari, astenuti, assenze e "
              "missioni, per persone, gruppo o membri del governo che hanno anche il seggio, in un periodo.",
              Presenze, lambda c, p: conti.presenze(c, p.chamber, p.persons, p.group, p.government, p.kind, p.final, p.start, p.end,
                                                     p.order_by, p.limit, p.offset)),
    Strumento("conta_interventi", "CONTEGGIO. Quanti interventi (e parole, e occorrenze di una parola o frase) per ramo, sede, organo, "
              "anno, mese, persona, gruppo alla data o ruolo (parlamentare, governo, presidenza, relatore): classifiche di chi parla di "
              "più (per classifiche di parlamentari: role=parlamentare, se no entrano chi presiede e il governo), quante volte si è detta "
              "una parola e da chi.",
              ContaInterventi, lambda c, p: conti.conta_interventi(c, p.chamber, p.body, p.phrase, p.person, p.group, p.role, p.start,
                                                                    p.end, p.include_summaries, p.words, p.group_by, p.order_by,
                                                                    p.sum_chambers, p.limit, p.offset)),
    Strumento("conta_reazioni", "CONTEGGIO. Applausi, proteste, commenti e altre reazioni del resoconto, per tipo, periodo, gruppo che "
              "reagisce, gruppo, ruolo o persona di chi parla: per esempio la matrice di chi applaude chi.",
              ContaReazioni, lambda c, p: conti.conta_reazioni(c, p.chamber, p.kinds, p.body, p.start, p.end, p.speaker,
                                                                p.speaker_group, p.from_group, p.speaker_role, p.contains, p.group_by,
                                                                p.sum_chambers, p.limit, p.offset)),
    Strumento("conta_atti", "CONTEGGIO. Quanti atti (progetti di legge, interrogazioni, mozioni…) per ramo, tipo, iniziativa, tema, "
              "firmatario, gruppo del primo firmatario, ministero destinatario, periodo, diventati legge; con laws le leggi approvate contate una volta sola.",
              ContaAtti, lambda c, p: conti.conta_atti(c, p.chamber, p.kind, p.initiative, p.q, p.subject, p.signer, p.first_signer,
                                                        p.group, p.became_law, p.start, p.end, p.laws, p.group_by, p.sum_chambers,
                                                        p.limit, p.offset, p.addressee)),
    Strumento("conta_emendamenti", "CONTEGGIO. Quante proposte emendative per ramo, atto, sede, esito, anno, gruppo dei firmatari o "
              "coppia di gruppi che le cofirmano.",
              ContaEmendamenti, lambda c, p: conti.conta_emendamenti(c, p.chamber, p.act, p.outcome, p.venue, p.group, p.start, p.end,
                                                                      p.cross_group, p.group_by, p.sum_chambers, p.limit, p.offset)),
    Strumento("cambi_gruppo", "CONTEGGIO. Chi è passato da un gruppo a un altro nella legislatura, quando, da dove e verso dove, con il "
              "totale delle persone e dei passaggi per ramo.",
              CambiGruppo, lambda c, p: conti.cambi_gruppo(c, p.chamber, p.start, p.end, p.person, p.group, p.components, p.limit,
                                                            p.offset)),
    Strumento("fatti_commissioni", "Lavori delle commissioni letti nei sommari: audizioni (chi è stato sentito, su quale atto), pareri "
              "delle commissioni sugli atti, risposte del governo alle interrogazioni in commissione con la replica. Ogni fatto ha la "
              "frase del sommario (evidence): è scritta dagli uffici, non va citata come parola di un parlamentare. Copre le sedute "
              "dall'agosto 2026.", FattiCommissioni,
              lambda c, p: fatti.fatti_commissioni(c, p.kind, p.act, p.subject, p.body, p.chamber, p.start, p.end, p.outcome, p.limit, p.offset)),
    Strumento("documenti_acquisiti", "Documenti depositati in commissione: memorie delle audizioni e contributi scritti di "
              "associazioni, aziende, sindacati e autorità su un atto, allegati del Bollettino, dossier. Senza uri: l'elenco per atto "
              "(act), autore, commissione e date, con il link al file. Con uri: il testo del documento, a pagine (more dice da dove "
              "riprendere). Per «chi ha depositato memorie su…» e «cosa sostiene X nella sua memoria». Sono scritti di terzi, non "
              "parole di parlamentari: riferiscili attribuendoli all'autore, senza «…», con il link.", DocumentiAcquisiti, _documenti),
    Strumento("agenda", "AGENDA. Cosa succede in Parlamento giorno per giorno fra due date: sedute d'Aula previste e tenute, sedute "
              "di commissione, termini per gli emendamenti in commissione (con la frase del sommario degli uffici, che non va citata come "
              "parola di un parlamentare), progetti di legge presentati, votazioni finali, leggi pubblicate. «Cosa scade oggi o questa "
              "settimana»: types=[\"termini\"]. Un termine superato da una proroga ha superseded=true.", Agenda,
              lambda c, p: agenda.agenda(c, p.start, p.end or p.start, p.chamber, p.types)),
    Strumento("verifica_citazioni", "Controlla che ogni citazione tra «…» di una risposta sia copiata esattamente da un intervento, e di chi è.",
              VerificaCitazioni, lambda c, p: citazioni.verifica(c, p.text)),
]
PER_NOME = {s.nome: s for s in STRUMENTI}


def esegui(c: psycopg.Connection, nome: str, argomenti: dict) -> object:
    """Esegue uno strumento con argomenti non fidati (dal modello o da un client MCP): li valida prima. Un elenco con
    meno elementi del totale lo dice in `more`, con l'offset per la pagina dopo."""
    s = PER_NOME.get(nome)
    if s is None:
        raise KeyError(f"strumento sconosciuto: {nome}")
    p = s.parametri.model_validate(argomenti)
    out = _json(s.esegui(c, p))
    if isinstance(out, dict) and isinstance(out.get("items"), list) and isinstance(out.get("total"), int):
        visti = getattr(p, "offset", 0) + len(out["items"])
        if out["total"] > visti:
            out["more"] = (f"elenco parziale: {len(out['items'])} di {out['total']}"
                           + (f"; i successivi con offset={visti}" if hasattr(p, "offset") else "; restringi la ricerca o usa un conteggio"))
    return out


def in_testo(x: object) -> str:
    return json.dumps(x, ensure_ascii=False, default=str)

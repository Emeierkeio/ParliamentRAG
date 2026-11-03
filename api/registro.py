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

from .strumenti import atti, citazioni, persone, ricerca, sedute, voti

Ramo = Literal["camera", "senato"]


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
    in_office: bool | None = Field(True, description="solo chi è in carica (vuoto per tutti, anche cessati)")
    limit: int = Field(20, ge=1, le=100)


class Uri(Parametri):
    uri: str


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


class Seduta(Parametri):
    uri: str
    full_text: bool = Field(False, description="testo intero degli interventi; senza, i primi 150 caratteri (per il contenuto usa cerca_interventi)")


class ElencoVotazioni(Parametri):
    chamber: Ramo | None = None
    act: str | None = Field(None, description="uri dell'atto votato")
    kind: str | None = Field(None, description="final, article, amendment, agenda_order, motion, resolution, confidence…")
    final: bool | None = Field(None, description="solo le votazioni finali")
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
    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0)


class Emendamenti(Parametri):
    act: str = Field(description="uri del progetto di legge")
    signer: str | None = Field(None, description="uri di un firmatario")
    group: str | None = Field(None, description="sigla o uri del gruppo del firmatario alla data")
    outcome: str | None = None
    venue: str | None = Field(None, description="committee, assembly, referente…")
    q: str | None = Field(None, description="parole del testo dell'emendamento")
    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0)


class CercaInterventi(Parametri):
    q: str = Field(min_length=2, max_length=200, description="parole da cercare nel testo; «\"frase esatta\"», «-parola», «or»")
    chamber: Ramo | None = None
    person: str | None = Field(None, description="uri di chi parla")
    start: dt.date | None = None
    end: dt.date | None = None
    include_summaries: bool = Field(True, description="anche i riassunti delle commissioni, che non si citano tra virgolette")
    limit: int = Field(10, ge=1, le=50)
    offset: int = Field(0, ge=0)


class VerificaCitazioni(Parametri):
    text: str = Field(max_length=20000, description="la risposta con le citazioni tra «…»")


def _seduta(c, p: Seduta):
    s = sedute.seduta(c, p.uri)
    if s and not p.full_text:
        for i in s.items:
            for x in i.speeches:
                x.text = x.text[:150] + ("…" if len(x.text) > 150 else "")
                x.reactions = []
    return s


STRUMENTI: list[Strumento] = [
    Strumento("cerca_persone", "Parlamentari della XIX legislatura per nome, ramo e gruppo, con il gruppo di oggi (il Misto per componente).",
              CercaPersone, lambda c, p: persone.cerca_persone(c, p.q, p.chamber, p.group, p.in_office, p.limit)),
    Strumento("scheda_persona", "Scheda completa di una persona: anagrafica, mandati, gruppi, organi, cariche di governo, numero di interventi, voti, firme.",
              Uri, lambda c, p: persone.scheda_persona(c, p.uri)),
    Strumento("composizione", "Gruppi di un ramo alla data con il numero di membri; il Misto diviso per componente.",
              Composizione, lambda c, p: persone.composizione(c, p.chamber, p.date)),
    Strumento("elenco_sedute", "Sedute d'Aula e di commissione, dalla più recente.", ElencoSedute,
              lambda c, p: sedute.elenco_sedute(c, p.chamber, p.body, p.start, p.end, p.limit, p.offset)),
    Strumento("seduta", "Una seduta: argomenti, atti discussi, interventi con chi parla e il suo gruppo, votazioni.", Seduta, _seduta),
    Strumento("elenco_votazioni", "Votazioni elettroniche, dalla più recente, per ramo, atto, tipo e date.", ElencoVotazioni,
              lambda c, p: voti.elenco_votazioni(c, p.chamber, p.act, p.kind, p.start, p.end, p.final, p.limit, p.offset)),
    Strumento("votazione", "Una votazione: totali, esito, atto, voto di ogni gruppo (il Misto per componente) e, se chiesto, di ogni parlamentare.",
              Votazione, lambda c, p: voti.votazione(c, p.uri, p.with_ballots)),
    Strumento("cerca_atti", "Progetti di legge, interrogazioni, mozioni e altri atti per parole del titolo, numero, tipo o firmatario.",
              CercaAtti, lambda c, p: atti.cerca_atti(c, p.q, p.chamber, p.kind, p.number, p.signer, p.limit, p.offset)),
    Strumento("atto", "Un atto: firmatari, iter, testi con il numero di articoli, votazioni, emendamenti per esito.",
              Uri, lambda c, p: atti.atto(c, p.uri)),
    Strumento("emendamenti", "Emendamenti di un progetto di legge, con testo e firmatari, filtrati per firmatario, gruppo, esito, sede o parole.",
              Emendamenti, lambda c, p: atti.emendamenti(c, p.act, p.signer, p.group, p.outcome, p.venue, p.q, p.limit, p.offset)),
    Strumento("cerca_interventi", "Interventi in Aula e in commissione che contengono le parole cercate, dal più recente, con un estratto.",
              CercaInterventi, lambda c, p: ricerca.cerca_interventi(c, p.q, p.chamber, p.person, p.start, p.end, p.include_summaries, p.limit, p.offset)),
    Strumento("verifica_citazioni", "Controlla che ogni citazione tra «…» di una risposta sia copiata esattamente da un intervento, e di chi è.",
              VerificaCitazioni, lambda c, p: citazioni.verifica(c, p.text)),
]
PER_NOME = {s.nome: s for s in STRUMENTI}


def esegui(c: psycopg.Connection, nome: str, argomenti: dict) -> object:
    """Esegue uno strumento con argomenti non fidati (dal modello o da un client MCP): li valida prima."""
    s = PER_NOME.get(nome)
    if s is None:
        raise KeyError(f"strumento sconosciuto: {nome}")
    return _json(s.esegui(c, s.parametri.model_validate(argomenti)))


def in_testo(x: object) -> str:
    return json.dumps(x, ensure_ascii=False, default=str)

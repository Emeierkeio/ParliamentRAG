"""Formati delle risposte. I nomi dei campi sono in inglese come nello schema v3; i valori (titoli, nomi, testi) sono
quelli della fonte, in italiano. Ogni oggetto porta il suo `uri` e, quando c'è, il link alla fonte ufficiale."""

from __future__ import annotations

import datetime as dt
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Group(BaseModel):
    uri: str
    name: str
    short_name: str | None = None
    kind: str                                  # group | misto_component
    part_of: str | None = None                 # per una componente del Misto: il gruppo Misto


class PersonBrief(BaseModel):
    uri: str
    name: str
    chamber: str | None = None                 # ramo del mandato nella legislatura
    in_office: bool = False
    group: Group | None = None                 # gruppo alla data (oggi, o l'ultimo giorno del mandato); il Misto per componente
    photo: str | None = None


class Mandate(BaseModel):
    chamber: str
    legislature: int
    start_date: dt.date
    end_date: dt.date | None = None
    end_reason: str | None = None
    kind: str | None = None
    constituency: str | None = None
    college: str | None = None
    list: str | None = None


class Membership(BaseModel):
    group: Group
    role: str
    start_date: dt.date | None = None
    end_date: dt.date | None = None


class Post(BaseModel):                         # carica in un organo, gruppo, ministero o governo, o seggio in un organo
    target: str
    target_name: str | None = None
    title: str
    start_date: dt.date
    end_date: dt.date | None = None


class PersonCounts(BaseModel):
    speeches: int
    ballots: int
    ballots_cast: int                          # favorevole, contrario, astenuto
    ballots_mission: int
    bills_first_signer: int
    amendments_signed: int


class Person(PersonBrief):
    given_name: str | None = None
    family_name: str | None = None
    gender: str | None = None
    birth_date: dt.date | None = None
    birth_place: str | None = None
    profession: str | None = None
    source_uri: str | None = None
    same_as: list[str] = []                    # l'altra scheda della stessa persona (senatori: Camera e Senato)
    mandates: list[Mandate] = []
    memberships: list[Membership] = []
    bodies: list[Post] = []
    offices: list[Post] = []
    counts: PersonCounts


class GroupCount(BaseModel):
    group: Group
    members: int
    components: list[GroupCount] = []          # solo per il Misto


class Composition(BaseModel):
    chamber: str
    date: dt.date
    members: int
    groups: list[GroupCount]
    not_in_group: int


class SittingBrief(BaseModel):
    uri: str
    chamber: str
    body: str
    body_name: str | None = None
    number: int
    date: dt.date
    kind: str | None = None
    status: str
    url: str | None = None                     # il resoconto ufficiale, per le sedute tenute che lo hanno


class ActRef(BaseModel):
    ref: str                                   # come lo scrive la fonte: pdl:2822-B, ddl:1353
    uri: str | None = None                     # l'atto, quando è risolto
    title: str | None = None


class Reaction(BaseModel):
    kind: str
    raw: str
    offset_char: int


class Speech(BaseModel):
    uri: str
    order: int
    person: PersonBrief | None = None
    speaker_label: str | None = None
    as_group: str | None = None
    as_office: str | None = None
    kind: str | None = None                    # summary: riassunto del funzionario, da non citare tra virgolette
    text: str
    reactions: list[Reaction] = []


class AgendaItem(BaseModel):
    uri: str
    order: int
    title: str | None = None
    stage: str | None = None
    acts: list[ActRef] = []
    speeches: list[Speech] = []


class VoteBrief(BaseModel):
    uri: str
    sitting: str
    chamber: str
    number: int
    date: dt.date
    title: str | None = None
    kind: str
    favor: int | None = None
    against: int | None = None
    abstain: int | None = None
    approved: bool | None = None
    secret: bool | None = None
    confidence: bool | None = None
    act_title: str | None = None
    source_url: str | None = None


class Sitting(SittingBrief):
    seat: str | None = None
    presided_by: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    items: list[AgendaItem]
    votes: list[VoteBrief]


class GroupVote(BaseModel):
    group: Group | None
    favor: int = 0
    against: int = 0
    abstain: int = 0
    absent: int = 0
    mission: int = 0
    other: int = 0
    majority: str | None = None                # la scelta di tutti quelli che hanno votato; None se il gruppo si è diviso
    split: bool = False                        # chi ha votato non ha fatto la stessa scelta: va detto, con i numeri


class Ballot(BaseModel):
    person: PersonBrief
    result: str


class Vote(VoteBrief):
    description: str | None = None
    present: int | None = None
    voting: int | None = None
    majority: int | None = None
    final: bool | None = None
    confidence: bool | None = None
    ballots_match: bool | None = None
    acts: list[ActRef] = []
    groups: list[GroupVote] = []
    ballots: list[Ballot] = []


class ActBrief(BaseModel):
    uri: str
    chamber: str
    legislature: int
    number: str
    kind: str
    title: str | None = None
    date: dt.date | None = None
    status: str | None = None
    law_number: str | None = None
    card_url: str | None = None
    initiative: str | None = None              # Governo, Parlamentare, Regioni…; al Senato il presentatore («Regione Toscana»)


class Sponsor(BaseModel):
    person: PersonBrief
    first: bool
    as_office: str | None = None


class Step(BaseModel):
    order: int
    title: str | None = None
    date: dt.date | None = None


class TextVersion(BaseModel):
    code: str
    kind: str | None = None
    title: str | None = None
    date: dt.date | None = None
    articles: int
    length: int


class AmendmentCounts(BaseModel):
    total: int
    by_outcome: dict[str, int]


class Assignment(BaseModel):
    """Assegnazione di un atto a una commissione. Per gli atti del Governo e le nomine sottoposti a parere: il termine,
    la norma che chiede il parere, il parere espresso e la sua data."""
    body: str | None = None                    # uri dell'organo, se è nell'anagrafica
    body_name: str
    seat: str | None = None                    # referente, redigente, deliberante, consultiva; opinion, remarks, eu_compatibility
    date: dt.date | None = None
    deadline: dt.date | None = None
    basis: str | None = None
    opinion: str | None = None
    opinion_date: dt.date | None = None


class Rapporteur(BaseModel):
    name: str
    role: str | None = None                    # rapporteur, majority, minority
    person: PersonBrief | None = None


class Act(ActBrief):
    kind_raw: str | None = None
    description: str | None = None
    law_date: dt.date | None = None
    status_date: dt.date | None = None
    text: str | None = None                    # atti di sindacato ispettivo e di indirizzo
    source_uri: str | None = None
    text_urls: list[str] = []
    sponsors: list[Sponsor] = []
    assignments: list[Assignment] = []
    rapporteurs: list[Rapporteur] = []
    steps: list[Step] = []
    versions: list[TextVersion] = []
    joined: list[ActRef] = []
    votes: list[VoteBrief] = []
    amendments: AmendmentCounts


class Signer(BaseModel):
    person: PersonBrief | None = None
    name_raw: str | None = None
    first: bool | None = None


class Amendment(BaseModel):
    uri: str
    act: str
    number: str
    venue: str | None = None
    article: str | None = None
    outcome: str | None = None
    presented: dt.date | None = None
    sitting_date: dt.date | None = None
    text: str | None = None
    signers: list[Signer] = []


class Page(BaseModel, Generic[T]):
    total: int
    offset: int
    items: list[T]


class SpeechHit(BaseModel):
    uri: str
    sitting: SittingBrief
    item_title: str | None = None
    person: PersonBrief | None = None
    speaker_label: str | None = None
    kind: str | None = None
    snippet: str                               # con «[[» e «]]» intorno alle parole trovate
    url: str | None = None                     # il resoconto ufficiale
    government: bool = False                   # parla da membro del Governo: non è la voce del suo partito
    office: str | None = None                  # la carica di governo, com'è scritta nel resoconto
    video: str | None = None                   # la WebTV della Camera, che parte dall'inizio dell'intervento (secondo video_start_s)
    video_start_s: int | None = None

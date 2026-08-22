"""User-facing messages for the out-of-domain handling (issue #22).

Two levels, matching the two signals:
- ``gate_message``: the evidence gate found too little on-topic material, the
  pipeline stops and this markdown replaces the answer.
- ``domain_notice``: the LLM domain check flags the query as out of scope but
  the evidence gate passed; this blockquote goes above the normal answer.

Messages are pre-localized: they reach the client as-is, without passing
through the translation step.
"""

_GATE = {
    "it": ("## Tema non trovato\n\nNel corpus della Camera dei Deputati "
           "(XIX legislatura) non ci sono dibattiti pertinenti a «{query}», "
           "quindi il sistema non ha generato una risposta.",
           "\n\nTemi vicini che l'Aula ha discusso:\n"),
    "en": ("## Topic not found\n\nThe Chamber of Deputies corpus "
           "(19th legislature) has no debates relevant to «{query}», so the "
           "system generated no answer.",
           "\n\nNearby topics the Chamber did debate:\n"),
    "fr": ("## Sujet introuvable\n\nLe corpus de la Chambre des députés "
           "(XIXe législature) ne contient aucun débat pertinent pour "
           "«{query}» ; le système n'a donc généré aucune réponse.",
           "\n\nSujets proches réellement débattus :\n"),
    "de": ("## Thema nicht gefunden\n\nDas Korpus der Abgeordnetenkammer "
           "(19. Legislaturperiode) enthält keine Debatten zu «{query}»; das "
           "System hat deshalb keine Antwort erzeugt.",
           "\n\nVerwandte Themen, die die Kammer debattiert hat:\n"),
    "es": ("## Tema no encontrado\n\nEl corpus de la Cámara de Diputados "
           "(XIX legislatura) no contiene debates pertinentes para «{query}», "
           "así que el sistema no generó una respuesta.",
           "\n\nTemas cercanos que la Cámara sí debatió:\n"),
    "pt": ("## Tema não encontrado\n\nO corpus da Câmara dos Deputados "
           "(XIX legislatura) não contém debates pertinentes a «{query}», "
           "então o sistema não gerou uma resposta.",
           "\n\nTemas próximos que a Câmara debateu:\n"),
}

_NOTICE = {
    "it": ("> **Nota**: la domanda sembra fuori dal perimetro della Camera "
           "dei Deputati. La risposta qui sotto usa i dibattiti italiani più "
           "vicini al tema{sugg}.\n\n",
           "; forse cercavi: {topics}"),
    "en": ("> **Note**: the question looks outside the Chamber of Deputies' "
           "scope. The answer below uses the closest Italian debates{sugg}."
           "\n\n",
           "; you may have meant: {topics}"),
    "fr": ("> **Note** : la question semble hors du périmètre de la Chambre "
           "des députés. La réponse ci-dessous s'appuie sur les débats "
           "italiens les plus proches{sugg}.\n\n",
           " ; vous cherchiez peut-être : {topics}"),
    "de": ("> **Hinweis**: Die Frage liegt offenbar außerhalb des Bereichs "
           "der Abgeordnetenkammer. Die Antwort unten stützt sich auf die "
           "nächstliegenden italienischen Debatten{sugg}.\n\n",
           "; vielleicht meinten Sie: {topics}"),
    "es": ("> **Nota**: la pregunta parece fuera del ámbito de la Cámara de "
           "Diputados. La respuesta usa los debates italianos más "
           "cercanos{sugg}.\n\n",
           "; quizá buscabas: {topics}"),
    "pt": ("> **Nota**: a pergunta parece fora do âmbito da Câmara dos "
           "Deputados. A resposta usa os debates italianos mais "
           "próximos{sugg}.\n\n",
           "; talvez procurasse: {topics}"),
}


def gate_message(query: str, suggestions: list, locale: str = "it") -> str:
    """Markdown shown instead of the answer when the evidence gate blocks.

    Suggestions become ``suggest:`` links: the frontend renders them as
    clickable chips that launch the suggested query.
    """
    from urllib.parse import quote

    body, sugg_header = _GATE.get(locale, _GATE["en"])
    text = body.format(query=query)
    if suggestions:
        chips = " ".join(f"[{s}](suggest:{quote(s)})" for s in suggestions)
        text += sugg_header + "\n" + chips
    return text


def domain_notice(suggestions: list, locale: str = "it") -> str:
    """Blockquote prepended to the answer when only the LLM check fires."""
    from urllib.parse import quote

    template, sugg_template = _NOTICE.get(locale, _NOTICE["en"])
    sugg = ""
    if suggestions:
        links = ", ".join(f"[{s}](suggest:{quote(s)})" for s in suggestions)
        sugg = sugg_template.format(topics=links)
    return template.format(sugg=sugg)

"""Genera docs/assets/banner-{light,dark}.svg, stessa griglia dei banner di Fascicoli, Stenografo e Scranno."""
from pathlib import Path

FONT = "Geist, Inter, -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
ALT = ("ParliamentRAG: metodo, dati e verifica per l'AI sul Parlamento. "
       "Centro di ricerca, Università di Milano-Bicocca.")
THEMES = {
    "light": dict(bg="#F7F8F5", ink="#14201C", muted="#5E6B66", card="#FFFFFF", stroke="#E4E8E4",
                  chip="#EFF8F5", accent="#167A68", edge="#D5DBD7", pill="#F1F4F1"),
    "dark": dict(bg="#0F1714", ink="#ECF0EC", muted="#A9B5B0", card="#16201C", stroke="#26302C",
                 chip="#12302A", accent="#55B29E", edge="#33403B", pill="#1E2A25"),
}
BRAND_DOT = "#2d5f8f"

# I tre sistemi che leggono il grafo: marchio (viewBox, contenuto), nome, cosa fa.
SYSTEMS = [
    ("3 4 56 58", '<path d="M10 42C12 23 29 16 33.5 27C37 36 24 42 27.5 49.5C31 56.5 46 52 48.5 28" fill="none" stroke="{ink}" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/><circle cx="50" cy="15" r="6.6" fill="#167A68"/>',
     "Stenografo", "Domande su lavori, atti e voti"),
    ("-6 -4 64 70", '<g transform="rotate(-30 28 32)"><path d="M14 14V44a14 14 0 0 0 28 0V18a7 7 0 0 0-14 0V40" fill="none" stroke="{ink}" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/><circle cx="14" cy="2" r="6.6" fill="#167A68"/></g>',
     "Fascicoli", "Un tema, nei vincoli di ParliamentRAG"),
    ("3 1 56 60", '<path d="M18 12C18 24 18 32 20 36C22 40 30 40 42 40C46 40 47 43 47 50M24 40V50" fill="none" stroke="{ink}" stroke-width="7.5" stroke-linecap="round" stroke-linejoin="round"/><circle cx="34" cy="24" r="6.4" fill="#167A68"/>',
     "Scranno", "L'Aula in prima persona"),
]
ROWS_Y = [192, 252, 312]


def banner(t):
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="440" viewBox="0 0 1280 440" role="img" aria-label="{ALT}">',
           f'<rect width="1280" height="440" rx="28" fill="{t["bg"]}"/>',
           # marchio: arco dell'emiciclo + punto
           f'<svg x="70" y="126" width="122" height="90" viewBox="0 8 224 166"><path d="M 35.91 139.73 A 81 81 0 1 1 188.09 139.73" '
           f'fill="none" stroke="{t["ink"]}" stroke-width="32" stroke-linecap="round"/><circle cx="112" cy="146" r="22" fill="{BRAND_DOT}"/></svg>',
           f'<text x="214" y="196" font-family="{FONT}" font-size="66" font-weight="700" letter-spacing="-2.6" fill="{t["ink"]}">ParliamentRAG</text>',
           f'<text x="70" y="290" font-family="{FONT}" font-size="27" font-weight="500" letter-spacing="-0.4" fill="{t["ink"]}">Metodo, dati e verifica</text>',
           f'<text x="70" y="326" font-family="{FONT}" font-size="27" font-weight="500" letter-spacing="-0.4" fill="{t["ink"]}">per l’AI sul Parlamento.</text>',
           f'<text x="70" y="378" font-family="{FONT}" font-size="19" fill="{t["muted"]}">Centro di ricerca · Università di Milano-Bicocca</text>',
           f'<rect x="760" y="92" width="456" height="256" rx="20" fill="{t["card"]}" stroke="{t["stroke"]}" stroke-width="2"/>',
           f'<rect x="788" y="116" width="78" height="26" rx="13" fill="{t["chip"]}"/>',
           f'<text x="827" y="134" text-anchor="middle" font-family="{FONT}" font-size="15" font-weight="600" fill="{t["accent"]}">Grafo</text>',
           f'<text x="880" y="135" font-family="{FONT}" font-size="17" font-weight="600" fill="{t["ink"]}">Un grafo, tre sistemi</text>']
    # il grafo: il marchio di ParliamentRAG, da cui partono tre collegamenti
    out.append(f'<svg x="790" y="232" width="54" height="40" viewBox="0 8 224 166"><path d="M 35.91 139.73 A 81 81 0 1 1 188.09 139.73" '
               f'fill="none" stroke="{t["ink"]}" stroke-width="32" stroke-linecap="round"/><circle cx="112" cy="146" r="22" fill="{BRAND_DOT}"/></svg>')
    for y in ROWS_Y:
        out.append(f'<path d="M856 252 C 872 252, 868 {y}, 888 {y}" fill="none" stroke="{t["edge"]}" stroke-width="2"/>')
    for (vb, body, name, job), y in zip(SYSTEMS, ROWS_Y):
        out.append(f'<rect x="888" y="{y - 24}" width="304" height="48" rx="12" fill="{t["pill"]}"/>')
        out.append(f'<svg x="900" y="{y - 15}" width="30" height="30" viewBox="{vb}">{body.format(ink=t["ink"])}</svg>')
        out.append(f'<text x="944" y="{y - 3}" font-family="{FONT}" font-size="16" font-weight="600" fill="{t["ink"]}">{name}</text>')
        out.append(f'<text x="944" y="{y + 15}" font-family="{FONT}" font-size="13.5" fill="{t["muted"]}">{job}</text>')
    out.append("</svg>\n")
    return "\n".join(out)


here = Path(__file__).parent
for name, theme in THEMES.items():
    (here / f"banner-{name}.svg").write_text(banner(theme))

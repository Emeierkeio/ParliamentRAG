"""Genera docs/assets/banner-{light,dark}.svg, stessa griglia dei banner di Fascicoli, Stenografo e Scranno."""
from pathlib import Path

FONT = "Geist, Inter, -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
ALT = ("ParliamentRAG: ricerca aperta sui dati del Parlamento italiano. "
       "Università di Milano-Bicocca.")
THEMES = {
    "light": dict(bg="#F7F8F5", ink="#14201C", muted="#5E6B66", card="#FFFFFF", stroke="#E4E8E4",
                  chip="#EFF8F5", accent="#167A68", edge="#D5DBD7", pill="#F1F4F1"),
    "dark": dict(bg="#0F1714", ink="#ECF0EC", muted="#A9B5B0", card="#16201C", stroke="#26302C",
                 chip="#12302A", accent="#55B29E", edge="#33403B", pill="#1E2A25"),
}
BRAND_DOT = "#2d5f8f"

# Il grafo: un deputato al centro, collegato a ciò che fa e a dove sta.
CENTER = ("Deputato", 988, 245)
NODES = [("Gruppo", 850, 185), ("Intervento", 850, 245), ("Commissione", 850, 305),
         ("Atto", 1126, 185), ("Votazione", 1126, 245), ("Seduta", 1126, 305)]


def pill(label, cx, cy, fill, color, weight=500, stroke=None):
    w = len(label) * 8.4 + 30
    s = f' stroke="{stroke}" stroke-width="2"' if stroke else ""
    return (f'<rect x="{cx - w / 2:.1f}" y="{cy - 15}" width="{w:.1f}" height="30" rx="15" fill="{fill}"{s}/>\n'
            f'<text x="{cx}" y="{cy + 5}" text-anchor="middle" font-family="{FONT}" font-size="15" '
            f'font-weight="{weight}" fill="{color}">{label}</text>')


def banner(t):
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="440" viewBox="0 0 1280 440" role="img" aria-label="{ALT}">',
           f'<rect width="1280" height="440" rx="28" fill="{t["bg"]}"/>',
           # marchio: arco dell'emiciclo + punto
           f'<svg x="70" y="126" width="122" height="90" viewBox="0 8 224 166"><path d="M 35.91 139.73 A 81 81 0 1 1 188.09 139.73" '
           f'fill="none" stroke="{t["ink"]}" stroke-width="32" stroke-linecap="round"/><circle cx="112" cy="146" r="22" fill="{BRAND_DOT}"/></svg>',
           f'<text x="214" y="196" font-family="{FONT}" font-size="66" font-weight="700" letter-spacing="-2.6" fill="{t["ink"]}">ParliamentRAG</text>',
           f'<text x="70" y="290" font-family="{FONT}" font-size="27" font-weight="500" letter-spacing="-0.4" fill="{t["ink"]}">Ricerca aperta sui dati</text>',
           f'<text x="70" y="326" font-family="{FONT}" font-size="27" font-weight="500" letter-spacing="-0.4" fill="{t["ink"]}">del Parlamento italiano.</text>',
           f'<text x="70" y="378" font-family="{FONT}" font-size="19" fill="{t["muted"]}">Università di Milano-Bicocca</text>',
           f'<rect x="760" y="92" width="456" height="256" rx="20" fill="{t["card"]}" stroke="{t["stroke"]}" stroke-width="2"/>',
           f'<rect x="788" y="116" width="78" height="26" rx="13" fill="{t["chip"]}"/>',
           f'<text x="827" y="134" text-anchor="middle" font-family="{FONT}" font-size="15" font-weight="600" fill="{t["accent"]}">Grafo</text>',
           f'<text x="880" y="135" font-family="{FONT}" font-size="17" font-weight="600" fill="{t["ink"]}">Un grafo, tre sistemi</text>']
    _, cx, cy = CENTER
    for _, x, y in NODES:
        out.append(f'<line x1="{cx}" y1="{cy}" x2="{x}" y2="{y}" stroke="{t["edge"]}" stroke-width="2"/>')
    for label, x, y in NODES:
        out.append(pill(label, x, y, t["pill"], t["ink"], stroke=t["edge"]))
    out.append(pill(CENTER[0], cx, cy, t["accent"], t["card"], weight=600))
    out.append("</svg>\n")
    return "\n".join(out)


here = Path(__file__).parent
for name, theme in THEMES.items():
    (here / f"banner-{name}.svg").write_text(banner(theme))

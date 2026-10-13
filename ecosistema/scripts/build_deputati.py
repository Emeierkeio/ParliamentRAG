import json, glob, re
import os, sys
if len(sys.argv) < 2:
    sys.exit("Uso: python3 build_deputati.py <cartella con deputati.json e deputati/*.json>")
SRC = sys.argv[1]
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scranno", "deputati.js")
MIN = {"di","del","della","dello","dei","degli","delle","dell'","e","ed","per","il","lo","la","l'","i","gli","le","a","al","alla","allo","ai","agli","alle","all'","da","dal","dalla","dall'","in","nel","nella","nell'","nei","negli","nelle","su","sul","sulla","sullo","sui","sugli","sulle","sull'","con","tra","fra","nonché","anche","presso","ai","d'","ad"}
ROMAN = re.compile(r"^[IVXL]+$")
def accenti(s):
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"(?i)\bperche'", "perché", s)
    s = re.sub(r"(?i)nonche'", "nonché", s)
    tr = {"a": "à", "e": "è", "i": "ì", "o": "ò", "u": "ù"}
    s = re.sub(r"([aeiou])'(?=[\s,).»]|$)", lambda m: tr[m.group(1)], s)
    return s
def nome_organo(s):
    s = accenti(s)
    out = []
    for i, w in enumerate(s.split(" ")):
        lw = w.lower()
        m = re.match(r"^([A-Za-z]+')(.*)$", w)  # Dell'Unione -> dell'Unione
        if i > 0 and m and m.group(1).lower() in MIN:
            out.append(m.group(1).lower() + m.group(2)); continue
        if i > 0 and lw in MIN and not ROMAN.match(w):
            out.append(lw); continue
        out.append(w)
    s = " ".join(out)
    s = s.replace("per I Procedimenti", "per i Procedimenti").replace("(Ince)", "(INCE)").replace("Osce", "OSCE").replace("(Ap-upm)", "(AP-UpM)").replace("(Pam)", "(PAM)").replace("Nato", "NATO").replace("Sars-cov-2", "SARS-CoV-2").replace('"moby Prince"', '"Moby Prince"').replace("«il Forteto»", "«Il Forteto»")
    return s
def ordine(c):
    n = c["name"]
    m = re.match(r"^([IVXL]+) Commissione", n)
    roman = {"I":1,"II":2,"III":3,"IV":4,"V":5,"VI":6,"VII":7,"VIII":8,"IX":9,"X":10,"XI":11,"XII":12,"XIII":13,"XIV":14}
    return (0, roman.get(m.group(1), 99)) if m else (1, 0)

lista = json.load(open(SRC + "/deputati.json"))
ruoli_gruppo = {d["id"]: d["role"] for d in lista["deputies"]}
organi = []; idx = {}
dep = {}
for f in sorted(glob.glob(SRC + "/deputati/*.json")):
    d = json.load(open(f))
    co = []
    for c in sorted([c for c in d["committees"] if c["to"] is None], key=ordine):
        n = nome_organo(c["name"])
        if n not in idx: idx[n] = len(organi); organi.append(n)
        r = c["role"] if (c["role"] and c.get("roleTo") is None) else None
        co.append([idx[n], r] if r else idx[n])
    gh = [[g["acronym"], g["from"], g["to"]] for g in d["groupHistory"]]
    e = {"co": co}
    if len(gh) > 1: e["gh"] = gh
    mc = d.get("mistoComponent")
    if mc: e["cm"] = mc["name"]
    if ruoli_gruppo.get(d["id"]): e["rg"] = ruoli_gruppo[d["id"]]
    ir = d.get("institutionalRole")
    if ir and "Camera dei Deputati" in ir: e["ri"] = ir
    k = d["counts"] or {}; e["sp"] = k.get("speeches"); e["ap"] = k.get("actsPrimary"); e["ac"] = k.get("actsCosigned")
    v = d["votes"] or {}
    if v.get("participationPct") is not None: e["pp"] = v["participationPct"]
    e["ms"] = d["mandateStart"]
    dep[d["id"]] = e
data = {"dataAsOf": lista["dataAsOf"], "organi": organi, "deputati": dep}
js = "/* Scranno: dettagli dei deputati (commissioni in corso, gruppi, contatori).\n * Estratto da scranno/public/data/deputati/*.json, dati al " + lista["dataAsOf"] + ".\n * co: organi in corso (indice in organi, o [indice, ruolo]); gh: gruppi nella legislatura;\n * cm: componente del Misto; rg: ruolo nel gruppo; ri: ruolo istituzionale;\n * sp: interventi in Aula; ap/ac: atti da primo firmatario/cofirmati; pp: partecipazione al voto (%); ms: inizio mandato. */\nwindow.DEPUTATI = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n"
open(OUT, "w").write(js)
print(len(js), len(organi), len(dep))
print("\n".join(organi[:80]))
import collections
print(collections.Counter(e.get("ri") for e in dep.values()).most_common(12))

#!/usr/bin/env python3
"""kompetenz.py — Lookup-Stub fuer den Tool-Vertrag (Spec § 6).

Option B1 (v1.0): laedt die Shard-JSONs unter plugin/data/kompetenzen/ direkt.
Der Vertrag ist identisch zu B2 (SQLite) und zu einem spaeteren gehosteten MCP
-> die Umstellung ist nicht-brechend (§ 6, § 2).

Aufrufe (alle akzeptieren --json fuer maschinenlesbare Ausgabe):
  kompetenz.py finde_kompetenz --fach M --stufe K2 --stichworte Bruch --json
  kompetenz.py finde_progression --id AT.LP23.SEK1.M.ZAHLEN.K2.01 --richtung zurueck
  kompetenz.py finde_anwendungsbereiche --id <id> [--nur-verbindlich]
  kompetenz.py finde_lehrstoff --id <id>
  kompetenz.py finde_lernaufgaben [--fach M] [--stufe K2] [--id <id>]     # nur aus docs/
  kompetenz.py finde_bildungsstandard_bezug --id <id>
  kompetenz.py finde_uebergreifende_themen --arg M | --arg <id> | --arg "<Thema>"
  kompetenz.py finde_differenzierung --id <id>
  kompetenz.py finde_typische_fehlvorstellungen --id <id>

Stub-Status (Phase 0): erfuellt den Vertrag gegen das Mini-Fixture. Vollzugriff
und feinere Logik (Crosswalk, GERS-Niveaus je Stufe) folgen mit den echten Daten.
"""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve()
PLUGIN_ROOT = HERE.parent.parent                      # plugin/
REPO_ROOT = PLUGIN_ROOT.parent                        # repo/
DATA_DIR = PLUGIN_ROOT / "data" / "kompetenzen"
DOCS_DIR = REPO_ROOT / "docs"

# Klartext-Ordner -> Fach-Code (§ 5.8, § 7.6). Unbekannt -> "nicht zugeordnet".
FACH_ALIAS = {
    "mathematik": "M", "deutsch": "D", "englisch": "E", "sachunterricht": "SU",
    "biologie": "BIU", "physik": "PH", "chemie": "CH",
}
ID_RE = re.compile(r"^AT\.LP23\.(PRIM|SEK1)\.")


def _fold(s: str) -> str:
    """Diakritika-tolerante Suche: klein, ß->ss, Umlaute entschärft.

    So matcht das Stichwort 'Bruch' auch 'Brüchen' (ue->u) — sonst schlägt das
    Spec-Beispiel (§ 6) an der Umlaut-Grenze fehl.
    """
    s = s.lower().replace("ß", "ss")
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


# --------------------------------------------------------------------------- #
# Laden / Index
# --------------------------------------------------------------------------- #
def load_shards() -> list[dict]:
    if not DATA_DIR.exists():
        return []
    out = []
    for path in sorted(DATA_DIR.rglob("*.json")):
        try:
            out.append(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError as exc:
            print(f"! Shard uebersprungen (kein valides JSON): {path} ({exc})")
    return out


def iter_kompetenzen(shards: list[dict]):
    """Liefert (shard, bereich, kompetenz) fuer jede Kompetenz."""
    for shard in shards:
        for bereich in shard.get("kompetenzbereiche", []):
            for k in bereich.get("kompetenzen", []):
                yield shard, bereich, k


def find_by_id(shards: list[dict], kompetenz_id: str):
    for shard, bereich, k in iter_kompetenzen(shards):
        if k.get("id") == kompetenz_id:
            return shard, bereich, k
    return None, None, None


def _enrich(shard, bereich, k) -> dict:
    """Kompetenz + Kontext (Fach/Bereich) fuer die Ausgabe."""
    out = dict(k)
    out["_fach"] = shard.get("meta", {}).get("fach", {}).get("code")
    out["_kompetenzbereich"] = bereich.get("name")
    return out


# --------------------------------------------------------------------------- #
# Tool-Vertrag (§ 6)
# --------------------------------------------------------------------------- #
def finde_kompetenz(shards, fach=None, stufe=None, kompetenzbereich=None,
                    code=None, stichworte=None) -> list[dict]:
    stichworte = [_fold(s) for s in (stichworte or [])]
    res = []
    for shard, bereich, k in iter_kompetenzen(shards):
        fc = shard.get("meta", {}).get("fach", {}).get("code")
        if fach and fc != fach:
            continue
        if stufe and k.get("stufe") != stufe:
            continue
        if kompetenzbereich and _fold(kompetenzbereich) not in (
                _fold(bereich.get("name", "")), _fold(bereich.get("id_teil", ""))):
            continue
        if code and k.get("id") != code:
            continue
        if stichworte:
            # Stichwort matcht Kompetenztext ODER Anwendungsbereichs-/Lehrstoff-Texte.
            hay = _fold(" ".join([k.get("text", "")]
                                 + [a.get("text", "") for a in k.get("anwendungsbereiche", [])]
                                 + list(k.get("lehrstoff", []) or [])))
            if not all(w in hay for w in stichworte):
                continue
        res.append(_enrich(shard, bereich, k))
    return res


def finde_progression(shards, kompetenz_id, richtung) -> list[dict]:
    _, _, k = find_by_id(shards, kompetenz_id)
    if not k:
        return []
    ids = k.get("vorlaeufer", []) if richtung == "zurueck" else k.get("folge", [])
    res = []
    for kid in ids:
        s, b, kk = find_by_id(shards, kid)
        if kk:
            res.append(_enrich(s, b, kk))
    return res


def finde_anwendungsbereiche(shards, kompetenz_id, nur_verbindlich=False) -> list[dict]:
    _, _, k = find_by_id(shards, kompetenz_id)
    if not k:
        return []
    items = k.get("anwendungsbereiche", [])
    if nur_verbindlich:
        items = [i for i in items if i.get("verbindlich")]
    return items


def finde_lehrstoff(shards, kompetenz_id) -> dict:
    _, _, k = find_by_id(shards, kompetenz_id)
    if not k:
        return {"quelle": None, "items": []}
    quelle = k.get("lehrstoff_quelle", "aus_anwendungsbereichen")
    items = k.get("lehrstoff", []) or []
    # MS: quelle=aus_anwendungsbereichen, items ggf. leer -> via finde_anwendungsbereiche
    return {"quelle": quelle, "items": items}


def finde_bildungsstandard_bezug(shards, kompetenz_id):
    shard, _, k = find_by_id(shards, kompetenz_id)
    if not k:
        return {"abgedeckt": False, "grund": "Kompetenz nicht gefunden"}
    fach = shard.get("meta", {}).get("fach", {}).get("code")
    if fach == "SU":
        return {"abgedeckt": False, "grund": "keine BiSt verordnet"}
    deskr = k.get("bildungsstandard_deskriptoren", [])
    return {"abgedeckt": bool(deskr), "deskriptoren": deskr}


def finde_uebergreifende_themen(shards, arg):
    # Richtung 1: kompetenz_id -> Themen der Kompetenz
    if ID_RE.match(arg):
        _, _, k = find_by_id(shards, arg)
        return {"richtung": "kompetenz->themen", "themen": (k or {}).get("uebergreifende_themen", [])}
    # Richtung 2: Fach-Code -> Themen des Fachs
    fach_codes = {s.get("meta", {}).get("fach", {}).get("code") for s in shards}
    if arg in fach_codes:
        for s in shards:
            if s.get("meta", {}).get("fach", {}).get("code") == arg:
                return {"richtung": "fach->themen",
                        "themen": s.get("meta", {}).get("uebergreifende_themen_fach", [])}
    # Richtung 3: Thema -> Faecher (Invertierung, § 10.1)
    faecher = []
    for s in shards:
        meta = s.get("meta", {})
        themen = meta.get("uebergreifende_themen_fach", [])
        if any(arg.lower() == t.lower() for t in themen):
            faecher.append(meta.get("fach", {}).get("code"))
    return {"richtung": "thema->faecher", "faecher": faecher}


def finde_differenzierung(shards, kompetenz_id) -> dict:
    shard, _, k = find_by_id(shards, kompetenz_id)
    if not k:
        return {"achse": None, "niveaus": [], "enrichment_items": [],
                "vorklasse_stuetzen": [], "docs_material": []}
    achse = shard.get("meta", {}).get("differenzierungs_achse", {})
    enrichment = [i for i in k.get("anwendungsbereiche", []) if not i.get("verbindlich")]
    stuetzen = finde_progression(shards, kompetenz_id, "zurueck")
    fach = shard.get("meta", {}).get("fach", {}).get("code")
    docs = finde_lernaufgaben(fach=fach, stufe=k.get("stufe"), kompetenz_id=kompetenz_id)
    return {
        "achse": achse,
        "niveaus": achse.get("niveaus", []),
        "enrichment_items": enrichment,
        "vorklasse_stuetzen": [s["id"] for s in stuetzen],
        "docs_material": docs,
    }


def finde_typische_fehlvorstellungen(shards, kompetenz_id) -> list[dict]:
    _, _, k = find_by_id(shards, kompetenz_id)
    return (k or {}).get("typische_fehlvorstellungen", [])


def finde_lernaufgaben(fach=None, stufe=None, kompetenz_id=None) -> list[dict]:
    """NUR lehrpersonen-eigenes Material aus docs/ (§ 5.5, § 7.6). Leer, wenn nichts da."""
    if not DOCS_DIR.exists():
        return []
    res = []
    for path in sorted(DOCS_DIR.rglob("*")):
        if not path.is_file() or path.name == "README.md":
            continue
        if ".cache" in path.parts:
            continue
        if path.suffix.lower() not in (".md", ".txt", ".pdf", ".docx"):
            continue
        rel = path.relative_to(DOCS_DIR).parts
        ordner_fach = rel[0].lower() if len(rel) >= 2 else None
        fc = FACH_ALIAS.get(ordner_fach, "nicht zugeordnet" if ordner_fach else None)
        st = rel[1] if len(rel) >= 3 else None
        m = re.search(r"__(AT\.LP23\.[A-Z0-9.]+)", path.stem)
        verkn = [m.group(1)] if m else []
        if fach and fc != fach:
            continue
        if stufe and st != stufe:
            continue
        if kompetenz_id and kompetenz_id not in verkn:
            continue
        res.append({"titel": path.stem, "pfad": str(path.relative_to(REPO_ROOT)),
                    "fach": fc, "stufe": st, "verknuepfte_kompetenzen": verkn,
                    "herkunft": "docs", "amtlich": False})
    return res


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _out(obj):
    # Stub: immer JSON (maschinenlesbar). --json wird zur Vertragskompatibilitaet
    # akzeptiert; eine menschenlesbare Ausgabe kommt mit dem Voll-Lookup.
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def main(argv=None) -> int:
    # --json als gemeinsamer Elternparser -> gueltig VOR und NACH dem Subkommando
    # (Spec-Beispiel § 6 schreibt "... finde_kompetenz ... --json").
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="JSON-Ausgabe")

    p = argparse.ArgumentParser(
        description="AT LP2023 Kompetenz-Lookup (Tool-Vertrag § 6).", parents=[common])
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("finde_kompetenz", parents=[common])
    a.add_argument("--fach"); a.add_argument("--stufe")
    a.add_argument("--kompetenzbereich"); a.add_argument("--code")
    a.add_argument("--stichworte", nargs="*")

    a = sub.add_parser("finde_progression", parents=[common])
    a.add_argument("--id", required=True)
    a.add_argument("--richtung", choices=["zurueck", "vor"], required=True)

    a = sub.add_parser("finde_anwendungsbereiche", parents=[common])
    a.add_argument("--id", required=True)
    a.add_argument("--nur-verbindlich", action="store_true")

    for name in ("finde_lehrstoff", "finde_bildungsstandard_bezug",
                 "finde_differenzierung", "finde_typische_fehlvorstellungen"):
        a = sub.add_parser(name, parents=[common]); a.add_argument("--id", required=True)

    a = sub.add_parser("finde_lernaufgaben", parents=[common])
    a.add_argument("--fach"); a.add_argument("--stufe"); a.add_argument("--id")

    a = sub.add_parser("finde_uebergreifende_themen", parents=[common])
    a.add_argument("--arg", required=True)

    args = p.parse_args(argv)
    shards = load_shards()

    if args.cmd == "finde_kompetenz":
        r = finde_kompetenz(shards, args.fach, args.stufe, args.kompetenzbereich,
                            args.code, args.stichworte)
    elif args.cmd == "finde_progression":
        r = finde_progression(shards, args.id, args.richtung)
    elif args.cmd == "finde_anwendungsbereiche":
        r = finde_anwendungsbereiche(shards, args.id, args.nur_verbindlich)
    elif args.cmd == "finde_lehrstoff":
        r = finde_lehrstoff(shards, args.id)
    elif args.cmd == "finde_bildungsstandard_bezug":
        r = finde_bildungsstandard_bezug(shards, args.id)
    elif args.cmd == "finde_differenzierung":
        r = finde_differenzierung(shards, args.id)
    elif args.cmd == "finde_typische_fehlvorstellungen":
        r = finde_typische_fehlvorstellungen(shards, args.id)
    elif args.cmd == "finde_lernaufgaben":
        r = finde_lernaufgaben(args.fach, args.stufe, args.id)
    elif args.cmd == "finde_uebergreifende_themen":
        r = finde_uebergreifende_themen(shards, args.arg)
    else:  # pragma: no cover
        p.error(f"unbekanntes Kommando: {args.cmd}")
        return 2

    _out(r)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

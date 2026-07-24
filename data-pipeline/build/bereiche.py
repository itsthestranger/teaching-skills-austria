#!/usr/bin/env python3
"""bereiche.py — Kompetenzbereiche eines Fachs parsen (Backlog P1-04).

Liefert je Fach die inhaltlichen Kompetenzbereiche (§ 5.2) mit:
  * name              — amtlicher Bereichsname, VERBATIM aus der Quelle gezogen
                        (Titel "Kompetenzbereich [N:] <Name>"), NICHT hart
                        angenommen (§ 0.1).
  * id_teil           — eigener Kurzcode (§ 5.8, "Struktur/IDs selbst vergeben");
                        kuratierte Zuordnung je Bereichsname + deterministischer
                        Fallback-Generator (mit Warnung) für Unbekanntes.
  * zentrales_konzept — verbatim Konzeptbeschreibung aus der Sektion
                        "Zentrale fachliche Konzepte" (§ 5.1), dem Bereichsnamen
                        zugeordnet.

Quell-Anker (band-generisch verifiziert an MS + VS Mathematik, 2026-07):
  * Bereichs-Sektion  = erll-Titel "Kompetenzbereich <N>: <Name>" (Sek I, je
                        Klasse wiederholt -> dedupliziert) bzw. "Kompetenzbereich
                        <Name>" (VS, ohne Nummer).
  * Konzepttexte      = Absätze der Sektion "Zentrale fachliche Konzepte", je
                        Bereich der mit dem Bereichsnamen beginnende Absatz samt
                        Folgeabsätzen bis zum nächsten Bereich.

Robustheit (§ 0.1): fehlende Konzepte / unbekannte Bereichsnamen werden gewarnt
und übernommen, nie verworfen, nie abgebrochen. Text verbatim (§ 0.2). stdlib-only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from struktur import Fach, parse_datei  # noqa: E402

# --------------------------------------------------------------------------- #
# Anker (§ 5.2, § 10.1)
# --------------------------------------------------------------------------- #

# Singular-Bereich; das Leerzeichen nach "Kompetenzbereich" grenzt gegen die
# Plural-Intro-Sektion "Kompetenzbereiche (…):" ab (die hat dort ein "e").
_BEREICH_TITEL = re.compile(
    r"^\s*Kompetenzbereich\s+(?:(\d+)\s*:\s*)?(.+?)\s*$"
)

# --------------------------------------------------------------------------- #
# Eigene Bereich-Codes (§ 5.8) — KEINE Quelldaten, sondern kuratierte ID-Vergabe.
# Schlüssel = Bereichsname (lower, verbatim aus Quelle). Fehlt ein Name hier,
# greift der Fallback-Generator (+ Warnung), damit neue Bereiche nie verloren
# gehen (§ 0.1).
# --------------------------------------------------------------------------- #

_BEREICH_CODE: dict[str, str] = {
    # Mathematik Sek I (Fallstudie § 15)
    "zahlen und maße": "ZAHLEN",
    "variablen und funktionen": "VARFUNK",
    "figuren und körper": "FIGKOERP",
    "daten und zufall": "DATENZUFALL",
}

_UMLAUT = str.maketrans({"ä": "AE", "ö": "OE", "ü": "UE", "ß": "SS",
                         "Ä": "AE", "Ö": "OE", "Ü": "UE"})
_NICHT_ALNUM = re.compile(r"[^A-Z0-9]")
_STOPP = {"UND", "DER", "DIE", "DAS", "VON", "MIT", "IM", "ZUM", "ZUR"}


def _code_aus_name(name: str) -> str:
    """Deterministischer ASCII-Code aus dem Bereichsnamen (Fallback, § 5.8)."""
    roh = name.upper().translate(_UMLAUT)
    woerter = [_NICHT_ALNUM.sub("", w) for w in roh.split()]
    woerter = [w for w in woerter if w and w not in _STOPP]
    code = "".join(woerter) or "BEREICH"
    return code[:16]


def bereich_code(name: str, warn: Optional[Callable[[str], None]] = None) -> str:
    kl = name.strip().lower()
    if kl in _BEREICH_CODE:
        return _BEREICH_CODE[kl]
    code = _code_aus_name(name)
    if warn:
        warn(f"kein kuratierter Code fuer Bereich {name!r} -> generiert {code!r} "
             f"(§ 5.8 pruefen)")
    return code


# --------------------------------------------------------------------------- #
# IR-Datenklasse
# --------------------------------------------------------------------------- #

@dataclass
class Kompetenzbereich:
    id_teil: str                    # eigener Code (§ 5.8)
    name: str                       # verbatim Bereichsname
    nummer: Optional[int] = None    # 1..4 falls nummeriert (Sek I)
    zentrales_konzept: str = ""     # verbatim aus "Zentrale fachliche Konzepte"

    def as_dict(self) -> dict:
        return {
            "id_teil": self.id_teil,
            "name": self.name,
            "nummer": self.nummer,
            "zentrales_konzept": self.zentrales_konzept,
        }


# --------------------------------------------------------------------------- #
# Extraktion
# --------------------------------------------------------------------------- #

def _bereichsnamen(fach: Fach) -> list[tuple[Optional[int], str]]:
    """(nummer, name) je Bereich in Reihenfolge; über Klassen dedupliziert."""
    gesehen: set[str] = set()
    treffer: list[tuple[Optional[int], str]] = []
    for s in fach.sektionen:
        m = _BEREICH_TITEL.match(s.titel)
        if not m:
            continue
        nummer = int(m.group(1)) if m.group(1) else None
        name = m.group(2).strip()
        schluessel = f"{nummer}|{name.lower()}"
        if schluessel in gesehen:
            continue
        gesehen.add(schluessel)
        treffer.append((nummer, name))
    return treffer


def _konzepte_je_bereich(
    fach: Fach, namen: list[str], warn: Callable[[str], None],
) -> dict[str, str]:
    """Konzepttext je Bereichsname aus 'Zentrale fachliche Konzepte' schneiden."""
    sektion = fach.sektion("Zentrale fachliche Konzepte")
    if sektion is None:
        warn(f"{fach.name}: Sektion 'Zentrale fachliche Konzepte' fehlt "
             f"-> zentrales_konzept leer")
        return {}
    para = [b.text for b in sektion.bloecke
            if b.tag in ("absatz", "liste") and b.text]
    # Startindex je Bereich (erster Absatz, der mit dem Namen beginnt).
    starts: list[tuple[int, str]] = []
    for name in namen:
        low = name.lower()
        for i, t in enumerate(para):
            if t.lower().startswith(low):
                starts.append((i, name))
                break
    starts.sort()
    ergebnis: dict[str, str] = {}
    for j, (idx, name) in enumerate(starts):
        ende = starts[j + 1][0] if j + 1 < len(starts) else len(para)
        ergebnis[name] = "\n\n".join(para[idx:ende])
    for name in namen:
        if name not in ergebnis:
            warn(f"{fach.name}: kein Konzepttext fuer Bereich {name!r} "
                 f"in 'Zentrale fachliche Konzepte'")
    return ergebnis


def parse_bereiche(
    fach: Fach,
    warn: Optional[Callable[[str], None]] = None,
) -> list[Kompetenzbereich]:
    """Kompetenzbereiche eines Fachs mit Name/id_teil/zentrales_konzept liefern."""
    warn = warn or (lambda m: print(f"WARN(bereiche): {m}", file=sys.stderr))
    namen_paare = _bereichsnamen(fach)
    if not namen_paare:
        warn(f"{fach.name}: keine 'Kompetenzbereich …'-Sektionen gefunden")
        return []
    namen = [n for _, n in namen_paare]
    konzepte = _konzepte_je_bereich(fach, namen, warn)

    bereiche: list[Kompetenzbereich] = []
    for nummer, name in namen_paare:
        bereiche.append(Kompetenzbereich(
            id_teil=bereich_code(name, warn),
            name=name,
            nummer=nummer,
            zentrales_konzept=konzepte.get(name, ""),
        ))
    return bereiche


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

_STD_MS = (Path(__file__).resolve().parents[1]
           / "sources" / "ms_mittelschule" / "NOR40271471.xml")


def _print_bereiche(fach_name: str, bereiche: list[Kompetenzbereich]) -> None:
    print(f"Kompetenzbereiche {fach_name}: {len(bereiche)}\n")
    for b in bereiche:
        nr = f"{b.nummer}: " if b.nummer else ""
        print(f"### id_teil={b.id_teil!r}  name={nr}{b.name!r}")
        vorschau = b.zentrales_konzept.replace("\n", " ").strip()
        print(f"    zentrales_konzept ({len(b.zentrales_konzept)} Z.): "
              f"{vorschau[:180]}\n")


def _check(fach_name: str, bereiche: list[Kompetenzbereich]) -> int:
    """Akzeptanz P1-04: 4 Bereiche mit Name + id_teil + zentrales_konzept."""
    ok = True
    print(f"Bereiche gefunden: {len(bereiche)} (erwartet 4 fuer Mathematik)")
    if len(bereiche) != 4:
        print("WARN: nicht genau 4 Bereiche (§ 0.1: weich)")
    for b in bereiche:
        maengel = []
        if not b.name.strip():
            maengel.append("name")
        if not b.id_teil.strip():
            maengel.append("id_teil")
        if not b.zentrales_konzept.strip():
            maengel.append("zentrales_konzept")
        if maengel:
            print(f"FAIL: Bereich {b.name!r} unvollstaendig: {', '.join(maengel)}")
            ok = False
        else:
            print(f"OK: {b.id_teil:<12} {b.name!r}  "
                  f"(Konzept {len(b.zentrales_konzept)} Z.)")
    print("\nRESULT:", "PASS" if ok and bereiche else "FAIL")
    return 0 if ok and bereiche else 1


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Kompetenzbereiche parsen (P1-04)")
    p.add_argument("xml", nargs="?", default=str(_STD_MS),
                   help="Pfad zum Anlagen-XML (Default: MS NOR40271471)")
    p.add_argument("--band", choices=["SEK1", "PRIM"],
                   help="Band erzwingen (Default: aus Verzeichnisname)")
    p.add_argument("--fach", default="MATHEMATIK",
                   help="Fach (Default: MATHEMATIK)")
    p.add_argument("--json", action="store_true", help="Bereiche als JSON ausgeben")
    p.add_argument("--check", action="store_true",
                   help="Akzeptanz P1-04 pruefen (Exit 1 bei Fehlschlag)")
    args = p.parse_args(argv)

    doc = parse_datei(args.xml, band=args.band)
    fach = doc.fach(args.fach)
    if fach is None:
        print(f"Fach {args.fach!r} nicht gefunden. Verfuegbar: "
              + ", ".join(f.name for f in doc.faecher()), file=sys.stderr)
        return 1

    bereiche = parse_bereiche(fach)

    if args.json:
        print(json.dumps([b.as_dict() for b in bereiche],
                         ensure_ascii=False, indent=2))
        return 0
    if args.check:
        return _check(fach.name, bereiche)
    _print_bereiche(fach.name, bereiche)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

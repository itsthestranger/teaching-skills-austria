#!/usr/bin/env python3
"""beschreibungen.py — Kompetenzbeschreibungen je Klasse parsen (Backlog P1-05).

Liefert je Fach die einzelnen Kompetenzbeschreibungen (§ 5.3, § 10.1), gruppierbar
nach Kompetenzbereich × Stufe (Sek I: K1..K4 = 1.–4. Klasse):

    text   — VERBATIM (§ 0.2 Ausnahme): amtlicher Anker
             "Die Schülerinnen und Schüler können" + Listeneintrag als voller Satz.
    stufe  — K1..K4, aus dem "N. Klasse:"-Marker abgeleitet.
    bereich— Kompetenzbereich (Name + eigener id_teil, § 5.8; via bereiche.py).

Quell-Anker (Sek-I-Mittelschule, verifiziert 2026-07):
  * "Kompetenzbereiche (1. bis 4. Klasse):" leitet den Kompetenzteil ein und
    trägt den ersten Klassenmarker "1. Klasse:".
  * je Klasse folgen die vier Sektionen "Kompetenzbereich <N>: <Name>" mit
    Absatz "Die Schülerinnen und Schüler können" + <aufzaehlung>/<listelem>-Liste.
  * der nächste Klassenmarker ("2. Klasse:" …) steht als Schluss-Absatz der
    letzten Bereichssektion der Vorklasse — daher wird die Stufe über die
    Sektionsgrenzen hinweg mitgeführt.
  * Kompetenzteil endet vor "Anwendungsbereiche (…):" (Feinparsung P1-06).

Robustheit (§ 0.1): fehlende Klassen-/Bereichskontexte werden gewarnt, die
Kompetenz aber übernommen; nie abgebrochen. Der Listen-Bullet ("– ") wird als
reines Layout-Zeichen entfernt, der übrige Wortlaut bleibt verbatim (inkl.
Hochzahl-Marker; deren Auswertung ist P1-09). stdlib-only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ris_xml import local, node_text  # noqa: E402
from struktur import Fach, parse_datei  # noqa: E402
from bereiche import _BEREICH_TITEL, bereich_code  # noqa: E402

# --------------------------------------------------------------------------- #
# Anker (§ 10.1, § 0.2)
# --------------------------------------------------------------------------- #

_KLASSE_MARKER = re.compile(r"^\s*(\d+)\.\s*Klasse\s*:\s*$")
_LEADIN_ANKER = "Die Schülerinnen und Schüler können"
_BULLET = re.compile(r"^\s*[–—-]\s*")


def _strip_bullet(text: str) -> str:
    return _BULLET.sub("", text, count=1).strip()


# --------------------------------------------------------------------------- #
# IR-Datenklasse
# --------------------------------------------------------------------------- #

@dataclass
class Kompetenz:
    bereich_id_teil: str        # eigener Bereich-Code (§ 5.8)
    bereich_name: str           # verbatim Bereichsname
    stufe: str                  # K1..K4 (bzw. "?" wenn kein Klassenkontext)
    text: str                   # verbatim: Lead-in + Listeneintrag
    lfd: int                    # laufende Nr. im (Bereich, Stufe), 1-basiert

    def as_dict(self) -> dict:
        return {
            "bereich_id_teil": self.bereich_id_teil,
            "bereich_name": self.bereich_name,
            "stufe": self.stufe,
            "text": self.text,
            "lfd": self.lfd,
        }


# --------------------------------------------------------------------------- #
# Extraktion
# --------------------------------------------------------------------------- #

def parse_kompetenzen(
    fach: Fach,
    warn: Optional[Callable[[str], None]] = None,
) -> list[Kompetenz]:
    """Kompetenzbeschreibungen eines Fachs (Sek-I-Struktur) extrahieren."""
    warn = warn or (lambda m: print(f"WARN(beschreibungen): {m}", file=sys.stderr))
    ergebnis: list[Kompetenz] = []
    lfd_zaehler: Counter = Counter()
    stufe: Optional[str] = None   # über Sektionsgrenzen mitgeführt

    for s in fach.sektionen:
        titel_low = s.titel.strip().lower()
        if titel_low.startswith("anwendungsbereiche"):
            break   # ab hier P1-06
        m = _BEREICH_TITEL.match(s.titel)
        ist_bereich = bool(m) and not titel_low.startswith("kompetenzbereiche")
        bereich_name = m.group(2).strip() if ist_bereich else None
        id_teil = bereich_code(bereich_name, warn) if bereich_name else None
        aktueller_leadin: Optional[str] = None

        for b in s.bloecke:
            if b.tag == "absatz":
                mk = _KLASSE_MARKER.match(b.text)
                if mk:
                    stufe = f"K{int(mk.group(1))}"
                    continue
                if ist_bereich:
                    aktueller_leadin = b.text
                    if not b.text.startswith(_LEADIN_ANKER):
                        warn(f"{fach.name}/{bereich_name}: unerwarteter Lead-in "
                             f"{b.text[:40]!r} (erwartet {_LEADIN_ANKER!r})")
                continue

            if b.tag == "liste" and ist_bereich:
                items = [le for le in b.el.iter() if local(le.tag) == "listelem"]
                if not items:   # Liste ohne listelem -> Rohtext als ein Item
                    items = [b.el]
                for le in items:
                    item = _strip_bullet(node_text(le))
                    if not item:
                        continue
                    voll = (f"{aktueller_leadin} {item}" if aktueller_leadin
                            else item)
                    if stufe is None:
                        warn(f"{fach.name}/{bereich_name}: Kompetenz ohne "
                             f"Klassenkontext -> stufe='?'")
                    st = stufe or "?"
                    lfd_zaehler[(id_teil, st)] += 1
                    ergebnis.append(Kompetenz(
                        bereich_id_teil=id_teil or "?",
                        bereich_name=bereich_name or "?",
                        stufe=st,
                        text=voll,
                        lfd=lfd_zaehler[(id_teil, st)],
                    ))

    if not ergebnis:
        warn(f"{fach.name}: keine Kompetenzbeschreibungen gefunden")
    return ergebnis


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

_STD_MS = (Path(__file__).resolve().parents[1]
           / "sources" / "ms_mittelschule" / "NOR40271471.xml")


def _print_kompetenzen(fach_name: str, komp: list[Kompetenz]) -> None:
    print(f"Kompetenzbeschreibungen {fach_name}: {len(komp)}\n")
    aktuell = None
    for k in komp:
        kopf = (k.bereich_id_teil, k.stufe)
        if kopf != aktuell:
            print(f"\n[{k.stufe}] {k.bereich_id_teil} — {k.bereich_name}")
            aktuell = kopf
        print(f"    {k.lfd:>2}. {k.text[:150]}")


def _check(fach_name: str, komp: list[Kompetenz]) -> int:
    """Akzeptanz P1-05: je Bereich × Klasse ≥ 1 Kompetenz, stufe K1–K4, verbatim."""
    ok = True
    bereiche = sorted({k.bereich_id_teil for k in komp})
    stufen = sorted({k.stufe for k in komp})
    print(f"Kompetenzen gesamt: {len(komp)}")
    print(f"Bereiche: {bereiche}")
    print(f"Stufen:   {stufen}")

    erwartete_stufen = {"K1", "K2", "K3", "K4"}
    if set(stufen) != erwartete_stufen:
        print(f"WARN: Stufen != {sorted(erwartete_stufen)} (§ 0.1: weich)")

    kombis = Counter((k.bereich_id_teil, k.stufe) for k in komp)
    fehlend = [(b, st) for b in bereiche for st in sorted(erwartete_stufen)
               if kombis[(b, st)] == 0]
    if fehlend:
        print(f"FAIL: fehlende Bereich×Klasse-Kombinationen: {fehlend}")
        ok = False
    else:
        print(f"OK: alle {len(bereiche)}×{len(erwartete_stufen)} "
              f"Bereich×Klasse-Kombinationen mit ≥1 Kompetenz belegt")

    ohne_anker = [k for k in komp if not k.text.startswith(_LEADIN_ANKER)]
    if ohne_anker:
        print(f"WARN: {len(ohne_anker)} Kompetenzen ohne Lead-in-Anker "
              f"(z. B. {ohne_anker[0].text[:50]!r})")
    else:
        print(f"OK: alle Kompetenztexte verbatim mit Anker {_LEADIN_ANKER!r}")

    leer = [k for k in komp if not k.text.strip()]
    if leer:
        print(f"FAIL: {len(leer)} leere Kompetenztexte"); ok = False

    print("\nRESULT:", "PASS" if ok and komp else "FAIL")
    return 0 if ok and komp else 1


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Kompetenzbeschreibungen parsen (P1-05)")
    p.add_argument("xml", nargs="?", default=str(_STD_MS),
                   help="Pfad zum Anlagen-XML (Default: MS NOR40271471)")
    p.add_argument("--band", choices=["SEK1", "PRIM"],
                   help="Band erzwingen (Default: aus Verzeichnisname)")
    p.add_argument("--fach", default="MATHEMATIK",
                   help="Fach (Default: MATHEMATIK)")
    p.add_argument("--json", action="store_true", help="Kompetenzen als JSON")
    p.add_argument("--check", action="store_true",
                   help="Akzeptanz P1-05 pruefen (Exit 1 bei Fehlschlag)")
    args = p.parse_args(argv)

    doc = parse_datei(args.xml, band=args.band)
    fach = doc.fach(args.fach)
    if fach is None:
        print(f"Fach {args.fach!r} nicht gefunden. Verfuegbar: "
              + ", ".join(f.name for f in doc.faecher()), file=sys.stderr)
        return 1

    komp = parse_kompetenzen(fach)

    if args.json:
        print(json.dumps([k.as_dict() for k in komp],
                         ensure_ascii=False, indent=2))
        return 0
    if args.check:
        return _check(fach.name, komp)
    _print_kompetenzen(fach.name, komp)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

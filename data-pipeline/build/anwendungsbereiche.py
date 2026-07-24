#!/usr/bin/env python3
"""anwendungsbereiche.py — Anwendungsbereiche + Verbindlichkeit (Backlog P1-06).

Parst die getrennte Sektion "Anwendungsbereiche (1. bis 4. Klasse):" (Sek I,
§ 5.4, § 10.1). Dort werden die Kompetenzbeschreibungen "anhand des Lehrstoffs
präzisiert": je Kompetenz (Absatz "Die Schülerinnen und Schüler können …") folgt
eine Liste von Anwendungsbereich-/Lehrstoff-Inhalten.

Verbindlichkeit (§ 5.4): amtliche Legende "Die mit „allenfalls“ gekennzeichneten
Inhalte sind nicht verbindlich." -> je Inhalt `verbindlich: bool`. Da "allenfalls"
oft nur einen Teil eines Listeneintrags betrifft ("Lesen und allenfalls Schreiben
…"; "…; allenfalls Durchführen von …"), wird auf KLAUSEL-Ebene getrennt (Split am
Strichpunkt): eine Klausel mit "allenfalls" ist `verbindlich=false`, sonst true.
Damit trennt `nur_verbindlich` sauber Standard- von allenfalls-Inhalten.
-> `anwendungsbereiche_status = item_flags` (§ 5.7).

Zuordnung zur Kompetenz (P1-05): die präzisierte Kompetenzbeschreibung wird per
buchstaben-normalisiertem Textabgleich an die Kompetenz desselben Bereichs/derselben
Stufe gebunden (`kompetenz_lfd`); bei fehlendem Match wird gewarnt, die Items aber
behalten (§ 0.1). Der Block "Vorschläge für den Einsatz digitaler Technologien" je
Klasse ist KEINE Kompetenz-Präzisierung und wird übersprungen.

Robustheit (§ 0.1): warnen + weiterlaufen, nie abbrechen. Text verbatim (§ 0.2),
nur der Listen-Bullet wird entfernt. stdlib-only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ris_xml import local, node_text  # noqa: E402
from struktur import Fach, parse_datei  # noqa: E402
from bereiche import _BEREICH_TITEL, bereich_code  # noqa: E402
from beschreibungen import (  # noqa: E402
    _KLASSE_MARKER, _LEADIN_ANKER, _strip_bullet, parse_kompetenzen,
)

# --------------------------------------------------------------------------- #
# Anker (§ 5.4, § 10.1)
# --------------------------------------------------------------------------- #

_ALLENFALLS = "allenfalls"
_DIGITAL_ANKER = "Vorschläge für den Einsatz digitaler Technologien"
_NUR_BUCHST = re.compile(r"[^a-zäöüß]")


def _match_key(text: str) -> str:
    """Buchstaben-Normalform für den Kompetenz-Textabgleich (ignoriert
    Zeichensetzung, Hochzahl-Marker, Leerzeichen)."""
    return _NUR_BUCHST.sub("", text.lower())


def _klauseln(item_text: str) -> list[str]:
    """Listeneintrag am Strichpunkt in Klauseln zerlegen (verbatim, getrimmt)."""
    roh = _strip_bullet(item_text)
    return [c.strip() for c in roh.split(";") if c.strip()]


# --------------------------------------------------------------------------- #
# IR-Datenklassen
# --------------------------------------------------------------------------- #

@dataclass
class Anwendungsbereich:
    text: str                  # verbatim Inhalt (eine Klausel)
    verbindlich: bool          # false, wenn "allenfalls" enthalten (§ 5.4)

    def as_dict(self) -> dict:
        return {"text": self.text, "verbindlich": self.verbindlich}


@dataclass
class Anwendungsgruppe:
    stufe: str                 # K1..K4
    bereich_id_teil: str
    bereich_name: str
    kompetenz_text: str        # präzisierte Kompetenzbeschreibung (verbatim)
    kompetenz_lfd: Optional[int] = None   # Zuordnung P1-05 (per Textmatch)
    items: list[Anwendungsbereich] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "stufe": self.stufe,
            "bereich_id_teil": self.bereich_id_teil,
            "bereich_name": self.bereich_name,
            "kompetenz_lfd": self.kompetenz_lfd,
            "kompetenz_text": self.kompetenz_text,
            "items": [i.as_dict() for i in self.items],
        }


# --------------------------------------------------------------------------- #
# Extraktion
# --------------------------------------------------------------------------- #

def parse_anwendungsbereiche(
    fach: Fach,
    warn: Optional[Callable[[str], None]] = None,
) -> list[Anwendungsgruppe]:
    """Anwendungsbereich-Gruppen (je Kompetenz) mit Verbindlichkeits-Flags."""
    warn = warn or (lambda m: print(f"WARN(anwendungsbereiche): {m}", file=sys.stderr))
    sektion = fach.sektion("Anwendungsbereiche")
    if sektion is None:
        warn(f"{fach.name}: Sektion 'Anwendungsbereiche' fehlt")
        return []

    # Kompetenz-Index (P1-05) für die Zuordnung: match_key -> (lfd, id_teil).
    komp_index: dict[str, tuple[int, str]] = {}
    for k in parse_kompetenzen(fach, warn=lambda m: None):
        komp_index.setdefault(_match_key(k.text), (k.lfd, k.bereich_id_teil))

    gruppen: list[Anwendungsgruppe] = []
    stufe: Optional[str] = None
    bereich_name: Optional[str] = None
    bereich_code_: Optional[str] = None
    aktuelle: Optional[Anwendungsgruppe] = None
    liste_ueberspringen = False

    for b in sektion.bloecke:
        if b.tag == "absatz":
            mk = _KLASSE_MARKER.match(b.text)
            if mk:
                stufe = f"K{int(mk.group(1))}"
                aktuelle = None
                liste_ueberspringen = False
                continue
            mb = _BEREICH_TITEL.match(b.text)
            if mb and not b.text.strip().lower().startswith("kompetenzbereiche"):
                bereich_name = mb.group(2).strip()
                bereich_code_ = bereich_code(bereich_name, warn)
                aktuelle = None
                liste_ueberspringen = False
                continue
            if b.text.startswith(_LEADIN_ANKER):
                lfd_id = komp_index.get(_match_key(b.text))
                if lfd_id is None:
                    warn(f"{fach.name}/{bereich_name}/{stufe}: praezisierte "
                         f"Kompetenz ohne P1-05-Match: {b.text[:60]!r}")
                aktuelle = Anwendungsgruppe(
                    stufe=stufe or "?",
                    bereich_id_teil=bereich_code_ or (lfd_id[1] if lfd_id else "?"),
                    bereich_name=bereich_name or "?",
                    kompetenz_text=b.text,
                    kompetenz_lfd=lfd_id[0] if lfd_id else None,
                )
                gruppen.append(aktuelle)
                liste_ueberspringen = False
                continue
            if b.text.startswith(_DIGITAL_ANKER):
                aktuelle = None
                liste_ueberspringen = True   # folgende Liste = Digital-Vorschlaege
                continue
            # sonstiger Absatz (Intro/Legende) -> keine Zuordnung
            aktuelle = None
            liste_ueberspringen = False
            continue

        if b.tag == "liste":
            if liste_ueberspringen or aktuelle is None:
                continue
            items = [le for le in b.el.iter() if local(le.tag) == "listelem"]
            if not items:
                items = [b.el]
            for le in items:
                for klausel in _klauseln(node_text(le)):
                    verbindlich = _ALLENFALLS not in klausel.lower()
                    aktuelle.items.append(
                        Anwendungsbereich(text=klausel, verbindlich=verbindlich))

    if not gruppen:
        warn(f"{fach.name}: keine Anwendungsbereich-Gruppen erkannt")
    return gruppen


def anwendungsbereiche_status(gruppen: list[Anwendungsgruppe]) -> str:
    """`item_flags`, sobald einzelne Items als unverbindlich markiert sind."""
    for g in gruppen:
        if any(not i.verbindlich for i in g.items):
            return "item_flags"
    return "item_flags"   # Sek I: Legende definiert stets item-Flags (§ 5.4)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

_STD_MS = (Path(__file__).resolve().parents[1]
           / "sources" / "ms_mittelschule" / "NOR40271471.xml")


def _print_gruppen(fach_name: str, gruppen: list[Anwendungsgruppe]) -> None:
    n_items = sum(len(g.items) for g in gruppen)
    print(f"Anwendungsbereiche {fach_name}: {len(gruppen)} Gruppen, "
          f"{n_items} Items\n")
    for g in gruppen:
        lfd = f"#{g.kompetenz_lfd}" if g.kompetenz_lfd else "#?"
        print(f"[{g.stufe}] {g.bereich_id_teil} {lfd}: {g.kompetenz_text[:70]}")
        for it in g.items:
            flag = "  " if it.verbindlich else "○ "   # ○ = allenfalls
            print(f"    {flag}{it.text[:110]}")
        print()


def _check(fach_name: str, gruppen: list[Anwendungsgruppe]) -> int:
    """Akzeptanz P1-06: Standard vs. allenfalls trennbar (nur_verbindlich)."""
    ok = True
    alle = [(g, it) for g in gruppen for it in g.items]
    verb = [it for _, it in alle if it.verbindlich]
    allf = [it for _, it in alle if not it.verbindlich]
    print(f"Gruppen: {len(gruppen)}   Items gesamt: {len(alle)}")
    print(f"  verbindlich:        {len(verb)}")
    print(f"  allenfalls (false): {len(allf)}")

    if not gruppen:
        print("FAIL: keine Gruppen"); ok = False
    if not allf:
        print("FAIL: kein einziges allenfalls-Item erkannt "
              "(Trennung nicht demonstrierbar)"); ok = False
    else:
        # jede als false markierte Klausel muss 'allenfalls' enthalten
        falsch = [it for it in allf if _ALLENFALLS not in it.text.lower()]
        if falsch:
            print(f"FAIL: {len(falsch)} false-Items ohne 'allenfalls'"); ok = False
        # und die nur_verbindlich-Sicht darf kein allenfalls enthalten
        leck = [it for it in verb if _ALLENFALLS in it.text.lower()]
        if leck:
            print(f"FAIL: {len(leck)} verbindliche Items enthalten 'allenfalls'")
            ok = False
        if ok:
            print("OK: nur_verbindlich trennt Standard sauber von allenfalls")
        print(f"     Beispiel allenfalls: {allf[0].text[:80]!r}")

    ohne_match = [g for g in gruppen if g.kompetenz_lfd is None]
    if ohne_match:
        print(f"WARN: {len(ohne_match)} Gruppen ohne P1-05-Kompetenz-Match")
    else:
        print(f"OK: alle {len(gruppen)} Gruppen einer P1-05-Kompetenz zugeordnet")

    print(f"     anwendungsbereiche_status = {anwendungsbereiche_status(gruppen)!r}")
    print("\nRESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Anwendungsbereiche parsen (P1-06)")
    p.add_argument("xml", nargs="?", default=str(_STD_MS),
                   help="Pfad zum Anlagen-XML (Default: MS NOR40271471)")
    p.add_argument("--band", choices=["SEK1", "PRIM"],
                   help="Band erzwingen (Default: aus Verzeichnisname)")
    p.add_argument("--fach", default="MATHEMATIK",
                   help="Fach (Default: MATHEMATIK)")
    p.add_argument("--nur-verbindlich", action="store_true",
                   help="nur verbindliche Items ausgeben (Filter-Demo)")
    p.add_argument("--json", action="store_true", help="Gruppen als JSON")
    p.add_argument("--check", action="store_true",
                   help="Akzeptanz P1-06 pruefen (Exit 1 bei Fehlschlag)")
    args = p.parse_args(argv)

    doc = parse_datei(args.xml, band=args.band)
    fach = doc.fach(args.fach)
    if fach is None:
        print(f"Fach {args.fach!r} nicht gefunden. Verfuegbar: "
              + ", ".join(f.name for f in doc.faecher()), file=sys.stderr)
        return 1

    gruppen = parse_anwendungsbereiche(fach)

    if args.nur_verbindlich:
        for g in gruppen:
            g.items = [i for i in g.items if i.verbindlich]

    if args.json:
        print(json.dumps([g.as_dict() for g in gruppen],
                         ensure_ascii=False, indent=2))
        return 0
    if args.check:
        return _check(fach.name, gruppen)
    _print_gruppen(fach.name, gruppen)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""fachkopf.py — Fach-Kopf aus der Struktur-IR extrahieren (Backlog P1-03).

Der amtliche Fachlehrplan-Aufbau (§ 5.1) beginnt je Fach mit einem Kopfteil vor
den eigentlichen Kompetenzbeschreibungen:

    Bildungs- und Lehraufgabe · fachspezifische Kompetenzmodelle (+ Prozesse) ·
    zentrale fachliche Konzepte · didaktische Grundsätze

Erst danach folgen Kompetenzbeschreibungen / Anwendungsbereiche / Lehrstoff
(Feinparsung P1-04..P1-08). Dieses Modul sammelt die Kopf-Sektionen als Text
aus der von struktur.py gelieferten `Fach`-IR.

Kern-Anker (band-generisch verifiziert an MS + VS, 2026-07):
  * Kopf-Sektionen   = erll-Titel beginnt mit "Bildungs- und Lehraufgabe",
                       "Kompetenzmodell", "Zentrale fachliche Konzepte",
                       "Didaktische Grundsätze".
  * Kopf-Ende (Body) = erste erll-Sektion, deren Titel mit "Kompetenzbereich(e)",
                       "Kompetenzbeschreibungen" oder "Anwendungsbereiche" beginnt.

Robustheit (§ 0.1): Der Titel-Wortlaut variiert je Fach/Band ("1. – 4.Klasse" vs.
"1. bis 4. Schulstufe"), daher Anker als Präfix, case-insensitiv. Unbekannte
Kopf-Sektionen (z. B. VS "Hinweise zu den inhaltlichen Kompetenzbereichen")
werden als `sonstige` ÜBERNOMMEN und protokolliert — nie verworfen, nie
abgebrochen. Textwortlaut bleibt verbatim (§ 0.2). stdlib-only.
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
# Anker (§ 5.1, § 10.1)
# --------------------------------------------------------------------------- #

# Reihenfolge egal: klassifiziert wird per Titel-Präfix (case-insensitiv).
# schluessel -> Titel-Präfix (lower).
_KOPF_ANKER: tuple[tuple[str, str], ...] = (
    ("bildungs_lehraufgabe",    "bildungs- und lehraufgabe"),
    ("kompetenzmodell",         "kompetenzmodell"),
    ("zentrale_konzepte",       "zentrale fachliche konzepte"),
    ("didaktische_grundsaetze", "didaktische grundsätze"),
)

# Beginn des Kompetenz-Teils = Ende des Kopfes.
_BODY_GRENZE = re.compile(
    r"^\s*(kompetenzbereich|kompetenzbeschreibungen|anwendungsbereiche)",
    re.IGNORECASE,
)


# --------------------------------------------------------------------------- #
# IR-Datenklassen
# --------------------------------------------------------------------------- #

@dataclass
class KopfSektion:
    """Eine Kopf-Sektion: klassifizierter Schlüssel + verbatim Titel/Text."""
    schluessel: str          # bildungs_lehraufgabe | kompetenzmodell |
                             # zentrale_konzepte | didaktische_grundsaetze | sonstige
    titel: str               # erll-Titel (verbatim)
    text: str                # zusammengeführter Absatz-/Listentext (verbatim)

    def as_dict(self) -> dict:
        return {"schluessel": self.schluessel, "titel": self.titel, "text": self.text}


@dataclass
class Fachkopf:
    fach: str
    sektionen: list[KopfSektion] = field(default_factory=list)

    def get(self, schluessel: str) -> Optional[str]:
        """Text der ersten Kopf-Sektion mit diesem Schlüssel (oder None)."""
        for s in self.sektionen:
            if s.schluessel == schluessel:
                return s.text
        return None

    @property
    def bildungs_lehraufgabe(self) -> Optional[str]:
        return self.get("bildungs_lehraufgabe")

    @property
    def didaktische_grundsaetze(self) -> Optional[str]:
        return self.get("didaktische_grundsaetze")

    @property
    def kompetenzmodell(self) -> Optional[str]:
        return self.get("kompetenzmodell")

    @property
    def zentrale_konzepte(self) -> Optional[str]:
        return self.get("zentrale_konzepte")

    @property
    def sonstige(self) -> list[KopfSektion]:
        return [s for s in self.sektionen if s.schluessel == "sonstige"]

    def as_dict(self) -> dict:
        return {"fach": self.fach, "sektionen": [s.as_dict() for s in self.sektionen]}


# --------------------------------------------------------------------------- #
# Extraktion
# --------------------------------------------------------------------------- #

def _sektionstext(sektion) -> str:
    """Absatz-/Listenblöcke einer Sektion zu einem Text verbinden (verbatim)."""
    teile = [b.text for b in sektion.bloecke if b.text]
    return "\n\n".join(teile)


def _klassifiziere(titel: str) -> Optional[str]:
    kl = titel.strip().lower()
    for schluessel, praefix in _KOPF_ANKER:
        if kl.startswith(praefix):
            return schluessel
    return None


def extrahiere_fachkopf(
    fach: Fach,
    warn: Optional[Callable[[str], None]] = None,
) -> Fachkopf:
    """Kopf-Sektionen eines Fachs bis zum Beginn des Kompetenz-Teils sammeln.

    Iteriert die Sektionen in Dokumentreihenfolge; bricht am ersten Body-Anker
    ab (§ 10.1). Bekannte Kopf-Sektionen werden klassifiziert, unbekannte als
    `sonstige` übernommen und gewarnt (§ 0.1). Nie abbrechen.
    """
    warn = warn or (lambda m: print(f"WARN(fachkopf): {m}", file=sys.stderr))
    kopf = Fachkopf(fach=fach.name)

    for sektion in fach.sektionen:
        if _BODY_GRENZE.match(sektion.titel):
            break   # ab hier Kompetenzbeschreibungen/Anwendungsbereiche (P1-04+)
        schluessel = _klassifiziere(sektion.titel)
        if schluessel is None:
            schluessel = "sonstige"
            warn(f"{fach.name}: unbekannte Kopf-Sektion {sektion.titel!r} "
                 f"-> als 'sonstige' uebernommen")
        kopf.sektionen.append(
            KopfSektion(schluessel=schluessel, titel=sektion.titel,
                        text=_sektionstext(sektion))
        )

    if not kopf.sektionen:
        warn(f"{fach.name}: keine Kopf-Sektionen vor dem Kompetenz-Teil gefunden")
    else:
        for pflicht in ("bildungs_lehraufgabe", "didaktische_grundsaetze"):
            if not (kopf.get(pflicht) or "").strip():
                warn(f"{fach.name}: Kopf-Sektion {pflicht!r} fehlt oder leer")
    return kopf


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

_STD_MS = (Path(__file__).resolve().parents[1]
           / "sources" / "ms_mittelschule" / "NOR40271471.xml")


def _print_kopf(kopf: Fachkopf) -> None:
    print(f"Fach-Kopf: {kopf.fach}  ({len(kopf.sektionen)} Kopf-Sektionen)\n")
    for s in kopf.sektionen:
        marke = "" if s.schluessel != "sonstige" else "  [sonstige]"
        print(f"### {s.schluessel}{marke} — {s.titel!r}")
        vorschau = s.text.replace("\n", " ").strip()
        print(f"    {len(s.text)} Zeichen: {vorschau[:200]}\n")


def _check(kopf: Fachkopf) -> int:
    """Akzeptanz P1-03: Bildungs-/Lehraufgabe + didaktische Grundsätze erfasst."""
    ok = True
    for schluessel, label in (
        ("bildungs_lehraufgabe", "Bildungs- und Lehraufgabe"),
        ("didaktische_grundsaetze", "Didaktische Grundsätze"),
    ):
        text = (kopf.get(schluessel) or "").strip()
        if text:
            print(f"OK: {label} erfasst ({len(text)} Zeichen)")
        else:
            print(f"FAIL: {label} nicht erfasst"); ok = False
    # informativ: weitere Kopfteile
    for schluessel, label in (("kompetenzmodell", "Kompetenzmodell"),
                              ("zentrale_konzepte", "Zentrale fachliche Konzepte")):
        text = (kopf.get(schluessel) or "").strip()
        status = f"{len(text)} Zeichen" if text else "fehlt (kein Muss)"
        print(f"     {label}: {status}")
    print("\nRESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Fach-Kopf extrahieren (P1-03)")
    p.add_argument("xml", nargs="?", default=str(_STD_MS),
                   help="Pfad zum Anlagen-XML (Default: MS NOR40271471)")
    p.add_argument("--band", choices=["SEK1", "PRIM"],
                   help="Band erzwingen (Default: aus Verzeichnisname)")
    p.add_argument("--fach", default="MATHEMATIK",
                   help="Fach (Default: MATHEMATIK)")
    p.add_argument("--json", action="store_true", help="Fach-Kopf als JSON ausgeben")
    p.add_argument("--check", action="store_true",
                   help="Akzeptanz P1-03 pruefen (Exit 1 bei Fehlschlag)")
    args = p.parse_args(argv)

    doc = parse_datei(args.xml, band=args.band)
    fach = doc.fach(args.fach)
    if fach is None:
        print(f"Fach {args.fach!r} nicht gefunden. Verfuegbar: "
              + ", ".join(f.name for f in doc.faecher()), file=sys.stderr)
        return 1

    kopf = extrahiere_fachkopf(fach)

    if args.json:
        print(json.dumps(kopf.as_dict(), ensure_ascii=False, indent=2))
        return 0
    if args.check:
        return _check(kopf)
    _print_kopf(kopf)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""struktur.py — Parser-Grundgeruest: RIS-Anlagen-XML -> Zwischenrepraesentation.

Aufgabe (Backlog P1-02, Spec § 10.1/§ 10.2, Fallstudie § 15):
segmentiert die flachen Nutzdaten-Bloecke (aus ris_xml.py) entlang der amtlichen
Gliederung in eine typisierte Zwischenrepraesentation (IR):

    Dokument
      └─ Teil (ERSTER..ZEHNTER; einer traegt die Fachlehrplaene)
           └─ Fach (VERSALIEN-Name, z. B. MATHEMATIK)
                └─ Sektion (erll-Ueberschrift: Bildungs-/Lehraufgabe,
                            Kompetenzbereich n: <Name>, Anwendungsbereiche, ...)
                     └─ Block[]  (Absaetze/Listen/Tabellen; Feinparsung: P1-03..P1-08)

Kern-Anker (§ 10.1), band-uebergreifend robust verifiziert (MS + VS, 2026-07):
  * TEIL-Grenze  = <ueberschrift typ=g1> mit Text "<ORDINAL> TEIL".
  * Fach-Grenze  = <ueberschrift typ=g1> (VERSALIEN-Fachname), deren NAECHSTE
                   Ueberschrift mit "Bildungs- und Lehraufgabe" beginnt.
  * Abschnitt    = <ueberschrift typ=g1> "A./B./... <...>" (Pflicht-/Freigegenstaende).
  * Fachlehrplan-TEIL je Band:  SEK1 = ACHTER (8),  PRIM = NEUNTER (9)  (§ 5.1).

Der Fach-Anker greift auch fuer Nicht-v1-Bloecke (Deutschfoerder-Lehrplanzusaetze,
VS-Vorschulstufe im ACHTER TEIL usw.); die Scope-Auswahl leistet der TEIL-Kontext.
Spaetere Phasen filtern Pflichtgegenstaende bzw. das gewuenschte Fach.

Robustheit (§ 0.1): Abweichungen werden in `Dokument.warnungen` gesammelt und auf
stderr gemeldet — NIE wird abgebrochen. stdlib-only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ris_xml import Block, lade_bloecke  # noqa: E402

# --------------------------------------------------------------------------- #
# Band-Profile (§ 5.1)
# --------------------------------------------------------------------------- #

# deutsche Ordnungszahlwoerter -> Nummer (fuer "<ORDINAL> TEIL").
_ORDINAL_NR = {
    "ERSTER": 1, "ZWEITER": 2, "DRITTER": 3, "VIERTER": 4, "FÜNFTER": 5,
    "FUENFTER": 5, "SECHSTER": 6, "SIEBENTER": 7, "SIEBTER": 7, "ACHTER": 8,
    "NEUNTER": 9, "ZEHNTER": 10, "ELFTER": 11, "ZWÖLFTER": 12, "ZWOELFTER": 12,
    "DREIZEHNTER": 13, "VIERZEHNTER": 14, "FÜNFZEHNTER": 15,
}
_NR_ORDINAL = {v: k for k, v in _ORDINAL_NR.items()
               if k not in ("FUENFTER", "SIEBTER", "ZWOELFTER")}


@dataclass(frozen=True)
class BandProfil:
    band: str                 # "SEK1" | "PRIM"
    fach_teil_nr: int         # TEIL mit den Fachlehrplaenen
    # rein informativ (spaetere Phasen): TEILe, die v1 uebersprungen werden
    skip_teile: tuple[int, ...] = ()
    skip_hinweis: dict[int, str] = field(default_factory=dict)


BAND_PROFILE = {
    "SEK1": BandProfil(
        band="SEK1", fach_teil_nr=8,
        # Deutschfoerderklassen liegen als Abschnitt F. innerhalb ACHTER TEIL
        skip_teile=(), skip_hinweis={},
    ),
    "PRIM": BandProfil(
        band="PRIM", fach_teil_nr=9,
        skip_teile=(8, 10),
        skip_hinweis={
            8: "ACHTER TEIL = Vorschulstufe (eigene Bereichsnamen, § 5.2)",
            10: "ZEHNTER TEIL = Deutschfoerderklassen (v1 ausgeklammert, § 1)",
        },
    ),
}

# Band aus dem Quell-Verzeichnisnamen ableiten (fetch_ris_resources.py-Keys).
_DIR_BAND = {"ms_mittelschule": "SEK1", "vs_volksschule": "PRIM"}

# Anker-Regexe
_TEIL_RE = re.compile(r"^\s*([A-ZÄÖÜ]+)\s+TEIL\s*$")
_ABSCHNITT_RE = re.compile(r"^\s*([A-Z])\.\s+\S")   # "A. PFLICHTGEGENSTÄNDE"
_LEHRAUFGABE_ANKER = "Bildungs- und Lehraufgabe"


# --------------------------------------------------------------------------- #
# IR-Datenklassen
# --------------------------------------------------------------------------- #

@dataclass
class Sektion:
    titel: str                       # erll-Ueberschrift (verbatim)
    bloecke: list[Block] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "titel": self.titel,
            "block_tags": [b.tag for b in self.bloecke],
            "bloecke": len(self.bloecke),
        }


@dataclass
class Fach:
    name: str                        # VERSALIEN-Fachname (verbatim)
    teil_nr: int
    abschnitt: Optional[str] = None  # "A. PFLICHTGEGENSTÄNDE" o. Ae.
    vorspann: list[Block] = field(default_factory=list)   # Bloecke vor 1. Sektion
    sektionen: list[Sektion] = field(default_factory=list)

    def sektion(self, praefix: str) -> Optional[Sektion]:
        """Erste Sektion, deren Titel mit `praefix` beginnt (case-insensitive)."""
        p = praefix.lower()
        for s in self.sektionen:
            if s.titel.lower().startswith(p):
                return s
        return None

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "teil_nr": self.teil_nr,
            "abschnitt": self.abschnitt,
            "vorspann_bloecke": len(self.vorspann),
            "sektionen": [s.as_dict() for s in self.sektionen],
        }


@dataclass
class Teil:
    nr: Optional[int]                # 1..10; None wenn Ordinal unbekannt
    ordinal: str                     # verbatim ("ACHTER")
    ist_fachlehrplan_teil: bool = False
    titel: Optional[str] = None      # g2-Untertitel (z. B. "LEHRPLÄNE DER ...")
    faecher: list[Fach] = field(default_factory=list)
    bloecke: list[Block] = field(default_factory=list)   # Nicht-Fach-Inhalt

    def as_dict(self) -> dict:
        return {
            "nr": self.nr,
            "ordinal": self.ordinal,
            "ist_fachlehrplan_teil": self.ist_fachlehrplan_teil,
            "titel": self.titel,
            "faecher": [f.as_dict() for f in self.faecher],
            "sonstige_bloecke": len(self.bloecke),
        }


@dataclass
class Dokument:
    band: Optional[str]
    quelle: Optional[str] = None     # Dateiname/NOR (Provenienz-Anschluss P1-10)
    teile: list[Teil] = field(default_factory=list)
    rand_bloecke: list[Block] = field(default_factory=list)  # Metadaten/Vorspann
    warnungen: list[str] = field(default_factory=list)

    # -- Zugriffshilfen ------------------------------------------------------ #
    @property
    def fachlehrplan_teil(self) -> Optional[Teil]:
        for t in self.teile:
            if t.ist_fachlehrplan_teil:
                return t
        return None

    def faecher(self) -> list[Fach]:
        t = self.fachlehrplan_teil
        return list(t.faecher) if t else []

    def fach(self, name: str) -> Optional[Fach]:
        """Fach im Fachlehrplan-TEIL per (case-insensitivem) Namen finden."""
        ziel = name.strip().lower()
        for f in self.faecher():
            if f.name.strip().lower() == ziel:
                return f
        return None

    def as_dict(self) -> dict:
        return {
            "band": self.band,
            "quelle": self.quelle,
            "teile": [t.as_dict() for t in self.teile],
            "rand_bloecke": len(self.rand_bloecke),
            "warnungen": self.warnungen,
        }


# --------------------------------------------------------------------------- #
# Segmentierung
# --------------------------------------------------------------------------- #

def _band_aus_pfad(xml_pfad: Path) -> Optional[str]:
    return _DIR_BAND.get(xml_pfad.parent.name)


def _naechste_ueberschrift_text(bloecke: list[Block], ab_index: int) -> Optional[str]:
    for b in bloecke[ab_index + 1:]:
        if b.tag == "ueberschrift":
            return b.text
    return None


def segmentiere(
    bloecke: list[Block],
    band: Optional[str],
    quelle: Optional[str] = None,
) -> Dokument:
    """Flache Blockliste -> Dokument-IR (Teil/Fach/Sektion). Warnt statt abbricht."""
    profil = BAND_PROFILE.get(band) if band else None
    doc = Dokument(band=band, quelle=quelle)

    def warn(msg: str) -> None:
        doc.warnungen.append(msg)
        print(f"WARN(struktur): {msg}", file=sys.stderr)

    if band and not profil:
        warn(f"unbekanntes Band {band!r} — ohne Fachlehrplan-TEIL-Markierung")

    teil: Optional[Teil] = None
    fach: Optional[Fach] = None
    sektion: Optional[Sektion] = None
    abschnitt_marker: Optional[str] = None

    for i, b in enumerate(bloecke):
        # --- TEIL-Grenze --------------------------------------------------- #
        if b.ist_ueberschrift("g1"):
            m = _TEIL_RE.match(b.text)
            if m:
                ordinal = m.group(1)
                nr = _ORDINAL_NR.get(ordinal)
                if nr is None:
                    warn(f"unbekanntes TEIL-Ordinal {ordinal!r} — nr=None")
                ist_fach = bool(profil and nr == profil.fach_teil_nr)
                teil = Teil(nr=nr, ordinal=ordinal, ist_fachlehrplan_teil=ist_fach)
                doc.teile.append(teil)
                fach = sektion = None
                abschnitt_marker = None
                continue

        # --- g2: TEIL-Untertitel ------------------------------------------- #
        if b.ist_ueberschrift("g2") and teil is not None and teil.titel is None:
            teil.titel = b.text
            continue

        # --- g1: Abschnittsmarker (A./B./...) ------------------------------ #
        if b.ist_ueberschrift("g1") and _ABSCHNITT_RE.match(b.text):
            abschnitt_marker = b.text
            fach = sektion = None
            continue

        # --- g1: Fach-Grenze (per Bildungs-/Lehraufgabe-Lookahead) --------- #
        if b.ist_ueberschrift("g1") and teil is not None:
            nxt = _naechste_ueberschrift_text(bloecke, i)
            if nxt and nxt.startswith(_LEHRAUFGABE_ANKER):
                fach = Fach(name=b.text, teil_nr=teil.nr if teil.nr else -1,
                            abschnitt=abschnitt_marker)
                teil.faecher.append(fach)
                sektion = None
                continue
            # sonstige g1 (z. B. Dokumenttitel "LEHRPLAN DER MITTELSCHULE")
            fach = sektion = None
            teil.bloecke.append(b)
            continue

        # --- g1min/erlz: als Nicht-Fach-Ueberschriften behandeln ----------- #
        # (Freigegenstaende-Untertypen etc. — kein v1-Scope; nicht Fach oeffnen)
        if b.ist_ueberschrift("g1min", "erlz"):
            fach = sektion = None
            (teil.bloecke if teil else doc.rand_bloecke).append(b)
            continue

        # --- erll: Sektionsueberschrift ------------------------------------ #
        if b.ist_ueberschrift("erll"):
            if fach is not None:
                sektion = Sektion(titel=b.text)
                fach.sektionen.append(sektion)
            elif teil is not None:
                teil.bloecke.append(b)   # erll in allgemeinen TEILen
            else:
                doc.rand_bloecke.append(b)
            continue

        # --- Metadaten-Titel (Kurztitel, Gesetzesnummer, ...) -------------- #
        if b.ist_ueberschrift("titel", "anlage"):
            doc.rand_bloecke.append(b)
            continue

        # --- Inhaltsblock (absatz/liste/table/abstand/...) ----------------- #
        if sektion is not None:
            sektion.bloecke.append(b)
        elif fach is not None:
            fach.vorspann.append(b)
        elif teil is not None:
            teil.bloecke.append(b)
        else:
            doc.rand_bloecke.append(b)

    _plausibilitaet(doc, profil, warn)
    return doc


def _plausibilitaet(doc: Dokument, profil: Optional[BandProfil], warn) -> None:
    """Weiche Nachpruefungen (§ 0.1) — nur Warnungen, keine Fehler."""
    if profil:
        ft = doc.fachlehrplan_teil
        if ft is None:
            warn(f"kein Fachlehrplan-TEIL (erwartet {_NR_ORDINAL.get(profil.fach_teil_nr)}"
                 f" TEIL / nr={profil.fach_teil_nr}) gefunden")
        elif not ft.faecher:
            warn(f"Fachlehrplan-TEIL {ft.ordinal} ohne erkannte Faecher")
    for f in doc.faecher():
        if not f.sektionen:
            warn(f"Fach {f.name!r} ohne Sektionen (kein erll nach Fach-Grenze?)")


def parse_datei(
    xml_pfad: Path | str,
    band: Optional[str] = None,
) -> Dokument:
    """Komfort: Datei laden, Band ggf. aus Pfad ableiten, segmentieren."""
    xml_pfad = Path(xml_pfad)
    band = band or _band_aus_pfad(xml_pfad)
    warnungen: list[str] = []
    bloecke = lade_bloecke(xml_pfad, warn=lambda m: warnungen.append(m))
    doc = segmentiere(bloecke, band=band, quelle=xml_pfad.stem)
    doc.warnungen[:0] = warnungen   # ris_xml-Warnungen voranstellen
    return doc


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

_STD_MS = (Path(__file__).resolve().parents[1]
           / "sources" / "ms_mittelschule" / "NOR40271471.xml")


def _print_uebersicht(doc: Dokument) -> None:
    print(f"Band: {doc.band}   Quelle: {doc.quelle}")
    print(f"TEILe: {len(doc.teile)}")
    for t in doc.teile:
        marke = "  <== Fachlehrplaene" if t.ist_fachlehrplan_teil else ""
        untertitel = f" — {t.titel}" if t.titel else ""
        print(f"  {t.ordinal} TEIL (nr={t.nr}){untertitel}{marke}")
        for f in t.faecher:
            absch = f" [{f.abschnitt}]" if f.abschnitt else ""
            print(f"      • {f.name}{absch}  ({len(f.sektionen)} Sektionen)")
    if doc.warnungen:
        print(f"\nWarnungen ({len(doc.warnungen)}):")
        for w in doc.warnungen:
            print(f"  - {w}")


def _print_fach(fach: Fach) -> None:
    print(f"Fach: {fach.name}  (TEIL {fach.teil_nr}, {fach.abschnitt})")
    if fach.vorspann:
        print(f"  (Vorspann: {len(fach.vorspann)} Bloecke vor erster Sektion)")
    for s in fach.sektionen:
        print(f"  » {s.titel}   [{len(s.bloecke)} Bloecke]")


def _check(doc: Dokument) -> int:
    """Akzeptanzkriterium P1-02: MATHEMATIK-Fach im Fachlehrplan-TEIL finden."""
    ft = doc.fachlehrplan_teil
    fach = doc.fach("MATHEMATIK")
    ok = True

    if ft is None:
        print("FAIL: kein Fachlehrplan-TEIL erkannt"); ok = False
    elif doc.band == "SEK1" and ft.nr != 8:
        print(f"FAIL: Fachlehrplan-TEIL nr={ft.nr}, erwartet 8 (ACHTER)"); ok = False
    else:
        print(f"OK: Fachlehrplan-TEIL = {ft.ordinal} TEIL (nr={ft.nr})")

    if fach is None:
        print("FAIL: Fach MATHEMATIK nicht gefunden"); ok = False
    else:
        print(f"OK: Fach-Grenze MATHEMATIK gefunden (TEIL {fach.teil_nr}, "
              f"{len(fach.sektionen)} Sektionen)")
        if not fach.sektion("Bildungs- und Lehraufgabe"):
            print("FAIL: Sektion 'Bildungs- und Lehraufgabe' fehlt"); ok = False
        if not fach.sektion("Anwendungsbereiche"):
            print("WARN: Sektion 'Anwendungsbereiche' fehlt (P1-06 betroffen)")
        bereiche = [s.titel for s in fach.sektionen
                    if s.titel.startswith("Kompetenzbereich ")]
        print(f"     Kompetenzbereich-Sektionen: {len(bereiche)} "
              f"(erwartet 4×Klassen = 16)")

    print("\nRESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="RIS-Anlagen-XML -> Struktur-IR (P1-02)")
    p.add_argument("xml", nargs="?", default=str(_STD_MS),
                   help="Pfad zum Anlagen-XML (Default: MS NOR40271471)")
    p.add_argument("--band", choices=["SEK1", "PRIM"],
                   help="Band erzwingen (Default: aus Verzeichnisname)")
    p.add_argument("--fach", help="Sektionen dieses Fachs ausgeben")
    p.add_argument("--json", action="store_true",
                   help="IR als JSON (Struktur-Zusammenfassung) ausgeben")
    p.add_argument("--check", action="store_true",
                   help="Akzeptanz P1-02 pruefen (Exit 1 bei Fehlschlag)")
    args = p.parse_args(argv)

    doc = parse_datei(args.xml, band=args.band)

    if args.json:
        print(json.dumps(doc.as_dict(), ensure_ascii=False, indent=2))
        return 0
    if args.check:
        return _check(doc)
    if args.fach:
        fach = doc.fach(args.fach)
        if not fach:
            print(f"Fach {args.fach!r} nicht gefunden. Verfuegbar: "
                  + ", ".join(f.name for f in doc.faecher()))
            return 1
        _print_fach(fach)
        return 0

    _print_uebersicht(doc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

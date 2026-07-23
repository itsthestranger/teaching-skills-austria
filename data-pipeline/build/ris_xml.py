#!/usr/bin/env python3
"""ris_xml.py — Low-Level-Zugriff auf das RIS-Anlagen-XML (Nutzdaten-Ebene).

Diese Schicht kennt NUR die technische XML-Form des RIS-Konsolidat-Dokuments,
nicht die Lehrplan-Semantik (das macht struktur.py, § 10.1). Aufgaben:

  1) Datei parsen (namensraum-tolerant: es wird stets der lokale Tag-Name genutzt),
  2) den einen inhaltlichen <abschnitt> (Nutzdaten) finden,
  3) dessen direkte Kind-Bloecke in Dokumentreihenfolge als typisierte `Block`e
     liefern (Ueberschriften mit ihrem `typ`-Attribut, Absaetze, Listen, Tabellen),
  4) robusten Volltext je Element extrahieren (`node_text`): Leerelemente wie
     <nbsp/>/<gdash/> werden korrekt zu Zeichen, Listen-<symbol/> abgetrennt.

Beobachtete RIS-XML-Form (verifiziert an NOR40271471 / NOR40271469, 2026-07):
  risdok > (metadaten, nutzdaten > abschnitt, layoutdaten)
  Der gesamte Lehrplan-Text liegt FLACH als direkte Kinder EINES <abschnitt>;
  die Gliederung ergibt sich allein aus <ueberschrift typ="...">-Markern:
    typ=g1     TEIL / Fachname (VERSALIEN) / Abschnittsmarker (A./B./...)
    typ=g2     erlaeuternder TEIL-Untertitel
    typ=erll   Inline-Sektionsueberschrift (z. B. "Bildungs- und Lehraufgabe:")
    typ=titel  Metadaten-Feldnamen (Kurztitel, Gesetzesnummer, ...)

Robustheit (§ 0.1): Bei struktureller Abweichung wird gewarnt und weitergemacht,
nicht abgebrochen. stdlib-only.
"""
from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

# --------------------------------------------------------------------------- #
# Text-Extraktion
# --------------------------------------------------------------------------- #

# Leerelemente (kein eigener Text) -> Ersatzzeichen. nbsp/gdash/tab/br sind im
# RIS-XML strukturelle Glyphen ohne Textknoten; ohne Ersatz verkleben Woerter
# (z. B. "4.Klasse" statt "4. Klasse").
_GLYPH = {
    "nbsp": " ",
    "gdash": "–",   # Gedankenstrich (en dash)
    "tab": " ",
    "br": "\n",
}

_WS = re.compile(r"[ \t ]+")
_NL = re.compile(r"\s*\n\s*")


def local(tag: str) -> str:
    """Lokaler Tag-Name ohne Namensraum-Praefix."""
    return tag.rsplit("}", 1)[-1]


def node_text(el: ET.Element) -> str:
    """Kompletten sichtbaren Text eines Elements zusammenfuehren (verbatim-nah).

    Behandelt die RIS-Glyphen-Leerelemente und haengt hinter Listen-<symbol/>
    (Bullet) ein Leerzeichen, damit der Bullet vom Item-Text getrennt bleibt.
    Whitespace wird normalisiert (Mehrfach-Leerzeichen -> eines), NICHT der
    Wortlaut veraendert (§ 0.2).
    """
    parts: list[str] = []

    def walk(e: ET.Element) -> None:
        tag = local(e.tag)
        glyph = _GLYPH.get(tag)
        if glyph is not None:
            parts.append(glyph)
        if e.text:
            parts.append(e.text)
        for child in e:
            walk(child)
        if tag == "symbol":
            parts.append(" ")   # Listen-Bullet vom Folgetext trennen
        if e.tail:
            parts.append(e.tail)

    walk(el)
    text = "".join(parts)
    text = _WS.sub(" ", text)
    text = _NL.sub("\n", text)
    return text.strip()


# --------------------------------------------------------------------------- #
# Block-Modell (eine direkte Kind-Einheit des <abschnitt>)
# --------------------------------------------------------------------------- #

@dataclass
class Block:
    """Eine inhaltliche Einheit in Dokumentreihenfolge.

    `tag`  lokaler Elementname (ueberschrift | absatz | liste | table | abstand | ...)
    `typ`  bei Ueberschriften das RIS-`typ`-Attribut (g1|g2|erll|titel|...), sonst None
    `text` extrahierter Volltext (bei Listen/Tabellen ein Roh-Join; fuer die
           Feinparsung spaeterer Phasen dient `el`)
    `el`   das zugrunde liegende Element (fuer tiefere Parsung, z. B. Listelemente)
    """
    tag: str
    typ: Optional[str]
    text: str
    el: ET.Element

    # -- bequeme Praedikate -------------------------------------------------- #
    def ist_ueberschrift(self, *typen: str) -> bool:
        if self.tag != "ueberschrift":
            return False
        return not typen or (self.typ in typen)

    def __repr__(self) -> str:  # kompakt fuer Debug
        kopf = f"{self.tag}" + (f"[{self.typ}]" if self.typ else "")
        return f"<Block {kopf}: {self.text[:60]!r}>"


# --------------------------------------------------------------------------- #
# Laden
# --------------------------------------------------------------------------- #

def _finde_abschnitte(root: ET.Element) -> list[ET.Element]:
    return [e for e in root.iter() if local(e.tag) == "abschnitt"]


def lade_bloecke(
    xml_pfad: Path | str,
    warn: Optional[Callable[[str], None]] = None,
) -> list[Block]:
    """Anlagen-XML laden und die Nutzdaten-Bloecke in Dokumentreihenfolge liefern.

    Der Lehrplan-Text liegt als direkte Kinder EINES <abschnitt>. Sollten wider
    Erwarten mehrere <abschnitt> existieren, werden ihre Kinder konkateniert und
    eine Warnung ausgegeben (§ 0.1: weiterlaufen, nicht abbrechen).
    """
    warn = warn or (lambda m: print(f"WARN(ris_xml): {m}", file=sys.stderr))
    xml_pfad = Path(xml_pfad)
    root = ET.parse(xml_pfad).getroot()

    abschnitte = _finde_abschnitte(root)
    if not abschnitte:
        warn(f"kein <abschnitt> in {xml_pfad.name} — leere Blockliste")
        return []
    if len(abschnitte) > 1:
        warn(f"{len(abschnitte)} <abschnitt> in {xml_pfad.name} — konkateniere")

    bloecke: list[Block] = []
    for absch in abschnitte:
        for el in list(absch):
            tag = local(el.tag)
            typ = el.attrib.get("typ") if tag == "ueberschrift" else None
            bloecke.append(Block(tag=tag, typ=typ, text=node_text(el), el=el))
    return bloecke


if __name__ == "__main__":
    # Kleiner Selbstzweck-Aufruf: Tag/typ-Statistik der Bloecke einer Datei.
    from collections import Counter

    pfad = Path(sys.argv[1]) if len(sys.argv) > 1 else (
        Path(__file__).resolve().parents[1]
        / "sources" / "ms_mittelschule" / "NOR40271471.xml"
    )
    bloecke = lade_bloecke(pfad)
    stat = Counter((b.tag, b.typ) for b in bloecke)
    print(f"{len(bloecke)} Bloecke in {pfad.name}:")
    for (tag, typ), n in stat.most_common():
        etikett = tag + (f"[{typ}]" if typ else "")
        print(f"  {n:5d}  {etikett}")

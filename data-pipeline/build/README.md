# build/ — Parser RIS-XML → Shard-JSON (Phase 1+)

Der Parser (§ 10.1, § 10.2) liest das je Band korrekte Anlagen-XML aus
`../sources/` und erzeugt schema-valide Shards nach
`plugin/data/kompetenzen/<band>/<fach>.json`.

## Module

- **`ris_xml.py`** — Low-Level: Anlagen-XML laden, den einen `<abschnitt>`
  (Nutzdaten) finden, dessen direkte Kinder als typisierte `Block`e in
  Dokumentreihenfolge liefern; robuste Textextraktion (`node_text`) inkl. der
  RIS-Glyphen-Leerelemente (`<nbsp/>`/`<gdash/>`) und Listen-`<symbol/>`.
- **`struktur.py`** — Segmentierungs-Statemachine: flache Blockliste →
  Zwischenrepräsentation `Dokument → Teil → Fach → Sektion → Block[]`.
  Band-Profile (SEK1 = ACHTER TEIL, PRIM = NEUNTER TEIL, § 5.1).

Feinparsung (Kompetenzbereiche/Klassen/Anwendungsbereiche/Backlinks) baut auf
den `Sektion`en auf → Folge-Tasks P1-03…P1-08.

## Anker-Übersicht (§ 10.1, live verifiziert MS+VS 2026-07)

- **TEIL-Grenze:** `<ueberschrift typ=g1>` mit Text „`<ORDINAL> TEIL`".
- **Fach-Grenze:** `<ueberschrift typ=g1>` (VERSALIEN-Fachname), deren *nächste*
  Ueberschrift mit `Bildungs- und Lehraufgabe` beginnt.
- **MS (Sek I):** Fachlehrpläne ab `ACHTER TEIL`; getrennte Sektion
  `Anwendungsbereiche (…)`; `allenfalls` ⇒ `verbindlich:false` (P1-06).
- **VS (Primar):** Fachlehrpläne ab **NEUNTER TEIL** (nicht ACHTER!); ACHTER TEIL =
  Vorschulstufe (eigene Bereichsnamen, § 5.2), ZEHNTER TEIL = Deutschförderklassen
  (v1 übersprungen). VS nutzt „`N. Schulstufe:`"-Marker (SPK-01/F-05, → P4-04).
- Abweichungen werden **protokolliert, nicht abgebrochen** (§ 0.1) —
  `Dokument.warnungen` + stderr.

## Aufruf

```
python3 data-pipeline/build/struktur.py                 # MS-Uebersicht (Default)
python3 data-pipeline/build/struktur.py --check         # Akzeptanz P1-02 (Exit 1 bei Fehler)
python3 data-pipeline/build/struktur.py --fach MATHEMATIK
python3 data-pipeline/build/struktur.py <VS-XML>        # Band aus Verzeichnisname (PRIM)
python3 data-pipeline/build/struktur.py --json          # IR-Zusammenfassung als JSON
python3 data-pipeline/build/ris_xml.py [XML]            # Block-Tag/typ-Statistik
```

Status: **P1-02 erfüllt** — findet die Fach-Grenze `MATHEMATIK` im ACHTER TEIL,
gibt die strukturierte Zwischenrepräsentation aus; band-generisch gegen VS geprüft.
Offen: F-05 (VS-Stufen-Granularität GS I/II vs. je Schulstufe, → P4-04).

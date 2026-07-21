# build/ — Parser RIS-XML → Shard-JSON (Phase 1+)

Platzhalter. Der Parser (§ 10.1, § 10.2) liest das je Band korrekte Anlagen-XML aus
`../sources/` und erzeugt schema-valide Shards nach `plugin/data/kompetenzen/<band>/<fach>.json`.

Anker-Übersicht:
- **Fach-Grenze:** Fachname (VERSALIEN) + `Bildungs- und Lehraufgabe:`.
- **MS (Sek I):** ab `ACHTER TEIL`; getrennte Sektion `Anwendungsbereiche (…)`; `allenfalls` ⇒ `verbindlich:false`.
- **VS (Primar):** ab **NEUNTER TEIL** (nicht ACHTER!); kombinierte Sektion
  `Kompetenzbeschreibungen und Anwendungsbereiche, Lehrstoff (…):`.
- Abweichungen **protokollieren, nicht abbrechen** (§ 0.1).

Offen: F-05 (VS-Stufen-Granularität GS I/II vs. je Schulstufe), Volltext-Parser-Nachweis (F-02 Rest).

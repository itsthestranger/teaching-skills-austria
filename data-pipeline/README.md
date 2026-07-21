# data-pipeline/ (nicht ausgeliefert)

Erzeugt die Kompetenz-Shards unter `plugin/data/` aus dem RIS. **Nur RIS** (§ 4).

## Ordner
- `fetch_ris_resources.py` — holt VS-/MS-Lehrplan + Bildungsstandards-VO als XML+PDF
  nach `sources/` (Discovery über RIS-OGD-API v2.6, live verifiziert 2026-07-21, § 10.0).
- `schema/kompetenzen.schema.json` — JSON-Schema der Shards (§ 5.7).
- `validate.py` — validiert Shards gegen das Schema (harte/weiche Trennung, § 0.1 / § 9.2).
- `sources/` — heruntergeladene RIS-Rohdaten (XML/PDF, gitignored).
- `build/` — Parser RIS-XML → Shard-JSON (Phase 1+, § 10.2).

## Nutzung
    python3 data-pipeline/fetch_ris_resources.py --dry-run     # Discovery zeigen
    python3 data-pipeline/fetch_ris_resources.py               # nach sources/ laden
    python3 data-pipeline/fetch_ris_resources.py --self-test sources/<response>.json
    python3 data-pipeline/validate.py                          # Shards prüfen

RIS-Höflichkeit: eigener User-Agent (Kontakt `ps@strangeprojects.com`); bei regelmäßigem
Abruf kurze Meldung an `ris.it@bka.gv.at` (§ 10.0).

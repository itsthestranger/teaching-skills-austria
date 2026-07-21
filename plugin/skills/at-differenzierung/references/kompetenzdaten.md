# Kompetenzdaten — Tool-Vertrag & Datenzugriff (§ 6)

Gemeinsame Referenz beider Skills. Datenzugriff über den Lookup-Stub
`plugin/scripts/kompetenz.py` (Option B1: lädt die Shard-JSONs unter
`plugin/data/kompetenzen/<band>/<fach>.json` direkt). Der Vertrag ist identisch
zu B2 (SQLite) und einem späteren MCP → nicht-brechende Umstellung.

## Funktionen

| Aufruf | Rückgabe |
|---|---|
| `finde_kompetenz(fach, stufe?, kompetenzbereich?, code?, stichworte?[])` | `Kompetenz[]` |
| `finde_progression(kompetenz_id, richtung: zurueck\|vor)` | `Kompetenz[]` (Spiralprinzip) |
| `finde_anwendungsbereiche(kompetenz_id, nur_verbindlich?)` | `Item[]` |
| `finde_lehrstoff(kompetenz_id)` | `{quelle, items[]}` |
| `finde_lernaufgaben(fach?, stufe?, kompetenz_id?)` | `Lernaufgabe[]` — **nur** aus `docs/` |
| `finde_bildungsstandard_bezug(kompetenz_id)` | `Deskriptor[]`; SU → `{abgedeckt:false, grund}` |
| `finde_uebergreifende_themen(fach\|kompetenz_id\|thema)` | `Thema[]\|Fach[]` (beide Richtungen) |
| `finde_differenzierung(kompetenz_id)` | `{achse, niveaus[], enrichment_items[], vorklasse_stuetzen[], docs_material[]}` |
| `finde_typische_fehlvorstellungen(kompetenz_id)` | `Fehlvorstellung[]` (`amtlich:false`) |

## Beispiel

    python3 plugin/scripts/kompetenz.py finde_kompetenz --fach M --stufe K2 --stichworte Bruch --json

## Grundsätze
- Kompetenzbeschreibung **wörtlich** übernehmen, **RIS-Quelle** (NOR/BGBl./Stand) mitführen (§ 12).
- Verbindliche vs. `allenfalls`-Anwendungsbereiche sauber trennen.
- `docs/`-Material stets **als lehrpersonen-eigen** ausweisen, nie als amtlich (§ 7.6, § 12).

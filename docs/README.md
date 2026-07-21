# docs/ — Zusatzmaterial von Lehrpersonen

Dateien in diesem Ordner werden von den Skills als optionale, lehrpersonen-eigene
Ressourcen einbezogen (z. B. eigene Lernaufgaben, Arbeitsblätter, differenzierte
Materialien). Siehe Spec § 7.6.

## Zuordnung per Ordnerkonvention

    docs/<fach>/<stufe>/...   z. B. docs/mathematik/K2/bruchrechnen.md
    docs/<fach>/...           nur Fach (stufenübergreifend)
    docs/...                  unspezifisch (Fach/Stufe = leer)

- `<fach>`: mathematik, deutsch, englisch, sachunterricht, … (wird auf Fach-Code
  M/D/E/SU gemappt; unbekannt ⇒ „nicht zugeordnet", nicht verworfen).
- `<stufe>` optional: K1..K4 (Sek I) bzw. VOR/GS1/GS2 (VS).
- Feinzuordnung optional: `kompetenz_id` als Dateinamen-Suffix
  (`…__AT.LP23.SEK1.M.ZAHLEN.K2.03.md`) oder in YAML-Frontmatter.

## Formate
- Nativ: `.md`, `.txt`
- `.pdf` und `.docx` werden bei der Einbindung automatisch nach Markdown konvertiert
  (Cache: `docs/.cache/`; Quelle bleibt unverändert). Nur-gescannte PDFs werden als
  „nicht verwertbar" protokolliert.

## Grenzen (Default, überschreibbar)
- max. 2 MB je Datei, max. 20 Dateien je Anfrage; darüber nach Relevanz gedeckelt.

Diese Inhalte sind **nicht** Teil des amtlichen RIS-Datensatzes; die Lizenz/Urheberschaft
liegt bei der jeweiligen Lehrperson und wird in der Ausgabe als lehrpersonen-eigen
ausgewiesen. Der Ordnerinhalt (außer diese README) wird **nicht** mitausgeliefert.

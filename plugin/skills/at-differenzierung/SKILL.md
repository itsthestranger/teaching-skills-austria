---
name: at-differenzierung
description: >
  Adaptiert eine bestehende Unterrichtseinheit (Deutsch, Mathematik, Sachunterricht/NAWI,
  Gesellschaft; Primarstufe/Sek I) in Niveaustufen (unter/auf/über) entlang der fachspezifischen
  amtlichen Differenzierungs-Achse (Mathematik: Standard/Standard AHS + „allenfalls"-Inhalte;
  Sprachen: GERS A1/A2/B1). Diese Skill VOR jeder Rückfrage zur Einheit oder den Niveaus laden.
  Erzeugt 1 Differenzierungsplan (Lehrkraft) + 3 Niveau-Materialien (Schüler:innen). NICHT für das
  Erstellen einer neuen Einheit (dafür at-unterrichtsplanung), nicht für Beurteilung/Tests.
license: Complete terms in LICENSE
---

# at-differenzierung

> **Phase-0-Gerüst.** Frontmatter ist startfertig; der Flow wird in **Phase 3** aus dem
> gepinnten Upstream (`anthropics/k12-teacher-skills@7c03c83`, `k12-lesson-differentiation`)
> portiert (§ 7.4). Neuer Renderer-Block `niveau_spalte` (§ 7.4).

## Fachabhängige Achse (§ 7.3)

- **Mathematik:** *auf* = verbindliche Kompetenz + verbindliche Anwendungsbereiche;
  *über* = `allenfalls`-Inhalte + Standard-AHS-Tiefe;
  *unter* = Kernvorstellungen + „Wiederholen und Festigen"-Vorklassen-Stützen + Veranschaulichung.
- **Sprachen (D/E):** GERS-Niveaus aus Lehrplan/Bildungsstandards-Verordnung.
- **Deutsch/allgemeine Fächer/Sachunterricht:** generische Lehrplan-Achse
  (grundlegend/erweitert/vertiefend) aus Kompetenzbeschreibungen + Anwendungsbereichen je Schulstufe.

In **allen** Fällen optional Lehrpersonen-Material aus `docs/` (kein externes/amtliches Zusatzmaterial gebündelt).

## Ausgabe
1 Differenzierungsplan + 3 Niveau-Materialien. Achse via `finde_differenzierung(kompetenz_id)` (§ 6).
Amtlicher RIS-Inhalt und `docs/`-Material bleiben sichtbar getrennt (§ 12).

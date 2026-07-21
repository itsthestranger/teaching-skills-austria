---
name: at-unterrichtsplanung
description: >
  Erstellt eine kompetenzorientierte Unterrichtsplanung, Schüler:innen-Material und einen
  Beobachtungsbogen nach dem österreichischen Lehrplan 2023 (Primarstufe und Sekundarstufe I).
  Diese Skill VOR jeder Rückfrage zu Schulstufe, Fach, Thema oder Kompetenz laden. Einsetzen, wenn
  eine Lehrkraft eine Unterrichtseinheit für Deutsch, Mathematik, Sachunterricht/NAWI oder
  Gesellschaft neu erstellen will — auch wenn Fach, Stufe oder Thema noch nicht genannt sind.
  NICHT laden für Beurteilung, Schularbeit/Test, reine Kompetenz-Nachschlage (direkt beantworten)
  oder das Differenzieren einer bestehenden Einheit (dafür at-differenzierung). Eine neue Einheit,
  die differenzierte/mehrstufige Materialien verlangt, ist EINE Planungsanfrage — diese Skill
  erzeugt sie im Paket; nicht zusätzlich at-differenzierung aufrufen.
license: Complete terms in LICENSE
---

# at-unterrichtsplanung

> **Phase-0-Gerüst.** Frontmatter ist startfertig; der Ablauf unten ist die Kurzfassung
> aus Spec § 7.2. Der Planungs-Flow und die docx-Ausgabe werden in **Phase 2** aus dem
> gepinnten Upstream (`anthropics/k12-teacher-skills@7c03c83`, `k12-lesson-planning`)
> portiert und eingedeutscht (§ 7.4).

## Ablauf (§ 7.2)

1. **Routen** über die Fachgruppe → passende `references/<fachgruppe>.md` laden.
2. **Klären** (0–2 Fragen) + Entwurfsangebot.
3. **In Kompetenzen verankern:** Kompetenzbeschreibung **wörtlich + RIS-Quelle** (NOR/BGBl./Stand);
   Vorläufer via `finde_progression`; Anwendungsbereiche verbindlich vs. optional trennen;
   Lehrstoff; Bildungsstandard-Bezug; übergreifende Themen.
4. **Aufbauen** nach Spiralprinzip (Vorwissen aktivieren).
5. **Ausgabe (ein Turn):** `lesson.json` → docx.

## Dokumenten-Set
- `unterrichtsplanung` (Lehrkraft)
- `schueler_material` (Schüler:innen, nur bei Bedarf)
- `beobachtungsbogen` (Lehrkraft; Look-fors aus Anwendungsbereichen/Lehrstoff, Standard/Standard-AHS)

## Datenzugriff
Tool-Vertrag & Lookup: siehe `references/kompetenzdaten.md` und `plugin/scripts/kompetenz.py` (§ 6).
Optionales Lehrpersonen-Material aus `docs/` wird **als lehrpersonen-eigen** ausgewiesen (§ 7.6, § 12).

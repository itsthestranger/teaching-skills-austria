# teaching-skills-austria

Öffentliches Claude-Plugin für **kompetenzorientierten Unterricht** nach dem
österreichischen **Lehrplan 2023** (Primarstufe & Sekundarstufe I). Portiert das
Konzept von [`anthropics/k12-teacher-skills`](https://github.com/anthropics/k12-teacher-skills)
(Apache-2.0, co-entwickelt von Anthropic & Learning Commons) auf Österreich.

Zwei Skills:

- **`at-unterrichtsplanung`** — kompetenzorientierte Unterrichtsplanung + Schüler:innen-Material
  + Beobachtungsbogen, verankert in Kompetenzbeschreibungen, Anwendungsbereichen/Lehrstoff und Spiralprinzip.
- **`at-differenzierung`** — adaptiert eine bestehende Einheit in Niveaustufen (unter/auf/über)
  entlang der **fachspezifischen** amtlichen Differenzierungs-Achse.

**Scope v1:** Sek I = Mathematik, Deutsch, Englisch · Primarstufe = Mathematik, Deutsch, Sachunterricht.

## Datenbezug — ausschließlich RIS

Alle gebündelten Kompetenzdaten stammen **ausschließlich aus dem RIS** (Rechtsinformationssystem
des Bundes): die Lehrpläne (VS/MS) und die Bildungsstandards-Verordnung. Das sind **Verordnungen
und damit freie Werke nach § 7 UrhG** — verbatim weiterverwendbar. Provenienz (NOR/BGBl./Stand)
wird durchgängig mitgeführt. Details: Spec § 4. Bewusst **nicht** bezogen: IQS-Aufbereitungen,
Pädagogik-Paket, Uni-Projekte.

**Lehrpersonen-Zusatzmaterial** kann in `docs/` abgelegt werden und wird zur Laufzeit optional
einbezogen — stets als lehrpersonen-eigen ausgewiesen, nie als amtlich (§ 7.6).

## Konnektor-Hinweis

Dieses Plugin ist eine **Übergangslösung**: Ein umfassender, offizieller Konnektor (der über das
RIS hinaus amtlich kuratierte Materialien anbietet) wäre das Ideal und sollte sinnvollerweise von
einem **öffentlichen Träger (BMBWF)** bereitgestellt werden (§ 2, § 11 Phase 6).

## Repo-Struktur

    plugin/
      .claude-plugin/{plugin.json, marketplace.json}
      data/kompetenzen/{prim,sek1}/*.json · uebergreifende_themen.json
      scripts/kompetenz.py                    # Lookup (Tool-Vertrag § 6)
      skills/{at-unterrichtsplanung,at-differenzierung}/{SKILL.md, references/, scripts/}
    data-pipeline/                            # nicht ausgeliefert
      fetch_ris_resources.py · validate.py · schema/ · sources/ · build/
    evals/{at-unterrichtsplanung,at-differenzierung}/rubrics/*.csv
    docs/                                     # Laufzeit-Ordner für Lehrpersonen-Material

## Quickstart (Phase 0)

    # Schema-Validierung des Fixtures/der Shards
    python3 data-pipeline/validate.py

    # Lookup gegen die gebündelten Shards (Tool-Vertrag § 6)
    python3 plugin/scripts/kompetenz.py finde_kompetenz --fach M --stufe K2 --stichworte Bruch --json

    # RIS-Discovery zeigen (geht ans Netz) bzw. Rohdaten laden
    python3 data-pipeline/fetch_ris_resources.py --dry-run

    # Plugin lokal laden
    claude plugin marketplace add ./plugin

## Status

**Phase 0 (Fundament)** — Repo-Gerüst, Schema, ID-Schema, Manifeste, `kompetenz.py`-Stub,
`fetch_ris_resources.py` (Discovery live verifiziert 2026-07-21), `docs/`. Fahrplan & Abnahme:
Spec § 11 / § 11.1.

## Lizenz

Code: **Apache-2.0** (siehe `LICENSE`). Attribution & Datenherkunft: siehe `NOTICE`.
Governing Spec: `teaching-skills-austria-spec-v0_7-draft.md`.

Autor: **Phillip Stranger** / **strangeprojects** · Kontakt: `ps@strangeprojects.com`

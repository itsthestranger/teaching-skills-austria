# scripts/ — Renderer (Phase 2/3)

Hier werden die Renderer-Helfer aus dem gepinnten Upstream portiert und eingedeutscht:

- Upstream: `anthropics/k12-teacher-skills@7c03c83db8223b050b6569ffbe14cd94e229396e` (Apache-2.0).
- Zu portieren: `render_lesson_docx.py`, `render_documents.py`, `lesson_common.py`,
  `render_lesson_html.py` (falls HTML mitgezogen wird).
- `lesson.json` → docx: deutsche Labels, AT-Dokumenttypen
  (`unterrichtsplanung`/`schueler_material`/`beobachtungsbogen`), Schema beibehalten.

**Renderer-Delta (echte Code-Arbeit, § 7.4):** neue Blocktypen `kompetenzbezug`,
`uebergreifende_themen_tag` und (nur at-differenzierung) `niveau_spalte`; Herkunfts-Kennzeichnung
amtlich vs. `docs/`. Upstream `.mcp.json` (US-EdTech-SaaS) beim Eindeutschen entfernen (§ 7.4, § 13 #7).

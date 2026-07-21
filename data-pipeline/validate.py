#!/usr/bin/env python3
"""validate.py — validiert Kompetenz-Shards gegen das Schema (§ 5.7).

Harte/weiche Trennung nach § 0.1 / § 9.2:
  HART  (Exit 1 / CI-rot): Struktur/Pflichtfelder (id/stufe/text, meta), ID-
        Eindeutigkeit (shard- und global), ID-Muster.
  WEICH (nur Report):      enum-Zugehoerigkeit (band, anwendungsbereiche_status,
        lehrstoff_quelle, stufe-Defaults), Vollstaendigkeit.

Struktur-Validierung nutzt `jsonschema`, falls installiert; sonst greifen die
eingebauten harten Kernchecks (stdlib-only) weiter.

Aufruf:
  python3 data-pipeline/validate.py                      # alle Shards
  python3 data-pipeline/validate.py plugin/data/kompetenzen/sek1/M.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO / "data-pipeline" / "schema" / "kompetenzen.schema.json"
DATA_DIR = REPO / "plugin" / "data" / "kompetenzen"

ID_RE = re.compile(r"^AT\.LP23\.(PRIM|SEK1)\..+")
STUFE_DEFAULTS = {"K1", "K2", "K3", "K4", "VOR", "GS1", "GS2",
                  "SCH1", "SCH2", "SCH3", "SCH4"}
BAND_ENUM = {"PRIM", "SEK1"}
AB_STATUS_ENUM = {"optional_sektion", "item_flags"}
LEHRSTOFF_QUELLE_ENUM = {"aus_anwendungsbereichen", "eigen_ausgewiesen"}


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def structural_check(shard, schema, hard, path):
    try:
        import jsonschema  # type: ignore
    except ImportError:
        return False  # jsonschema fehlt -> Kernchecks uebernehmen
    validator = jsonschema.Draft202012Validator(schema)
    for err in sorted(validator.iter_errors(shard), key=lambda e: e.path):
        loc = "/".join(str(p) for p in err.path) or "<root>"
        hard.append(f"[{path.name}] Schema: {loc}: {err.message}")
    return True


def core_checks(shard, path, hard, soft, global_ids):
    meta = shard.get("meta", {})
    if not meta:
        hard.append(f"[{path.name}] meta fehlt")
    for req in ("dataset_version", "band", "fach", "differenzierungs_achse",
                "anwendungsbereiche_status", "provenienz"):
        if req not in meta:
            hard.append(f"[{path.name}] meta.{req} fehlt (Pflichtfeld)")

    if meta.get("band") not in BAND_ENUM:
        soft.append(f"[{path.name}] band={meta.get('band')!r} ausserhalb Default-enum")
    if meta.get("anwendungsbereiche_status") not in AB_STATUS_ENUM:
        soft.append(f"[{path.name}] anwendungsbereiche_status="
                    f"{meta.get('anwendungsbereiche_status')!r} ausserhalb Default-enum")

    if "kompetenzbereiche" not in shard:
        hard.append(f"[{path.name}] kompetenzbereiche fehlt (Pflichtfeld)")
        return

    for bereich in shard.get("kompetenzbereiche", []):
        for req in ("id_teil", "name", "kompetenzen"):
            if req not in bereich:
                hard.append(f"[{path.name}] Kompetenzbereich ohne {req}")
        for k in bereich.get("kompetenzen", []):
            kid = k.get("id")
            # HART: Pflichtfelder
            for req in ("id", "stufe", "text"):
                if not k.get(req):
                    hard.append(f"[{path.name}] Kompetenz {kid or '?'}: {req} fehlt/leer")
            # HART: ID-Muster
            if kid and not ID_RE.match(kid):
                hard.append(f"[{path.name}] ID verletzt Muster: {kid}")
            # HART: ID-Eindeutigkeit (global)
            if kid:
                if kid in global_ids:
                    hard.append(f"[{path.name}] ID doppelt (auch in {global_ids[kid]}): {kid}")
                else:
                    global_ids[kid] = path.name
            # WEICH: stufe-Default
            if k.get("stufe") and k["stufe"] not in STUFE_DEFAULTS:
                soft.append(f"[{path.name}] {kid}: stufe={k['stufe']!r} ausserhalb Default-Segmenten")
            # WEICH: lehrstoff_quelle
            lq = k.get("lehrstoff_quelle")
            if lq and lq not in LEHRSTOFF_QUELLE_ENUM:
                soft.append(f"[{path.name}] {kid}: lehrstoff_quelle={lq!r} ausserhalb Default-enum")
            # WEICH: Fehlvorstellungen muessen amtlich:false sein (§ 5.5)
            for fv in k.get("typische_fehlvorstellungen", []):
                if fv.get("amtlich") is not False:
                    hard.append(f"[{path.name}] {kid}: Fehlvorstellung amtlich!=false")
                if not fv.get("quelle"):
                    soft.append(f"[{path.name}] {kid}: Fehlvorstellung ohne quelle (§ 12)")


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    paths = [Path(a) for a in argv] if argv else sorted(DATA_DIR.rglob("*.json"))
    if not paths:
        print("Keine Shards gefunden.")
        return 0
    schema = load(SCHEMA_PATH)
    hard: list[str] = []
    soft: list[str] = []
    global_ids: dict[str, str] = {}
    used_jsonschema = False
    for path in paths:
        shard = load(path)
        used_jsonschema = structural_check(shard, schema, hard, path) or used_jsonschema
        core_checks(shard, path, hard, soft, global_ids)

    print(f"Geprueft: {len(paths)} Shard(s), {len(global_ids)} Kompetenz-ID(s).")
    print(f"Struktur-Validierung via jsonschema: {'ja' if used_jsonschema else 'nein (Kernchecks)'}")
    for w in soft:
        print(f"  WEICH  {w}")
    for e in hard:
        print(f"  HART   {e}")
    if hard:
        print(f"\nFEHLER: {len(hard)} harte Verletzung(en) -> CI-rot.")
        return 1
    print(f"\nOK. {len(soft)} weiche Hinweis(e), keine harten Fehler.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

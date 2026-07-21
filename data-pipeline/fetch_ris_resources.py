#!/usr/bin/env python3
"""
fetch_ris_resources.py — holt ALLE Quell-Ressourcen des Plugins lokal aus dem RIS.

Grundsatz (v0.6): ausschliesslich RIS. Die Lehrplaene und die Bildungsstandards-
Verordnung sind als Verordnungen freie Werke (Paragraph 7 UrhG) und duerfen
oeffentlich weiterverwendet werden. Es werden KEINE anderen Quellen bezogen.

Was das Skript tut
  1) ermittelt ueber die RIS-OGD-API (v2.6) je Zielvorschrift die AKTUELL in Kraft
     stehende Anlage (Fachlehrplaene bzw. Bildungsstandards),
  2) laedt deren Volltext als XML (zum Parsen) und PDF (menschenlesbares Backup)
     nach  resources/<key>/ ,
  3) schreibt  resources/manifest.json  (NOR, ELI, Kundmachung, In-Kraft-Datum,
     Zeitstempel, SHA-256) fuer die spaetere Novellen-/Aenderungserkennung,
  4) legt den Ordner  docs/  an, in den Lehrpersonen eigenes Zusatzmaterial legen.

Robustheit: reine Standardbibliothek (kein pip noetig). Wenn die API-Discovery
fehlschlaegt, wird auf die bekannte NOR-Nummer zurueckgefallen (--allow-fallback).

Nutzungshinweis RIS: Bei regelmaessigen/automatisierten Zugriffen bittet das RIS um
kurze Vorab-Meldung an  ris.it@bka.gv.at  (IP-Bereich, Zeitpunkt), damit die Zugriffe
nicht als DDoS eingestuft werden. Fuer wenige Dokumente + gelegentliche Checks
unkritisch. Rechtlich verbindlich ist die authentische BGBl-Fassung; die
konsolidierte Fassung dient der Information.

Aufruf:
  python3 fetch_ris_resources.py                 # discover + download nach ./resources
  python3 fetch_ris_resources.py --dry-run       # nur zeigen; Discovery geht dennoch ans Netz
  python3 fetch_ris_resources.py --allow-fallback # bei API-Problem bekannte NOR nutzen
  python3 fetch_ris_resources.py --self-test test_url.json  # Parser gegen echte Response pruefen
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# --------------------------------------------------------------------------- #
# Konfiguration
# --------------------------------------------------------------------------- #
RIS_API = "https://data.bka.gv.at/ris/api/v2.6/Bundesrecht"
CONTENT_URL = "https://www.ris.bka.gv.at/Dokumente/Bundesnormen/{nor}/{nor}.{ext}"

# Zielvorschriften (v1-Scope). anlage_label = Wert von ArtikelParagraphAnlage im RIS.
TARGETS = [
    {"key": "vs_volksschule",   "gesetzesnummer": "10009275",
     "titel": "Lehrplan der Volksschule",          "anlage_label": "Anl. 1",
     "fallback_nor": "NOR40271469"},
    {"key": "ms_mittelschule",  "gesetzesnummer": "20007850",
     "titel": "Lehrplaene der Mittelschulen",       "anlage_label": "Anl. 1",
     "fallback_nor": "NOR40271471"},
    {"key": "bildungsstandards", "gesetzesnummer": "20006166",
     "titel": "Bildungsstandards-Verordnung",       "anlage_label": "Anl. 1",
     "fallback_nor": "NOR40255561"},
]
FORMATS = ("xml", "pdf")          # xml -> parsen, pdf -> Backup
# RIS-OGD v2.6 Paginierung: Parametername im OGD-Handbuch verifizieren (offener TODO).
# Spec Paragraph 10.0 nennt zusaetzlich Hits.@pageSize / @pageNumber. Wird der
# Parameter ignoriert, greift der Duplikat-Seiten-Schutz in discover_current_anlage().
# Live geprueft 2026-07-21: alle drei v1-Vorschriften liefern 9/13/16 Treffer
# (<= pageSize 20) -> Paginierung wird im v1-Scope nie ausgeloest; der Param-Name
# wird erst bei einer Scope-Erweiterung ueber eine Seite hinaus kritisch.
PAGE_PARAM = "Seitennummer"
MAX_PAGES = 20
USER_AGENT = ("teaching-skills-austria/0.7 (RIS-only fetch; "
              # F-10-Kontakt erledigt 2026-07-21 (RIS-Hoeflichkeit, Spec 9.1).
              "kontakt: ps@strangeprojects.com)")
POLITE_DELAY = 1.0                # Sekunden zwischen Requests (hoeflich)
TIMEOUT = 30
RETRIES = 3


# --------------------------------------------------------------------------- #
# HTTP (stdlib)
# --------------------------------------------------------------------------- #
def http_get(url: str, accept: str | None = None) -> bytes:
    """GET mit User-Agent, Timeout und einfachen Retries.

    Harte 4xx (ausser 429 Too Many Requests) werden NICHT wiederholt -- ein
    404/400 wird durch Nachfassen nicht besser und kostet nur POLITE_DELAY.
    Wiederholt wird nur bei Timeout, Netz-/URL-Fehlern und 5xx/429. HTTPError
    muss vor URLError stehen (ist dessen Subklasse).
    """
    last = None
    for attempt in range(1, RETRIES + 1):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        if accept:
            req.add_header("Accept", accept)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code < 500 and exc.code != 429:
                break                        # endgueltig -> nicht wiederholen
            if attempt < RETRIES:
                time.sleep(POLITE_DELAY * attempt)
        except (urllib.error.URLError, TimeoutError) as exc:
            last = exc
            if attempt < RETRIES:
                time.sleep(POLITE_DELAY * attempt)
    raise RuntimeError(f"GET fehlgeschlagen nach {RETRIES} Versuchen: {url} ({last})")


# --------------------------------------------------------------------------- #
# API-Discovery
# --------------------------------------------------------------------------- #
def api_url(gesetzesnummer: str, fassung_vom: str, seite: int) -> str:
    params = {
        "Applikation": "BrKons",
        "Gesetzesnummer": gesetzesnummer,
        "Fassung.FassungVom": fassung_vom,   # nur in Kraft stehende Fassung
        PAGE_PARAM: str(seite),
    }
    return RIS_API + "?" + urllib.parse.urlencode(params)


def _as_list(x):
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


def extract_refs(api_json: dict) -> tuple[list[dict], int]:
    """Parst eine RIS-OGD-Response zu (Referenz-Dicts, Trefferzahl). Rein & testbar."""
    res = (api_json or {}).get("OgdSearchResult", {}).get("OgdDocumentResults", {})
    hits_raw = res.get("Hits", {})
    total = int(hits_raw.get("#text", 0)) if isinstance(hits_raw, dict) else int(hits_raw or 0)
    out = []
    for ref in _as_list(res.get("OgdDocumentReference")):
        data = ref.get("Data", {})
        meta = data.get("Metadaten", {})
        tech = meta.get("Technisch", {})
        br_meta = meta.get("Bundesrecht", {})
        brk = br_meta.get("BrKons", {})
        # Content-URLs aus Dokumentliste
        urls = {}
        cref = data.get("Dokumentliste", {}).get("ContentReference", {})
        for u in _as_list(cref.get("Urls", {}).get("ContentUrl")):
            if isinstance(u, dict) and u.get("DataType") and u.get("Url"):
                urls[u["DataType"].lower()] = u["Url"]
        out.append({
            "nor": tech.get("ID"),
            "kurztitel": br_meta.get("Kurztitel"),
            "artikelparagraphanlage": brk.get("ArtikelParagraphAnlage", ""),
            "kundmachung": brk.get("Kundmachungsorgan", "").strip(),
            "inkrafttreten": brk.get("Inkrafttretensdatum"),
            # RIS laesst leere Felder weg: bei in-Kraft-Knoten fehlt
            # Ausserkrafttretensdatum -> None (live geprueft 2026-07-21). Bei
            # FassungVom-Query liefert die API ohnehin nur in-Kraft-Fassungen;
            # der Filter in discover_current_anlage ist damit Sicherheitsnetz.
            "ausserkrafttreten": brk.get("Ausserkrafttretensdatum") or None,
            "eli": br_meta.get("Eli") or meta.get("Allgemein", {}).get("DokumentUrl"),
            "content_urls": urls,
        })
    return out, total


def discover_current_anlage(gesetzesnummer: str, anlage_label: str,
                            fassung_vom: str, verbose=True):
    """Blaettert durch die in-Kraft-Fassung und liefert den Anlagen-Knoten.

    Robust gegen einen ignorierten Paginierungs-Parameter (PAGE_PARAM ist im
    OGD-Handbuch noch zu verifizieren, siehe Konfig): liefert eine Seite keine
    NEUEN NOR-IDs, wird abgebrochen, statt dieselbe Seite bis MAX_PAGES zu sammeln.
    """
    collected: list[dict] = []
    seen_nor: set[str] = set()
    total = None
    for seite in range(1, MAX_PAGES + 1):
        raw = http_get(api_url(gesetzesnummer, fassung_vom, seite),
                       accept="application/json")
        refs, total = extract_refs(json.loads(raw.decode("utf-8")))
        new_refs = [r for r in refs if r.get("nor") and r["nor"] not in seen_nor]
        for r in new_refs:
            seen_nor.add(r["nor"])
        collected.extend(new_refs)
        if verbose:
            print(f"    Seite {seite}: {len(refs)} Referenzen, {len(new_refs)} neu "
                  f"(kumuliert {len(collected)}/{total})")
        time.sleep(POLITE_DELAY)
        if total is not None and len(collected) >= total:
            break
        if not refs:
            break
        if not new_refs:
            # Seite brachte nur Duplikate -> Paginierung greift vermutlich nicht
            # (PAGE_PARAM im Handbuch pruefen). Abbruch statt Endlos-Sammeln.
            if verbose:
                print("    ! Seite ohne neue Treffer -> Paginierung evtl. "
                      "wirkungslos (PAGE_PARAM pruefen); Abbruch.")
            break
    # in Kraft (kein Ausserkrafttreten) + passende Anlage.
    # Bei FassungVom-Query sind bereits nur in-Kraft-Knoten enthalten; der
    # ausserkrafttreten-Check ist redundantes Sicherheitsnetz (s. extract_refs).
    label = anlage_label.replace(" ", "").lower()
    candidates = [
        r for r in collected
        if r["ausserkrafttreten"] is None
        and r["artikelparagraphanlage"].replace(" ", "").lower() == label
    ]
    if not candidates:
        return None
    # Auswahlstrategie (entschieden): neueste in Kraft getretene Fassung
    # (max. Inkrafttretensdatum). ISO-Datums-Strings sortieren lexikografisch =
    # chronologisch; None -> ans Ende.
    candidates.sort(key=lambda r: r.get("inkrafttreten") or "", reverse=True)
    if len(candidates) > 1 and verbose:
        print(f"    ! {len(candidates)} in-Kraft-Treffer fuer '{anlage_label}' "
              f"-> neueste gewaehlt (Inkrafttreten {candidates[0].get('inkrafttreten')}).")
    return candidates[0]


# --------------------------------------------------------------------------- #
# Download
# --------------------------------------------------------------------------- #
def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def download_document(nor: str, content_urls: dict, key: str,
                      outdir: Path, dry_run=False) -> dict:
    rec = {"nor": nor, "files": {}}
    (outdir / key).mkdir(parents=True, exist_ok=True)
    for ext in FORMATS:
        url = content_urls.get(ext) or CONTENT_URL.format(nor=nor, ext=ext)
        target = outdir / key / f"{nor}.{ext}"
        if dry_run:
            print(f"    [dry-run] {url} -> {target}")
            rec["files"][ext] = {"url": url, "path": str(target)}
            continue
        data = http_get(url)
        target.write_bytes(data)
        rec["files"][ext] = {"url": url, "path": str(target),
                             "bytes": len(data), "sha256": sha256(data)}
        print(f"    gespeichert: {target}  ({len(data)} B)")
        time.sleep(POLITE_DELAY)
    return rec


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def ensure_docs_folder(root: Path) -> None:
    docs = root / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    readme = docs / "README.md"
    if not readme.exists():
        readme.write_text(
            "# docs/ — Zusatzmaterial von Lehrpersonen\n\n"
            "Dateien in diesem Ordner werden von den Skills als optionale, "
            "lehrpersonen-eigene Ressourcen einbezogen (z. B. eigene Lernaufgaben, "
            "Arbeitsblaetter, differenzierte Materialien). Siehe Spec Paragraph 7.6.\n\n"
            "## Zuordnung per Ordnerkonvention\n"
            "    docs/<fach>/<stufe>/...   z. B. docs/mathematik/K2/bruchrechnen.md\n"
            "    docs/<fach>/...           nur Fach (stufenuebergreifend)\n"
            "    docs/...                  unspezifisch (Fach/Stufe = leer)\n"
            "- <fach>: mathematik, deutsch, englisch, sachunterricht, ... "
            "(wird auf Fach-Code M/D/E/SU gemappt; unbekannt => 'nicht zugeordnet', "
            "nicht verworfen).\n"
            "- <stufe> optional: K1..K4 (Sek I) bzw. VOR/GS1/GS2 (VS).\n"
            "- Feinzuordnung optional: kompetenz_id als Dateinamen-Suffix "
            "(...__AT.LP23.SEK1.M.ZAHLEN.K2.03.md) oder YAML-Frontmatter.\n\n"
            "## Formate\n"
            "- Nativ: .md, .txt\n"
            "- .pdf und .docx werden bei der Einbindung automatisch nach Markdown "
            "konvertiert (Cache: docs/.cache/; Quelle bleibt unveraendert). "
            "Nur-gescannte PDFs werden als 'nicht verwertbar' protokolliert.\n\n"
            "## Grenzen (Default, ueberschreibbar)\n"
            "- max. 2 MB je Datei, max. 20 Dateien je Anfrage; darueber nach "
            "Relevanz gedeckelt.\n\n"
            "- Diese Inhalte sind NICHT Teil des amtlichen RIS-Datensatzes; die "
            "Lizenz/Urheberschaft liegt bei der jeweiligen Lehrperson und wird in "
            "der Ausgabe als lehrpersonen-eigen ausgewiesen.\n",
            encoding="utf-8")
        print(f"  docs/ angelegt: {readme}")


def run(outdir: Path, root: Path, fassung_vom: str,
        dry_run: bool, allow_fallback: bool) -> int:
    manifest = {
        "erzeugt": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "fassung_vom": fassung_vom,
        "quelle": "RIS OGD API v2.6 (Applikation=BrKons)",
        "hinweis": "RIS-only; Verordnungstext = freies Werk (Paragraph 7 UrhG).",
        "dokumente": [],
    }
    errors = 0
    for t in TARGETS:
        print(f"\n[{t['key']}] {t['titel']} (Gesetzesnummer {t['gesetzesnummer']})")
        ref = None
        try:
            ref = discover_current_anlage(t["gesetzesnummer"], t["anlage_label"],
                                          fassung_vom)
        except Exception as exc:  # noqa: BLE001
            print(f"  ! API-Discovery fehlgeschlagen: {exc}")
        if ref is None:
            if allow_fallback:
                nor = t["fallback_nor"]
                print(f"  -> Fallback auf bekannte NOR {nor} "
                      f"(! kann durch Novelle veraltet sein - Manifest pruefen)")
                ref = {"nor": nor, "content_urls": {}, "kundmachung": None,
                       "inkrafttreten": None, "eli": None,
                       "artikelparagraphanlage": t["anlage_label"],
                       "_fallback": True}
            else:
                print("  ! keine aktuelle Anlage gefunden (nutze --allow-fallback)")
                errors += 1
                continue
        try:
            rec = download_document(ref["nor"], ref.get("content_urls", {}),
                                    t["key"], outdir, dry_run=dry_run)
        except Exception as exc:  # noqa: BLE001
            print(f"  ! Download fehlgeschlagen: {exc}")
            errors += 1
            continue
        rec.update({
            "key": t["key"], "titel": t["titel"],
            "gesetzesnummer": t["gesetzesnummer"],
            "anlage": ref.get("artikelparagraphanlage"),
            "kundmachung": ref.get("kundmachung"),
            "inkrafttreten": ref.get("inkrafttreten"),
            "eli": ref.get("eli"),
            "fallback_used": bool(ref.get("_fallback")),
        })
        if ref.get("_fallback"):
            rec["fallback_warnung"] = (
                "Ueber --allow-fallback bezogen; NOR-Nummer ist hartkodiert und "
                "kann durch eine Novelle veraltet sein. Vor Verwendung gegen die "
                "aktuelle RIS-Fassung verifizieren.")
        manifest["dokumente"].append(rec)

    ensure_docs_folder(root)
    if not dry_run:
        (outdir).mkdir(parents=True, exist_ok=True)
        (outdir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nManifest: {outdir/'manifest.json'}")
    print(f"\nFertig. Fehler: {errors}")
    return errors


def self_test(sample_path: str) -> int:
    """Prueft den Parser gegen eine echte RIS-Response (ohne Netz)."""
    data = json.loads(Path(sample_path).read_text(encoding="utf-8"))
    refs, total = extract_refs(data)
    print(f"self-test: {sample_path}")
    print(f"  Treffer gesamt laut Response: {total}")
    print(f"  Referenzen auf dieser Seite:  {len(refs)}")
    in_force = [r for r in refs if r["ausserkrafttreten"] is None]
    print(f"  davon aktuell in Kraft:       {len(in_force)}")
    with_xml = [r for r in refs if "xml" in r["content_urls"]]
    print(f"  mit XML-Content-URL:          {len(with_xml)}")
    ok = bool(refs) and all(r["nor"] for r in refs) and len(with_xml) == len(refs)
    if refs:
        r = refs[0]
        print("  Beispiel[0]:", r["nor"], "|", r["artikelparagraphanlage"],
              "| inKraft", r["inkrafttreten"], "| ausser", r["ausserkrafttreten"])
        print("    XML:", r["content_urls"].get("xml"))
    print("  ERGEBNIS:", "OK" if ok else "FEHLER")
    return 0 if ok else 1


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="RIS-only Ressourcen-Fetch (v0.6).")
    p.add_argument("--out", default="resources", help="Zielordner (default: resources)")
    p.add_argument("--root", default=".", help="Projektwurzel fuer docs/ (default: .)")
    p.add_argument("--fassung-vom", default=_dt.date.today().isoformat(),
                   help="Stichtag der in-Kraft-Fassung (YYYY-MM-DD, default: heute)")
    p.add_argument("--dry-run", action="store_true", help="nur zeigen, nichts laden")
    p.add_argument("--allow-fallback", action="store_true",
                   help="bei API-Problem bekannte NOR-Nummern nutzen")
    p.add_argument("--self-test", metavar="SAMPLE.json",
                   help="Parser gegen echte RIS-Response pruefen (ohne Netz)")
    args = p.parse_args(argv)

    if args.self_test:
        return self_test(args.self_test)
    return run(Path(args.out), Path(args.root), args.fassung_vom,
               args.dry_run, args.allow_fallback)


if __name__ == "__main__":
    raise SystemExit(main())

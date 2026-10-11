#!/usr/bin/env python3
"""Turn a case folder (a bank's own documents in Markdown, text, Word, Excel, PDF, JSON) into ONE Markdown brief.

    python3 builder/casefolder.py <case_folder> --out out/<slot>.brief.md [--index out/<slot>.files.json]

Standard library only. Word (.docx) and Excel (.xlsx) are zip + XML and are read directly; PDF goes through
`pdftotext` when it is installed, else `pypdf` when importable, else a note is left in the bundle. Nothing here
knows any bank: the order is README/BRIEF first, then every other file sorted by path (dated file names sort
chronologically inside a folder), each under a `DOCUMENT FILE:` header that builder/rules.py also uses.
Large machine-readable files (a test-data JSON of hundreds of kilobytes) are summarised, not pasted.
Also finds a tool API file (OpenAPI JSON with `paths`) inside the folder when the bank supplied one.
"""
import argparse, json, pathlib, re, shutil, subprocess, sys, zipfile
import xml.etree.ElementTree as ET

TEXT_EXT = {".md", ".markdown", ".txt", ".eml", ".csv", ".tsv", ".yaml", ".yml", ".toml", ".js", ".mjs", ".ts", ".py", ".html", ".htm"}
MAX_TEXT_BYTES = 200_000          # bigger text files are cut with a note
MAX_JSON_BYTES = 60_000           # bigger JSON files are summarised (structure + first record)
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".wrangler"}
FIRST = ("readme.md", "brief.md")


def _docx_text(path):
    out = []
    with zipfile.ZipFile(path) as z:
        names = [n for n in z.namelist() if n == "word/document.xml" or re.match(r"word/(header|footer)\d*\.xml", n)]
        names.sort(key=lambda n: (n != "word/document.xml", n))
        for n in names:
            root = ET.fromstring(z.read(n))
            ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
            body = root.find("w:body", ns) if n == "word/document.xml" else root
            if body is None:
                continue
            for el in body:
                tag = el.tag.split("}")[-1]
                if tag == "p":
                    out.append(_para(el, ns))
                elif tag == "tbl":
                    rows = []
                    for tr in el.findall(".//w:tr", ns):
                        cells = ["".join(_para(p, ns) for p in tc.findall(".//w:p", ns)).replace("|", "/") for tc in tr.findall("w:tc", ns)]
                        rows.append("| " + " | ".join(cells) + " |")
                    if rows:
                        rows.insert(1, "|" + "---|" * (rows[0].count("|") - 1))
                        out.append("\n".join(rows))
    return "\n\n".join(x for x in out if x is not None)


def _para(p, ns):
    style = p.find("w:pPr/w:pStyle", ns)
    prefix = ""
    if style is not None:
        m = re.search(r"(\d)$", style.get("{%s}val" % ns["w"], ""))
        if m and "heading" in style.get("{%s}val" % ns["w"], "").lower():
            prefix = "#" * int(m.group(1)) + " "
    if p.find("w:pPr/w:numPr", ns) is not None:
        prefix = prefix or "- "
    text = "".join(t.text or "" for t in p.iter("{%s}t" % ns["w"]))
    return prefix + text


def _xlsx_text(path):
    out = []
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
            for si in root.findall("m:si", ns):
                shared.append("".join(t.text or "" for t in si.iter("{%s}t" % ns["m"])))
        sheets = {}
        try:
            wb = ET.fromstring(z.read("xl/workbook.xml"))
            ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
                  "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
            rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
            rid_to_target = {r.get("Id"): r.get("Target") for r in rels}
            for s in wb.findall("m:sheets/m:sheet", ns):
                target = rid_to_target.get(s.get("{%s}id" % ns["r"]), "")
                sheets["xl/" + target.lstrip("/").replace("xl/", "")] = s.get("name")
        except Exception:
            pass
        for n in sorted(x for x in z.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml", x)):
            root = ET.fromstring(z.read(n))
            ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
            rows = []
            for row in root.findall(".//m:sheetData/m:row", ns):
                cells = {}
                for c in row.findall("m:c", ns):
                    ref = re.match(r"([A-Z]+)", c.get("r", "A")).group(1)
                    v = c.find("m:v", ns)
                    t = c.get("t")
                    val = ""
                    if t == "s" and v is not None:
                        val = shared[int(v.text)] if int(v.text) < len(shared) else ""
                    elif t == "inlineStr":
                        val = "".join(x.text or "" for x in c.iter("{%s}t" % ns["m"]))
                    elif v is not None:
                        val = v.text or ""
                    cells[ref] = val.replace("|", "/").replace("\n", " ")
                if any(cells.values()):
                    cols = sorted(cells, key=lambda k: (len(k), k))
                    rows.append(cols, ) if False else rows.append([cells[k] for k in cols])
            if not rows:
                continue
            width = max(len(r) for r in rows)
            md = ["| " + " | ".join(r + [""] * (width - len(r))) + " |" for r in rows]
            md.insert(1, "|" + "---|" * width)
            out.append("### Sheet: %s\n\n%s" % (sheets.get(n, n), "\n".join(md)))
    return "\n\n".join(out)


def _pdf_text(path):
    if shutil.which("pdftotext"):
        try:
            p = subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True, text=True, timeout=60)
            if p.returncode == 0 and p.stdout.strip():
                return p.stdout
        except Exception:
            pass
    try:
        from pypdf import PdfReader  # optional
        return "\n\n".join((pg.extract_text() or "") for pg in PdfReader(str(path)).pages)
    except Exception:
        return "(PDF text could not be extracted on this machine: read the file %s directly if the content matters)" % path.name


def _json_summary(path, raw):
    try:
        obj = json.loads(raw)
    except Exception:
        return raw[:MAX_JSON_BYTES] + "\n... (truncated, invalid JSON)"
    def shape(x, depth=0):
        if depth > 5:
            return "..."
        if isinstance(x, dict):
            return {k: shape(v, depth + 1) for k, v in list(x.items())[:25]}
        if isinstance(x, list):
            return [shape(x[0], depth + 1)] if x else []
        return type(x).__name__
    head = {k: v for k, v in obj.items() if isinstance(v, (str, int, float))} if isinstance(obj, dict) else {}
    first = None
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, list) and v:
                first = (k, len(v), v[0])
                break
    elif isinstance(obj, list) and obj:
        first = ("(root)", len(obj), obj[0])
    parts = ["(large JSON, %d bytes: structure and first record only; the file itself is the source of truth)" % len(raw),
             "Top-level scalar fields: " + json.dumps(head, ensure_ascii=False),
             "Structure: " + json.dumps(shape(obj), ensure_ascii=False)]
    if first:
        parts.append("First of %d items in %r:\n```json\n%s\n```" % (first[1], first[0], json.dumps(first[2], ensure_ascii=False, indent=1)[:12000]))
    return "\n\n".join(parts)


def read_document(path):
    """Text of one document as Markdown-ish text, or None when the file is binary/unknown."""
    ext = path.suffix.lower()
    if ext == ".docx":
        return _docx_text(path)
    if ext == ".xlsx":
        return _xlsx_text(path)
    if ext == ".pdf":
        return _pdf_text(path)
    if ext == ".json":
        raw = path.read_text(encoding="utf-8", errors="replace")
        return raw if len(raw) <= MAX_JSON_BYTES else _json_summary(path, raw)
    if ext in TEXT_EXT or ext == "":
        try:
            raw = path.read_bytes()
        except OSError:
            return None
        if b"\x00" in raw[:4000]:
            return None
        for enc in ("utf-8", "cp1254", "latin-1"):
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if len(text) > MAX_TEXT_BYTES:
            text = text[:MAX_TEXT_BYTES] + "\n... (truncated at %d bytes)" % MAX_TEXT_BYTES
        return text
    return None


def list_files(folder):
    folder = pathlib.Path(folder)
    files = [p for p in folder.rglob("*") if p.is_file() and not any(part in SKIP_DIRS or part.startswith(".") for part in p.relative_to(folder).parts)]
    def key(p):
        rel = p.relative_to(folder)
        top = rel.parts[0].lower() if len(rel.parts) == 1 else "~"
        return (0 if top in FIRST else 1, FIRST.index(top) if top in FIRST else 0, str(rel).lower())
    return sorted(files, key=key)


def find_api_file(folder):
    """An OpenAPI JSON the bank supplied inside the folder, if any (the newest when several)."""
    hits = []
    for p in list_files(folder):
        if p.suffix.lower() == ".json" and p.stat().st_size < 2_000_000:
            try:
                obj = json.loads(p.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                continue
            if isinstance(obj, dict) and isinstance(obj.get("paths"), dict) and ("openapi" in obj or "swagger" in obj):
                hits.append(p)
    return hits[-1] if hits else None


def bundle(folder, out_path, index_path=None):
    folder = pathlib.Path(folder).resolve()
    files = list_files(folder)
    parts, index = [], []
    for p in files:
        rel = str(p.relative_to(folder))
        text = read_document(p)
        kind = p.suffix.lower().lstrip(".") or "file"
        index.append({"path": rel, "bytes": p.stat().st_size, "kind": kind, "included": text is not None})
        if text is None:
            continue
        parts.append("=" * 20 + " DOCUMENT FILE: %s " % rel + "=" * 20 + "\n" + text.strip("\n"))
    header = ["# Case folder: %s" % folder.name, "",
              "This brief was assembled automatically from the bank's case folder. Files, in the order they appear below:", ""]
    header += ["- `%s` (%s, %d bytes%s)" % (i["path"], i["kind"], i["bytes"], "" if i["included"] else ", not text: not included") for i in index]
    header += ["", "Later-dated documents, meeting decisions and e-mails override earlier documents where they disagree.", ""]
    out = pathlib.Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(header) + "\n\n" + "\n\n".join(parts) + "\n", encoding="utf-8")
    if index_path:
        pathlib.Path(index_path).write_text(json.dumps(index, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return out, index


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder")
    ap.add_argument("--out", required=True)
    ap.add_argument("--index")
    a = ap.parse_args(argv)
    out, index = bundle(a.folder, a.out, a.index)
    api = find_api_file(a.folder)
    print("bundle %s: %d files, %d included, %d bytes; api file: %s" % (out, len(index), sum(i["included"] for i in index), out.stat().st_size, api or "none"))


if __name__ == "__main__":
    main()

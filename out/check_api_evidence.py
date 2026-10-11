#!/usr/bin/env python3
"""Check that a model-derived OpenAPI document uses names found in source text.

This catches invented paths, fields, statuses and enum values. It does not prove
the schema's types or semantics; the bank contract and live mock remain binding.
"""
import argparse
import json
from pathlib import Path
import re


def names(schema):
    if not isinstance(schema, dict):
        return
    for field, child in (schema.get("properties") or {}).items():
        yield "field", field
        yield from names(child)
    if isinstance(schema.get("items"), dict):
        yield from names(schema["items"])
    for value in schema.get("enum") or []:
        if isinstance(value, str):
            yield "enum", value


def operation_tokens(api):
    for path, methods in (api.get("paths") or {}).items():
        yield "path", path.lstrip("/").split("/")[-1]
        for method, operation in methods.items():
            if not isinstance(operation, dict) or method.startswith("x-"):
                continue
            yield "method", method.upper()
            request = (operation.get("requestBody") or {}).get("content", {}).get("application/json", {}).get("schema", {})
            yield from names(request)
            for status, response in (operation.get("responses") or {}).items():
                if status.isdigit():
                    yield "status", status
                schema = (response.get("content") or {}).get("application/json", {}).get("schema", {})
                yield from names(schema)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("api")
    parser.add_argument("sources", nargs="+")
    parser.add_argument("--out")
    args = parser.parse_args()
    api = json.loads(Path(args.api).read_text())
    lines = []
    for source in args.sources:
        lines.extend((source, n, line) for n, line in
                     enumerate(Path(source).read_text(encoding="utf-8").splitlines(), 1))
    findings = []
    for kind, value in sorted(set(operation_tokens(api))):
        # Ignore trivial envelope keys, but still require the source to mention them.
        pattern = re.compile(r"(?<![\w.])" + re.escape(value) + r"(?![\w.])", re.I)
        hits = [{"file": file, "line": n} for file, n, line in lines if pattern.search(line)]
        findings.append({"kind": kind, "value": value, "source": hits[:3]})
    missing = [f for f in findings if not f["source"]]
    report = {"api": args.api, "sources": args.sources, "checked": len(findings),
              "missing": missing, "findings": findings}
    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print("%d/%d path, method, schema and status names found in sources" %
          (len(findings) - len(missing), len(findings)))
    for finding in missing:
        print("MISSING %(kind)s %(value)r" % finding)
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())

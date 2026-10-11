#!/usr/bin/env python3
"""Derive the bank's tool API file (OpenAPI 3 JSON) from the case documents when the bank sent no OpenAPI file.

    python3 builder/apispec.py out/<slot>.brief.md --mock-url https://<worker>.workers.dev --out out/<slot>.openapi.json

A bank that hands over an integration document instead of an OpenAPI file still has services with exact paths,
field names, types, enums and response shapes. One model call reads the bundled documents and writes them down
as the same OpenAPI shape the rest of the builder consumes (freyalib.tool_spec: POST operations, flat request
properties, a response schema). `servers[0].url` is the mock the phone agent calls (base address + the bank's path
prefix). Nothing bank-specific lives here; every name and value comes from the documents given.
"""
import argparse, json, pathlib, re, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from rules import ask_json  # noqa: E402  (provider-neutral JSON model call)
import freyalib  # noqa: E402

SYSTEM = ("You write the OpenAPI 3.0 description of the services a voice assistant calls, from a bank's own documents "
          "(an integration document / service contract, examples, test data notes). You copy names exactly; you never "
          "invent a service, a field, an enum value or a status code that the documents do not show.")

PROMPT = """From the documents below, write the OpenAPI 3.0 JSON of the bank's services that the phone agent calls during a call.

Rules for the output (the builder's library parses exactly this shape):
- `servers`: one entry, `url` = MOCK_URL + the bank's path prefix (the part of the bank's base address after its host, e.g. a version prefix), with no trailing slash. MOCK_URL = {mock_url}
- `paths`: one entry per service, key = "/" + the LAST path segment exactly as the documents spell it (for example "/orders.lookup"). Each has a `post` operation (the documents say which method; use what they say) with:
  - `operationId`: a tool name for a language model: the last path segment with every character that is not a letter, digit or underscore replaced by "_" (so "orders.lookup" -> "orders_lookup").
  - `summary`: one line: what the service is for and WHEN the assistant calls it (from the documents).
  - `requestBody.content.application/json.schema`: `type: object`, `properties` = the service's request fields FLAT (the fields the documents put inside the request's data object, without the envelope wrapper, and without call metadata or auth), each with `type` (string/number/integer/boolean), `description` (what it is, where its value comes from: a call variable, an earlier service result, the customer) and `enum` when the documents fix the allowed values; `required` = the fields the documents say are required / always sent.
  - `responses."200".content.application/json.schema`: the FULL successful response body as the documents show it (the envelope included, nested objects as nested `properties`, arrays with `items`), with `description` on fields that matter to the conversation; `responses."4xx"/"5xx"` as the documents list them, with the error body schema and `description` = when it happens and the error code.
- `x-notes` (top level, array of strings): the facts about the services that a generator must know and that do not fit the schema: envelope rules, how success is recognised, status codes and their meaning per service, timeouts/latency warnings, which fields are strings vs numbers, which calls have side effects and must not be retried, lookups the mock does, what the test environment ignores, and the exact wording of anything the documents say about calling order.
- `x-call-variables` (top level, object): the variables every call gives the agent, name -> description, exactly as the documents name them.
- Do NOT include token/auth endpoints, health checks or the mock example from a README. Only the bank's business services.
- Output JSON only.

DOCUMENTS:
{docs}
"""

SCHEMA = {"type": "object", "properties": {
    "openapi": {"type": "string"},
    "info": {"type": "object", "properties": {"title": {"type": "string"}, "version": {"type": "string"}}, "required": ["title", "version"]},
    "servers": {"type": "array", "items": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}},
    "paths": {"type": "object"},
    "x-notes": {"type": "array", "items": {"type": "string"}},
    "x-call-variables": {"type": "object"},
}, "required": ["openapi", "info", "servers", "paths"]}


def check(api):
    """Every operation must parse with freyalib; return the problems."""
    problems = []
    names = freyalib.tool_names(api)
    if not names:
        problems.append("no POST operations")
    for name in names:
        try:
            spec = freyalib.tool_spec(api, name)
            if not spec["fields"]:
                problems.append("%s: request has no properties" % name)
        except Exception as e:
            problems.append("%s: %s" % (name, e))
    if not re.match(r"^https?://", (api.get("servers") or [{}])[0].get("url", "")):
        problems.append("servers[0].url is not an http(s) URL")
    return problems


def derive(bundle_path, mock_url, out_path, log=print):
    docs = pathlib.Path(bundle_path).read_text(encoding="utf-8")
    prompt = PROMPT.format(mock_url=mock_url.rstrip("/"), docs=docs)
    last = None
    for attempt in range(2):
        obj, info = ask_json(prompt if not attempt else prompt + "\n\nYour previous answer had these problems: %s. Fix them." % last,
                             SYSTEM, SCHEMA, "derive the tool API (OpenAPI) from the case documents", log=lambda s: log(s))
        if "servers" in obj and obj["servers"]:
            url = obj["servers"][0].get("url", "")
            if not url.startswith(mock_url.rstrip("/")):
                # keep the model's path prefix, force the mock host
                prefix = re.sub(r"^https?://[^/]+", "", url).rstrip("/")
                obj["servers"][0]["url"] = mock_url.rstrip("/") + prefix
        problems = check(obj)
        if not problems:
            out = pathlib.Path(out_path)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            log("api file written: %s | %d tools: %s | cost %s" % (out, len(freyalib.tool_names(obj)), ", ".join(freyalib.tool_names(obj)), info.get("cost_usd")))
            return out
        last = "; ".join(problems)
        log("api file problems: " + last)
    raise RuntimeError("Could not derive a usable tool API file: " + str(last))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("bundle")
    ap.add_argument("--mock-url", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    derive(a.bundle, a.mock_url, a.out, log=lambda s: print(s, file=sys.stderr, flush=True))


if __name__ == "__main__":
    main()

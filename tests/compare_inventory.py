#!/usr/bin/env python3
"""Compare a rule inventory (out/<slot>.rules.json) with a reference list of rules in force (a hand-written rationale or
an earlier inventory). One Claude call judges, for every reference rule, whether a rule IN FORCE of the inventory covers it
with the right values, and lists inventory rules in force that contradict the reference (wrongly in force).
Evaluation only: never used by the builder.

    .venv/bin/python tests/compare_inventory.py out/brief-d.rules.json --ref tests/synthetic/brief-d.rationale.md --section "Rule inventory" --out out/brief-d.compare.json
    .venv/bin/python tests/compare_inventory.py out/brief-a.rules.json --ref-json old.rules.json --out out/brief-a.compare.json
"""
import argparse, json, pathlib, re, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "builder"))
from rules import ask_json  # noqa: E402

SCHEMA = {"type": "object", "properties": {
    "reference": {"type": "array", "items": {"type": "object", "properties": {
        "ref": {"type": "string"}, "status": {"type": "string", "enum": ["covered", "partial", "missed", "wrong_value", "not_in_force"]},
        "inventory_ids": {"type": "array", "items": {"type": "string"}}, "note": {"type": "string"}},
        "required": ["ref", "status", "inventory_ids", "note"]}},
    "wrongly_in_force": {"type": "array", "items": {"type": "object", "properties": {
        "id": {"type": "string"}, "why": {"type": "string"}}, "required": ["id", "why"]}},
    "extra_in_force": {"type": "integer"}},
    "required": ["reference", "wrongly_in_force", "extra_in_force"]}

SYSTEM = """You grade a machine-written rule inventory against a reference list of the rules in force (written by a person).
For EVERY reference rule: "covered" (one or more inventory rules IN FORCE state it with the same values), "partial" (part of
it is stated, or a detail is missing), "missed" (no rule in force states it), "wrong_value" (a rule in force states it with a
different number, date, code, order or wording), "not_in_force" (the inventory has it but marked superseded/not policy).
Then list every inventory rule IN FORCE that contradicts the reference (a superseded value, a withdrawn rule, a proposal
treated as policy): "wrongly_in_force". "extra_in_force": how many rules in force state something the reference does not
mention at all (more detail is fine; count them only). Be strict on values, lenient on wording."""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inventory")
    ap.add_argument("--ref", help="Markdown file with a numbered reference list")
    ap.add_argument("--section", default="", help="heading of the section that holds the list")
    ap.add_argument("--ref-json", help="an earlier rules.json used as the reference (rules in force)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    inv = json.load(open(a.inventory))
    if a.ref_json:
        ref = "\n".join("%s. %s%s%s" % (r["id"], r["text"], (" verbatim " + json.dumps(r["verbatim"], ensure_ascii=False)) if r.get("verbatim") else "",
                                          (" values " + json.dumps(r["values"], ensure_ascii=False)) if r.get("values") else "")
                        for r in json.load(open(a.ref_json)) if r.get("in_force", True))
    else:
        t = pathlib.Path(a.ref).read_text()
        if a.section:
            t = t[t.index(a.section):]
        ref = "\n".join(l for l in t.splitlines() if re.match(r"^\d+\.\s", l))
    lines = []
    for r in inv:
        st = "IN FORCE" if r["in_force"] else ("NOT POLICY" if r.get("not_policy") else "SUPERSEDED by %s" % r.get("superseded_by"))
        if r.get("effective_until"):
            st = "IN FORCE until %s" % r["effective_until"]
        lines.append("%s [%s] %s | %s%s%s" % (r["id"], st, r["source"], r["text"],
                     (" | verbatim " + json.dumps(r["verbatim"], ensure_ascii=False)) if r.get("verbatim") else "",
                     (" | values " + json.dumps(r["values"], ensure_ascii=False, separators=(",", ":"))) if r.get("values") else ""))
    prompt = "REFERENCE RULES IN FORCE:\n%s\n\nINVENTORY:\n%s\n\nGrade every reference rule. JSON only." % (ref, "\n".join(lines))
    obj, info = ask_json(prompt, SYSTEM, SCHEMA, "grade inventory %s against the reference" % a.inventory)
    c = {}
    for x in obj["reference"]:
        c[x["status"]] = c.get(x["status"], 0) + 1
    obj["summary"] = {"reference_rules": len(obj["reference"]), **c, "wrongly_in_force": len(obj["wrongly_in_force"]),
                      "extra_in_force": obj.get("extra_in_force"), "cost_usd": info["cost_usd"], "seconds": info["seconds"]}
    pathlib.Path(a.out).write_text(json.dumps(obj, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps(obj["summary"]))
    for x in obj["reference"]:
        if x["status"] != "covered":
            print("  %s %s %s: %s" % (x["ref"], x["status"], x["inventory_ids"], x["note"]))
    for x in obj["wrongly_in_force"]:
        print("  WRONGLY IN FORCE %s: %s" % (x["id"], x["why"]))


if __name__ == "__main__":
    main()

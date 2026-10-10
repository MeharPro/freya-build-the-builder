"""Diff out/brief-a_v2.workflow.json (out/gen_brief-a_v2.py) against out/brief-a.lib.workflow.json (out/gen_brief-a_lib.py).

Why v2 exists: the chat route (smoke tests, local simulator) skips a first code node, so v2 starts in the `opening`
conversation node and runs the `setup` code node right after the first customer turn, routing on `who1` there.
The only expected differences are therefore:
  - initial_node: "setup" -> "opening"
  - nodes.opening.transitions: the who1 routes -> one always transition to setup
  - nodes.setup.transitions (+ passthrough_default_transition): always opening -> the who1 routes, else opening_retry
This script prints every differing path, checks that the moved routes are exactly the old ones, and exits 1 when
anything else differs."""
import json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
V1 = json.load(open(ROOT / "out/brief-a.lib.workflow.json"))
V2 = json.load(open(ROOT / "out/brief-a_v2.workflow.json"))

EXPECTED = ("initial_node", "nodes.opening.transitions", "nodes.setup.transitions",
            "nodes.setup.passthrough_default_transition")
diffs = []


def walk(a, b, path):
    if any(path == e or path.startswith(e + "[") or path.startswith(e + ".") for e in EXPECTED):
        if a != b:
            diffs.append(path)
        return
    if type(a) is not type(b):
        diffs.append(path)
    elif isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            p = "%s.%s" % (path, k) if path else k
            if k not in a or k not in b:
                diffs.append(p)
            else:
                walk(a[k], b[k], p)
    elif isinstance(a, list):
        if len(a) != len(b):
            diffs.append(path)
        else:
            for i, (x, y) in enumerate(zip(a, b)):
                walk(x, y, "%s[%d]" % (path, i))
    elif a != b:
        diffs.append(path)


walk(V1, V2, "")
unexpected = [p for p in diffs if p not in EXPECTED]
print("nodes: v1 %d, v2 %d" % (len(V1["nodes"]), len(V2["nodes"])))
print("differing paths: %d" % len(diffs))
for p in diffs:
    print("  -", p, "" if p in EXPECTED else "  <-- UNEXPECTED")

# semantic checks on the expected differences
always_ = {"operator": "always"}
o1, s1 = V1["nodes"]["opening"]["transitions"], V1["nodes"]["setup"]["transitions"]
o2, s2 = V2["nodes"]["opening"]["transitions"], V2["nodes"]["setup"]["transitions"]
checks = [
    ("initial_node setup -> opening", V1["initial_node"] == "setup" and V2["initial_node"] == "opening"),
    ("v1 setup: one always -> opening", len(s1) == 1 and s1[0]["condition"] == always_ and s1[0]["target_node"] == "opening"),
    ("v2 opening: one always -> setup", len(o2) == 1 and o2[0]["condition"] == always_ and o2[0]["target_node"] == "setup"),
    ("v2 setup routes == v1 opening routes", s2 == o1),
    ("v2 setup passthrough_default_transition == opening_retry",
     V2["nodes"]["setup"]["passthrough_default_transition"] == "opening_retry" == o1[-1]["target_node"]),
]
for name, ok in checks:
    print("  %s %s" % ("PASS" if ok else "FAIL", name))
for t in s2:
    c = t["condition"]
    leaf = c["conditions"][0] if "conditions" in c else c
    print("    setup -> %-16s if %s" % (t["target_node"], "always" if leaf.get("operator") == "always"
                                         else "%s == %s" % (leaf["variable"], leaf["operand"])))
failed = [n for n, ok in checks if not ok]
print("\nSUMMARY: %d differing paths, %d expected, %d unexpected; %d/%d checks pass"
      % (len(diffs), len(diffs) - len(unexpected), len(unexpected), len(checks) - len(failed), len(checks)))
sys.exit(1 if unexpected or failed else 0)

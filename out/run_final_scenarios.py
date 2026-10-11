#!/usr/bin/env python3
"""Run the final case's published example scenarios against a published Freya agent.

This is diagnostic evidence, not the organisers' hidden score. The JSON report
keeps the platform verdict, call id, retry count, and transcript for each call.
"""
import argparse
import datetime as dt
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import freya


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("agent_id")
    ap.add_argument("--scenarios", default=str(ROOT / "out/final.scenarios.json"))
    ap.add_argument("--out", default=str(ROOT / "results/final-scenarios.json"))
    ap.add_argument("--max-seconds", type=int, default=240)
    args = ap.parse_args()
    scenarios = json.loads(Path(args.scenarios).read_text())
    if not scenarios or any(not s.get("criteria") or not s.get("customer") for s in scenarios):
        ap.error("Each scenario needs customer instructions and observable criteria")

    prefix = ("You are the caller. Speak naturally in Turkish, using only words you "
              "would say on the phone. Follow the situation below. Do not invent new "
              "identity or card facts. When the call ends, say goodbye and stop.\n\n")
    payload = [{"name": "final example %d: %s" % (i, s["name"]),
                "prompt": prefix + s["customer"],
                "successCriteria": "All conditions must hold:\n" +
                                   "\n".join("- " + c for c in s["criteria"]),
                "tags": ["final-case-example"]}
               for i, s in enumerate(scenarios, 1)]
    created = freya.create_personas(payload)["personas"]
    if len(created) != len(scenarios):
        raise RuntimeError("Freya returned a different number of personas")
    variables = {p["id"]: s["variables"] for p, s in zip(created, scenarios)}
    names = {p["id"]: s["name"] for p, s in zip(created, scenarios)}
    sim_id, iteration_id, status = freya.run_simulation(
        args.agent_id, "final examples " + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        variables, max_seconds=args.max_seconds)
    runs = freya.get_iteration(sim_id, iteration_id).get("runs", [])
    rows = []
    for run in runs:
        pid = run.get("personaId")
        call_id = run.get("callId")
        attempts = run.get("attempts", 0)
        row = {"scenario": names.get(pid, pid), "persona_id": pid, "outcome": run.get("outcome"),
               "reason": run.get("reason"), "attempts": attempts, "call_id": call_id}
        if call_id:
            try:
                row["messages"] = freya.get_call(call_id).get("messages", [])
            except Exception as error:
                row["call_read_error"] = str(error)
        rows.append(row)
        label = "VOID" if attempts else "PASS" if row["outcome"] == "pass" else "FAIL"
        print("%s %s | call %s | %s" % (label, row["scenario"], call_id,
                                       str(row["reason"] or "")[:240]), flush=True)
    report = {"source": "final-case/example-scenarios.md", "agent_id": args.agent_id,
              "simulation_id": sim_id, "iteration_id": iteration_id, "status": status,
              "scenarios": len(scenarios), "rows": rows}
    destination = Path(args.out)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    valid = [r for r in rows if not r["attempts"]]
    passed = sum(r["outcome"] == "pass" for r in valid)
    print("%d/%d valid runs passed; %d void; report %s" %
          (passed, len(valid), len(rows) - len(valid), destination), flush=True)
    return 0 if len(rows) == len(scenarios) and len(valid) == len(rows) and passed == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())

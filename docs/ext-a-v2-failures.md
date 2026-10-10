# Extended Brief A run against the conversation-first reference (brief-a-v2)

`python3 builder/sim.py brief-a-v2 --cases tests/cases/brief-a-extended.cases.json --concurrency 2`
on 2026-10-10 (workflow 4045179c-42e8-436d-9fe2-c21c616c71fc, the port of the 10/10 generator): **34 / 42**.
Transcripts are in `results/ext-a-v2/` (gitignored). The 8 failures, classified after reading the transcripts:

## Agent bugs (fix in the reference generators and the library defaults)

| case | what happened | rule | fix |
|---|---|---|---|
| EXT-A-18 | customer says the full amount is too much; floor refused; attempt 1 proposed **2100** (the full amount) on Fri 16 Oct instead of **700** (the floor) | A rule 30: "Attempt 1 is for the full past-due amount, **or for the floor if the customer already said the full amount is too much**" | the attempt ladder must switch to the floor once `too_much` was said (a code flag, not a prompt note); attempt 2 = floor on the deadline |
| EXT-A-28 | hardship disclosed **and** the customer names 700 on Thu 22 Oct in the same sentence; the agent offered the transfer, it was declined, the call closed `no_promise/hardship`; the named promise was ignored | A rule 32 last sentence: "If the customer still names a date or an amount themselves, record the promise under sections 7 and 8" | the hardship node needs an offer route: a named date/amount goes through the offer check and the confirm node like any other offer; only an accepted transfer or a decline **without** a named offer closes `hardship` |
| EXT-A-31 | promise recorded, the call ended at once; the customer's "I'd like to talk to a person" after the promise never got a turn (expected: ask once whether you can help, then transfer `general`, outcome `transferred/human` with the promise kept) | A rule 42; audit R57 already flagged "a recorded promise ends the call at once" | after `create_promise` ok, say the text-message sentence and stay in a short **wrap-up conversation node** ("Is there anything else I can help you with?"): nothing/goodbye -> fin_promise; human request -> ask once, insist -> transfer general (the promise stays, close code of the transfer); plan/lower instalments -> transfer restructuring; change the promise -> the mobile-app sentence (rule 36), promise unchanged; a question -> answer from the brief or "I don't have that information"; a loop guard (2 turns max) |
| EXT-A-35 | same: "Can I move that to Monday?" after the promise never got a turn (expected the mobile-app sentence, promise unchanged) | A rule 36 | same wrap-up node |
| EXT-A-34 | at the read-back ("420 on Friday 16 October, do you confirm?") the customer said "Actually, make it 250 instead"; the extraction routed `topic == new_plan` and the call was transferred to **restructuring** | A rule 35: a changed date or amount at the read-back is checked and read back again; rule 41 restructuring is only for "a new payment plan or lower instalments" | the confirm node's extraction is `confirm in {yes, no, change}`; a new amount or date is `change` -> check_offer -> read back again; the `new_plan` enum description must say "a different amount or date for this promise is NOT a plan request"; (T22 in docs/research/sota-techniques.md) |

## Not agent bugs

| case | verdict | why |
|---|---|---|
| EXT-A-17 | **case error** | below-floor 100 -> floor 400 offered once (refused) -> attempt 1 full amount on Fri 16 (refused) -> attempt 2 floor 400 on the deadline Fri 23 (refused) -> `no_promise/refused`. Rule 26 says "Attempt 2 may name the floor again, on the deadline" and rule 30 says attempt 2 in the late band is "the floor amount on the deadline". The check "does not repeat an offer already refused" contradicts the brief. |
| EXT-A-25 | **judge artefact** | the agent made exactly one persuasion attempt (full amount on Fri 16 Oct) after "No, I'm not paying"; the judge counted the mandatory opening question "Can you make this payment today?" (rule 24) as a persuasion attempt. |
| EXT-A-01 | **customer-sim deviation / ambiguous** | the script said never say yes; the simulated customer answered "Yeah, go ahead." to the second ask. "Yeah" is a yes; rule 3 says "go ahead" alone is not. Keep the `who` enum descriptions quoting the brief's own lists of what counts and what does not. |

## What transfers to a hidden brief

The five agent bugs are architecture gaps, not Brief A values: the attempt ladder must be computed in code from flags
(`too_much`, `offered_floor`, attempts used), hardship must still accept a named offer, the read-back must have a
`change` route that never leaves the promise flow, and a recorded promise must not end the call before the customer has
had one more turn. The policy-as-code library (builder/policy.py: offer guard, confirm node, stance counter, state_line)
and the skill's default architecture must carry these.

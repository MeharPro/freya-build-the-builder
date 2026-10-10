# Brief C extended cases: rationale (Nordvik Savings Bank)

Source: `tests/synthetic/brief-c.md` (rule numbers below are that brief's). Cases: `brief-c-extended.cases.json`, ids `EXT-C-01`..`EXT-C-30`.
Every case reuses one of the organisers' fixed mock customers through `mock_case` (identity answers, product, `days_late` and faults are the mock's, copied verbatim from `public-test-set.json`); the script, the expected ledger and the checks are ours. Brief C never calls `add_note`, so every `notes` list is empty.

## 0. Shared facts

### Mock customers under Brief C

| mock | name | phone / DOB | product | past_due | days_late | band | floor (rule 26) |
|---|---|---|---|---|---|---|---|
| PUB-01 | Mr Daniel Reyes | 4471 / 1988-03-14 | credit card 4821 | 420.00 | 6 | green | ceil(168.00) = 168 |
| PUB-02 | Ms Maria Costa | 0358 / 1979-11-02 | personal loan | 310.50 | 11 | amber | 103.50 |
| PUB-03 | Mr Owen Park | 6630 / 1992-07-21 | credit card 0377 | 95.00 | 4 | green | ceil(38.00) = 38 |
| PUB-04 | Ms Lena Hoffmann | 2219 / 1984-01-30 | car loan | 1250.00 | 14 | amber | 400 |
| PUB-05 | Mr Tomas Novak | 8846 / 1990-09-09 | personal loan | 780.00 | 21 | amber | 260 |
| PUB-06 | Ms Priya Nair | 1502 / 1986-05-17 | credit card 1903 | 2125.10 | 12 | amber | ceil(850.04) = 851 |
| PUB-07 | Mr Samuel Ortiz | 7093 / 1975-12-05 | personal loan | 540.00 | 5 | green | 180 |
| PUB-08 | Ms Hannah Schmidt | 3317 / 1993-04-28 | credit card 5512 | 180.00 | 5 | green | ceil(72.00) = 72 |
| PUB-09 | Mr Victor Ionescu | 5560 / 1981-08-11 | personal loan | 2100.00 | 28 | amber | 700 |
| PUB-10 | Ms Grace Lin | 9904 / 1989-02-23 | credit card 7740 | 365.00 | 8 | green | 146 |

PUB-10's session carries the mock fault `create_promise fail_first_n 1`, so it is used only where a first failed `create_promise` is intended (EXT-C-25). PUB-11..13 have several products and Brief C is single-product, so they are not used.

Bands (rule 19): green = 1-10 days late, deadline = 9th business day after today, 2 attempts; amber = 11-45, 4th business day, 1 attempt. Attempt 1 = the amount in play on the next business day after today; attempt 2 (green only) = the floor on the deadline (rule 31). Promise reason (rule 47): `full` when the recorded amount equals `past_due`, else `partial`.

Calendar (rule 19 / section 7): business days Monday to Saturday; holidays 2026-10-16, 2026-11-02, 2026-11-21, 2026-12-08, 2026-12-24, 2026-12-25, 2026-12-26, 2026-12-31. Sundays and holidays are never business days. Today is not counted.

### Business-day ladders (computed with a script, then recounted by hand)

**now = Wednesday 2026-10-14 11:00** (EXT-C-01..25)

| n | 1 | - | 2 | - | 3 | 4 | 5 | 6 | 7 | 8 | - | 9 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| date | Thu 15 | Fri 16 (holiday) | Sat 17 | Sun 18 | Mon 19 | **Tue 20 = amber deadline** | Wed 21 | Thu 22 | Fri 23 | Sat 24 | Sun 25 | **Mon 26 = green deadline** |

Attempt 1 = Thu 2026-10-15. Callback window (rule 6): today after 11:00, Thu 15, Sat 17; 09:00-18:00.

**now = Saturday 2026-10-17 10:00** (EXT-C-26). Today is a business day (Saturday).
Sun 18 -, Mon 19 = 1, Tue 20 = 2, Wed 21 = 3, Thu 22 = 4 (amber deadline), Fri 23 = 5, Sat 24 = 6, Sun 25 -, Mon 26 = 7, Tue 27 = 8, Wed 28 = 9 (green deadline).

**now = Wednesday 2026-10-14 18:30** (EXT-C-27, 28). Same ladder as 14 October. Callback window: today needs a time later than 18:30 and not after 18:00, so no slot is left today; Thu 15 and Sat 17, 09:00-18:00. Fri 16 is a holiday and outside the window.

**now = Friday 2026-10-30 11:00** (EXT-C-29)
Sat 31 = 1, Sun 1 Nov -, Mon 2 Nov (holiday) -, Tue 3 = 2, Wed 4 = 3, **Thu 5 = 4 (amber deadline)**, Fri 6 = 5, Sat 7 = 6, Sun 8 -, Mon 9 = 7, Tue 10 = 8, **Wed 11 = 9 (green deadline)**. Attempt 1 = Sat 2026-10-31.

**now = Monday 2026-12-07 11:00** (EXT-C-30)
Tue 8 (holiday) -, Wed 9 = 1, Thu 10 = 2, Fri 11 = 3, **Sat 12 = 4 (amber deadline)**, Sun 13 -, Mon 14 = 5, Tue 15 = 6, Wed 16 = 7, Thu 17 = 8, **Fri 18 = 9 (green deadline)**. Attempt 1 = Wed 2026-12-09.

## 1. Per-case derivations

### Opening
- **EXT-C-01** (PUB-01): Reply to the first ask is the scam question, so rule 44 applies (they may hang up and call the number on the card or statement), and by rule 3 the ask that follows the answer is the **second** ask. "Go ahead, I'm listening" is not one of the confirming words (rule 3 lists "go ahead" as not counting). Two asks without confirmation: `not_reached` / `unconfirmed`. No identity tool (score.py also fails any `verify_identity` on a `not_reached` case).

### Third party
- **EXT-C-02** (PUB-02): "Four o'clock this afternoon" = 2026-10-14 16:00: today, later than 11:00, inside 09:00-18:00 (rule 6). `schedule_callback 2026-10-14 16:00`; `not_reached` / `scheduled`.
- **EXT-C-03** (PUB-06): number does not belong to the customer, rule 8: apologise; `not_reached` / `wrong_party`.
- **EXT-C-04** (PUB-09): customer died, rule 9: "Please accept my condolences.", nothing further; `not_reached` / `estate`.
- **EXT-C-27** (PUB-05, now 18:30): "Tonight around eight" = 20:00 today: after 18:00, outside. Rule 7: state the window, ask once. "Saturday at ten" = Sat 2026-10-17 10:00: business day 2 (Saturday counts), inside 09:00-18:00. `schedule_callback 2026-10-17 10:00`; `not_reached` / `scheduled`.
- **EXT-C-28** (PUB-02, now 18:30): "Tonight at seven" (19:00 today) is outside; the second slot "Friday morning at ten" = Fri 2026-10-16 is a holiday, not a business day, and not one of today/15/17. Second slot outside, rule 7: schedule nothing; `not_reached` / `no_slot`.

### Identity
- **EXT-C-05** (PUB-07): phone first (rule 11). 7039 is wrong (wrong answers = 1), repeat (rule 13); 7093 passes. DOB "12 May 1975" = 1975-05-12; swapping day and month gives 1975-12-05 = the record, so the mock returns `hint: day_month_swapped`. Rule 14: first swapped retry per call is free, wrong answers stay at 1. "5 December 1975" = 1975-12-05 passes. `get_account`; he says he already paid (rule 40): two business days, no promise; `paid` / `self_reported`. An agent that counts the hint as the second wrong answer closes `not_verified` / `exhausted` and fails.
- **EXT-C-06** (PUB-01): first refusal, rule 16: say once that nothing can be discussed until the check is complete, ask again; he answers, so the call continues. Then "not all of it, I could do 100 today": 100 < floor 168 (40% of 420 = 168.00, already whole) -> rule 28: say 168 is the smallest amount and propose it once (if the agent reads "not all of it" as "too much", rule 27 also proposes 168: same ledger). Accepts 168 today 2026-10-14 (a Wednesday, business day). 168 < 420 -> `promise` / `partial`.
- **EXT-C-07** (PUB-06): two deflections ("what is this about?") instead of answers, rule 16: first one gets the once-only explanation, the second closes `not_verified` / `withheld`. No identity call with an invented answer.
- **EXT-C-08** (PUB-09): 5506 wrong (1), 5065 wrong (2): rule 13, the second wrong answer ends the check immediately, on the first question; DOB never asked. Rule 15 wording; `not_verified` / `exhausted`. (The mock allows 3 wrong answers; the case checks the agent stops at 2.)

### Amounts
- **EXT-C-09** (PUB-02, amber, deadline Tue 20): 320 > 310.50 -> rule 28: record the full amount and say so. "This Saturday, the 17th" = Sat 2026-10-17, business day 2, <= deadline -> valid as is (rule 21: Saturday is accepted). 310.50 == past_due -> `promise` / `full`.
- **EXT-C-10** (PUB-08, green, deadline Mon 26): "too much" -> rule 27: floor 72 (40% of 180 = 72.00) once with the arrears sentence. Declines -> flat refusal (rules 27, 31). Whichever way the agent counts the floor decline, the only proposal she accepts is the floor 72 on the deadline Mon 2026-10-26, which is exactly attempt 2 (green only, rule 31). 72 < 180 -> `promise` / `partial`.
- **EXT-C-11** (PUB-06, amber): "too much" -> floor 851 (40% of 2125.10 = 850.04, rounded up). Declined = flat refusal using the single amber attempt; at most one further proposal (attempt 1 on Thu 15); everything declined -> rule 32: `no_promise` / `declined_offer`.

### Dates
- **EXT-C-12** (PUB-03, green): "Sunday the 25th" = Sun 2026-10-25, not later than the deadline Mon 26 -> rule 21: not a business day, propose the next business day = Mon 2026-10-26 = the deadline itself, valid (rule 20). Full 95 -> `promise` / `full`.
- **EXT-C-13** (PUB-04, amber, deadline Tue 20): "next Friday" said on Wednesday 14 = the first Friday after today = Fri 2026-10-16 (rule 22), a holiday not later than the deadline -> rule 21: propose the next business day Sat 2026-10-17. 1250 -> `promise` / `full`. (A Mon-Fri or "next week's Friday" reading gives 23 October, after the amber deadline, and a different ledger.)
- **EXT-C-14** (PUB-01, green): "Sometime next week" is a vague period (rule 23): ask once for the exact day; "can't say" = non-answer = one attempt (rule 23 -> 31): attempt 1 = full 420 on Thu 2026-10-15. Accepts -> `promise` / `full`.
- **EXT-C-29** (PUB-04, now Fri 30 Oct, amber deadline Thu 5 Nov): "next Monday" = the first Monday after today = Mon 2026-11-02, a holiday not later than the deadline -> propose the next business day Tue 2026-11-03 (business day 2). `promise` / `full`, 1250 on 2026-11-03.
- **EXT-C-30** (PUB-09, now Mon 7 Dec, amber deadline Sat 12 Dec): "Friday the 18th" = 2026-12-18 > 2026-12-12 -> rule 24: name the deadline Saturday 12 December and propose it; accepted. The ladder skips the 8 December holiday (an agent that counts it lands on Fri 11). `promise` / `full`, 2100 on 2026-12-12.
- **EXT-C-26** (PUB-01, now Sat 17 Oct 10:00): Saturday is a business day; "yes, today" = 2026-10-17, valid (rule 20). `promise` / `full`, 420 on 2026-10-17.

### Persuasion
- **EXT-C-15** (PUB-07, green): robot question, rule 4 sentence. Bare "No, I can't" to the opener = flat refusal (rule 31) -> attempt 1: full 540 on Thu 2026-10-15; accepted. `promise` / `full`.
- **EXT-C-16** (PUB-03, green): flat refusals only. Attempt 1: 95 on Thu 15; attempt 2: floor 38 (40% of 95) on Mon 26 (deadline). Both refused -> rule 32: stop; `no_promise` / `declined_offer`.

### Hardship
- **EXT-C-17** (PUB-02): hospital / no income = hardship (rule 33): the exact sentence, no attempt, care team offered; yes -> `transfer_to_agent support`; `transferred` / `care_team`.
- **EXT-C-18** (PUB-08, green): bereavement -> rule 33 sentence; declines the care team but names 100 on "Friday the 23rd" herself = Fri 2026-10-23 (business day 7 <= deadline 26). 72 <= 100 <= 180 -> accepted (rule 28); rule 33 last sentence: record it. 100 < 180 -> `promise` / `partial`.

### Other situations
- **EXT-C-19** (PUB-05): "I never had a personal loan" -> rule 41: no argument, no promise, "a colleague will look into it", `transfer_to_agent general`; `transferred` / `contested`. (Brief C transfers disputes, unlike Brief D.)
- **EXT-C-20** (PUB-09): spread over six months -> rule 42: describe nothing, plan review team, ask to connect; "no" -> `no_promise` / `declined_offer`, no transfer.
- **EXT-C-21** (PUB-04): request for a person at the first security question -> rule 43 applies before the check: transfer `general` at once; `transferred` / `agent_request`; no identity call.
- **EXT-C-22** (PUB-05): verified, then "I don't want to talk" -> rule 46 after the check: `no_promise` / `declined_offer`.
- **EXT-C-23** (PUB-08): "I don't want to talk" at the first security question -> rule 46 before the check: `not_verified` / `withheld`.
- **EXT-C-24** (PUB-09, amber): pays the full 2100 today (2026-10-14), recorded, then asks for a person -> rule 43 transfer `general`; rule 47: a transfer after a recorded promise closes as `promise` / `full`. Ledger: promise + transfer `general`.
- **EXT-C-25** (PUB-10, green, floor 146 = ceil(0.4 x 365)): "Monday the 19th" = Mon 2026-10-19 (business day 3, <= 26) with the full amount; at the read-back changes to 200 -> rule 36: re-check (146 <= 200 <= 365) and read back again. First `create_promise` fails (mock fault) -> rule 38: call again (up to two more times), "noted" only after ok. One promise 200 on 2026-10-19, `partial`.

## 2. Expected ledger summary

| Case | mock | now | Outcome / reason | Promise | Callback | Transfer |
|---|---|---|---|---|---|---|
| EXT-C-01 | PUB-01 | 10-14 11:00 | not_reached / unconfirmed | - | - | - |
| EXT-C-02 | PUB-02 | 10-14 11:00 | not_reached / scheduled | - | 2026-10-14 16:00 | - |
| EXT-C-03 | PUB-06 | 10-14 11:00 | not_reached / wrong_party | - | - | - |
| EXT-C-04 | PUB-09 | 10-14 11:00 | not_reached / estate | - | - | - |
| EXT-C-05 | PUB-07 | 10-14 11:00 | paid / self_reported | - | - | - |
| EXT-C-06 | PUB-01 | 10-14 11:00 | promise / partial | p1 168.00 2026-10-14 | - | - |
| EXT-C-07 | PUB-06 | 10-14 11:00 | not_verified / withheld | - | - | - |
| EXT-C-08 | PUB-09 | 10-14 11:00 | not_verified / exhausted | - | - | - |
| EXT-C-09 | PUB-02 | 10-14 11:00 | promise / full | p1 310.50 2026-10-17 | - | - |
| EXT-C-10 | PUB-08 | 10-14 11:00 | promise / partial | p1 72.00 2026-10-26 | - | - |
| EXT-C-11 | PUB-06 | 10-14 11:00 | no_promise / declined_offer | - | - | - |
| EXT-C-12 | PUB-03 | 10-14 11:00 | promise / full | p1 95.00 2026-10-26 | - | - |
| EXT-C-13 | PUB-04 | 10-14 11:00 | promise / full | p1 1250.00 2026-10-17 | - | - |
| EXT-C-14 | PUB-01 | 10-14 11:00 | promise / full | p1 420.00 2026-10-15 | - | - |
| EXT-C-15 | PUB-07 | 10-14 11:00 | promise / full | p1 540.00 2026-10-15 | - | - |
| EXT-C-16 | PUB-03 | 10-14 11:00 | no_promise / declined_offer | - | - | - |
| EXT-C-17 | PUB-02 | 10-14 11:00 | transferred / care_team | - | - | support |
| EXT-C-18 | PUB-08 | 10-14 11:00 | promise / partial | p1 100.00 2026-10-23 | - | - |
| EXT-C-19 | PUB-05 | 10-14 11:00 | transferred / contested | - | - | general |
| EXT-C-20 | PUB-09 | 10-14 11:00 | no_promise / declined_offer | - | - | - |
| EXT-C-21 | PUB-04 | 10-14 11:00 | transferred / agent_request | - | - | general |
| EXT-C-22 | PUB-05 | 10-14 11:00 | no_promise / declined_offer | - | - | - |
| EXT-C-23 | PUB-08 | 10-14 11:00 | not_verified / withheld | - | - | - |
| EXT-C-24 | PUB-09 | 10-14 11:00 | promise / full | p1 2100.00 2026-10-14 | - | general |
| EXT-C-25 | PUB-10 | 10-14 11:00 | promise / partial | p1 200.00 2026-10-19 (after 1 failed try) | - | - |
| EXT-C-26 | PUB-01 | 10-17 10:00 (Sat) | promise / full | p1 420.00 2026-10-17 | - | - |
| EXT-C-27 | PUB-05 | 10-14 18:30 | not_reached / scheduled | - | 2026-10-17 10:00 | - |
| EXT-C-28 | PUB-02 | 10-14 18:30 | not_reached / no_slot | - | - | - |
| EXT-C-29 | PUB-04 | 10-30 11:00 (Fri) | promise / full | p1 1250.00 2026-11-03 | - | - |
| EXT-C-30 | PUB-09 | 12-07 11:00 (Mon) | promise / full | p1 2100.00 2026-12-12 | - | - |

## 3. Rule coverage (rules of brief-c.md; P = original practice case, E = extended)

| Rules | Covered by |
|---|---|
| 1-2 opening, no forbidden words before the check | every case's checks (E-01, E-02, E-07, E-21 explicitly) |
| 3 unconfirmed after two asks; a question first makes the next ask the second | E-01 |
| 4 robot | P-04, E-15 |
| 5, 10 third party says nothing, declines offers | P-02, E-02, E-27, E-28 |
| 6 callback today later than now / next two business days / Saturday | P-02 (tomorrow), E-02 (today), E-27 (Saturday, evening call) |
| 7 slot outside twice -> no_slot | E-28 (E-27: once, then inside) |
| 8 wrong_party / 9 estate | E-03 / E-04 |
| 11 phone first | every verified case; E-08 ends on the phone question |
| 12 numeric date -> ask for the month as a word | not scripted (see section 4) |
| 13 two wrong answers in total | P-03 (DOB), E-08 (phone), E-05 (one wrong, still passes) |
| 14 one free swapped retry | E-05 |
| 15 exhausted wording | P-03, E-08 |
| 16 refusal once / two deflections | E-06 / E-07 |
| 17-18 get_account, title + last name, product in words | all verified cases |
| 19-20 bands, deadlines, valid dates | E-10, E-12 (green deadline), E-13, E-30 (amber deadline on a Saturday), E-26, E-29 |
| 21 Sunday/holiday -> next business day; Saturday accepted | E-12 (Sunday), E-13, E-29 (holiday), E-09, E-26 (Saturday) |
| 22 "next/this <weekday>" | E-13 (next Friday on a Wednesday), E-29 (next Monday on a Friday) |
| 23 vague twice -> non-answer uses an attempt | E-14 |
| 24 after the deadline -> propose the deadline | P-04, E-30 |
| 25, 29 full amount first, never ask what they can pay | E-06, E-10, E-11 |
| 26 floors | E-06 (168), E-10 (72), E-11 (851), E-16 (38), E-25 (146 bound) |
| 27 too much -> floor once, declined -> refusal | P-06, E-10, E-11 |
| 28 between / above / below | E-18, E-25 (between), E-09 (above), E-06 (below) |
| 30-32 attempts green 2 / amber 1, never repeat | E-14, E-15 (attempt 1), E-10, E-16 (attempt 2), E-11 (amber 1) |
| 33 hardship: care team yes / no / self-named promise | E-17 / P-05 / E-18 |
| 34 no reduction | P-05, E-11 check |
| 35-36 read-back, change at read-back | E-25 |
| 37 one promise per product, no change after recording | not scripted (see section 4) |
| 38 retry on failure | P-10, E-25 |
| 39 email sentence | E-06, E-24, E-25 |
| 40 already paid | P-08, E-05 |
| 41 dispute -> contested (transfer general) | E-19 |
| 42 plan yes / no | P-09 / E-20 |
| 43 person before / after the check | E-21 / E-24 |
| 44 scam | E-01 |
| 46 do not want to talk after / before | E-22 / E-23 |
| 47 promise then transfer closes as promise; reason full vs partial | E-24; full: E-09, E-12..15, partial: E-06, E-10, E-18, E-25 |

## 4. Rules the fixed mock customers cannot test (or that were left out)

- **Rule 38, all three tries fail -> `system_fault`**: the only fault the mock serves is PUB-10's single failure (`fail_first_n: 1`); no mock customer fails three times.
- **Rule 12, a value the service cannot read (`ok: false`)**: scriptable (a customer saying "3/7/85" should be asked for the month as a word before anything is sent), but the outcome is in what the agent says, not in the ledger, so it is left to the judge-only smoke tests.
- **Rule 37, asking to change a recorded promise**: the ledger cannot show a refused change (the expected ledger equals a plain promise); not given its own case.
- **Rule 45, unanswerable question**: conversation-only, no ledger effect.
- **Amber band customers aged >45 days, more than one product**: no such mock customer.
- **A day_month_swapped answer given twice** (the second one counts as wrong): possible with PUB-02/07/09 but omitted to keep the count; easy to add.

## 5. Verification (separate pass, 10 Oct)

A separate reviewer re-read `brief-c.md`, recomputed every ladder, deadline, floor and weekday with its own script without reading this file, and simulated every script. A mechanical check also asserted that the mock data was copied exactly, that every promise date is a business day between today and its deadline, that every amount lies between the floor and past_due, that full/partial matches, and that every callback falls inside the window. **All 30 expected ledgers were confirmed.** Fixes made after the pass:
- EXT-C-28: check 1 reworded ("after the 19:00 offer is refused, the agent states the window and asks once"). The old wording could be read as "a slot later than 19:00".
- EXT-C-11: "once" dropped from the floor check. Rules 27 and 31 conflict for an amber customer who has said "too much": rule 31 makes attempt 1 the floor on Thu 15, while rule 27 allows the floor to be named again only as attempt 2. A correct agent may therefore name 851 twice, propose the full amount on the 15th, or stop after the declined floor. The ledger (`declined_offer`) is the same on every reading.

Known ambiguity risks (the ledger is unaffected):
- EXT-C-10: attempt 1 may be 72 or 180 on Thu 15, for the same rule 27/31 reason.
- EXT-C-01: the agent might answer "Go ahead" with a third ask; the brief says close after the second ask.
- EXT-C-05 depends on the mock returning `day_month_swapped` for 1975-05-12 against 1975-12-05. If it does not, the run ends `exhausted`; check the tool result in the transcript before blaming the agent.

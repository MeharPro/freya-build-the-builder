# Brief A extended cases: derivation of every expected value

`tests/cases/brief-a-extended.cases.json`: 42 cases, `EXT-A-01`..`EXT-A-42`. Each reuses a mock-bank practice customer
(`mock_case`), whose identity answers, product, `days_late` and faults are fixed by the mock and copied unchanged from
`public-test-set.json`. Only the script, the expected ledger and the checks are new. Cases 37 to 42 change `variables.now`.

Rule numbers are Brief A's. A reviewer can re-run the mechanical part of this file with
`python3 tests/cases/verify_cases.py .` (its own calendar code; it re-derives every promise and callback from a
re-stated rule path and checks the outcome table, floors, deadlines and the copied mock data).

## Mock customers used (fixed by the mock bank)

| mock | name | product | past_due | days_late → band | floor (rule 25) | DOB / phone |
|---|---|---|---|---|---|---|
| PUB-01 | Mr Daniel Reyes | credit card 4821 | 420.00 | 6 → early | min 126.00 | 1988-03-14 / 4471 |
| PUB-02 | Ms Maria Costa | personal loan | 310.50 | 11 → late | inst 103.50 | 1979-11-02 / 0358 |
| PUB-03 | Mr Owen Park | credit card 0377 | 95.00 | 4 → early | min 28.50 | 1992-07-21 / 6630 |
| PUB-04 | Ms Lena Hoffmann | car loan | 1250.00 | 14 → late | inst 400.00 | 1984-01-30 / 2219 |
| PUB-05 | Mr Tomas Novak | personal loan | 780.00 | 21 → late | inst 260.00 | 1990-09-09 / 8846 |
| PUB-06 | Ms Priya Nair | credit card 1903 | 2125.10 | 12 → late | min 637.50 | 1986-05-17 / 1502 |
| PUB-07 | Mr Samuel Ortiz | personal loan | 540.00 | 5 → early | inst 180.00 | 1975-12-05 / 7093 |
| PUB-08 | Ms Hannah Schmidt | credit card 5512 | 180.00 | 5 → early | min 54.00 | 1993-04-28 / 3317 |
| PUB-09 | Mr Victor Ionescu | personal loan | 2100.00 | 28 → late | inst 700.00 | 1981-08-11 / 5560 |
| PUB-10 | Ms Grace Lin | credit card 7740 | 365.00 | 8 → late | min 109.50 | 1989-02-23 / 9904; first `create_promise` fails |

## Business-day ladders (rule 18; holidays 2026-10-26, 11-11, 11-26, 12-25, 2027-01-01)

"Nth business day after today" counts from the day after `now`, skipping weekends and holidays.

| now | 1 | 2 | 3 | 4 | 5 | 6 | **7 (late)** | 8 | 9 | 10 | 11 | **12 (early)** | attempt 1 (rule 30) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Wed 2026-10-14 | Thu 15 | Fri 16 | Mon 19 | Tue 20 | Wed 21 | Thu 22 | **Fri 23 Oct** | Tue 27 (26 hol.) | Wed 28 | Thu 29 | Fri 30 | **Mon 2 Nov** | Fri 16 Oct |
| Fri 2026-10-16 | Mon 19 | Tue 20 | Wed 21 | Thu 22 | Fri 23 | Tue 27 (26 hol.) | **Wed 28 Oct** | Thu 29 | Fri 30 | Mon 2 Nov | Tue 3 | **Wed 4 Nov** | Fri 23 Oct (today is the last business day of this week) |
| Fri 2026-10-23 | Tue 27 (26 hol.) | Wed 28 | Thu 29 | Fri 30 | Mon 2 Nov | Tue 3 | **Wed 4 Nov** | Thu 5 | Fri 6 | Mon 9 | Tue 10 | **Thu 12 Nov** (11 hol.) | Fri 30 Oct |
| Tue 2026-11-10 | Thu 12 (11 hol.) | Fri 13 | Mon 16 | Tue 17 | Wed 18 | Thu 19 | **Fri 20 Nov** | Mon 23 | Tue 24 | Wed 25 | Fri 27 (26 hol.) | **Mon 30 Nov** | Fri 13 Nov |

So at the default `now` (Wed 14 Oct): late deadline **23 Oct**, early deadline **2 Nov**, attempt 1 **Fri 16 Oct**
(matches PUB-04's 23 Oct and PUB-06/PUB-10's Friday 16 Oct).

## Per case

`now` is Wed 2026-10-14T11:00 unless stated. "promise X on D" = ledger `{p1, X, D}`. Outcome/reason from the table in rule 46.

### Opening (rules 1-4, 43)
- **EXT-A-01** (PUB-01) "Hello?" then "go ahead": neither confirms (rule 3); after the second ask still unclear → `not_reached`/`unclear`. No tools but `close_call`.
- **EXT-A-02** (PUB-03) robot question first (rule 4, answered, then the second ask), then "that's me"; both answers right; full today → promise 95.00 on 2026-10-14.
- **EXT-A-03** (PUB-08) scam question (rule 43), then confirms; Thu 22 Oct is a business day, ≥ today, ≤ early deadline 2 Nov (rule 19) → promise 180.00 on 2026-10-22.

### Third party (rules 5-10)
- **EXT-A-04** (PUB-02) today 16:00: today, inside 10:00-19:00, later than 11:00 (rule 6) → callback 2026-10-14 16:00, `not_reached`/`callback`.
- **EXT-A-05** (PUB-02) "tonight at nine" (21:00 > 19:00, outside), asked once more (rule 7), "Saturday morning" (Sat 17 Oct is neither today nor the next business day Thu 15) → no callback, `not_reached`/`no_callback`.
- **EXT-A-06** (PUB-02) not the customer's number (rule 8) → `not_reached`/`wrong_number`.
- **EXT-A-07** (PUB-05) wife says he died (rule 9) → "I am sorry for your loss.", `not_reached`/`deceased`.
- **EXT-A-08** (PUB-06) husband offers to pay (rule 10: refused, nothing disclosed); "tomorrow at seven in the evening" = Thu 15 Oct (next business day) 19:00, 19:00 included (rule 6) → callback 2026-10-15 19:00.

### Identity (rules 11-15)
- **EXT-A-09** (PUB-07, DOB 5 Dec 1975) says "12, 5, 1975": numbers are read day-month-year (rule 11) → 1975-05-12, the true date with day and month swapped → `hint: day_month_swapped`, ask for the month as a word, not a wrong answer (rule 13); "fifth of December 1975" passes; phone 7093; full today → promise 540.00 on 2026-10-14. *Depends on the mock returning the hint (the brief says it does).*
- **EXT-A-10** (PUB-04) phone 2291 wrong (1 of 3), 2219 right (rule 12); Wed 21 Oct business day ≤ late deadline 23 Oct → promise 1250.00 on 2026-10-21.
- **EXT-A-11** (PUB-01) first refusal → explain once (rule 15), then answers; "tomorrow" = Thu 15 Oct, business day ≤ 2 Nov → promise 420.00 on 2026-10-15.
- **EXT-A-12** (PUB-03) refuses, explanation, refuses again (rule 15) → `not_verified`/`declined`, `verify_identity` never called.
- **EXT-A-13** (PUB-08) "what is this about?" twice instead of answering counts as declining (rule 15) → `not_verified`/`declined`.
- **EXT-A-14** (PUB-06) DOB wrong once (17 June), right (17 May); phone 1520 wrong, 1205 wrong → 3 wrong in total across both questions (rule 12) → `not_verified`/`failed`, app/branch (rule 14).

### Amounts (rules 24-27)
- **EXT-A-15** (PUB-01) 200 today: 126 ≤ 200 ≤ 420 (rule 27) → promise 200.00 on 2026-10-14.
- **EXT-A-16** (PUB-06) 300 on Friday: 300 < floor 637.50 → cannot be recorded, floor offered once (rule 27); accepted for Friday = Fri 16 Oct (business day ≤ 23 Oct) → promise 637.50 on 2026-10-16.
- **EXT-A-17** (PUB-04) 100 < floor 400 → floor offered once, refused → flat refusal (rule 27 → 30): late band, attempt 1 (Fri 16 Oct) and attempt 2 (400 on 23 Oct) refused → `no_promise`/`refused` (rule 31).
- **EXT-A-18** (PUB-09) full too much → floor 700 offered once (rule 26), refused → flat refusal: attempt 1 = floor (full already called too much) on Fri 16 Oct, refused; attempt 2 = floor on the late deadline 23 Oct, accepted → promise 700.00 on 2026-10-23.

### Dates (rules 19-23)
- **EXT-A-19** (PUB-08) Sat 17 Oct, not after the early deadline 2 Nov → next business day Mon 19 Oct (rule 20) → promise 180.00 on 2026-10-19.
- **EXT-A-20** (PUB-01) "next Friday" said on Wed 14 Oct = Friday of the following calendar week = Fri 23 Oct (rule 22); ≤ early deadline 2 Nov → promise 420.00 on 2026-10-23.
- **EXT-A-21** (PUB-05) vague twice → propose the deadline (rule 21), late band → promise 780.00 on 2026-10-23.
- **EXT-A-22** (PUB-03) 12 Oct is before today (rule 19) → not accepted; Tue 20 Oct is valid → promise 95.00 on 2026-10-20.
- **EXT-A-23** (PUB-02 as a verified customer) Mon 26 Oct is a holiday *after* the late deadline 23 Oct → rule 20 defers to rule 23: deadline offered, accepted → promise 310.50 on 2026-10-23 (not the next business day 27 Oct).

### Persuasion (rules 28-31)
- **EXT-A-24** (PUB-07, early) "No." = flat refusal → attempt 1: full on Fri 16 Oct, accepted → promise 540.00 on 2026-10-16.
- **EXT-A-25** (PUB-08, early, 1 attempt) refuses attempt 1 → stop → `no_promise`/`refused`.
- **EXT-A-26** (PUB-10, late, 2 attempts) refuses 365.00 on Fri 16 Oct and 109.50 on 23 Oct → `no_promise`/`refused`. (No promise, so the fault never fires.)

### Hardship (rule 32)
- **EXT-A-27** (PUB-06) illness, accepts support → `transfer_to_agent(support)`, `transferred`/`support`.
- **EXT-A-28** (PUB-09) death in the family, declines support, names 700 on Thu 22 Oct herself: 700 = floor ≤ 2100, Thu 22 Oct ≤ 23 Oct → promise 700.00 on 2026-10-22, outcome `promise`, no transfer.

### Dispute, human, refusal to talk (rules 40, 42, 45)
- **EXT-A-29** (PUB-03) "closed that card years ago" is a dispute, not rule 39 → `no_promise`/`dispute`.
- **EXT-A-30** (PUB-01) asks for a person, asked once, insists → `transfer_to_agent(general)`, `transferred`/`human`.
- **EXT-A-31** (PUB-07) full today recorded, then insists on a person → promise 540.00 on 2026-10-14 stays; `transferred`/`human` (note under rule 46).
- **EXT-A-32** (PUB-04) "don't want to talk" twice after verification → `no_promise`/`refused`.
- **EXT-A-33** (PUB-05) same before verification → `not_verified`/`declined`.

### Confirmation, tool failure (rules 34-37)
- **EXT-A-34** (PUB-01) full on "this Friday" = Fri 16 Oct, changed to 250 at the read-back: 126 ≤ 250 ≤ 420 (rule 35), read back again → promise 250.00 on 2026-10-16.
- **EXT-A-35** (PUB-08) full tomorrow (Thu 15 Oct) recorded; change request after recording → mobile app (rule 36), still one promise 180.00 on 2026-10-15.
- **EXT-A-36** (PUB-10) full too much → floor 109.50 today; first `create_promise` fails (mock fault), retry succeeds (rule 37) → exactly one promise 109.50 on 2026-10-14.

### Other call dates (`variables.now` changed)
- **EXT-A-37** (PUB-01, now Fri 16 Oct) "No." → attempt 1: today is the last business day of this week → last business day of next week = Fri 23 Oct; ≤ early deadline 4 Nov → promise 420.00 on 2026-10-23.
- **EXT-A-38** (PUB-03, now Fri 16 Oct) "this Friday" = the Friday of the current week = today (rule 22) → promise 95.00 on 2026-10-16.
- **EXT-A-39** (PUB-02 third party, now Wed 14 Oct 18:30) "seven tonight" = 19:00 today: inside the window (19:00 included), later than 18:30 → callback 2026-10-14 19:00.
- **EXT-A-40** (PUB-02 third party, now 18:30) "tonight at eight" = 20:00, outside → asked once more → "tomorrow at ten" = Thu 15 Oct 10:00 (next business day, 10:00 included) → callback 2026-10-15 10:00.
- **EXT-A-41** (PUB-04 late, now Fri 23 Oct) late deadline = 7th business day = Wed 4 Nov (26 Oct skipped; without the holiday it would be Tue 3 Nov); 6 Nov is after it → offered and accepted (rule 23) → promise 1250.00 on 2026-11-04.
- **EXT-A-42** (PUB-01 early, now Tue 10 Nov) vague twice → deadline = 12th business day = Mon 30 Nov (11 Nov and 26 Nov skipped; without them it would be Wed 25 Nov) → promise 420.00 on 2026-11-30.

## Self-verification (task 3)

Second pass: re-read Brief A, recomputed the ladders with separate code (`verify_cases.py`: its own `nth_biz`,
`attempt1`, "this/next weekday", rule 19/20/23 resolver, callback window check, outcome table, transfer queues,
"Brief A never uses add_note", mock data unchanged). Result: no ledger discrepancy.

Changed after the review:
- **EXT-A-42**: the script said "end of the month"; on 10 Nov that phrase lands on 30 Nov, which is also the deadline, so
  an agent that wrongly took it as a date would still pass. Changed to "in a couple of weeks" / "when my salary comes"
  so only the rule 21 path (ask once, then propose the deadline) gives 30 Nov. Expected ledger unchanged.

## What the fixed customers cannot test (Brief A)
- `create_promise` failing **twice** → `no_promise`/`service_error` (rule 37): the only fault is PUB-10's `fail_first_n: 1`.
- A day/month swap on a customer whose day > 12 (e.g. PUB-01's 14 March): the swapped form is not a date, so the
  service rejects it rather than hinting; only PUB-07 (5 Dec), PUB-09 (11 Aug) and the B customers PUB-11 (3 June) /
  PUB-13 (8 Jan) can produce the hint. EXT-A-09 uses PUB-07.
- The mock enforces no date rule, so cases 37-42 are only as good as the recomputed expectations above (the mock ledger
  records whatever date the agent sends).

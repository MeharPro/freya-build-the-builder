# Brief D extended cases: rationale (Kestrel Bank, after the memo)

Source: `tests/synthetic/brief-d.md`. [E] email of 6 Oct, [P] CP-7 section 4, [M] memo of 12 Oct (overrides P and the code list), [C] code list v3. Cases: `brief-d-extended.cases.json`, ids `EXT-D-01`..`EXT-D-30`. Every case reuses a fixed mock customer through `mock_case`; script, expected ledger and checks are ours.

## 0. Shared facts

### Memo values in force
- M1 Band S (11-45 days) latest date = **5th** business day after the call date (was 7th).
- M2 attempts: Band F **1**, Band S **2** (the "final-offer repeat" is withdrawn).
- M3 card floor = **2 x minimum_payment**, capped at past_due; loans = instalment_amount.
- M4 Founders' Day **Fri 2026-10-30** is a closure day; Mon 26 Oct is a normal business day.
- M5 hardship-declined code **HSHP** (not HARD), outcome `no_promise`.
- M6 callback window end **18:00** inclusive (start 09:00; today later than now or the next two business days).
- Band F latest date = 21 calendar days after the call date; if not a business day, the last business day before it [P4.1].
- Named Saturday/Sunday/closure day not after the latest date -> the nearest business day **before** it [P4.6].
- Vague period with no exact day -> the last business day of the current week (next business day if the call is on it), or the latest date if earlier [P4.6].
- "next/this <weekday>" and a bare weekday = the first such weekday after the call date [P4.7].
- Attempt 1 = amount in play on the next business day; attempt 2 (S) = the floor on the latest date [P4.8, M2].

Business days: Monday to Friday except 2026-10-30, 2026-11-20, 2026-12-24, 2026-12-25, 2026-12-28, 2026-12-31.

### Mock customers under Brief D

| mock | name | phone / DOB | products (id: type, past_due, days_late, band, floor) |
|---|---|---|---|
| PUB-01 | Mr Daniel Reyes | 4471 / 1988-03-14 | p1: card 4821, 420.00, 6, F, 2 x 126 = 252 |
| PUB-02 | Ms Maria Costa | 0358 / 1979-11-02 | p1: personal loan, 310.50, 11, S, 103.50 |
| PUB-03 | Mr Owen Park | 6630 / 1992-07-21 | p1: card 0377, 95.00, 4, F, 2 x 28.50 = 57 |
| PUB-04 | Ms Lena Hoffmann | 2219 / 1984-01-30 | p1: car loan, 1250.00, 14, S, 400 |
| PUB-05 | Mr Tomas Novak | 8846 / 1990-09-09 | p1: personal loan, 780.00, 21, S, 260 |
| PUB-06 | Ms Priya Nair | 1502 / 1986-05-17 | p1: card 1903, 2125.10, 12, S, 2 x 637.50 = 1275 |
| PUB-07 | Mr Samuel Ortiz | 7093 / 1975-12-05 | p1: personal loan, 540.00, 5, F, 180 |
| PUB-08 | Ms Hannah Schmidt | 3317 / 1993-04-28 | p1: card 5512, 180.00, 5, F, 2 x 54 = 108 |
| PUB-09 | Mr Victor Ionescu | 5560 / 1981-08-11 | p1: personal loan, 2100.00, 28, S, 700 |
| PUB-10 | Ms Grace Lin | 9904 / 1989-02-23 | p1: card 7740, 365.00, 8, F, 2 x 109.50 = 219; fault: first create_promise fails |
| PUB-11 | Ms Sofia Almeida | 2288 / 1987-06-03 | p1: card 2288, 220.00, 9, F, 132; p2: personal loan, 640.00, 9, F, 213; p3: car loan, 75.00, 3, F, 25 |
| PUB-12 | Mr Marcus Bell | 4410 / 1983-10-19 | p1: card 9015, 510.00, 16, S, 306; p2: personal loan, 1320.00, 16, S, 440; p3: car loan, 140.00, 7, F, 46 |
| PUB-13 | Ms Elena Rossi | 6604 / 1991-01-08 | p1: card 6604, 300.00, 4, F, 180; p2: personal loan, 900.00, 20, S, 300 |

No card floor reaches the cap (2 x minimum is below past_due for every mock card).

### Business-day ladders

**now = Wednesday 2026-10-14 11:00** (EXT-D-01..25)
Thu 15 = 1, Fri 16 = 2, Mon 19 = 3, Tue 20 = 4, **Wed 21 = 5 (S latest)**, Thu 22 = 6, Fri 23 = 7 (the old S latest), Mon 26 = 8, Tue 27 = 9, Wed 28 = 10, Thu 29 = 11, Fri 30 closed (Founders' Day), Mon 2 Nov = 12, Tue 3 = 13, Wed 4 = 14.
F latest: 14 Oct + 21 = **Wed 2026-11-04** (a business day). Attempt 1 = Thu 15. Last business day of the current week = Fri 16. Callback window: today 11:00-18:00, Thu 15, Fri 16, 09:00-18:00.

**now = Thursday 2026-10-29 11:00** (EXT-D-26)
Fri 30 closed, Sat 31/Sun 1 -, **Mon 2 Nov = 1**, Tue 3 = 2, Wed 4 = 3, Thu 5 = 4, Fri 6 = 5 (S latest). F latest: 29 Oct + 21 = Thu 2026-11-19. Attempt 1 = Mon 2026-11-02.

**now = Thursday 2026-11-19 11:00** (EXT-D-27)
Fri 20 closed (migration), Sat/Sun -, Mon 23 = 1, Tue 24 = 2, Wed 25 = 3, Thu 26 = 4, **Fri 27 = 5 (S latest)**. F latest: 19 Nov + 21 = Thu 2026-12-10. Nearest business day before Fri 20 Nov = Thu 19 Nov = today (valid: today or later).

**now = Friday 2026-10-16 17:30** (EXT-D-28)
Callback window: today later than 17:30 up to 18:00; Mon 19 and Tue 20, 09:00-18:00. A quarter to six = 17:45 today fits (it would not under the old 17:00 end).

**now = Wednesday 2026-12-23 11:00** (EXT-D-29)
Thu 24 closed, Fri 25 closed, Sat 26/Sun 27 -, Mon 28 closed, **Tue 29 = 1**, Wed 30 = 2, Thu 31 closed. Attempt 1 = Tue 2026-12-29. (F latest = 23 Dec + 21 = Wed 2027-01-13, and an S latest would need 2027's closure days, which the material does not give, so no case at this date depends on either.)

**now = Thursday 2026-12-03 11:00** (EXT-D-30)
3 Dec + 21 = **Thu 2026-12-24**, a closure day -> the last business day before it = **Wed 2026-12-23** (Band F latest). Fri 4 = 1, Mon 7 = 2, Tue 8 = 3, Wed 9 = 4, Thu 10 = 5 (S latest).

## 1. Per-case derivations

### Memo values
- **EXT-D-01** (PUB-09, S): "Friday the 23rd" = 2026-10-23 > S latest Wed 21 (M1; under CP-7 v6.2 the 7th business day would be 23 Oct and it would be accepted). [P4.6]: say the latest date is the last recordable day and offer it; accepted. 2100 on 2026-10-21, `promise` / `PRM`.
- **EXT-D-02** (PUB-01, F): "too much" -> floor once: 2 x 126 = 252 (M3; 126 under CP-7), with the remainder sentence; he takes it "tomorrow" = Thu 2026-10-15 (business day, <= F latest 4 Nov). `PRM`.
- **EXT-D-03** (PUB-04, third party): six this evening = 18:00 today: later than 11:00, <= 18:00 inclusive (M6). `schedule_callback 2026-10-14 18:00`, `not_reached` / `CBK`.
- **EXT-D-04** (PUB-07, F): "Friday the 30th" = Founders' Day (M4), not after F latest 4 Nov -> [P4.6] nearest business day BEFORE = Thu 2026-10-29. 540, `PRM`.

### Third party / opening
- **EXT-D-05** (PUB-03): "Who's asking?" is a question first: answer, ask again = second ask [E]; "What is this about?" does not confirm -> `not_reached` / `UNC`. Forbidden words not said while answering.
- **EXT-D-06** (PUB-06): wrong number -> `not_reached` / `WN`.
- **EXT-D-07** (PUB-09): deceased -> "Please accept my condolences.", nothing else -> `not_reached` / `DEC`.
- **EXT-D-08** (PUB-02): only next Wednesday (21 Oct): not today/15/16 -> outside. [E]: propose the nearest slot inside the window once; declined -> book nothing, `not_reached` / `NCB`.
- **EXT-D-28** (PUB-05, now Fri 17:30): 17:45 today -> `CBK`, callback 2026-10-16 17:45.

### Identity
- **EXT-D-09** (PUB-08): 3371 wrong (1), 3713 wrong (2) on the phone question -> the second wrong answer ends the check although the service reports one left [E]; app or branch; `not_verified` / `IDF`. DOB never asked.
- **EXT-D-10** (PUB-04): declines, explanation once, declines again -> `not_verified` / `IDD` [E, C12].
- **EXT-D-11** (PUB-10): 9940 wrong (1), 9904 passes; DOB "23 March 1989" = 1989-03-23, wrong (no swap hint: swapping gives month 23) = second wrong answer -> stop; `IDF`. The mock fault is on create_promise and is never reached.

### Persuasion and refusal notes
- **EXT-D-12** (PUB-03, F): flat refusal -> attempt 1: 95 on Thu 15 Oct; refused; F has one attempt (M2) -> stop. Note `refused` on p1 (text: 1 attempt, last offer 95.00 on 15 Oct). `no_promise` / `RF`.
- **EXT-D-13** (PUB-04, S): attempt 1: 1250 on Thu 15; attempt 2: floor 400 on Wed 21 (S latest); no attempt 3 (M2). Note `refused` (2 attempts, 400.00 on 21 Oct). `RF`.

### Dispute / paid
- **EXT-D-14** (PUB-06): "not mine" -> no argument, no promise, note `dispute`, `no_promise` / `DSP`; no transfer (Brief D does not transfer disputes).
- **EXT-D-15** (PUB-02): paid yesterday by bank transfer -> the fixed sentence, note `paid` (channel and day), every product noted paid -> `paid` / `AP`.

### Multi-product
- **EXT-D-16** (PUB-12; p1 S, p2 S, p3 F): all refused. p1: 510 on 15 Oct, then floor 306 (2 x 153) on 21 Oct; p2: 1320 on 15 Oct, then 440 on 21 Oct; p3: 140 on 15 Oct only. Refused notes on p1, p2, p3; most serious note = refused -> `no_promise` / `RF`. (Whether the "no" to "all of these today?" already spends attempt 1 per product is a known ambiguity in the brief; the customer refuses everything, so the ledger is the same.)
- **EXT-D-17** (PUB-13): card paid yesterday in the app -> note `paid` on p1; loan (S, latest 21 Oct) in full "tomorrow" = Thu 15 Oct -> promise p2 900. A promise was recorded and nothing was transferred -> `promise` / `PRM` [C].
- **EXT-D-18** (PUB-11, all F, latest 4 Nov): car loan disputed -> note `dispute` p3, the call continues [E]; card and personal loan in full "this Friday" = Fri 16 Oct (business day). One read-back, two create_promise. `PRM`, notes p3 dispute.
- **EXT-D-19** (PUB-12): off work sick = hardship: "I am sorry to hear that.", no attempt; support offered once and declined -> `hardship` note on every product (p1, p2, p3) -> `no_promise` / `HSHP` (M5).

### Transfer after a promise
- **EXT-D-20** (PUB-05, S): pays all 780 today (2026-10-14), recorded; then asks for lower instalments -> transfer `restructuring` [E]; a transfer freezes the ledger: the recorded promise stays, no notes; close with the transfer's code: `transferred` / `TRS` [C: "a transfer always closes with its transfer code ... even when a promise was recorded earlier"]. (Brief C closes the same situation as `promise`.)

### Dates
- **EXT-D-21** (PUB-08, F): "when I get paid" = vague; asked once; no exact day -> the last business day of the current week = Fri 2026-10-16 (call is on Wednesday), not after F latest. Full 180, `PRM`.
- **EXT-D-22** (PUB-02, S, latest 21 Oct): "Sunday the 18th" -> not a business day, not after the latest date -> nearest business day BEFORE = Fri 2026-10-16 (Brief C would move it forward to Monday). 310.50, `PRM`.
- **EXT-D-23** (PUB-07, F): "Monday the 12th" = 2026-10-12, before today -> cannot be recorded, ask for a day from today onwards (not a refusal). "Tuesday the 20th" = 2026-10-20, a business day <= 4 Nov. 540, `PRM`.
- **EXT-D-24** (PUB-04, S, latest Wed 21): "next Monday" said on Wednesday 14 = the first Monday after the call date = Mon 2026-10-19 [P4.7] (<= 21 Oct). Reading it as 26 Oct would hit the latest-date rule and give 21 Oct instead. 1250, `PRM`.

### Service error
- **EXT-D-25** (PUB-10, F): "too much" -> floor 2 x 109.50 = 219, accepted for "tomorrow" Thu 15 Oct. First create_promise fails (mock fault); retry (up to three tries in total) succeeds -> one promise 219 on 2026-10-15, no `service_error` note, `PRM`.

### Other call dates
- **EXT-D-26** (PUB-01, F, now Thu 29 Oct): bare "No, I can't" -> attempt 1 = next business day after the call date = Mon 2026-11-02 (30 Oct closed, then the weekend). 420, `PRM`.
- **EXT-D-27** (PUB-09, S, now Thu 19 Nov, S latest Fri 27 Nov): "tomorrow" = Fri 2026-11-20, a closure day not after the latest date -> nearest business day before = Thu 2026-11-19 = today (valid). 2100, `PRM`.
- **EXT-D-29** (PUB-03, F, now Wed 23 Dec): bare refusal -> attempt 1 = Tue 2026-12-29. 95, `PRM`.
- **EXT-D-30** (PUB-07, F, now Thu 3 Dec): F latest = 24 Dec (closed) -> Wed 23 Dec. "The 30th of December" is after it -> say the latest date is the last recordable day and offer Wed 2026-12-23; accepted. 540, `PRM`.

## 2. Expected ledger summary

| Case | mock | now | Outcome / code | Promises | Notes | Callback / transfer |
|---|---|---|---|---|---|---|
| EXT-D-01 | PUB-09 | 10-14 | promise / PRM | p1 2100.00 2026-10-21 | - | - |
| EXT-D-02 | PUB-01 | 10-14 | promise / PRM | p1 252.00 2026-10-15 | - | - |
| EXT-D-03 | PUB-04 | 10-14 | not_reached / CBK | - | - | cb 2026-10-14 18:00 |
| EXT-D-04 | PUB-07 | 10-14 | promise / PRM | p1 540.00 2026-10-29 | - | - |
| EXT-D-05 | PUB-03 | 10-14 | not_reached / UNC | - | - | - |
| EXT-D-06 | PUB-06 | 10-14 | not_reached / WN | - | - | - |
| EXT-D-07 | PUB-09 | 10-14 | not_reached / DEC | - | - | - |
| EXT-D-08 | PUB-02 | 10-14 | not_reached / NCB | - | - | - |
| EXT-D-09 | PUB-08 | 10-14 | not_verified / IDF | - | - | - |
| EXT-D-10 | PUB-04 | 10-14 | not_verified / IDD | - | - | - |
| EXT-D-11 | PUB-10 | 10-14 | not_verified / IDF | - | - | - |
| EXT-D-12 | PUB-03 | 10-14 | no_promise / RF | - | p1 refused | - |
| EXT-D-13 | PUB-04 | 10-14 | no_promise / RF | - | p1 refused | - |
| EXT-D-14 | PUB-06 | 10-14 | no_promise / DSP | - | p1 dispute | - |
| EXT-D-15 | PUB-02 | 10-14 | paid / AP | - | p1 paid | - |
| EXT-D-16 | PUB-12 | 10-14 | no_promise / RF | - | p1, p2, p3 refused | - |
| EXT-D-17 | PUB-13 | 10-14 | promise / PRM | p2 900.00 2026-10-15 | p1 paid | - |
| EXT-D-18 | PUB-11 | 10-14 | promise / PRM | p1 220.00, p2 640.00 2026-10-16 | p3 dispute | - |
| EXT-D-19 | PUB-12 | 10-14 | no_promise / HSHP | - | p1, p2, p3 hardship | - |
| EXT-D-20 | PUB-05 | 10-14 | transferred / TRS | p1 780.00 2026-10-14 | - | restructuring |
| EXT-D-21 | PUB-08 | 10-14 | promise / PRM | p1 180.00 2026-10-16 | - | - |
| EXT-D-22 | PUB-02 | 10-14 | promise / PRM | p1 310.50 2026-10-16 | - | - |
| EXT-D-23 | PUB-07 | 10-14 | promise / PRM | p1 540.00 2026-10-20 | - | - |
| EXT-D-24 | PUB-04 | 10-14 | promise / PRM | p1 1250.00 2026-10-19 | - | - |
| EXT-D-25 | PUB-10 | 10-14 | promise / PRM | p1 219.00 2026-10-15 (after 1 failed try) | - | - |
| EXT-D-26 | PUB-01 | 10-29 11:00 | promise / PRM | p1 420.00 2026-11-02 | - | - |
| EXT-D-27 | PUB-09 | 11-19 11:00 | promise / PRM | p1 2100.00 2026-11-19 | - | - |
| EXT-D-28 | PUB-05 | 10-16 17:30 | not_reached / CBK | - | - | cb 2026-10-16 17:45 |
| EXT-D-29 | PUB-03 | 12-23 11:00 | promise / PRM | p1 95.00 2026-12-29 | - | - |
| EXT-D-30 | PUB-07 | 12-03 11:00 | promise / PRM | p1 540.00 2026-12-23 | - | - |

## 3. Rules the fixed mock customers cannot test

- **SVC after three failed create_promise tries** (single product -> `no_promise` / `SVC`; multi-product -> `service_error` note on that product): the mock's only fault is PUB-10's single failure.
- **SVC during identity / get_account failing** (codes 9 and 10): no mock fault on those tools.
- **Card floor cap at past_due** (M3 "never more than the overdue amount"): every mock card has 2 x minimum below past_due.
- **"Over 45 days -> treat as Band S"**: no mock product is over 45 days late.
- **A refused transfer to restructuring**: Brief D transfers at once without asking, so there is no "no" branch to test.
- **Closure days in 2027**: CP-7 lists closures "for the remainder of 2026", so no case relies on a date after 2026-12-31.

## 4. Verification (separate pass, 10 Oct)

A separate reviewer re-read `brief-d.md` (the memo applies to every case, since all call dates are on or after 14 October), recomputed every ladder, latest date, floor and code with its own script without reading this file, and simulated every script. The same mechanical check as for Brief C was run. **All 30 expected ledgers were confirmed.** Notes:
- EXT-D-11 lists PUB-10's `create_promise` fault because the mock session carries it. The call ends IDF before any promise, so the fault never fires; `faults` is informative only.

Known ambiguity risks (the ledger is unaffected):
- EXT-D-16: a "No." to "all of these today?" may or may not spend attempt 1 on every product. The proposals and RF are the same either way; only the attempt counts written in the note texts could differ.
- EXT-D-05: the agent might answer "What is this about?" and ask a third time; the brief says close UNC after the second ask.
- EXT-D-08: "nearest slot" most naturally means Fri 16 Oct; the check accepts any slot inside the window.
- EXT-D-21: the brief does not say whether the vague-period fallback counts as an attempt; the customer accepts it.

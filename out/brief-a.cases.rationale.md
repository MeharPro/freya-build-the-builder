# Generated practice cases: rationale

Written by `builder/cases.py` (independent case-writer call, claude-opus-5-5; dates evaluated by freyalib CAL_HELPERS). The building agent reads only the cases file, never this rationale.

## Calendar

Business weekdays: Monday, Tuesday, Wednesday, Thursday, Friday. Holidays: 2026-10-26, 2026-11-11, 2026-11-26, 2026-12-25, 2027-01-01.


Business-day ladder from `now` = 2026-10-14T11:00:

```
2026-10-14 Wed today
2026-10-15 Thu +1
2026-10-16 Fri +2
2026-10-17 Sat -- not a business day
2026-10-18 Sun -- not a business day
2026-10-19 Mon +3
2026-10-20 Tue +4
2026-10-21 Wed +5
2026-10-22 Thu +6
2026-10-23 Fri +7
2026-10-24 Sat -- not a business day
2026-10-25 Sun -- not a business day
2026-10-26 Mon -- holiday
2026-10-27 Tue +8
2026-10-28 Wed +9
2026-10-29 Thu +10
2026-10-30 Fri +11
2026-10-31 Sat -- not a business day
2026-11-01 Sun -- not a business day
2026-11-02 Mon +12
2026-11-03 Tue +13
2026-11-04 Wed +14
```

Business-day ladder from `now` = 2026-10-16T10:00:

```
2026-10-16 Fri today
2026-10-17 Sat -- not a business day
2026-10-18 Sun -- not a business day
2026-10-19 Mon +1
2026-10-20 Tue +2
2026-10-21 Wed +3
2026-10-22 Thu +4
2026-10-23 Fri +5
2026-10-24 Sat -- not a business day
2026-10-25 Sun -- not a business day
2026-10-26 Mon -- holiday
2026-10-27 Tue +6
2026-10-28 Wed +7
2026-10-29 Thu +8
2026-10-30 Fri +9
2026-10-31 Sat -- not a business day
2026-11-01 Sun -- not a business day
2026-11-02 Mon +10
2026-11-03 Tue +11
2026-11-04 Wed +12
2026-11-05 Thu +13
2026-11-06 Fri +14
```

Business-day ladder from `now` = 2026-10-23T11:00:

```
2026-10-23 Fri today
2026-10-24 Sat -- not a business day
2026-10-25 Sun -- not a business day
2026-10-26 Mon -- holiday
2026-10-27 Tue +1
2026-10-28 Wed +2
2026-10-29 Thu +3
2026-10-30 Fri +4
2026-10-31 Sat -- not a business day
2026-11-01 Sun -- not a business day
2026-11-02 Mon +5
2026-11-03 Tue +6
2026-11-04 Wed +7
2026-11-05 Thu +8
2026-11-06 Fri +9
2026-11-07 Sat -- not a business day
2026-11-08 Sun -- not a business day
2026-11-09 Mon +10
2026-11-10 Tue +11
2026-11-11 Wed -- holiday
2026-11-12 Thu +12
2026-11-13 Fri +13
2026-11-14 Sat -- not a business day
2026-11-15 Sun -- not a business day
2026-11-16 Mon +14
```

## Outcome rows covered

- [x] `promise` / `-`
- [x] `paid` / `-`
- [x] `transferred` / `restructuring`
- [x] `transferred` / `human`
- [x] `transferred` / `support`
- [x] `no_promise` / `refused`
- [x] `no_promise` / `hardship`
- [x] `no_promise` / `dispute`
- [ ] NOT COVERED `no_promise` / `service_error`
- [x] `not_verified` / `failed`
- [x] `not_verified` / `declined`
- [x] `not_reached` / `callback`
- [x] `not_reached` / `no_callback`
- [x] `not_reached` / `wrong_number`
- [x] `not_reached` / `deceased`
- [x] `not_reached` / `unclear`

## Cases

### GEN-C-01 Question then 'Hello?' uses both asks: unclear (opening, PUB-01, now 2026-10-14T11:00, confidence high)

- Rules: R06, R07, R08, R09, R10, R56, R59
- Expected: `not_reached` / `unclear`; promises []; notes []; callbacks []; transfers []
- Derivation: R09/R10: 'Who is this?' is not a confirmation and is a question; the agent answers it, and the ask that follows is the second ask. 'Hello?' after the second ask is still unclear -> not_reached / unclear. No tool other than close_call.
- Evaluated: -
- Confidence: Rule 3 states explicitly that the ask after answering a question is the second ask and that 'hello' and 'who is this' are not confirmation.

### GEN-C-02 Husband offers to pay, callback at 19:00 today (window edge) (third_party, PUB-02, now 2026-10-14T11:00, confidence high)

- Rules: R07, R12, R13, R17, R63, R56, R59
- Expected: `not_reached` / `callback`; promises []; notes []; callbacks [{"date": "2026-10-14", "time": "19:00"}]; transfers []
- Derivation: R12/R17: relative gets nothing about the account despite offering to pay. R13: 19:00 today is inside 10:00-19:00 (both included) and later than now 11:00 -> schedule_callback(today, 19:00), not_reached / callback.
- Evaluated: callback date: today = 2026-10-14
- Confidence: Rule 6 includes 19:00 explicitly; the time offered is single and unambiguous.

### GEN-C-04 Stranger: wrong number (third_party, PUB-03, now 2026-10-14T11:00, confidence high)

- Rules: R07, R12, R15, R56, R59
- Expected: `not_reached` / `wrong_number`; promises []; notes []; callbacks []; transfers []
- Derivation: R15: the person says the number does not belong to the customer -> not_reached / wrong_number; nothing recorded.
- Evaluated: -
- Confidence: Rule 8 maps this statement directly.

### GEN-C-05 Relative reports death (third_party, PUB-04, now 2026-10-14T11:00, confidence high)

- Rules: R07, R16, R56, R59
- Expected: `not_reached` / `deceased`; promises []; notes []; callbacks []; transfers []
- Derivation: R16: customer reported dead -> 'I am sorry for your loss.', no questions, not_reached / deceased.
- Evaluated: -
- Confidence: Rule 9 fixes the sentence and outcome.

### GEN-C-06 Three wrong answers spread across both questions (identity, PUB-05, now 2026-10-14T11:00, confidence high)

- Rules: R18, R19, R20, R22, R07, R60, R56, R59
- Expected: `not_verified` / `failed`; promises []; notes []; callbacks []; transfers []
- Derivation: R20: wrong answers count in total across questions: DOB wrong (1), DOB right, phone 8864 wrong (2), phone 8486 wrong (3) -> check ends. R22: not_verified / failed.
- Evaluated: -
- Confidence: Rule 12 says three wrong answers in total whichever question; the persona's answers are fixed.

### GEN-C-07 Asks what the call is about twice instead of answering (identity, PUB-06, now 2026-10-14T11:00, confidence high)

- Rules: R07, R18, R23, R56, R59
- Expected: `not_verified` / `declined`; promises []; notes []; callbacks []; transfers []
- Derivation: R23: asking what the call is about counts as declining; first -> one explanation; second -> close not_verified / declined.
- Evaluated: -
- Confidence: Rule 15 states a second such question closes the call.

### GEN-C-08 Swapped day/month retry, then 'I already paid' (special, PUB-07, now 2026-10-14T11:00, confidence high)

- Rules: R19, R21, R18, R24, R25, R37, R49, R56, R59
- Expected: `paid` / `None`; promises []; notes []; callbacks []; transfers []
- Derivation: R19: numbers read day-month-year -> 1975-05-12, hint day_month_swapped; R21 retry with month in words -> 1975-12-05 passes, not a wrong answer. R49: already paid -> no promise, outcome paid (no reason).
- Evaluated: -
- Confidence: Rule 13 and the API hint fix the retry; rule 39 fixes the outcome.

### GEN-C-09 Card 'closed and paid off last year' is a dispute, not paid (special, PUB-08, now 2026-10-14T11:00, confidence high)

- Rules: R50, R49, R25, R56, R59
- Expected: `no_promise` / `dispute`; promises []; notes []; callbacks []; transfers []
- Derivation: R50: a claim that the product was closed or paid off in the past is a dispute; rule 39 covers only a payment of this past-due amount -> no_promise / dispute.
- Evaluated: -
- Confidence: Rule 40 explicitly classifies this claim as a dispute.

### GEN-C-10 Lower instalments request: restructuring transfer (special, PUB-09, now 2026-10-14T11:00, confidence high)

- Rules: R51, R43, R56, R59
- Expected: `transferred` / `restructuring`; promises []; notes []; callbacks []; transfers [{"queue": "restructuring"}]
- Derivation: R51: request for a new plan / lower instalments -> transfer_to_agent(restructuring), transferred / restructuring.
- Evaluated: -
- Confidence: Rule 41 maps directly.

### GEN-C-11 Human requested before verification, insists (special, PUB-01, now 2026-10-14T11:00, confidence medium)

- Rules: R52, R55, R07, R56, R59
- Expected: `transferred` / `human`; promises []; notes []; callbacks []; transfers [{"queue": "general"}]
- Derivation: R52/R55: rule 42 applies before verification; one offer to help, customer insists -> transfer general, transferred / human.
- Evaluated: -
- Confidence: Rule 45 says rule 42 applies before verification, but an agent might read the refusal to answer as declining (rule 15); the brief's explicit precedence favours the transfer.

### GEN-C-12 Job loss, accepts support transfer (hardship, PUB-02, now 2026-10-14T11:00, confidence high)

- Rules: R42, R37, R56, R59
- Expected: `transferred` / `support`; promises []; notes []; callbacks []; transfers [{"queue": "support"}]
- Derivation: R42 precedes R39: job loss -> sympathy, no attempt, offer support; accepted -> transfer support, transferred / support.
- Evaluated: -
- Confidence: Rule 32 explicitly takes precedence over rule 30.

### GEN-C-13 Illness, declines support: hardship (hardship, PUB-04, now 2026-10-14T11:00, confidence high)

- Rules: R42, R40, R56, R59
- Expected: `no_promise` / `hardship`; promises []; notes []; callbacks []; transfers []
- Derivation: R42: illness -> no persuasion, support offered and declined -> no_promise / hardship (not refused).
- Evaluated: -
- Confidence: Rule 32 fixes the decline outcome.

### GEN-P-01 Early band, full amount on 'this Saturday' moved to the next business day (promise_dates, PUB-01, now 2026-10-14T11:00, confidence high)

- Rules: R28, R29, R31, R37, R44, R48
- Expected: `promise` / `None`; promises [{"product_id": "p1", "amount": 420.0, "date": "2026-10-19"}]; notes []; callbacks []; transfers []
- Derivation: R31: 'this Saturday' on Wed 2026-10-14 = Saturday of the current week. R29: a weekend day not after the deadline (early band, 6 days late -> addbd(today,12)) -> next_bd. Amount: customer accepts the full past_due (R33).
- Evaluated: deadline p1: addbd(today, 12) = 2026-11-02; amount p1: product('p1')['past_due'] = 420; promise date p1: next_bd(weekday_in_week(today, 'Saturday')) = 2026-10-19
- Confidence: R29 and R31 fix the date and the customer agrees to the full amount; no choice is left.

### GEN-P-02 Friday call: full too much, floor accepted, 'next Monday' falls on a holiday (promise_dates, PUB-04, now 2026-10-23T11:00, confidence high)

- Rules: R26, R29, R31, R34, R35, R44
- Expected: `promise` / `None`; promises [{"product_id": "p1", "amount": 400.0, "date": "2026-10-27"}]; notes []; callbacks []; transfers []
- Derivation: R34/R35: car loan floor = instalment_amount (400), offered once after 'too much'. R31: 'next Monday' said on Fri 2026-10-23 = Monday of the following week = 2026-10-26, a holiday (R26). R29: not after the late-band deadline addbd(today,7), so next_bd -> Tuesday.
- Evaluated: deadline p1: addbd(today, 7) = 2026-11-04; amount p1: product('p1')['instalment_amount'] = 400; promise date p1: next_bd(weekday_in_week(today + days(7), 'Monday')) = 2026-10-27
- Confidence: R31 defines 'next Monday' literally and R29 moves the holiday; the floor is fixed by R34.

### GEN-P-03 Late band: date after the deadline, deadline refused, both attempts, attempt 2 accepted (persuasion, PUB-05, now 2026-10-14T11:00, confidence medium)

- Rules: R27, R32, R39, R40, R41, R44
- Expected: `promise` / `None`; promises [{"product_id": "p1", "amount": 260.0, "date": "2026-10-23"}]; notes []; callbacks []; transfers []
- Derivation: R27: 21 days late -> late band, deadline addbd(today,7), 2 attempts. R32: date after deadline -> offer deadline; refusal = flat refusal (R39). Attempt 1 (R40): full 780 on lastbd_of_week(today), refused. Attempt 2: floor 260 on deadline, accepted.
- Evaluated: script [[d('2026-11-13')]] = 2026-11-13; deadline p1: addbd(today, 7) = 2026-10-23; amount p1: product('p1')['instalment_amount'] = 260; promise date p1: addbd(today, 7) = 2026-10-23
- Confidence: R32/R39: reading that the refused deadline offer triggers attempt 1 rather than counting as attempt 1 itself; an agent could also consider floor-on-deadline a repeat of the refused deadline offer.

### GEN-P-04 Vague salary date then deadline proposed, amount below the floor then floor accepted (promise_amounts, PUB-02, now 2026-10-14T11:00, confidence high)

- Rules: R30, R34, R36, R38, R44
- Expected: `promise` / `None`; promises [{"product_id": "p1", "amount": 103.5, "date": "2026-10-23"}]; notes []; callbacks []; transfers []
- Derivation: R30: vague period -> ask once, no day given -> propose deadline addbd(today,7) (11 days late = late band). R36: 50 is below floor (instalment_amount 103.5) -> offer floor once, accepted.
- Evaluated: deadline p1: addbd(today, 7) = 2026-10-23; amount p1: product('p1')['instalment_amount'] = 103.50; promise date p1: addbd(today, 7) = 2026-10-23
- Confidence: R30 and R36 fix the date and amount; the customer accepts each proposal.

### GEN-P-05 Friday call: flat refusal, attempt 1 on last business day of next week accepted (persuasion, PUB-08, now 2026-10-16T10:00, confidence high)

- Rules: R39, R40, R44, R48
- Expected: `promise` / `None`; promises [{"product_id": "p1", "amount": 180.0, "date": "2026-10-23"}]; notes []; callbacks []; transfers []
- Derivation: R39: a no with no date or amount = flat refusal -> attempt 1. R40: today (Fri 2026-10-16) is the last business day of this week -> last business day of next week. Amount = full past_due (180).
- Evaluated: deadline p1: addbd(today, 12) = 2026-11-04; amount p1: product('p1')['past_due'] = 180; promise date p1: lastbd_of_week(today + days(7)) = 2026-10-23
- Confidence: R40 states the Friday exception explicitly; the customer accepts.

### GEN-P-06 Early band: full too much, floor refused, single attempt at the floor refused (persuasion, PUB-03, now 2026-10-14T11:00, confidence high)

- Rules: R27, R35, R39, R40, R41
- Expected: `no_promise` / `refused`; promises []; notes []; callbacks []; transfers []
- Derivation: R27: 4 days late -> early band, 1 attempt. R35: floor (minimum_payment 28.5) offered once, refused -> flat refusal. R40: attempt 1 at the floor (full already too much) on lastbd_of_week(today), refused. R41: attempts used up -> no_promise/refused.
- Evaluated: deadline p1: addbd(today, 12) = 2026-11-02
- Confidence: Customer refuses everything, so the ledger is no_promise/refused under R41 whatever the attempt wording.

### GEN-P-07 Read-back correction moves the date to a holiday inside the deadline (confirmation, PUB-07, now 2026-10-14T11:00, confidence high)

- Rules: R26, R29, R44, R45
- Expected: `promise` / `None`; promises [{"product_id": "p1", "amount": 540.0, "date": "2026-10-27"}]; notes []; callbacks []; transfers []
- Derivation: R45: change at read-back re-checked under section 7. 2026-10-26 is a holiday (R26) and before the early-band deadline addbd(today,12) (5 days late) -> R29 next_bd. Amount unchanged = past_due 540.
- Evaluated: script [[d('2026-10-26')]] = 2026-10-26; deadline p1: addbd(today, 12) = 2026-11-02; amount p1: product('p1')['past_due'] = 540; promise date p1: next_bd(d('2026-10-26')) = 2026-10-27
- Confidence: R45 and R29 fix the new date; exactly one promise is recorded after the second yes.

### GEN-X-01 Wife offers Saturday, then 21:00 tonight: both outside the callback window (third_party, PUB-03, now 2026-10-14T11:00, confidence high)

- Rules: R12, R13, R14, R17, R56, R59
- Expected: `not_reached` / `no_callback`; promises []; notes []; callbacks []; transfers []
- Derivation: R13: window is today (Wed 2026-10-14) or next_bd_after(today) (Thu 2026-10-15), 10:00-19:00, later than 11:00. Saturday is neither -> outside. R14: one retry; 21:00 today is after 19:00 -> outside again; no schedule, not_reached / no_callback.
- Evaluated: -
- Confidence: Rules 6 and 7 fix the window and the single retry; neither offered slot can fall inside it.

## Valid but trimmed (cap of 20 cases)

- GEN-C-14 Verified customer twice does not want to talk
- GEN-C-15 Robot and scam questions, then promise with one failed create_promise
- GEN-P-08 create_promise fails once, retry succeeds
- GEN-P-09 Job loss, support declined, customer still names the floor this Friday
- GEN-C-03 Friday call: holiday Monday then 08:00 next business day, both outside


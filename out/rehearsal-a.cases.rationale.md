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

Business-day ladder from `now` = 2026-10-21T11:00:

```
2026-10-21 Wed today
2026-10-22 Thu +1
2026-10-23 Fri +2
2026-10-24 Sat -- not a business day
2026-10-25 Sun -- not a business day
2026-10-26 Mon -- holiday
2026-10-27 Tue +3
2026-10-28 Wed +4
2026-10-29 Thu +5
2026-10-30 Fri +6
2026-10-31 Sat -- not a business day
2026-11-01 Sun -- not a business day
2026-11-02 Mon +7
2026-11-03 Tue +8
2026-11-04 Wed +9
2026-11-05 Thu +10
2026-11-06 Fri +11
2026-11-07 Sat -- not a business day
2026-11-08 Sun -- not a business day
2026-11-09 Mon +12
2026-11-10 Tue +13
2026-11-11 Wed -- holiday
2026-11-12 Thu +14
```

Business-day ladder from `now` = 2026-10-23T18:00:

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

Business-day ladder from `now` = 2026-12-18T11:00:

```
2026-12-18 Fri today
2026-12-19 Sat -- not a business day
2026-12-20 Sun -- not a business day
2026-12-21 Mon +1
2026-12-22 Tue +2
2026-12-23 Wed +3
2026-12-24 Thu +4
2026-12-25 Fri -- holiday
2026-12-26 Sat -- not a business day
2026-12-27 Sun -- not a business day
2026-12-28 Mon +5
2026-12-29 Tue +6
2026-12-30 Wed +7
2026-12-31 Thu +8
2027-01-01 Fri -- holiday
2027-01-02 Sat -- not a business day
2027-01-03 Sun -- not a business day
2027-01-04 Mon +9
2027-01-05 Tue +10
2027-01-06 Wed +11
2027-01-07 Thu +12
2027-01-08 Fri +13
2027-01-09 Sat -- not a business day
2027-01-10 Sun -- not a business day
2027-01-11 Mon +14
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

### GEN-C-01 Who-is-this question then 'go ahead': unclear after the second ask (opening, PUB-01, now 2026-10-14T11:00, confidence high)

- Rules: rule 1, rule 2, rule 3
- Expected: `not_reached` / `unclear`; promises []; notes []; callbacks []; transfers []
- Derivation: Rule 3: 'who is this' and 'go ahead' are not confirmation; the agent answers the question first and the following ask is the second ask; still unclear -> not_reached / unclear. Nothing recorded.
- Evaluated: -
- Confidence: Rule 3 explicitly says the ask after answering the question is the second ask.

### GEN-C-02 Relative on Friday evening: Monday holiday refused, Tuesday 10:00 booked (third_party, PUB-02, now 2026-10-23T18:00, confidence high)

- Rules: rule 5, rule 6, rule 7, section 7 calendar
- Expected: `not_reached` / `callback`; promises []; notes []; callbacks [{"date": "2026-10-27", "time": "10:00"}]; transfers []
- Derivation: Rule 6: callback today or next business day, 10:00-19:00. Today is Friday 23 Oct; Monday 26 Oct is a holiday, so the next business day is addbd(today,1) = Tuesday. Monday is outside -> rule 7 one re-ask; Tuesday 10:00 is inside -> callback, not_reached / callback.
- Evaluated: callback date: addbd(today, 1) = 2026-10-27
- Confidence: Holiday list and window both included; the relative's second slot is unambiguous.

### GEN-C-03 Wife offers to pay, then two slots outside the window: no callback (third_party, PUB-05, now 2026-10-14T11:00, confidence high)

- Rules: rule 5, rule 6, rule 7, rule 10
- Expected: `not_reached` / `no_callback`; promises []; notes []; callbacks []; transfers []
- Derivation: Rules 5 and 10: say nothing, accept no payment from a relative. 20:00 today is after 19:00; re-ask once (rule 7); 09:00 tomorrow is before 10:00 -> no schedule, not_reached / no_callback.
- Evaluated: -
- Confidence: Both slots are clearly outside 10:00-19:00.

### GEN-C-04 Stranger: wrong number (third_party, PUB-03, now 2026-10-14T11:00, confidence high)

- Rules: rule 1, rule 8
- Expected: `not_reached` / `wrong_number`; promises []; notes []; callbacks []; transfers []
- Derivation: Rule 8: number does not belong to the customer -> not_reached / wrong_number. Nothing recorded.
- Evaluated: -
- Confidence: Direct rule 8 trigger.

### GEN-C-05 Son reports the customer died (third_party, PUB-09, now 2026-10-14T11:00, confidence high)

- Rules: rule 9
- Expected: `not_reached` / `deceased`; promises []; notes []; callbacks []; transfers []
- Derivation: Rule 9: customer has died -> sympathy sentence, ask nothing else, not_reached / deceased.
- Evaluated: -
- Confidence: Rule 9 is explicit.

### GEN-C-06 Three wrong answers spread over both questions (identity, PUB-04, now 2026-10-14T11:00, confidence high)

- Rules: rule 11, rule 12, rule 14
- Expected: `not_verified` / `failed`; promises []; notes []; callbacks []; transfers []
- Derivation: Rule 12: three wrong answers in total across questions end the check: DOB wrong (1), DOB right, phone 2291 (2), phone 2290 (3). Rule 14 -> not_verified / failed.
- Evaluated: -
- Confidence: Counter is total across questions per rule 12; 31 January is not a day/month swap.

### GEN-C-07 Two deflections instead of the date of birth: declined (identity, PUB-06, now 2026-10-14T11:00, confidence high)

- Rules: rule 15, rule 1
- Expected: `not_verified` / `declined`; promises []; notes []; callbacks []; transfers []
- Derivation: Rule 15: asking what the call is about instead of answering counts as declining; explain once; the second such question closes -> not_verified / declined.
- Evaluated: -
- Confidence: Rule 15 names this exact deflection.

### GEN-C-08 Numeric date with day and month swapped, then 'I already paid' (identity_then_topic, PUB-02, now 2026-10-14T11:00, confidence high)

- Rules: rule 11, rule 13, rule 16, rule 17, rule 39
- Expected: `paid` / `None`; promises []; notes []; callbacks []; transfers []
- Derivation: Rule 11: numbers read day-month-year -> 1979-02-11; hint day_month_swapped -> rule 13 retry, not a wrong answer; verified. Rule 39: already paid -> no promise, close paid (no reason).
- Evaluated: -
- Confidence: Rules 11, 13 and 39 fix every step; the mock returns the swap hint.

### GEN-C-09 Scam question at the opening, then 'card closed and paid off years ago' is a dispute (topic, PUB-06, now 2026-10-14T11:00, confidence high)

- Rules: rule 43, rule 3, rule 40, rule 39
- Expected: `no_promise` / `dispute`; promises []; notes []; callbacks []; transfers []
- Derivation: Rule 43 then continue; rule 3 'yes' after the answer confirms. Rule 40: a product closed or paid off in the past is a dispute, not rule 39 -> no_promise / dispute.
- Evaluated: -
- Confidence: Rule 40 explicitly classifies a past pay-off claim as a dispute.

### GEN-C-11 Insists on a human before identity is verified (topic, PUB-03, now 2026-10-14T11:00, confidence high)

- Rules: rule 42, rule 45, rule 15
- Expected: `transferred` / `human`; promises []; notes []; callbacks []; transfers [{"queue": "general"}]
- Derivation: Rule 42 applies before verification (rule 45 last sentence): ask once, customer insists -> transfer general, transferred / human.
- Evaluated: -
- Confidence: Rule 45 states rule 42 applies before verification.

### GEN-C-12 Job loss, support accepted (hardship, PUB-07, now 2026-10-14T11:00, confidence high)

- Rules: rule 32, rule 28
- Expected: `transferred` / `support`; promises []; notes []; callbacks []; transfers [{"queue": "support"}]
- Derivation: Rule 32 before rule 30: job loss -> sympathy, no attempt, offer support; accepted -> transfer support, transferred / support.
- Evaluated: -
- Confidence: Rule 32 states its precedence over rule 30.

### GEN-C-13 Illness, support declined: hardship without persuasion (hardship, PUB-08, now 2026-10-14T11:00, confidence high)

- Rules: rule 32, rule 30
- Expected: `no_promise` / `hardship`; promises []; notes []; callbacks []; transfers []
- Derivation: Rule 32: illness -> no persuasion attempt (overrides rule 30 flat refusal); support declined -> no_promise / hardship.
- Evaluated: -
- Confidence: Rule 32 fixes both the precedence and the ending.

### GEN-P-01 'This Saturday' moves to the next business day, then a restructuring transfer after the recorded promise (promise_date, PUB-01, now 2026-10-14T11:00, confidence high)

- Rules: rule 20, rule 22, rule 34, rule 38, rule 41, section 12 table
- Expected: `transferred` / `restructuring`; promises [{"product_id": "p1", "amount": 420.0, "date": "2026-10-19"}]; notes []; callbacks []; transfers [{"queue": "restructuring"}]
- Derivation: Rule 22: 'this Saturday' = the Saturday of the current week; rule 20: a weekend day not after the deadline (addbd(today,12), early band 6 days late) -> next_bd. Amount: full past_due 420 (rule 24). Rules 41 + section 12 note: a transfer after a recorded promise closes as transferred/restructuring, and the promise stays in the ledger.
- Evaluated: deadline p1: addbd(today, 12) = 2026-11-02; amount p1: product('p1')['past_due'] = 420; promise date p1: next_bd(weekday_in_week(today, 'Saturday')) = 2026-10-19
- Confidence: Rules 20, 22 and the note under the closing table fix the date, the amount and the outcome; the customer accepts every proposal.

### GEN-P-02 Full amount too much, floor accepted, holiday named inside a deadline window that the holiday stretches (promise_date_amount, PUB-04, now 2026-10-21T11:00, confidence high)

- Rules: rule 18, rule 19, rule 20, rule 25, rule 26, rule 29, rule 34
- Expected: `promise` / `None`; promises [{"product_id": "p1", "amount": 400.0, "date": "2026-10-27"}]; notes []; callbacks []; transfers []
- Derivation: 14 days late -> late band, deadline addbd(today,7) (rule 18), which skips the 26 October holiday. Rule 26: full too much -> floor = instalment_amount (car loan, rule 25). Rule 20: holiday not after the deadline -> next_bd(2026-10-26) = 27 October, within the deadline.
- Evaluated: script [[d('2026-10-26')]] = 2026-10-26; deadline p1: addbd(today, 7) = 2026-11-02; amount p1: product('p1')['instalment_amount'] = 400; promise date p1: next_bd(d('2026-10-26')) = 2026-10-27
- Confidence: The floor, the holiday shift and the deadline all follow directly from rules 18, 20, 25 and 26.

### GEN-P-03 Read-back change to a Saturday that is after the late-band deadline (readback_change, PUB-06, now 2026-10-14T11:00, confidence high)

- Rules: rule 18, rule 20, rule 23, rule 34, rule 35
- Expected: `promise` / `None`; promises [{"product_id": "p1", "amount": 2125.1, "date": "2026-10-23"}]; notes []; callbacks []; transfers []
- Derivation: 12 days late -> late band, deadline addbd(today,7) (rule 18). Rule 35: a change at the read-back is checked again. 24 October is a Saturday after the deadline, so rule 23 applies (rule 20 last sentence): offer the deadline. Amount stays at the full past_due of 2125.1.
- Evaluated: script [[d('2026-10-24')]] = 2026-10-24; deadline p1: addbd(today, 7) = 2026-10-23; amount p1: product('p1')['past_due'] = 2125.10; promise date p1: addbd(today, 7) = 2026-10-23
- Confidence: Rules 20 and 23 both lead to the deadline date; the customer accepts it.

### GEN-P-04 Vague 'when my salary comes', still no exact day: propose the early-band deadline (promise_date, PUB-07, now 2026-10-14T11:00, confidence medium)

- Rules: rule 18, rule 21, rule 29, rule 34
- Expected: `promise` / `None`; promises [{"product_id": "p1", "amount": 540.0, "date": "2026-11-02"}]; notes []; callbacks []; transfers []
- Derivation: 5 days late -> early band, deadline addbd(today,12), counting past the 26 October holiday (rule 18). Rule 29: a vague period is not a refusal; rule 21: ask once, still none -> propose the deadline. Amount: full past_due 540 (rule 24).
- Evaluated: deadline p1: addbd(today, 12) = 2026-11-02; amount p1: product('p1')['past_due'] = 540; promise date p1: addbd(today, 12) = 2026-11-02
- Confidence: Rule 21 fixes the deadline, but an agent could read 'not today' as a flat refusal under rule 30 and propose Friday; rule 29 says a date answer is never a refusal.

### GEN-P-05 Amount below the floor and 'next Friday' (following calendar week) (promise_amount_date, PUB-08, now 2026-10-14T11:00, confidence high)

- Rules: rule 22, rule 24, rule 25, rule 27, rule 29, rule 34
- Expected: `promise` / `None`; promises [{"product_id": "p1", "amount": 54.0, "date": "2026-10-23"}]; notes []; callbacks []; transfers []
- Derivation: Rule 27: 30 is below the floor (minimum_payment 54 for a credit card, rule 25) -> say it cannot be recorded and offer the floor once; accepted. Rule 22: 'next Friday' on Wednesday 14 October = the Friday of the following week = 23 October, within the deadline addbd(today,12) (early band, 5 days late).
- Evaluated: deadline p1: addbd(today, 12) = 2026-11-02; amount p1: product('p1')['minimum_payment'] = 54; promise date p1: weekday_in_week(today + days(7), 'Friday') = 2026-10-23
- Confidence: Rule 22 defines 'next' explicitly and rule 27 fixes the floor; the customer accepts.

### GEN-P-06 Late band, flat refusal of every attempt: two attempts then stop (persuasion, PUB-05, now 2026-10-14T11:00, confidence high)

- Rules: rule 18, rule 28, rule 30, rule 31
- Expected: `no_promise` / `refused`; promises []; notes []; callbacks []; transfers []
- Derivation: 21 days late -> late band, 2 attempts, deadline addbd(today,7) (rule 18). Rule 30: 'No' to today = flat refusal -> attempt 1 = full past_due on lastbd_of_week(today); attempt 2 = floor (instalment_amount) on the deadline. Rule 31: attempts used up -> no_promise/refused.
- Evaluated: deadline p1: addbd(today, 7) = 2026-10-23
- Confidence: Rules 30 and 31 fix both attempts and the close; the customer refuses everything.

### GEN-P-07 Friday call, early band attempt 1 = last business day of next week, which a holiday pulls back to Thursday (persuasion_calendar, PUB-03, now 2026-12-18T11:00, confidence high)

- Rules: rule 18, rule 28, rule 30, rule 34, rule 38
- Expected: `promise` / `None`; promises [{"product_id": "p1", "amount": 95.0, "date": "2026-12-24"}]; notes []; callbacks []; transfers []
- Derivation: 4 days late -> early band, 1 attempt, deadline addbd(today,12) (rule 18). Rule 30: flat refusal -> attempt 1, full amount on the last business day of this week; today (Friday 18 Dec) is that day, so the last business day of next week, lastbd_of_week(today+7) = 24 Dec because 25 Dec is a holiday.
- Evaluated: deadline p1: addbd(today, 12) = 2027-01-07; amount p1: product('p1')['past_due'] = 95; promise date p1: lastbd_of_week(today + days(7)) = 2026-12-24
- Confidence: Rule 30 covers the 'today is that day' case explicitly; the holiday calendar fixes Thursday 24 December.

### GEN-P-08 create_promise fails once, retry succeeds (service_fault, PUB-10, now 2026-10-14T11:00, confidence high)

- Rules: rule 28, rule 34, rule 37, rule 38
- Expected: `promise` / `None`; promises [{"product_id": "p1", "amount": 365.0, "date": "2026-10-14"}]; notes []; callbacks []; transfers []
- Derivation: 8 days late -> late band, deadline addbd(today,7); today is a valid promise date (rule 19). Full past_due 365 accepted for today. Rule 37: first create_promise fails -> try once more; the mock's second call succeeds -> promise recorded, outcome promise.
- Evaluated: deadline p1: addbd(today, 7) = 2026-10-23; amount p1: product('p1')['past_due'] = 365; promise date p1: today = 2026-10-14
- Confidence: Rule 37 says to retry once; the fault fails only the first call.

## Valid but trimmed (cap of 20 cases)

- GEN-C-10 Robot question, then a request for lower instalments: restructuring
- GEN-C-14 Says twice after verification that he does not want to talk
- GEN-C-15 First create_promise fails, one retry succeeds
- GEN-P-09 Job loss, support declined, customer still names the floor on a valid date


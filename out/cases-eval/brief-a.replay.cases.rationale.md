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

Business-day ladder from `now` = 2026-10-14T18:30:

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

Business-day ladder from `now` = 2026-10-16T11:00:

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

Business-day ladder from `now` = 2026-11-10T11:00:

```
2026-11-10 Tue today
2026-11-11 Wed -- holiday
2026-11-12 Thu +1
2026-11-13 Fri +2
2026-11-14 Sat -- not a business day
2026-11-15 Sun -- not a business day
2026-11-16 Mon +3
2026-11-17 Tue +4
2026-11-18 Wed +5
2026-11-19 Thu +6
2026-11-20 Fri +7
2026-11-21 Sat -- not a business day
2026-11-22 Sun -- not a business day
2026-11-23 Mon +8
2026-11-24 Tue +9
2026-11-25 Wed +10
2026-11-26 Thu -- holiday
2026-11-27 Fri +11
2026-11-28 Sat -- not a business day
2026-11-29 Sun -- not a business day
2026-11-30 Mon +12
2026-12-01 Tue +13
2026-12-02 Wed +14
```

## Cases

### EXT-A-01 Unclear answers to the identity question twice (opening, PUB-01, now 2026-10-14T11:00, confidence low)

- Rules: R09, R10, R07, R56
- Expected: `not_reached` / `unclear`; promises []; notes []; callbacks []; transfers []
- Derivation: R09: 'Hello' and 'go ahead' are not confirmation. R10: still unclear after the second ask -> not_reached/unclear.
- Evaluated: -
- Confidence: R09: 'Yeah' in 'Yeah, go ahead' can reasonably be read as a 'yes', which would count as confirmation.

### EXT-A-02 Asks if it is a robot, then confirms and pays today (opening, PUB-03, now 2026-10-14T11:00, confidence high)

- Rules: R11, R09, R10, R18, R27, R37, R44, R48
- Expected: `promise` / `None`; promises [{"product_id": "p1", "amount": 95.0, "date": "2026-10-14"}]; notes []; callbacks []; transfers []
- Derivation: R11/R10: answer the robot question, then ask again; 'Yes, that's me' confirms. R27: 4 days late -> early band, deadline addbd(today,12). R37/R44: full past_due 95 today, confirmed -> promise.
- Evaluated: deadline p1: addbd(today, 12) = 2026-11-02; amount p1: product('p1')['past_due'] = 95; promise date p1: today = 2026-10-14
- Confidence: R09/R37: a clear confirmation and the full amount today fix every value.

### EXT-A-03 Asks if it is a scam, then pays on a later day (special_questions, PUB-08, now 2026-10-14T11:00, confidence high)

- Rules: R09, R10, R53, R07, R27, R28, R38, R44, R47, R48
- Expected: `promise` / `None`; promises [{"product_id": "p1", "amount": 180.0, "date": "2026-10-22"}]; notes []; callbacks []; transfers []
- Derivation: R53/R10: answer the scam question, then the second ask gets 'yes'. R27: 5 days late = early band, deadline addbd(today,12) = 2 Nov. R38/R28: 22 Oct is a business day within the deadline, full past_due 180 accepted. Promise recorded -> promise.
- Evaluated: deadline p1: addbd(today, 12) = 2026-11-02; amount p1: product('p1')['past_due'] = 180; promise date p1: d('2026-10-22') = 2026-10-22
- Confidence: R28/R38 fix the date and amount the customer gives; 22 Oct is clearly a business day inside the deadline.

### EXT-A-04 Sister answers, callback later today (third_party, PUB-02, now 2026-10-14T11:00, confidence high)

- Rules: R07, R12, R13, R17, R63
- Expected: `not_reached` / `callback`; promises []; notes []; callbacks [{"date": "2026-10-14", "time": "16:00"}]; transfers []
- Derivation: R12: say nothing beyond the opening, ask when Maria can be reached. R13: today 16:00 falls in 10:00-19:00 and is after 11:00 -> schedule_callback(today, 16:00), close not_reached/callback.
- Evaluated: callback date: today = 2026-10-14
- Confidence: R13 window clearly contains today 16:00.

### EXT-A-05 Only times outside the callback window (third_party, PUB-02, now 2026-10-14T11:00, confidence high)

- Rules: R12, R13, R14
- Expected: `not_reached` / `no_callback`; promises []; notes []; callbacks []; transfers []
- Derivation: R13: 21:00 is after 19:00, outside the window. R14: ask once more; Saturday is neither today nor the next business day (Thursday), so outside too. No callback, close not_reached/no_callback.
- Evaluated: -
- Confidence: R14 fixes the one retry and the result; both offers are clearly outside.

### EXT-A-06 Wrong number (third_party, PUB-02, now 2026-10-14T11:00, confidence high)

- Rules: R15, R07
- Expected: `not_reached` / `wrong_number`; promises []; notes []; callbacks []; transfers []
- Derivation: R15: the person says the number is not the customer's -> close not_reached/wrong_number.
- Evaluated: -
- Confidence: R15 maps directly.

### EXT-A-07 The customer has died (third_party, PUB-05, now 2026-10-14T11:00, confidence high)

- Rules: R16, R07
- Expected: `not_reached` / `deceased`; promises []; notes []; callbacks []; transfers []
- Derivation: R16: the customer has died -> say the condolence sentence, ask nothing else, close not_reached/deceased.
- Evaluated: -
- Confidence: R16 maps directly.

### EXT-A-08 Husband offers to pay, then gives 7 pm tomorrow (third_party, PUB-06, now 2026-10-14T11:00, confidence high)

- Rules: R07, R12, R13, R17, R63
- Expected: `not_reached` / `callback`; promises []; notes []; callbacks [{"date": "2026-10-15", "time": "19:00"}]; transfers []
- Derivation: R12/R17: tell the relative nothing, even when he offers to pay. R13: tomorrow (Thursday) is the next business day and 19:00 is included in the window -> schedule_callback(next_bd_after(today), 19:00), close not_reached/callback.
- Evaluated: callback date: next_bd_after(today) = 2026-10-15
- Confidence: R13 says both ends are included, so 19:00 the next business day is valid.

### EXT-A-09 Gives the date of birth month first, then says the month as a word (identity, PUB-07, now 2026-10-14T11:00, confidence high)

- Rules: R19, R21, R18, R24, R37, R44, R48
- Expected: `promise` / `None`; promises [{"product_id": "p1", "amount": 540.0, "date": "2026-10-14"}]; notes []; callbacks []; transfers []
- Derivation: R19: numbers read as day/month/year -> 1975-05-12 -> hint day_month_swapped. R21: ask for the month as a word, which does not count as wrong -> 1975-12-05 passes. Phone passes. R37: he pays full past_due 540 today, early band within deadline -> promise.
- Evaluated: deadline p1: addbd(today, 12) = 2026-11-02; amount p1: product('p1')['past_due'] = 540; promise date p1: today = 2026-10-14
- Confidence: R19 and R21 fix the conversion and the retry, and the payment is full and today.

### EXT-A-10 One wrong phone answer, then right (identity, PUB-04, now 2026-10-14T11:00, confidence high)

- Rules: R20, R27, R28, R38, R44, R48
- Expected: `promise` / `None`; promises [{"product_id": "p1", "amount": 1250.0, "date": "2026-10-21"}]; notes []; callbacks []; transfers []
- Derivation: R20: one wrong answer, re-asked, then 2219 passes. R27: 14 days late = late band, deadline addbd(today,7) = 23 Oct. R28/R38: 21 Oct is a business day within the deadline, full 1250 -> promise.
- Evaluated: deadline p1: addbd(today, 7) = 2026-10-23; amount p1: product('p1')['past_due'] = 1250; promise date p1: d('2026-10-21') = 2026-10-21
- Confidence: The date is within the deadline and the amount is the full past-due amount.

### EXT-A-11 Refuses once, hears why, then answers (identity, PUB-01, now 2026-10-14T11:00, confidence high)

- Rules: R23, R18, R27, R28, R38, R44, R48
- Expected: `promise` / `None`; promises [{"product_id": "p1", "amount": 420.0, "date": "2026-10-15"}]; notes []; callbacks []; transfers []
- Derivation: R23: explain once; he then answers, so the check passes. R27: 6 days late = early, deadline addbd(today,12). R38/R28: tomorrow (Thursday) is a business day within the deadline, full 420 -> promise.
- Evaluated: deadline p1: addbd(today, 12) = 2026-11-02; amount p1: product('p1')['past_due'] = 420; promise date p1: today + days(1) = 2026-10-15
- Confidence: R23 allows one explanation; the date and amount are given by the customer.

### EXT-A-12 Refuses the security questions twice (identity, PUB-03, now 2026-10-14T11:00, confidence high)

- Rules: R23, R07, R24
- Expected: `not_verified` / `declined`; promises []; notes []; callbacks []; transfers []
- Derivation: R23: first refusal -> one explanation; second refusal -> close not_verified/declined.
- Evaluated: -
- Confidence: R23 maps directly.

### EXT-A-13 Asks what the call is about instead of answering, twice (identity, PUB-08, now 2026-10-14T11:00, confidence high)

- Rules: R23, R07
- Expected: `not_verified` / `declined`; promises []; notes []; callbacks []; transfers []
- Derivation: R23: asking what the call is about instead of answering counts as declining; after one explanation, the second such question closes the call as not_verified/declined.
- Evaluated: -
- Confidence: R23 explicitly covers a second such question.

### EXT-A-14 Three wrong answers split across both questions (identity, PUB-06, now 2026-10-14T11:00, confidence high)

- Rules: R20, R22, R18, R24
- Expected: `not_verified` / `failed`; promises []; notes []; callbacks []; transfers []
- Derivation: R20: wrong DOB (1), correct DOB, wrong phone 1520 (2), wrong phone 1205 (3) = three wrong answers in total, so the check ends. R22: no debt stated, point to the app or a branch, close not_verified/failed.
- Evaluated: -
- Confidence: R20 counts wrong answers in total across both questions.

### EXT-A-15 Proposes an amount between the floor and the full amount (amounts, PUB-01, now 2026-10-14T11:00, confidence high)

- Rules: R24, R25, R33, R34, R36, R37, R38, R44, R47, R48, R56, R59
- Expected: `promise` / `None`; promises [{"product_id": "p1", "amount": 200.0, "date": "2026-10-14"}]; notes []; callbacks []; transfers []
- Derivation: R36: 200 is between floor minimum_payment 126 and past_due 420, so it is accepted. The date is today, which is a business day within the early deadline addbd(today,12) (R27/R28). R44/R47: the promise is recorded after confirmation, so the outcome is promise.
- Evaluated: deadline p1: addbd(today, 12) = 2026-11-02; amount p1: 200 = 200; promise date p1: today = 2026-10-14
- Confidence: R36 sets the accepted range with both ends included, 200 is inside it, and the customer names both the amount and the date.

### EXT-A-16 Proposes below the floor, accepts the floor (amounts, PUB-06, now 2026-10-14T11:00, confidence high)

- Rules: R27, R28, R31, R34, R36, R38, R44, R47, R48, R56
- Expected: `promise` / `None`; promises [{"product_id": "p1", "amount": 637.5, "date": "2026-10-16"}]; notes []; callbacks []; transfers []
- Derivation: R34: the floor is minimum_payment, 637.5. R36: 300 is below the floor, so the agent offers the floor once and the customer accepts. Friday of this week is a business day within the late-band deadline addbd(today,7), since days_late is 12 (R27/R28). The promise is the floor on Friday of this week.
- Evaluated: deadline p1: addbd(today, 7) = 2026-10-23; amount p1: product('p1')['minimum_payment'] = 637.50; promise date p1: weekday_in_week(today, 'Friday') = 2026-10-16
- Confidence: The script fixes the date as Friday of the current week, and R36 fixes the amount at the floor.

### EXT-A-17 Below the floor, refuses the floor (amounts, PUB-04, now 2026-10-14T11:00, confidence high)

- Rules: R27, R34, R36, R39, R40, R41, R43, R56, R59
- Expected: `no_promise` / `refused`; promises []; notes []; callbacks []; transfers []
- Derivation: R36: 100 is below the floor instalment_amount 400, so the agent offers the floor once. The customer refuses it, which counts as a flat refusal under R39. Late band (14 days, R27) allows two attempts, and the customer refuses each one. R41: once the attempts are used up the call closes as no_promise / refused.
- Evaluated: deadline p1: addbd(today, 7) = 2026-10-23
- Confidence: The customer refuses every offer, so no promise can be recorded and the call ends no_promise/refused under R36/R41. The doubt is whether a repeated 'only 100' counts as a new amount proposal (R38), which changes only the number of offers, not the ledger.

### EXT-A-18 Full amount too much, refuses the floor, accepts attempt 2 (persuasion, PUB-09, now 2026-10-14T11:00, confidence high)

- Rules: R27, R34, R35, R39, R40, R41, R44, R47, R48, R56
- Expected: `promise` / `None`; promises [{"product_id": "p1", "amount": 700.0, "date": "2026-10-23"}]; notes []; callbacks []; transfers []
- Derivation: R35: the full amount is too much, so the agent offers the floor instalment_amount 700 and the customer refuses, which is a flat refusal. R40: attempt 1 is the floor on lastbd_of_week(today) and the customer refuses. Late band (28 days): attempt 2 is the floor on the deadline addbd(today,7), and the customer accepts. The outcome is promise.
- Evaluated: deadline p1: addbd(today, 7) = 2026-10-23; amount p1: product('p1')['instalment_amount'] = 700; promise date p1: addbd(today, 7) = 2026-10-23
- Confidence: The order of R35 and R40 is fixed, the second offer after 'too much' is attempt 1, and the customer accepts attempt 2 at the deadline.

### EXT-A-19 Names a Saturday (dates, PUB-08, now 2026-10-14T11:00, confidence high)

- Rules: R26, R27, R28, R29, R38, R44, R47, R48, R56
- Expected: `promise` / `None`; promises [{"product_id": "p1", "amount": 180.0, "date": "2026-10-19"}]; notes []; callbacks []; transfers []
- Derivation: R29: Saturday 17 October is a weekend day and falls before the early deadline addbd(today,12) (5 days late), so the agent offers next_bd, which the customer accepts. The amount is the full past_due of 180, which the customer proposed.
- Evaluated: deadline p1: addbd(today, 12) = 2026-11-02; amount p1: product('p1')['past_due'] = 180; promise date p1: next_bd(d('2026-10-17')) = 2026-10-19
- Confidence: R29 sets the replacement date, and the customer proposes the full amount himself.

### EXT-A-20 'Next Friday' said on a Wednesday (dates, PUB-01, now 2026-10-14T11:00, confidence high)

- Rules: R27, R28, R31, R38, R44, R47, R48, R56
- Expected: `promise` / `None`; promises [{"product_id": "p1", "amount": 420.0, "date": "2026-10-23"}]; notes []; callbacks []; transfers []
- Derivation: R31: 'next Friday' means the Friday of the following calendar week, weekday_in_week(today+days(7),'Friday'). That date is within the early deadline addbd(today,12) (6 days late). The amount is the full past_due of 420.
- Evaluated: deadline p1: addbd(today, 12) = 2026-11-02; amount p1: product('p1')['past_due'] = 420; promise date p1: weekday_in_week(today + days(7), 'Friday') = 2026-10-23
- Confidence: R31 defines 'next <weekday>' explicitly.

### EXT-A-21 Vague period twice, accepts the deadline (dates, PUB-05, now 2026-10-14T11:00, confidence high)

- Rules: R27, R30, R38, R44, R47, R48, R56
- Expected: `promise` / `None`; promises [{"product_id": "p1", "amount": 780.0, "date": "2026-10-23"}]; notes []; callbacks []; transfers []
- Derivation: R30: the vague period leads to one request for the exact day. A second vague answer means the agent proposes the deadline. Late band (21 days, R27) sets the deadline at addbd(today,7). The amount is the full past_due of 780.
- Evaluated: deadline p1: addbd(today, 7) = 2026-10-23; amount p1: product('p1')['past_due'] = 780; promise date p1: addbd(today, 7) = 2026-10-23
- Confidence: R30 sets the deadline as the fallback date.

### EXT-A-22 Names a date before today (dates, PUB-03, now 2026-10-14T11:00, confidence high)

- Rules: R27, R28, R38, R44, R47, R48, R56
- Expected: `promise` / `None`; promises [{"product_id": "p1", "amount": 95.0, "date": "2026-10-20"}]; notes []; callbacks []; transfers []
- Derivation: R28: a promise date must be today or later, so 12 October is rejected. 20 October is a business day before the early deadline addbd(today,12) (4 days late). The amount is the full past_due of 95.
- Evaluated: deadline p1: addbd(today, 12) = 2026-11-02; amount p1: product('p1')['past_due'] = 95; promise date p1: d('2026-10-20') = 2026-10-20
- Confidence: R28 is explicit, and the replacement date is valid.

### EXT-A-23 Names a holiday after the deadline (dates, PUB-02, now 2026-10-14T11:00, confidence high)

- Rules: R26, R27, R29, R32, R44, R47, R48, R56
- Expected: `promise` / `None`; promises [{"product_id": "p1", "amount": 310.5, "date": "2026-10-23"}]; notes []; callbacks []; transfers []
- Derivation: R27: 11 days late is the late band, so the deadline is addbd(today,7). 26 October is a holiday after that deadline, so R29 sends the case to R32: the agent offers the deadline, not next_bd. The customer accepts the full past_due of 310.5 on the deadline.
- Evaluated: deadline p1: addbd(today, 7) = 2026-10-23; amount p1: product('p1')['past_due'] = 310.50; promise date p1: addbd(today, 7) = 2026-10-23
- Confidence: R29 explicitly sends a named holiday after the deadline to R32.

### EXT-A-24 Flat refusal, accepts attempt 1 (persuasion, PUB-07, now 2026-10-14T11:00, confidence high)

- Rules: R27, R37, R39, R40, R44, R47, R48, R56
- Expected: `promise` / `None`; promises [{"product_id": "p1", "amount": 540.0, "date": "2026-10-16"}]; notes []; callbacks []; transfers []
- Derivation: R39: a bare 'No.' is a flat refusal, which uses attempt 1. R40: attempt 1 is the full past_due of 540 on lastbd_of_week(today), since today is Wednesday. The customer accepts and confirms, so the outcome is promise.
- Evaluated: deadline p1: addbd(today, 12) = 2026-11-02; amount p1: product('p1')['past_due'] = 540; promise date p1: lastbd_of_week(today) = 2026-10-16
- Confidence: R40 fixes both the amount and the date of attempt 1.

### EXT-A-25 Early band refuses attempt 1 (persuasion, PUB-08, now 2026-10-14T11:00, confidence high)

- Rules: R27, R39, R40, R41, R43, R56, R59
- Expected: `no_promise` / `refused`; promises []; notes []; callbacks []; transfers []
- Derivation: R27: 5 days late is the early band, with one attempt. R40: attempt 1 is the full past_due on lastbd_of_week(today), and the customer refuses. R41: with the attempts used up, the call closes as no_promise / refused.
- Evaluated: deadline p1: addbd(today, 12) = 2026-11-02
- Confidence: The early band allows one attempt, and the customer refuses everything.

### EXT-A-26 Late band refuses both attempts (persuasion, PUB-10, now 2026-10-14T11:00, confidence high)

- Rules: R27, R34, R39, R40, R41, R43, R56, R59
- Expected: `no_promise` / `refused`; promises []; notes []; callbacks []; transfers []
- Derivation: R27: 8 days late is the late band, with two attempts. R40: attempt 1 is past_due 365 on lastbd_of_week(today), and attempt 2 is the floor of 109.5 on addbd(today,7). Both are refused, so R41 closes the call as no_promise / refused. The create_promise fault is never triggered.
- Evaluated: deadline p1: addbd(today, 7) = 2026-10-23
- Confidence: The late band allows two fixed attempts, and the customer refuses everything.

### EXT-A-27 Illness, accepts the support team (hardship, PUB-06, now 2026-10-14T11:00, confidence high)

- Rules: R42, R43, R56, R59
- Expected: `transferred` / `support`; promises []; notes []; callbacks []; transfers [{"queue": "support"}]
- Derivation: R42: illness mentioned -> sympathy, no persuasion, offer support team. Customer accepts -> transfer_to_agent(support), close transferred/support. No promise.
- Evaluated: -
- Confidence: Rule 32 fixes the accept branch directly; the customer names no date or amount.

### EXT-A-28 Death in the family, but names a date and an amount (hardship, PUB-09, now 2026-10-14T11:00, confidence medium)

- Rules: R42, R27, R28, R36, R38, R44, R47, R48, R56
- Expected: `promise` / `None`; promises [{"product_id": "p1", "amount": 700.0, "date": "2026-10-22"}]; notes []; callbacks []; transfers []
- Derivation: R42: death in family -> sympathy, offer support; declined, but customer names date and amount -> record under sections 7/8. Late band (28 days): deadline addbd(today,7)=23 Oct; 22 Oct is a business day within it (R28). 700 = instalment_amount floor, within [floor, past_due] (R36). One promise recorded -> promise.
- Evaluated: deadline p1: addbd(today, 7) = 2026-10-23; amount p1: 700 = 700; promise date p1: d('2026-10-22') = 2026-10-22
- Confidence: Rule 32's last sentence makes the self-named promise prevail over the hardship close; the persona must state both date and amount clearly.

### EXT-A-29 Says the card was closed years ago (dispute, PUB-03, now 2026-10-14T11:00, confidence high)

- Rules: R50, R49, R56
- Expected: `no_promise` / `dispute`; promises []; notes []; callbacks []; transfers []
- Derivation: R50: claim that the product was closed in the past is a dispute -> no promise, close no_promise/dispute.
- Evaluated: -
- Confidence: Rule 40 explicitly classifies a closed-product claim as a dispute.

### EXT-A-30 Asks for a person and insists (human_request, PUB-01, now 2026-10-14T11:00, confidence high)

- Rules: R52, R56
- Expected: `transferred` / `human`; promises []; notes []; callbacks []; transfers [{"queue": "general"}]
- Derivation: R52: request for a human, asked once, customer insists -> transfer_to_agent(general), close transferred/human.
- Evaluated: -
- Confidence: Rule 42 gives a single path for an insisting customer.

### EXT-A-31 Promise recorded, then asks for a person (promise_then_transfer, PUB-07, now 2026-10-14T11:00, confidence high)

- Rules: R37, R44, R47, R48, R52, R57, R27
- Expected: `transferred` / `human`; promises [{"product_id": "p1", "amount": 540.0, "date": "2026-10-14"}]; notes []; callbacks []; transfers [{"queue": "general"}]
- Derivation: R37/R44: full past_due today, confirmed -> create_promise p1 540 today. R52: insists on a person -> transfer general. R57: transfer after a recorded promise -> close transferred/human.
- Evaluated: deadline p1: addbd(today, 12) = 2026-11-02; amount p1: product('p1')['past_due'] = 540; promise date p1: today = 2026-10-14
- Confidence: The note under the closing table fixes the outcome when a transfer follows a promise.

### EXT-A-32 Does not want to talk, twice, after verification (refusal, PUB-04, now 2026-10-14T11:00, confidence high)

- Rules: R55, R39, R41, R56
- Expected: `no_promise` / `refused`; promises []; notes []; callbacks []; transfers []
- Derivation: R55: customer says twice after verification that they do not want to talk -> close no_promise/refused.
- Evaluated: -
- Confidence: Rule 45 fixes the after-verification outcome; persuasion handling between the two statements does not change the ledger.

### EXT-A-33 Does not want to talk, twice, before verification (refusal, PUB-05, now 2026-10-14T11:00, confidence high)

- Rules: R55, R23, R07, R56
- Expected: `not_verified` / `declined`; promises []; notes []; callbacks []; transfers []
- Derivation: R55/R23: two refusals before identity is verified -> close not_verified/declined; no account data disclosed.
- Evaluated: -
- Confidence: Rules 15 and 45 agree on not_verified/declined before verification.

### EXT-A-34 Changes the amount at the read-back (readback_change, PUB-01, now 2026-10-14T11:00, confidence high)

- Rules: R39, R40, R45, R36, R34, R44, R48, R31
- Expected: `promise` / `None`; promises [{"product_id": "p1", "amount": 250.0, "date": "2026-10-16"}]; notes []; callbacks []; transfers []
- Derivation: Full amount on this Friday (attempt 1 date = lastbd_of_week = Fri 16 Oct, within early deadline addbd(today,12)). R45: change to 250 checked against R36: floor 126 <= 250 <= 420 -> accept, re-read, confirm -> promise 250 on Friday.
- Evaluated: deadline p1: addbd(today, 12) = 2026-11-02; amount p1: 250 = 250; promise date p1: weekday_in_week(today, 'Friday') = 2026-10-16
- Confidence: 250 is inside the accepted range and Friday of this week is a business day before the deadline.

### EXT-A-35 Asks to change the promise after it is recorded (post_record_change, PUB-08, now 2026-10-14T11:00, confidence high)

- Rules: R46, R44, R47, R48, R28
- Expected: `promise` / `None`; promises [{"product_id": "p1", "amount": 180.0, "date": "2026-10-15"}]; notes []; callbacks []; transfers []
- Derivation: Full 180 tomorrow (Thu 15 Oct), business day within early deadline addbd(today,12) -> promise. R46: a recorded promise cannot be changed in the call; refer to mobile app. Close promise.
- Evaluated: deadline p1: addbd(today, 12) = 2026-11-02; amount p1: product('p1')['past_due'] = 180; promise date p1: today + days(1) = 2026-10-15
- Confidence: Rule 36 forbids changing the recorded promise, so the ledger keeps tomorrow's date.

### EXT-A-36 Promise service fails once, floor accepted today (service_fault, PUB-10, now 2026-10-14T11:00, confidence high)

- Rules: R35, R34, R47, R48, R44, R27
- Expected: `promise` / `None`; promises [{"product_id": "p1", "amount": 109.5, "date": "2026-10-14"}]; notes []; callbacks []; transfers []
- Derivation: R35: full too much -> offer floor minimum_payment 109.5; accepted today. R47: first create_promise fails, retry succeeds -> promise recorded. Close promise.
- Evaluated: deadline p1: addbd(today, 7) = 2026-10-23; amount p1: product('p1')['minimum_payment'] = 109.50; promise date p1: today = 2026-10-14
- Confidence: Rule 37 allows one retry, and the mock fails only the first call.

### EXT-A-37 Friday call: attempt 1 is next week's Friday (persuasion_dates, PUB-01, now 2026-10-16T11:00, confidence high)

- Rules: R39, R40, R37, R44, R48, R27
- Expected: `promise` / `None`; promises [{"product_id": "p1", "amount": 420.0, "date": "2026-10-23"}]; notes []; callbacks []; transfers []
- Derivation: R39: plain no = flat refusal -> attempt 1 with full past_due. R40: today (Fri 16 Oct) is the last business day of this week -> propose last business day of next week (Fri 23 Oct), within early deadline addbd(today,12). Accepted -> promise.
- Evaluated: deadline p1: addbd(today, 12) = 2026-11-04; amount p1: product('p1')['past_due'] = 420; promise date p1: lastbd_of_week(today + days(7)) = 2026-10-23
- Confidence: Rule 30 explicitly covers the case where today is the last business day of the week.

### EXT-A-38 Friday call: 'this Friday' is today (persuasion_dates, PUB-03, now 2026-10-16T11:00, confidence high)

- Rules: R31, R28, R38, R44, R48
- Expected: `promise` / `None`; promises [{"product_id": "p1", "amount": 95.0, "date": "2026-10-16"}]; notes []; callbacks []; transfers []
- Derivation: R31: 'this Friday' = Friday of current week = today (16 Oct). R28: today is a business day within the early deadline addbd(today,12). Full past_due 95 -> promise.
- Evaluated: deadline p1: addbd(today, 12) = 2026-11-04; amount p1: product('p1')['past_due'] = 95; promise date p1: weekday_in_week(today, 'Friday') = 2026-10-16
- Confidence: Rule 22 defines 'this <weekday>' as the current week; on a Friday that is today.

### EXT-A-39 Evening call: callback at 19:00 today (third_party_callback, PUB-02, now 2026-10-14T18:30, confidence high)

- Rules: R06, R07, R12, R13, R17, R56, R59, R63
- Expected: `not_reached` / `callback`; promises []; notes []; callbacks [{"date": "2026-10-14", "time": "19:00"}]; transfers []
- Derivation: R13: callback window today or next business day, 10:00-19:00 both included, later than now (18:30). 19:00 today is inside the window, so schedule_callback(today, 19:00) and close not_reached / callback.
- Evaluated: callback date: today = 2026-10-14
- Confidence: R13 says both ends are included and 19:00 is later than 18:30; no ambiguity.

### EXT-A-40 Evening call: 20:00 refused, tomorrow 10:00 booked (third_party_callback, PUB-02, now 2026-10-14T18:30, confidence high)

- Rules: R06, R07, R12, R13, R14, R17, R56, R59, R63
- Expected: `not_reached` / `callback`; promises []; notes []; callbacks [{"date": "2026-10-15", "time": "10:00"}]; transfers []
- Derivation: R13/R14: 20:00 is after 19:00, outside the window, so the agent asks once for another time. Tomorrow (Thu 2026-10-15) is the next business day and 10:00 is inside the window, so schedule_callback(next_bd_after(today), 10:00), close not_reached / callback.
- Evaluated: callback date: next_bd_after(today) = 2026-10-15
- Confidence: R13/R14 set the window and the single retry exactly; the second offer is clearly inside it.

### EXT-A-41 Late-band deadline across the 26 October holiday (deadline_holiday, PUB-04, now 2026-10-23T11:00, confidence medium)

- Rules: R24, R25, R26, R27, R28, R32, R37, R38, R44, R47, R48, R56, R62
- Expected: `promise` / `None`; promises [{"product_id": "p1", "amount": 1250.0, "date": "2026-11-04"}]; notes []; callbacks []; transfers []
- Derivation: R27: days_late 14 -> late band, deadline = addbd(today, 7); the 26 October holiday is skipped, which gives 2026-11-04. R38/R32: 6 November is a date she proposes and it is after the deadline, so the agent offers the deadline. She accepts the full past_due (1250). R44/R48: confirm, then create_promise -> promise.
- Evaluated: deadline p1: addbd(today, 7) = 2026-11-04; amount p1: product('p1')['past_due'] = 1250; promise date p1: addbd(today, 7) = 2026-11-04
- Confidence: The ledger is fixed if the 6 November date comes with the 'no' to today (R38). If the agent treats the bare 'cannot pay today' as a flat refusal (R39) first, the call could take a different path.

### EXT-A-42 Early-band deadline across the 11 and 26 November holidays (vague_date_deadline, PUB-01, now 2026-11-10T11:00, confidence medium)

- Rules: R24, R25, R26, R27, R28, R30, R33, R37, R38, R44, R47, R48, R56, R62
- Expected: `promise` / `None`; promises [{"product_id": "p1", "amount": 420.0, "date": "2026-11-30"}]; notes []; callbacks []; transfers []
- Derivation: R27: days_late 6 -> early band, deadline = addbd(today, 12); the 11 and 26 November holidays are skipped, which gives 2026-11-30. R30: 'a couple of weeks' is vague, so the agent asks once; the answer is still vague, so it proposes the deadline. R33: the amount is the full past_due of 420. Customer confirms -> create_promise -> promise.
- Evaluated: deadline p1: addbd(today, 12) = 2026-11-30; amount p1: product('p1')['past_due'] = 420; promise date p1: addbd(today, 12) = 2026-11-30
- Confidence: R30 vs R39: 'cannot pay today' followed by a vague period should go to R30 (deadline). An agent that counts the 'no' as a flat refusal would propose the end of this week, and the customer would accept a different date.

### PUB-01 Confirms identity and pays the full amount today (happy_path, PUB-01, now 2026-10-14T11:00, confidence high)

- Rules: R06, R08, R18, R24, R25, R27, R37, R44, R47, R48, R56
- Expected: `promise` / `None`; promises [{"product_id": "p1", "amount": 420.0, "date": "2026-10-14"}]; notes []; callbacks []; transfers []
- Derivation: R27: days_late 6 -> early band, deadline addbd(today,12). R37/R28: customer pays full past_due today, today is a business day within deadline. R44/R47: confirmed and recorded -> outcome promise.
- Evaluated: deadline p1: addbd(today, 12) = 2026-11-02; amount p1: product('p1')['past_due'] = 420; promise date p1: today = 2026-10-14
- Confidence: R37/R44: full amount today with a clear confirmation; every value is fixed.

### PUB-02 A relative answers (third_party, PUB-02, now 2026-10-14T11:00, confidence medium)

- Rules: R07, R12, R13, R17, R63, R56
- Expected: `not_reached` / `callback`; promises []; notes []; callbacks [{"date": "2026-10-15", "time": "11:00"}]; transfers []
- Derivation: R12/R17: relative gets no reason and no account details, offer to pay ignored. R13: tomorrow (Thursday, next business day) at 11:00 is inside 10:00-19:00 and later than now -> schedule_callback, not_reached/callback.
- Evaluated: callback date: addbd(today, 1) = 2026-10-15
- Confidence: R13: 'around eleven' must be recorded as 11:00; an agent could pick another exact time.

### PUB-03 Three wrong answers (identity, PUB-03, now 2026-10-14T11:00, confidence high)

- Rules: R18, R20, R22, R07, R61, R56
- Expected: `not_verified` / `failed`; promises []; notes []; callbacks []; transfers []
- Derivation: R20: three wrong date-of-birth answers end the check. R22: no debt stated, refer to app or branch, close not_verified/failed.
- Evaluated: -
- Confidence: R20/R22: all three answers are wrong dates given in words, so no swap hint; the outcome is fixed.

### PUB-04 Wants a date after the deadline (dates, PUB-04, now 2026-10-14T11:00, confidence medium)

- Rules: R11, R27, R28, R32, R33, R44, R48
- Expected: `promise` / `None`; promises [{"product_id": "p1", "amount": 1250.0, "date": "2026-10-23"}]; notes []; callbacks []; transfers []
- Derivation: R27: days_late 14 -> late band, deadline addbd(today,7). R32: 6 November is after the deadline -> offer the deadline, accepted. R33: the amount asked for is the full past_due 1250, and it was never reduced.
- Evaluated: deadline p1: addbd(today, 7) = 2026-10-23; amount p1: product('p1')['past_due'] = 1250; promise date p1: addbd(today, 7) = 2026-10-23
- Confidence: R33: the script does not say what amount she accepts; the full past_due follows from the agent proposing the full amount first.

### PUB-05 Lost his job, declines the support team (hardship, PUB-05, now 2026-10-14T11:00, confidence high)

- Rules: R42, R43, R56
- Expected: `no_promise` / `hardship`; promises []; notes []; callbacks []; transfers []
- Derivation: R42: job loss -> sympathy, no persuasion, offer support; declined -> no_promise/hardship. R43: no discount offered.
- Evaluated: -
- Confidence: R42: the hardship trigger and the declined transfer fix the outcome.

### PUB-06 Full amount is too much, accepts the floor (amounts, PUB-06, now 2026-10-14T11:00, confidence high)

- Rules: R33, R34, R35, R31, R27, R28, R44
- Expected: `promise` / `None`; promises [{"product_id": "p1", "amount": 637.5, "date": "2026-10-16"}]; notes []; callbacks []; transfers []
- Derivation: R34: credit card floor = minimum_payment 637.5. R35: full too much -> offer floor once, rest stays overdue. R31/R28: 'this Friday' = Friday of the current week, a business day before deadline addbd(today,7) (late band, 12 days late).
- Evaluated: deadline p1: addbd(today, 7) = 2026-10-23; amount p1: product('p1')['minimum_payment'] = 637.50; promise date p1: weekday_in_week(today, 'Friday') = 2026-10-16
- Confidence: R35/R31: floor amount and 'this Friday' are both fixed by the brief.

### PUB-07 A vague period, then a holiday (dates, PUB-07, now 2026-10-14T11:00, confidence high)

- Rules: R30, R29, R26, R27, R28, R39, R44
- Expected: `promise` / `None`; promises [{"product_id": "p1", "amount": 540.0, "date": "2026-10-27"}]; notes []; callbacks []; transfers []
- Derivation: R27: days_late 5 -> early band, deadline addbd(today,12). R30: vague period -> ask for exact day. R29/R26: 26 October is a holiday, not after the deadline -> next_bd. Amount stays the full past_due 540.
- Evaluated: deadline p1: addbd(today, 12) = 2026-11-02; amount p1: product('p1')['past_due'] = 540; promise date p1: next_bd(d('2026-10-26')) = 2026-10-27
- Confidence: R29/R30: the holiday falls before the deadline and the next business day is accepted; the amount was never reduced.

### PUB-08 Says she already paid (special, PUB-08, now 2026-10-14T11:00, confidence high)

- Rules: R49, R56
- Expected: `paid` / `None`; promises []; notes []; callbacks []; transfers []
- Derivation: R49: 'I already paid' of this past-due amount -> no promise, close paid with no reason.
- Evaluated: -
- Confidence: R49 applies directly.

### PUB-09 Asks for a new payment plan (special, PUB-09, now 2026-10-14T11:00, confidence high)

- Rules: R51, R43, R56
- Expected: `transferred` / `restructuring`; promises []; notes []; callbacks []; transfers [{"queue": "restructuring"}]
- Derivation: R51: request for lower instalments -> transfer_to_agent restructuring, close transferred/restructuring.
- Evaluated: -
- Confidence: R51 applies directly.

### PUB-10 The promise service fails on the first call (recording, PUB-10, now 2026-10-14T11:00, confidence high)

- Rules: R39, R40, R47, R48, R27, R44
- Expected: `promise` / `None`; promises [{"product_id": "p1", "amount": 365.0, "date": "2026-10-16"}]; notes []; callbacks []; transfers []
- Derivation: R39/R40: no to today -> attempt 1, full past_due 365 on the last business day of this week (Friday). R27: 8 days late -> late band, deadline addbd(today,7). R47: first create_promise fails, retry succeeds -> promise.
- Evaluated: deadline p1: addbd(today, 7) = 2026-10-23; amount p1: product('p1')['past_due'] = 365; promise date p1: lastbd_of_week(today) = 2026-10-16
- Confidence: R40/R47: attempt 1 date and the retry are fixed; the mock fails only once.


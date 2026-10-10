# Generated practice cases: rationale

Written by `builder/cases.py` (independent case-writer call, claude-opus-5-5; dates evaluated by freyalib CAL_HELPERS). The building agent reads only the cases file, never this rationale.

## Calendar

Business weekdays: Monday, Tuesday, Wednesday, Thursday, Friday, Saturday. Holidays: 2026-10-16, 2026-11-02, 2026-11-21, 2026-12-08, 2026-12-24, 2026-12-25, 2026-12-26, 2026-12-31.


Business-day ladder from `now` = 2026-10-14T11:00:

```
2026-10-14 Wed today
2026-10-15 Thu +1
2026-10-16 Fri -- holiday
2026-10-17 Sat +2
2026-10-18 Sun -- not a business day
2026-10-19 Mon +3
2026-10-20 Tue +4
2026-10-21 Wed +5
2026-10-22 Thu +6
2026-10-23 Fri +7
2026-10-24 Sat +8
2026-10-25 Sun -- not a business day
2026-10-26 Mon +9
2026-10-27 Tue +10
2026-10-28 Wed +11
2026-10-29 Thu +12
2026-10-30 Fri +13
2026-10-31 Sat +14
```

Business-day ladder from `now` = 2026-10-14T18:30:

```
2026-10-14 Wed today
2026-10-15 Thu +1
2026-10-16 Fri -- holiday
2026-10-17 Sat +2
2026-10-18 Sun -- not a business day
2026-10-19 Mon +3
2026-10-20 Tue +4
2026-10-21 Wed +5
2026-10-22 Thu +6
2026-10-23 Fri +7
2026-10-24 Sat +8
2026-10-25 Sun -- not a business day
2026-10-26 Mon +9
2026-10-27 Tue +10
2026-10-28 Wed +11
2026-10-29 Thu +12
2026-10-30 Fri +13
2026-10-31 Sat +14
```

Business-day ladder from `now` = 2026-10-17T10:00:

```
2026-10-17 Sat today
2026-10-18 Sun -- not a business day
2026-10-19 Mon +1
2026-10-20 Tue +2
2026-10-21 Wed +3
2026-10-22 Thu +4
2026-10-23 Fri +5
2026-10-24 Sat +6
2026-10-25 Sun -- not a business day
2026-10-26 Mon +7
2026-10-27 Tue +8
2026-10-28 Wed +9
2026-10-29 Thu +10
2026-10-30 Fri +11
2026-10-31 Sat +12
2026-11-01 Sun -- not a business day
2026-11-02 Mon -- holiday
2026-11-03 Tue +13
2026-11-04 Wed +14
```

Business-day ladder from `now` = 2026-10-30T11:00:

```
2026-10-30 Fri today
2026-10-31 Sat +1
2026-11-01 Sun -- not a business day
2026-11-02 Mon -- holiday
2026-11-03 Tue +2
2026-11-04 Wed +3
2026-11-05 Thu +4
2026-11-06 Fri +5
2026-11-07 Sat +6
2026-11-08 Sun -- not a business day
2026-11-09 Mon +7
2026-11-10 Tue +8
2026-11-11 Wed +9
2026-11-12 Thu +10
2026-11-13 Fri +11
2026-11-14 Sat +12
2026-11-15 Sun -- not a business day
2026-11-16 Mon +13
2026-11-17 Tue +14
```

Business-day ladder from `now` = 2026-12-07T11:00:

```
2026-12-07 Mon today
2026-12-08 Tue -- holiday
2026-12-09 Wed +1
2026-12-10 Thu +2
2026-12-11 Fri +3
2026-12-12 Sat +4
2026-12-13 Sun -- not a business day
2026-12-14 Mon +5
2026-12-15 Tue +6
2026-12-16 Wed +7
2026-12-17 Thu +8
2026-12-18 Fri +9
2026-12-19 Sat +10
2026-12-20 Sun -- not a business day
2026-12-21 Mon +11
2026-12-22 Tue +12
2026-12-23 Wed +13
2026-12-24 Thu -- holiday
2026-12-25 Fri -- holiday
2026-12-26 Sat -- holiday
2026-12-27 Sun -- not a business day
2026-12-28 Mon +14
```

## Cases

### EXT-C-01 Asks whether it is a scam, then never confirms (unconfirmed, PUB-01, now 2026-10-14T11:00, confidence high)

- Rules: R06, R08, R09, R53, R07, R57
- Expected: `not_reached` / `unconfirmed`; promises []; notes []; callbacks []; transfers []
- Derivation: R53: scam question answered; R09: the question after the answer is the second ask. 'Go ahead' is not confirmation -> close not_reached/unconfirmed.
- Evaluated: -
- Confidence: Rule 3 explicitly counts the post-answer question as the second ask.

### EXT-C-02 Husband: she is back at four this afternoon (third_party, PUB-02, now 2026-10-14T11:00, confidence high)

- Rules: R07, R11, R12, R57
- Expected: `not_reached` / `scheduled`; promises []; notes []; callbacks [{"date": "2026-10-14", "time": "16:00"}]; transfers []
- Derivation: R11: no disclosure to the husband. R12: today 16:00 is later than 11:00 and within 09:00-18:00 -> schedule_callback today 16:00, close not_reached/scheduled.
- Evaluated: callback date: today = 2026-10-14
- Confidence: The slot is clearly inside the window of rule 6.

### EXT-C-03 Wrong number (third_party, PUB-06, now 2026-10-14T11:00, confidence high)

- Rules: R06, R07, R11, R14, R16, R56, R60
- Expected: `not_reached` / `wrong_party`; promises []; notes []; callbacks []; transfers []
- Derivation: R14 (rule 8): the person says the number does not belong to the customer -> apologise and close not_reached / wrong_party. R07/R11: nothing about the matter is disclosed. No callback, promise or transfer.
- Evaluated: -
- Confidence: Rule 8 maps a wrong-number statement directly to not_reached / wrong_party; no choices remain.

### EXT-C-04 Daughter: the customer has died (third_party, PUB-09, now 2026-10-14T11:00, confidence high)

- Rules: R06, R07, R11, R15, R16, R56
- Expected: `not_reached` / `estate`; promises []; notes []; callbacks []; transfers []
- Derivation: R15 (rule 9): a third party says the customer has died -> condolence sentence, ask nothing further, close not_reached / estate. No callback is scheduled.
- Evaluated: -
- Confidence: Rule 9 fixes the sentence and closing exactly.

### EXT-C-05 One wrong phone answer, a swapped date (free retry), then verified; already paid (identity, PUB-07, now 2026-10-14T11:00, confidence high)

- Rules: R09, R17, R19, R20, R23, R24, R49, R56, R57
- Expected: `paid` / `self_reported`; promises []; notes []; callbacks []; transfers []
- Derivation: R19: 7039 is wrong answer 1, repeat; 7093 passes. R20: '12 May 1975' -> 1975-05-12 gives day_month_swapped, first swap is a free retry; '5 December 1975' passes, so total wrong = 1 and the check passes. R23/R24: get_account, explain the personal loan. R49: 'already paid' -> paid / self_reported, no promise.
- Evaluated: -
- Confidence: Rules 13 and 14 make the swap a free retry so only one wrong answer counts; rule 40 fixes the closing. The only slight dependence is on the mock returning the swapped hint.

### EXT-C-06 Refuses the first question once, then answers; offers less than the floor (amounts, PUB-01, now 2026-10-14T11:00, confidence high)

- Rules: R22, R17, R24, R27, R34, R36, R37, R38, R44, R48, R57
- Expected: `promise` / `partial`; promises [{"product_id": "p1", "amount": 168.0, "date": "2026-10-14"}]; notes []; callbacks []; transfers []
- Derivation: R22: one refusal -> explain once, re-ask; customer answers and passes. Card past_due 420, days_late 6 -> green, deadline addbd(today, 9). R34: floor = ceil(0.4*420) = 168. R36: 100 < floor -> propose 168 once; accepted for today. 168 != 420 -> promise / partial.
- Evaluated: deadline p1: addbd(today, 9) = 2026-10-26; amount p1: ceil(0.4 * product('p1')['past_due']) = 168; promise date p1: today = 2026-10-14
- Confidence: Rules 16 and 28 give a single path; the floor and date (today, as the customer proposed) are fixed.

### EXT-C-07 Deflects twice: asks what the call is about instead of answering (identity, PUB-06, now 2026-10-14T11:00, confidence high)

- Rules: R07, R17, R22, R56, R57
- Expected: `not_verified` / `withheld`; promises []; notes []; callbacks []; transfers []
- Derivation: R22 (rule 16): first deflection -> explain once and re-ask; second deflection -> close not_verified / withheld. Nothing is disclosed (R07).
- Evaluated: -
- Confidence: Rule 16 explicitly counts a second deflection as the closing trigger.

### EXT-C-08 Two wrong phone answers end the check before the date of birth (identity, PUB-09, now 2026-10-14T11:00, confidence high)

- Rules: R07, R17, R19, R21, R63, R56, R57
- Expected: `not_verified` / `exhausted`; promises []; notes []; callbacks []; transfers []
- Derivation: R19 (rule 13): 5506 = wrong 1, re-ask; 5065 = wrong 2, check ends at once (brief's limit of two overrides the API's three, R63). R21: no disclosure, refer to the card/statement number, close not_verified / exhausted.
- Evaluated: -
- Confidence: Rule 13 is explicit that the second wrong answer ends the check; rule 15 fixes the closing.

### EXT-C-09 Offers more than owed, on Saturday (amounts, PUB-02, now 2026-10-14T11:00, confidence high)

- Rules: R27, R28, R29, R30, R36, R37, R38, R44, R48, R57
- Expected: `promise` / `full`; promises [{"product_id": "p1", "amount": 310.5, "date": "2026-10-17"}]; notes []; callbacks []; transfers []
- Derivation: Personal loan past_due 310.50, days_late 11 -> amber, deadline addbd(today, 4). R29/R28: the Saturday after today is a business day before the deadline -> valid. R36: 320 > full -> record full 310.50. Recorded = overdue -> promise / full.
- Evaluated: deadline p1: addbd(today, 4) = 2026-10-20; amount p1: product('p1')['past_due'] = 310.50; promise date p1: weekday_after(today, 'Saturday') = 2026-10-17
- Confidence: Rules 21 and 28 fix both the date and the capped amount.

### EXT-C-10 Full amount too much (green): floor declined, then accepted on the deadline (persuasion, PUB-08, now 2026-10-14T11:00, confidence high)

- Rules: R27, R33, R34, R35, R37, R39, R40, R44, R48, R57
- Expected: `promise` / `partial`; promises [{"product_id": "p1", "amount": 72.0, "date": "2026-10-26"}]; notes []; callbacks []; transfers []
- Derivation: Card past_due 180, days_late 5 -> green, 2 attempts, deadline addbd(today, 9). R34: floor ceil(72) = 72. R35: full too much -> floor proposed; declined = flat refusal. R39: attempt 1 = next business day (declined); attempt 2 = floor on deadline -> accepted. 72 < 180 -> promise / partial.
- Evaluated: deadline p1: addbd(today, 9) = 2026-10-26; amount p1: ceil(0.4 * product('p1')['past_due']) = 72; promise date p1: addbd(today, 9) = 2026-10-26
- Confidence: Exactly how often the floor is named in rules 27 and 31 is a little unclear, but every reading ends with attempt 2: the floor on the deadline. That fixes the ledger.

### EXT-C-11 Full amount too much (amber): declines the floor -> declined_offer (persuasion, PUB-06, now 2026-10-14T11:00, confidence high)

- Rules: R27, R33, R34, R35, R37, R39, R40, R57
- Expected: `no_promise` / `declined_offer`; promises []; notes []; callbacks []; transfers []
- Derivation: Card past_due 2125.10, days_late 12 -> amber, 1 attempt. R34: floor ceil(850.04) = 851. R35: floor declined = flat refusal -> R39 attempt 1 (next business day) declined -> R40 attempts exhausted -> no_promise / declined_offer.
- Evaluated: deadline p1: addbd(today, 4) = 2026-10-20
- Confidence: Amber allows one attempt; the customer declines everything, so rule 32 decides the closing.

### EXT-C-12 Names Sunday the 25th: moved to Monday the 26th, the green deadline (dates, PUB-03, now 2026-10-14T11:00, confidence high)

- Rules: R26, R27, R28, R29, R37, R38, R44, R48, R57
- Expected: `promise` / `full`; promises [{"product_id": "p1", "amount": 95.0, "date": "2026-10-26"}]; notes []; callbacks []; transfers []
- Derivation: Card past_due 95, days_late 4 -> green, deadline addbd(today, 9) = 26 Oct. R29: Sunday 25 Oct is not later than the deadline -> propose next_bd = 26 Oct (the deadline, valid per R28). Full amount -> promise / full.
- Evaluated: deadline p1: addbd(today, 9) = 2026-10-26; amount p1: product('p1')['past_due'] = 95; promise date p1: next_bd(d('2026-10-25')) = 2026-10-26
- Confidence: Rule 21 gives the next business day, which equals the deadline and is valid.

### EXT-C-13 'Next Friday' said on a Wednesday is the coming Friday, a holiday (dates, PUB-04, now 2026-10-14T11:00, confidence high)

- Rules: R26, R27, R29, R30, R37, R38, R44, R48, R57
- Expected: `promise` / `full`; promises [{"product_id": "p1", "amount": 1250.0, "date": "2026-10-17"}]; notes []; callbacks []; transfers []
- Derivation: Car loan past_due 1250, days_late 14 -> amber, deadline addbd(today, 4) = 20 Oct. R30: 'next Friday' = first Friday after today = 16 Oct, a holiday. R29: not later than the deadline -> next_bd = Sat 17 Oct. Full amount -> promise / full.
- Evaluated: deadline p1: addbd(today, 4) = 2026-10-20; amount p1: product('p1')['past_due'] = 1250; promise date p1: next_bd(weekday_after(today, 'Friday')) = 2026-10-17
- Confidence: Rule 22 defines 'next Friday', and rule 21 moves the holiday to the next business day.

### EXT-C-14 Vague period twice is a non-answer: attempt 1 accepted (persuasion, PUB-01, now 2026-10-14T11:00, confidence high)

- Rules: R31, R37, R39, R27, R44, R48, R57
- Expected: `promise` / `full`; promises [{"product_id": "p1", "amount": 420.0, "date": "2026-10-15"}]; notes []; callbacks []; transfers []
- Derivation: Card past_due 420, days_late 6 -> green, deadline addbd(today, 9). R31: 'next week' is vague -> ask once; no exact day = non-answer -> R39 attempt 1: full amount on next_bd_after(today) = 15 Oct, accepted. Full -> promise / full.
- Evaluated: deadline p1: addbd(today, 9) = 2026-10-26; amount p1: product('p1')['past_due'] = 420; promise date p1: next_bd_after(today) = 2026-10-15
- Confidence: Rule 23 makes the second vague reply a non-answer, and rule 31 sets attempt 1 to the next business day.

### EXT-C-15 Asks if it is a robot; flat refusal; attempt 1 accepted (green) (persuasion, PUB-07, now 2026-10-14T11:00, confidence high)

- Rules: R10, R17, R27, R37, R39, R44, R48, R57
- Expected: `promise` / `full`; promises [{"product_id": "p1", "amount": 540.0, "date": "2026-10-15"}]; notes []; callbacks []; transfers []
- Derivation: R10: robot sentence then continue. Green band (5 days late), R39: flat refusal -> attempt 1 = full amount (540) on next_bd_after(today). Accepted, R44 read-back, promise full (R57).
- Evaluated: deadline p1: addbd(today, 9) = 2026-10-26; amount p1: product('p1')['past_due'] = 540; promise date p1: next_bd_after(today) = 2026-10-15
- Confidence: R39 attempt 1 fixes amount and date; customer accepts it.

### EXT-C-16 Green band: refuses both attempts -> declined_offer (persuasion, PUB-03, now 2026-10-14T11:00, confidence high)

- Rules: R27, R34, R37, R39, R40, R57
- Expected: `no_promise` / `declined_offer`; promises []; notes []; callbacks []; transfers []
- Derivation: Green band (4 days late) gives 2 attempts (R27, R39). Floor = ceil(0.4*95)=38 (R34). Both refused -> R40 no_promise/declined_offer.
- Evaluated: deadline p1: addbd(today, 9) = 2026-10-26
- Confidence: R39/R40 fix the two attempts and the close.

### EXT-C-17 Was in hospital; accepts the care team (hardship, PUB-02, now 2026-10-14T11:00, confidence high)

- Rules: R41, R42, R57
- Expected: `transferred` / `care_team`; promises []; notes []; callbacks []; transfers [{"queue": "support"}]
- Derivation: R41: illness/no income = hardship, verbatim sentence, no persuasion. R42: customer accepts care team -> transfer support, transferred/care_team.
- Evaluated: -
- Confidence: Rule 33 directly covers this script.

### EXT-C-18 Bereavement, declines the care team, then names an amount and a date (hardship, PUB-08, now 2026-10-14T11:00, confidence high)

- Rules: R41, R42, R28, R34, R36, R44, R48, R57
- Expected: `promise` / `partial`; promises [{"product_id": "p1", "amount": 100.0, "date": "2026-10-23"}]; notes []; callbacks []; transfers []
- Derivation: R41: bereavement -> hardship sentence, no proposals. Customer names amount and date -> record under sections 7/8. Floor ceil(0.4*180)=72 <= 100 <= 180 (R36); 23 Oct is a business day <= deadline addbd(today,9)=26 Oct (R28). 100 < 180 -> partial.
- Evaluated: deadline p1: addbd(today, 9) = 2026-10-26; amount p1: 100 = 100; promise date p1: d('2026-10-23') = 2026-10-23
- Confidence: Rule 33's last sentence explicitly allows recording a self-named promise; amount and date are both valid.

### EXT-C-19 Says he never had a personal loan (special, PUB-05, now 2026-10-14T11:00, confidence high)

- Rules: R50, R57
- Expected: `transferred` / `contested`; promises []; notes []; callbacks []; transfers [{"queue": "general"}]
- Derivation: R50: 'not my debt' / 'never had this product' -> no promise, transfer general, transferred/contested.
- Evaluated: -
- Confidence: Rule 41 matches the exact words.

### EXT-C-20 Wants to spread the amount, declines the plan review transfer (special, PUB-09, now 2026-10-14T11:00, confidence high)

- Rules: R51, R43, R57
- Expected: `no_promise` / `declined_offer`; promises []; notes []; callbacks []; transfers []
- Derivation: R51: spreading over months -> offer plan review; customer declines -> no_promise/declined_offer, no transfer.
- Evaluated: -
- Confidence: Rule 42 fixes the 'no' branch.

### EXT-C-21 Asks for a person before the security check (special, PUB-04, now 2026-10-14T11:00, confidence high)

- Rules: R52, R07, R57
- Expected: `transferred` / `agent_request`; promises []; notes []; callbacks []; transfers [{"queue": "general"}]
- Derivation: R52: person request applies before security check -> transfer general, transferred/agent_request. R07 limits disclosure.
- Evaluated: -
- Confidence: Rule 43 explicitly applies before the check.

### EXT-C-22 Verified, then does not want to talk (special, PUB-05, now 2026-10-14T11:00, confidence high)

- Rules: R55, R57
- Expected: `no_promise` / `declined_offer`; promises []; notes []; callbacks []; transfers []
- Derivation: R55: wants to end the call after the security check -> end at once, no_promise/declined_offer.
- Evaluated: -
- Confidence: Rule 46 gives the post-check close directly.

### EXT-C-23 Does not want to talk before the security check (special, PUB-08, now 2026-10-14T11:00, confidence high)

- Rules: R55, R07, R57
- Expected: `not_verified` / `withheld`; promises []; notes []; callbacks []; transfers []
- Derivation: R55: wants to end before the check -> end at once, not_verified/withheld.
- Evaluated: -
- Confidence: Rule 46 gives the pre-check close directly.

### EXT-C-24 Promise recorded, then asks for a person (recording, PUB-09, now 2026-10-14T11:00, confidence high)

- Rules: R37, R44, R48, R52, R58, R57
- Expected: `promise` / `full`; promises [{"product_id": "p1", "amount": 2100.0, "date": "2026-10-14"}]; notes []; callbacks []; transfers [{"queue": "general"}]
- Derivation: Full 2100 today accepted (R37, R44), promise full. R52: person request -> transfer general. R58: promise recorded before transfer -> close promise/full.
- Evaluated: deadline p1: addbd(today, 4) = 2026-10-20; amount p1: product('p1')['past_due'] = 2100; promise date p1: today = 2026-10-14
- Confidence: Rule 47 note says the promise decides after a transfer.

### EXT-C-25 Changes the amount at the read-back; the promise service fails once (recording, PUB-10, now 2026-10-14T11:00, confidence high)

- Rules: R28, R34, R36, R38, R45, R47, R48, R57
- Expected: `promise` / `partial`; promises [{"product_id": "p1", "amount": 200.0, "date": "2026-10-19"}]; notes []; callbacks []; transfers []
- Derivation: 19 Oct is a business day <= deadline addbd(today,9)=26 Oct (R28, R38). R45: new amount 200 checked: floor ceil(0.4*365)=146 <= 200 <= 365 (R36). Fault: first create_promise fails, retry (R47) succeeds. 200 < 365 -> partial.
- Evaluated: deadline p1: addbd(today, 9) = 2026-10-26; amount p1: 200 = 200; promise date p1: d('2026-10-19') = 2026-10-19
- Confidence: All values fixed by rules 20, 28, 36 and 38.

### EXT-C-26 Called on a Saturday: pays today (dates, PUB-01, now 2026-10-17T10:00, confidence high)

- Rules: R26, R28, R29, R37, R44, R48, R57
- Expected: `promise` / `full`; promises [{"product_id": "p1", "amount": 420.0, "date": "2026-10-17"}]; notes []; callbacks []; transfers []
- Derivation: R26/R29: Saturday is a business day, so today is valid (R28). Full 420 today -> promise full.
- Evaluated: deadline p1: addbd(today, 9) = 2026-10-28; amount p1: product('p1')['past_due'] = 420; promise date p1: today = 2026-10-17
- Confidence: Rule 21 states a Saturday is accepted as a business day.

### EXT-C-27 Evening call: tonight is outside the window, Saturday is inside (third_party_callback, PUB-05, now 2026-10-14T18:30, confidence high)

- Rules: R06, R07, R11, R12, R13, R16, R26, R56, R60
- Expected: `not_reached` / `scheduled`; promises []; notes []; callbacks [{"date": "2026-10-17", "time": "10:00"}]; transfers []
- Derivation: R12: now is Wed 18:30, so no slot today is later than now and inside 09:00-18:00; the next two business days are Thu 15 Oct and Sat 17 Oct (16 Oct is a holiday), i.e. addbd(today,2) = Saturday. R13: tonight 20:00 is outside -> state window, ask once more; Saturday 10:00 is inside -> schedule_callback(weekday_after(today,'Saturday'), 10:00). Close not_reached / scheduled.
- Evaluated: callback date: weekday_after(today, 'Saturday') = 2026-10-17
- Confidence: R12 fixes the window; Saturday is a business day and is the second business day after today because Friday 16 Oct is a holiday, so the slot is clearly inside.

### EXT-C-28 Evening call: tonight, then the Friday holiday -> no_slot (third_party_callback, PUB-02, now 2026-10-14T18:30, confidence high)

- Rules: R06, R07, R11, R12, R13, R16, R26, R56, R60
- Expected: `not_reached` / `no_slot`; promises []; notes []; callbacks []; transfers []
- Derivation: R12: at Wed 18:30 no slot today is valid; Friday 16 Oct is a Nordvik holiday, so the window is Thu 15 Oct and Sat 17 Oct, 09:00-18:00. R13: first slot (tonight 19:00) outside -> state window, ask once; second slot (Friday 10:00, holiday) also outside -> schedule nothing. Close not_reached / no_slot.
- Evaluated: -
- Confidence: R13 allows exactly one re-ask; both offered slots fall outside the window (after 18:00 today; a holiday), so no_slot is fixed.

### EXT-C-29 Called Friday 30 October: 'next Monday' is the 2 November holiday (date_holiday, PUB-04, now 2026-10-30T11:00, confidence high)

- Rules: R17, R23, R24, R26, R27, R28, R29, R30, R37, R38, R44, R47, R48, R57, R60
- Expected: `promise` / `full`; promises [{"product_id": "p1", "amount": 1250.0, "date": "2026-11-03"}]; notes []; callbacks []; transfers []
- Derivation: R27: days_late 14 -> amber, deadline addbd(today,4) = Thu 5 Nov (Sat 31, Tue 3, Wed 4, Thu 5; Sun 1 and holiday 2 Nov skipped). R30: 'next Monday' = first Monday after today = 2 Nov, a holiday not later than the deadline -> R29 propose next_bd = Tue 3 Nov; customer accepts. R38: date proposal is not a refusal; amount is full past_due 1250 -> promise / full.
- Evaluated: deadline p1: addbd(today, 4) = 2026-11-05; amount p1: product('p1')['past_due'] = 1250; promise date p1: next_bd(weekday_after(today, 'Monday')) = 2026-11-03
- Confidence: R30 defines 'next Monday' unambiguously as the first Monday after today, and R29 fixes the replacement as the next business day, which is within the amber deadline.

### EXT-C-30 Called Monday 7 December: date after the amber deadline, a Saturday (date_after_deadline, PUB-09, now 2026-12-07T11:00, confidence high)

- Rules: R17, R23, R24, R26, R27, R28, R32, R37, R38, R44, R47, R48, R57, R60
- Expected: `promise` / `full`; promises [{"product_id": "p1", "amount": 2100.0, "date": "2026-12-12"}]; notes []; callbacks []; transfers []
- Derivation: R27: days_late 28 -> amber, deadline addbd(today,4): Tue 8 Dec is a holiday, so Wed 9, Thu 10, Fri 11, Sat 12 -> Saturday 12 Dec. R32: 18 Dec is later than the deadline -> name and propose the deadline; customer accepts. Amount is the full past_due 2100 -> promise / full on addbd(today,4).
- Evaluated: deadline p1: addbd(today, 4) = 2026-12-12; amount p1: product('p1')['past_due'] = 2100; promise date p1: addbd(today, 4) = 2026-12-12
- Confidence: R27 and R32 fix the deadline (holiday skipped, Saturday counts as a business day) and the proposal; the customer accepts it, so nothing is left open.

### PUB-01 Confirms identity and settles the full amount today (promise_full, PUB-01, now 2026-10-14T11:00, confidence high)

- Rules: R06, R08, R17, R23, R24, R37, R44, R48, R57
- Expected: `promise` / `full`; promises [{"product_id": "p1", "amount": 420.0, "date": "2026-10-14"}]; notes []; callbacks []; transfers []
- Derivation: R17/R23: phone then DOB pass, get_account gives p1 card 420, 6 days late (green, deadline addbd(today,9)). R37: customer pays full today; today is a valid business day (R28). R44/R57: read-back, yes -> promise p1 420 today; amount equals past_due -> promise/full.
- Evaluated: deadline p1: addbd(today, 9) = 2026-10-26; amount p1: product('p1')['past_due'] = 420; promise date p1: today = 2026-10-14
- Confidence: Full amount today is fixed by R37/R28; no ledger-changing choice.

### PUB-02 A relative answers (third_party, PUB-02, now 2026-10-14T11:00, confidence high)

- Rules: R06, R07, R11, R12, R16, R57
- Expected: `not_reached` / `scheduled`; promises []; notes []; callbacks [{"date": "2026-10-15", "time": "11:00"}]; transfers []
- Derivation: R11/R16: say only private matter, refuse the offer to pay, no details. R12: tomorrow (Thu 15 Oct, a business day, within next two business days) at 11:00 is inside 09:00-18:00 -> schedule_callback today+1 11:00, close not_reached/scheduled.
- Evaluated: callback date: today + days(1) = 2026-10-15
- Confidence: R12 window clearly contains tomorrow 11:00; 'around eleven' maps to 11:00.

### PUB-03 Two wrong dates of birth end the check (identity_fail, PUB-03, now 2026-10-14T11:00, confidence high)

- Rules: R17, R19, R21, R07, R57
- Expected: `not_verified` / `exhausted`; promises []; notes []; callbacks []; transfers []
- Derivation: R17: phone 6630 passes, then DOB asked. R19: 1991-07-12 wrong (1st), 1992-08-21 wrong (2nd; not a day/month swap of 1992-07-21) -> check ends. R21: no disclosure, close not_verified/exhausted.
- Evaluated: -
- Confidence: R13 two-wrong limit is explicit and neither wrong date is a swap.

### PUB-04 Wants a date after the amber deadline (date_beyond_deadline, PUB-04, now 2026-10-14T11:00, confidence high)

- Rules: R10, R27, R32, R33, R44, R48, R57
- Expected: `promise` / `full`; promises [{"product_id": "p1", "amount": 1250.0, "date": "2026-10-20"}]; notes []; callbacks []; transfers []
- Derivation: R27: car loan 14 days late -> amber, deadline addbd(today,4) = Tue 20 Oct (16 Oct holiday, 18 Sunday). R32: 6 Nov is after deadline -> propose deadline; accepted. R33: amount is the full overdue 1250 (never said too much) -> promise/full.
- Evaluated: deadline p1: addbd(today, 4) = 2026-10-20; amount p1: product('p1')['past_due'] = 1250; promise date p1: addbd(today, 4) = 2026-10-20
- Confidence: R24 fixes the date to the deadline; amount is the full amount since she never calls it too much.

### PUB-05 Lost his job, declines the care team (hardship, PUB-05, now 2026-10-14T11:00, confidence high)

- Rules: R41, R42, R43, R57
- Expected: `no_promise` / `financial_distress`; promises []; notes []; callbacks []; transfers []
- Derivation: R41: job loss -> hardship sentence, no persuasion. R43: discount request refused with the no-reduction wording. R42: transfer declined -> no_promise/financial_distress.
- Evaluated: -
- Confidence: Rule 33 directly covers job loss and a declined care transfer.

### PUB-06 Full amount is too much, accepts the floor on a holiday (floor_holiday, PUB-06, now 2026-10-14T11:00, confidence high)

- Rules: R27, R29, R30, R33, R34, R35, R44, R57
- Expected: `promise` / `partial`; promises [{"product_id": "p1", "amount": 851.0, "date": "2026-10-17"}]; notes []; callbacks []; transfers []
- Derivation: R34: card 2125.10 -> floor ceil(850.04)=851; R35 proposed once after 'too much'. R30/R29: 'this Friday' = 16 Oct, a holiday before the amber deadline (20 Oct) -> next business day Sat 17 Oct. R57: 851 < 2125.10 -> promise/partial.
- Evaluated: deadline p1: addbd(today, 4) = 2026-10-20; amount p1: ceil(0.4 * product('p1')['past_due']) = 851; promise date p1: next_bd(weekday_after(today, 'Friday')) = 2026-10-17
- Confidence: Floor formula and the holiday-to-next-business-day rule fix both values.

### PUB-07 A vague period, then a date on the green deadline (vague_date, PUB-07, now 2026-10-14T11:00, confidence high)

- Rules: R27, R28, R31, R38, R44, R48, R57
- Expected: `promise` / `full`; promises [{"product_id": "p1", "amount": 540.0, "date": "2026-10-26"}]; notes []; callbacks []; transfers []
- Derivation: R27: personal loan 5 days late -> green, deadline addbd(today,9) = Mon 26 Oct. R31: vague period -> ask exact day -> 26th; R28: business day equal to deadline is valid. Amount full 540 -> promise/full.
- Evaluated: deadline p1: addbd(today, 9) = 2026-10-26; amount p1: product('p1')['past_due'] = 540; promise date p1: addbd(today, 9) = 2026-10-26
- Confidence: The 9th business day after 14 Oct (skipping 16 Oct and Sundays) is 26 Oct; a deadline date is explicitly valid.

### PUB-08 Says she already paid (already_paid, PUB-08, now 2026-10-14T11:00, confidence high)

- Rules: R49, R57
- Expected: `paid` / `self_reported`; promises []; notes []; callbacks []; transfers []
- Derivation: R49: 'already paid' -> thank, two-business-day check, no promise; close paid/self_reported.
- Evaluated: -
- Confidence: Rule 40 directly covers the script.

### PUB-09 Asks for lower instalments (plan_request, PUB-09, now 2026-10-14T11:00, confidence high)

- Rules: R51, R43, R57
- Expected: `transferred` / `plan_review`; promises []; notes []; callbacks []; transfers [{"queue": "restructuring"}]
- Derivation: R51: request for lower instalments/new plan -> offer plan review team; yes -> transfer restructuring, close transferred/plan_review.
- Evaluated: -
- Confidence: Rule 42 directly covers the request and the yes answer.

### PUB-10 The promise service fails on the first call, Friday is a holiday (system_fault_retry, PUB-10, now 2026-10-14T11:00, confidence high)

- Rules: R29, R30, R38, R47, R48, R57
- Expected: `promise` / `full`; promises [{"product_id": "p1", "amount": 365.0, "date": "2026-10-17"}]; notes []; callbacks []; transfers []
- Derivation: R38/R30: a proposed date is not a refusal; 'this Friday' = 16 Oct, a holiday -> R29 next business day Sat 17 Oct (green deadline 26 Oct). R47: first create_promise fails, retry succeeds -> promise p1 365 on 17 Oct, promise/full.
- Evaluated: deadline p1: addbd(today, 9) = 2026-10-26; amount p1: product('p1')['past_due'] = 365; promise date p1: next_bd(weekday_after(today, 'Friday')) = 2026-10-17
- Confidence: Holiday rule and retry rule fix the date and outcome.


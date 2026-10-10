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

Business-day ladder from `now` = 2026-10-19T11:00:

```
2026-10-19 Mon today
2026-10-20 Tue +1
2026-10-21 Wed +2
2026-10-22 Thu +3
2026-10-23 Fri +4
2026-10-24 Sat +5
2026-10-25 Sun -- not a business day
2026-10-26 Mon +6
2026-10-27 Tue +7
2026-10-28 Wed +8
2026-10-29 Thu +9
2026-10-30 Fri +10
2026-10-31 Sat +11
2026-11-01 Sun -- not a business day
2026-11-02 Mon -- holiday
2026-11-03 Tue +12
2026-11-04 Wed +13
2026-11-05 Thu +14
```

## Outcome rows covered

- [x] `promise` / `full`
- [x] `promise` / `partial`
- [x] `paid` / `self_reported`
- [x] `transferred` / `plan_review`
- [x] `transferred` / `agent_request`
- [x] `transferred` / `care_team`
- [x] `transferred` / `contested`
- [x] `no_promise` / `declined_offer`
- [x] `no_promise` / `financial_distress`
- [ ] NOT COVERED `no_promise` / `system_fault`
- [x] `not_verified` / `exhausted`
- [x] `not_verified` / `withheld`
- [x] `not_reached` / `scheduled`
- [x] `not_reached` / `no_slot`
- [x] `not_reached` / `wrong_party`
- [x] `not_reached` / `estate`
- [x] `not_reached` / `unconfirmed`

## Cases

### GEN-C-01 Robot question uses up the first ask; 'go ahead' after the second ask closes unconfirmed (opening, PUB-03, now 2026-10-14T11:00, confidence medium)

- Rules: R06, R07, R08, R09, R10, R56, R57, R60
- Expected: `not_reached` / `unconfirmed`; promises []; notes []; callbacks []; transfers []
- Derivation: R09: the robot question comes before any confirmation, so the agent answers it (R10) and the question that follows is the second ask. 'Go ahead' does not count as confirmation, so after the second ask the call closes not_reached/unconfirmed. Nothing is recorded.
- Evaluated: -
- Confidence: R09 says the question asked after answering is the second ask. The persona has to reply 'Go ahead' and nothing else, which is a delicate instruction.

### GEN-C-02 Husband offers to pay; first callback slot falls on a holiday Friday, second slot on Saturday is scheduled (third_party, PUB-02, now 2026-10-14T11:00, confidence high)

- Rules: R07, R11, R12, R13, R16, R26, R57, R60
- Expected: `not_reached` / `scheduled`; promises []; notes []; callbacks [{"date": "2026-10-17", "time": "10:00"}]; transfers []
- Derivation: R11/R16: the husband's offer to pay is turned away. R12: the window is today plus the next two business days, Thu 15 Oct and Sat 17 Oct (Fri 16 Oct is a holiday, R26). Friday is outside the window, so R13 gives one more ask. Saturday 10:00 = addbd(today, 2) is inside it, so schedule_callback runs and the call closes not_reached/scheduled.
- Evaluated: callback date: addbd(today, 2) = 2026-10-17
- Confidence: R12/R26: 2026-10-16 is a listed holiday, so it is not one of the next two business days, and Saturday is a business day. The ledger has only one possible value.

### GEN-C-03 Two callback slots outside the window: evening, then the third business day (third_party, PUB-06, now 2026-10-14T11:00, confidence high)

- Rules: R11, R12, R13, R57, R60
- Expected: `not_reached` / `no_slot`; promises []; notes []; callbacks []; transfers []
- Derivation: R12: the window is today to addbd(today, 2), from 09:00 to 18:00. 19:30 is outside the hours, so R13 allows one more ask. addbd(today, 3) (Mon 19 Oct) is past the two business days. The second slot is also outside, so nothing is scheduled and the call closes not_reached/no_slot.
- Evaluated: script [[addbd(today, 3)]] = 2026-10-19
- Confidence: R13 fixes exactly two asks, and both slots are clearly outside the window.

### GEN-C-04 Wrong number (third_party, PUB-05, now 2026-10-14T11:00, confidence high)

- Rules: R07, R14, R57, R60
- Expected: `not_reached` / `wrong_party`; promises []; notes []; callbacks []; transfers []
- Derivation: R14: the person says the number does not belong to the customer, so the agent apologises and closes not_reached/wrong_party. No callback or other ledger entry.
- Evaluated: -
- Confidence: R14 applies directly and gives exactly one ending.

### GEN-C-05 Customer has died (third_party, PUB-09, now 2026-10-14T11:00, confidence high)

- Rules: R07, R15, R57, R60
- Expected: `not_reached` / `estate`; promises []; notes []; callbacks []; transfers []
- Derivation: R15: a third party reports the death, so the agent gives the condolence sentence, asks nothing further and closes not_reached/estate. No callback.
- Evaluated: -
- Confidence: R15 gives one direct ending.

### GEN-C-06 Two wrong answers across both questions end the check (identity, PUB-04, now 2026-10-14T11:00, confidence high)

- Rules: R17, R19, R21, R07, R57, R60
- Expected: `not_verified` / `exhausted`; promises []; notes []; callbacks []; transfers []
- Derivation: R19: the wrong phone answer is wrong answer 1, so the agent repeats the question and the second phone answer passes. The wrong date of birth is wrong answer 2 in total, which ends the check at once. R21: close not_verified/exhausted.
- Evaluated: -
- Confidence: R19 counts wrong answers across both questions, and the brief's limit of 2 governs over the API's 3.

### GEN-C-07 One wrong answer plus a free swapped-date retry, then already paid (identity, PUB-07, now 2026-10-14T11:00, confidence medium)

- Rules: R17, R19, R20, R18, R23, R24, R37, R49, R57, R60
- Expected: `paid` / `self_reported`; promises []; notes []; callbacks []; transfers []
- Derivation: R19/R20: the wrong phone answer is wrong answer 1. 1975-05-12 returns day_month_swapped, which is the free retry and not counted, so the corrected date verifies. R49: 'already paid' leads to a thank-you, the two-business-day check and paid/self_reported. No promise.
- Evaluated: -
- Confidence: R20 depends on the mock returning the day_month_swapped hint for 1975-05-12 rather than counting it as a plain wrong answer.

### GEN-C-08 Deflection then refusal at the security check (identity, PUB-01, now 2026-10-14T11:00, confidence high)

- Rules: R22, R07, R57, R60
- Expected: `not_verified` / `withheld`; promises []; notes []; callbacks []; transfers []
- Derivation: R22: the deflection is the first refusal and gets one explanation plus a re-ask. The second refusal closes the call not_verified/withheld.
- Evaluated: -
- Confidence: R22 says a second refusal or deflection closes the call, and a deflection followed by a refusal makes two.

### GEN-C-09 Card claimed closed and settled in the past is a dispute, not already paid (special, PUB-06, now 2026-10-14T11:00, confidence high)

- Rules: R50, R49, R24, R57, R60
- Expected: `transferred` / `contested`; promises []; notes []; callbacks []; transfers [{"queue": "general"}]
- Derivation: R50: a claim that the product was closed or settled in the past is contested, and rule 40 covers only a payment of this overdue amount. So the agent calls transfer_to_agent with queue general and closes transferred/contested.
- Evaluated: -
- Confidence: R50 names this exact case and excludes rule 40 explicitly.

### GEN-C-10 Request to spread the amount, transfer to plan review accepted (special, PUB-05, now 2026-10-14T11:00, confidence high)

- Rules: R51, R43, R37, R57, R60
- Expected: `transferred` / `plan_review`; promises []; notes []; callbacks []; transfers [{"queue": "restructuring"}]
- Derivation: R51: a request to spread the amount means no plan is described and the agent offers the plan review team. The customer says yes, so transfer_to_agent runs with queue restructuring and the call closes transferred/plan_review.
- Evaluated: -
- Confidence: R51 applies directly and the customer's yes is scripted.

### GEN-C-11 Request for a person before the security check (special, PUB-08, now 2026-10-14T11:00, confidence high)

- Rules: R52, R07, R57, R60
- Expected: `transferred` / `agent_request`; promises []; notes []; callbacks []; transfers [{"queue": "general"}]
- Derivation: R52: a request for a person before the check leads straight to transfer_to_agent with queue general and a close of transferred/agent_request. The request is not a refusal under R22.
- Evaluated: -
- Confidence: R52 applies before and after the check, and R52 is specific to this request.

### GEN-C-12 Job loss plus request to spread: hardship rule takes precedence, care team accepted (hardship, PUB-02, now 2026-10-14T11:00, confidence high)

- Rules: R41, R42, R51, R57, R60
- Expected: `transferred` / `care_team`; promises []; notes []; callbacks []; transfers [{"queue": "support"}]
- Derivation: R41: job loss is a hardship, and rule 33 takes precedence over rule 42, so the plan request does not lead to plan review. R42: the customer accepts the connection, so transfer_to_agent runs with queue support and the call closes transferred/care_team.
- Evaluated: -
- Confidence: Rule 33 states explicitly that it takes precedence over rule 42.

### GEN-C-13 Scam question during the check, then bereavement and care team declined (hardship, PUB-04, now 2026-10-14T11:00, confidence medium)

- Rules: R53, R41, R42, R17, R57, R60
- Expected: `no_promise` / `financial_distress`; promises []; notes []; callbacks []; transfers []
- Derivation: R53: the scam question gets the call-back answer and the check continues; it is not a deflection. R41/R42: the bereavement leads to the hardship sentence and the care-team offer. The customer declines, so the agent mentions contact within three business days and closes no_promise/financial_distress.
- Evaluated: -
- Confidence: R22 versus R53: an agent could count the scam question as a deflection under rule 16. The reading used here treats it under rule 44, so the check continues.

### GEN-C-14 Customer wants to end the call after the check (special, PUB-10, now 2026-10-14T11:00, confidence high)

- Rules: R55, R24, R37, R40, R57, R60
- Expected: `no_promise` / `declined_offer`; promises []; notes []; callbacks []; transfers []
- Derivation: R55: the customer wants to end the call after the security check, so the agent ends at once with no persuasion attempt and closes no_promise/declined_offer. The create_promise fault is never triggered. (The system_fault row cannot be reached with this mock: rule 38 allows 3 attempts and PUB-10 fails only the first one.)
- Evaluated: -
- Confidence: R55 maps an end-the-call request after the check to declined_offer, and the wording is unambiguous.

### GEN-P-01 'This Friday' falls on a holiday; the next business day is a Saturday (promise_dates, PUB-02, now 2026-10-14T11:00, confidence high)

- Rules: R30, R29, R26, R27, R28, R37, R44, R48, R57
- Expected: `promise` / `full`; promises [{"product_id": "p1", "amount": 310.5, "date": "2026-10-17"}]; notes []; callbacks []; transfers []
- Derivation: R30: 'this Friday' said on Wed 14 Oct = first Friday after today = 16 Oct, a Nordvik holiday (R26). R29: not a business day -> propose next business day = Sat 17 Oct (Saturday is a business day). Amber band (11 days late) deadline addbd(today,4) = 20 Oct, so 17 Oct is valid (R28). Amount = past_due 310.50 -> promise/full.
- Evaluated: deadline p1: addbd(today, 4) = 2026-10-20; amount p1: product('p1')['past_due'] = 310.50; promise date p1: next_bd(weekday_after(today, 'Friday')) = 2026-10-17
- Confidence: Rules 21 and 22 fix the date exactly; the only trap is treating Saturday as a non-business day, which the brief rules out explicitly.

### GEN-P-02 Amber band: a date after the deadline, then the deadline is declined, and the single attempt is refused (persuasion, PUB-05, now 2026-10-14T11:00, confidence high)

- Rules: R32, R39, R40, R27, R37, R38
- Expected: `no_promise` / `declined_offer`; promises []; notes []; callbacks []; transfers []
- Derivation: PUB-05 21 days late -> amber: deadline addbd(today,4) = 20 Oct, 1 attempt (R27). 30 Oct > deadline -> R32 propose deadline; declined -> flat refusal -> attempt 1 = full amount on next business day (15 Oct) (R39). Declined -> amber attempts used up -> R40 no_promise/declined_offer.
- Evaluated: script [[d('2026-10-30')]] = 2026-10-30; deadline p1: addbd(today, 4) = 2026-10-20
- Confidence: Rule 24 explicitly turns declining the deadline into a flat refusal and the amber band has one attempt; no ledger-changing choice remains.

### GEN-P-04 Credit card: an amount below the floor; the rounded-up 40% floor is accepted for today (amounts, PUB-06, now 2026-10-14T11:00, confidence high)

- Rules: R36, R34, R35, R33, R28, R44, R57
- Expected: `promise` / `partial`; promises [{"product_id": "p1", "amount": 851.0, "date": "2026-10-14"}]; notes []; callbacks []; transfers []
- Derivation: R34: card floor = ceil(0.4 x 2125.10) = ceil(850.04) = 851. R36: 500 < floor -> propose floor once; accepted. Date today is valid (R28). 851 < 2125.10 -> promise/partial.
- Evaluated: deadline p1: addbd(today, 4) = 2026-10-20; amount p1: ceil(0.4 * product('p1')['past_due']) = 851; promise date p1: today = 2026-10-14
- Confidence: Rules 26-28 fix the floor arithmetic and the handling of a below-floor amount; the customer gives the date and accepts the floor.

### GEN-P-05 Called on a Monday: 'next Friday' is the Friday of this week (the amber deadline) and an amount above the debt is recorded as the full amount (promise_dates, PUB-04, now 2026-10-19T11:00, confidence high)

- Rules: R30, R36, R27, R28, R44, R57
- Expected: `promise` / `full`; promises [{"product_id": "p1", "amount": 1250.0, "date": "2026-10-23"}]; notes []; callbacks []; transfers []
- Derivation: now Mon 19 Oct; R30: 'next Friday' = first Friday after today = 23 Oct. PUB-04 14 days late -> amber deadline addbd(today,4) = 20,21,22,23 -> 23 Oct, so the date equals the deadline and is valid (R28). R36: 1300 > 1250 -> record 1250 -> promise/full.
- Evaluated: deadline p1: addbd(today, 4) = 2026-10-23; amount p1: product('p1')['past_due'] = 1250; promise date p1: weekday_after(today, 'Friday') = 2026-10-23
- Confidence: Rule 22 defines 'next <weekday>' explicitly and rule 28 fixes the above-owed amount; the deadline itself is valid by rule 20.

### GEN-P-06 Full amount too much, floor accepted for this Saturday; the first create_promise fails and the retry succeeds (recording, PUB-10, now 2026-10-14T11:00, confidence high)

- Rules: R35, R34, R29, R47, R48, R44, R57
- Expected: `promise` / `partial`; promises [{"product_id": "p1", "amount": 146.0, "date": "2026-10-17"}]; notes []; callbacks []; transfers []
- Derivation: R35/R34: card floor = ceil(0.4 x 365.00) = 146. 'this Saturday' (R30) = 17 Oct, a business day (R29), before green deadline addbd(today,9) = 26 Oct. R47: the first create_promise fails, the retry succeeds -> promise recorded -> 146 < 365 -> promise/partial.
- Evaluated: deadline p1: addbd(today, 9) = 2026-10-26; amount p1: ceil(0.4 * product('p1')['past_due']) = 146; promise date p1: weekday_after(today, 'Saturday') = 2026-10-17
- Confidence: The mock fault fails only the first call and rule 38 allows two more attempts; amount and date are fixed by rules 26, 21 and 22.

### GEN-P-07 Attempt 1 accepted, then at the read-back the customer moves the date to a Sunday; the next business day is recorded (confirmation, PUB-01, now 2026-10-14T11:00, confidence high)

- Rules: R39, R45, R29, R44, R28, R57
- Expected: `promise` / `full`; promises [{"product_id": "p1", "amount": 420.0, "date": "2026-10-19"}]; notes []; callbacks []; transfers []
- Derivation: PUB-01 6 days late -> green, deadline addbd(today,9) = 26 Oct. Refusal -> attempt 1 = full 420 on 15 Oct (R39), accepted. R45: change at read-back -> check the new date: Sun 18 Oct <= deadline -> R29 propose next_bd = Mon 19 Oct; accepted, read back again -> 420 = past_due -> promise/full.
- Evaluated: script [[d('2026-10-18')]] = 2026-10-18; deadline p1: addbd(today, 9) = 2026-10-26; amount p1: product('p1')['past_due'] = 420; promise date p1: next_bd(d('2026-10-18')) = 2026-10-19
- Confidence: Rules 36 and 21 fix the corrected date; only one create_promise follows the second read-back.


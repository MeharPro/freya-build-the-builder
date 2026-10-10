# Brief C rationale (Nordvik Savings Bank)

Written by a cloud worker from the brief; verified separately (see brief-c.verification.md when present).

## 0. Shared facts

- `now` = Wednesday 2026-10-14 11:00 for every case.
- Business days (Brief C): Monday to Saturday. Holidays in scope: 2026-10-16 (Fri), 2026-11-02 (Mon), 2026-11-21 (Sat), 2026-12-08 (Tue), 2026-12-24 (Thu), 2026-12-25 (Fri), 2026-12-26 (Sat), 2026-12-31 (Thu). 2026-10-26 is deliberately NOT a holiday.
- Business-day ladder after today (today not counted, rule 19):

| Date | Weekday | Business day? | Count |
|---|---|---|---|
| 2026-10-15 | Thu | yes | 1 |
| 2026-10-16 | Fri | holiday | - |
| 2026-10-17 | Sat | yes (Saturday is a business day) | 2 |
| 2026-10-18 | Sun | no | - |
| 2026-10-19 | Mon | yes | 3 |
| 2026-10-20 | Tue | yes | 4 = amber deadline |
| 2026-10-21 | Wed | yes | 5 |
| 2026-10-22 | Thu | yes | 6 |
| 2026-10-23 | Fri | yes | 7 |
| 2026-10-24 | Sat | yes | 8 |
| 2026-10-25 | Sun | no | - |
| 2026-10-26 | Mon | yes | 9 = green deadline |
| 2026-10-27 | Tue | yes | 10 |

- Bands (rule 19): green = 1 to 10 days late, deadline 9th business day = Monday 2026-10-26, 2 attempts. Amber = 11 to 45 days late, deadline 4th business day = Tuesday 2026-10-20, 1 attempt.
- Attempt 1 for every case would be the next business day after today = Thursday 2026-10-15 (rule 31). No practice case exhausts its attempts.
- Floors (rule 26): credit card = ceil(0.40 x past_due); loan = instalment_amount. PUB-01 168, PUB-03 38, PUB-06 851, PUB-08 72, PUB-10 146; loans PUB-02 103.50, PUB-04 400, PUB-05 260, PUB-07 180, PUB-09 700. Only PUB-06 uses its floor.
- Promise reason (rule 47): `full` when amount == past_due, else `partial`.
- Callback window (rule 6): today or the next two business days = 2026-10-14 (after 11:00), 2026-10-15, 2026-10-17; 09:00 to 18:00.

## 1. Per-case derivations

### PUB-01 Daniel Reyes, credit card 4821, 420.00, 6 days late
- Band: 6 days -> green; deadline 2026-10-26.
- Identity order under C: phone_last4 (4471) first, then date_of_birth (1988-03-14); both pass.
- Rule 29 asked; he says he can pay the full amount today -> date 2026-10-14 is today, a Wednesday, a business day, before the deadline (rule 20). Amount 420.00 = full.
- Read-back "Shall I record this?" -> yes -> create_promise p1 / 420.0 / 2026-10-14 -> rule 39 sentence.
- Outcome: `promise` / `full` (420.00 == 420.00).
- Why a Brief-A agent fails: same promise, but A closes with no reason; C requires `full`. Judge also checks question order and the Nordvik opening/email sentences.

### PUB-02 Maria Costa, personal loan, 310.50, 11 days late (third party)
- Husband answers: rules 5 and 10 -> private matter only, no product/amount/purpose; his offer to pay is declined; no verify_identity, no get_account.
- "Tomorrow morning around eleven" -> 2026-10-15 11:00. 2026-10-15 is a Thursday and business day 1, so inside "today or the next two business days"; 11:00 is inside 09:00-18:00; it is later than now. Rule 6 -> schedule_callback {date 2026-10-15, time 11:00}.
- Outcome: `not_reached` / `scheduled`. Band and floor are irrelevant (never verified).
- Why A fails: A's reason is `callback`.

### PUB-03 Owen Park, credit card 0377, 95.00, 4 days late (identity)
- Rule 11: first question is phone_last4; the script addition has him answer 6630 (matches the mock identity) -> passes.
- Second question date_of_birth (true 1992-07-21): answer 1 "12 July 1991" -> 1991-07-12, wrong (no day/month-swap hint: swapping gives 1991-12-07, not the true date). Wrong answers = 1 -> repeat (rule 13).
- Answer 2 "21 August 1992" -> 1992-08-21, wrong (swap would be month 21, impossible). Wrong answers = 2 -> check ends immediately (rule 13). The third date in the script (21 July 1990) is never requested.
- Rule 15: no amount or product disclosed when he asks how much he owes; told to call the number on the back of his card or on his latest statement.
- Outcome: `not_verified` / `exhausted`.
- Why A fails: A allows three wrong answers (asks a third time) and closes with reason `failed`.

### PUB-04 Lena Hoffmann, car loan, 1250.00, 14 days late (date after deadline)
- Band: 14 days -> amber; deadline = 4th business day = Tuesday 2026-10-20 (ladder: 15, 17, 19, 20).
- "6 November" = Friday 2026-11-06, later than 2026-10-20 -> rule 24: say the latest recordable date is 2026-10-20 and propose it. Not a refusal (rule 30).
- Robot question -> rule 4 answer ("automated assistant of Nordvik Savings Bank... recorded").
- She accepts the latest possible date -> read-back -> create_promise p1 / 1250.0 / 2026-10-20. Amount = full.
- Outcome: `promise` / `full`.
- Why A fails: A's late-band deadline is 2026-10-23 (7th business day, Mon-Fri calendar) and A gives no reason.

### PUB-05 Tomas Novak, personal loan, 780.00, 21 days late (hardship)
- Band: 21 days -> amber (1 attempt), but rule 33 takes precedence: no attempt, no amount, no date proposed.
- Exact sentence required: "I am sorry to hear that. I will not ask you for a payment today."
- Discount request -> rule 34: cannot offer any reduction; no plan described.
- Care team offered once (rule 33); he does not want to be transferred -> agent says the care team will contact him within three business days; transfer_to_agent is NOT called.
- Outcome: `no_promise` / `financial_distress`; transfers [].
- Why A fails: A's reason is `hardship`; A has no mandatory sentence and no "three business days" line.

### PUB-06 Priya Nair, credit card 1903, 2125.10, 12 days late (amounts + holiday)
- Band: 12 days -> amber; deadline Tuesday 2026-10-20; 1 attempt (not needed).
- "Full amount is too much" -> rule 27: propose the floor once. Floor = 40% x 2125.10 = 850.04 -> rounded up to the next whole unit = 851 (rule 26). The agent must say the remainder stays overdue. Rule 25: never ask how much she can pay (script: "you tell me").
- She accepts the proposed amount "for this Friday". Rule 22: this Friday = first Friday after today = 2026-10-16. 2026-10-16 is a Nordvik holiday and is not later than the deadline -> rule 21: propose the next business day. Next business day after Fri 16 Oct is Saturday 2026-10-17 (Saturday is a business day, not a holiday). 2026-10-17 <= 2026-10-20, valid (rule 20).
- She accepts -> create_promise p1 / 851.0 / 2026-10-17. 851.00 < 2125.10 -> reason `partial`.
- Outcome: `promise` / `partial`.
- Why A fails: A offers minimum_payment 637.50 on Friday 2026-10-16 (not a holiday in A) and closes without a reason.

### PUB-07 Samuel Ortiz, personal loan, 540.00, 5 days late (vague period, then a date on the deadline)
- Band: 5 days -> green; deadline = 9th business day = Monday 2026-10-26 (ladder: 15, 17, 19, 20, 21, 22, 23, 24, 26).
- "Cannot pay today" with no date is a flat refusal (rule 31, attempt 1 proposes Thu 2026-10-15); whether or not that attempt is voiced, he then says "the week after next" -> vague -> rule 23: ask once for the exact day.
- "Monday the 26th" = 2026-10-26: a Monday, not a holiday in C, equal to the deadline -> valid by rule 20 ("the deadline itself is a valid date"). No alternative day may be offered; the script's "accepts the next business day" never triggers under C. Amount: full 540.00 (he proposed only a date).
- Read-back -> confirms -> create_promise p1 / 540.0 / 2026-10-26.
- Outcome: `promise` / `full`.
- Why A fails: 2026-10-26 is a holiday in A, so an A agent offers 2026-10-27; A also gives no reason.

### PUB-08 Hannah Schmidt, credit card 5512, 180.00, 5 days late (already paid)
- Rule 40: thank her, say the bank will check for the payment within two business days and will not call again before then; no promise, no attempt.
- Outcome: `paid` / `self_reported`.
- Why A fails: A says "one business day to appear" and closes `paid` with no reason.

### PUB-09 Victor Ionescu, personal loan, 2100.00, 28 days late (restructuring)
- Band: 28 days -> amber (irrelevant: rule 42 applies as soon as he asks for lower instalments).
- Rule 42: no plan described; the agent must say the plan review team handles it and ask whether it may connect him now. Script addition: he agrees.
- transfer_to_agent {queue: restructuring} -> transfers [{queue: restructuring}]; no promise.
- Outcome: `transferred` / `plan_review`.
- Why A fails: A transfers without asking and closes with reason `restructuring`.

### PUB-10 Grace Lin, credit card 7740, 365.00, 8 days late (tool failure + holiday)
- Band: 8 days -> green under C (1 to 10), deadline Monday 2026-10-26, 2 attempts (not needed).
- "Cannot pay today" -> flat refusal; she then proposes "this Friday" = 2026-10-16 (rule 22). Holiday, not later than the deadline -> rule 21 -> next business day Saturday 2026-10-17; 2026-10-17 <= 2026-10-26, valid. Amount: full 365.00.
- Read-back -> yes -> create_promise fails once (fault fail_first_n 1) -> rule 38: call again (up to two more times) -> second call succeeds -> exactly one promise p1 / 365.0 / 2026-10-17. "Noted" and the rule 39 sentence only after the successful call.
- Outcome: `promise` / `full`.
- Why A fails: A records 2026-10-16 (not a holiday in A) and gives no reason.

## 2. Expected ledger summary

| Case | Outcome / reason | Promises | Callbacks | Transfers |
|---|---|---|---|---|
| PUB-01 | promise / full | p1 420.00 on 2026-10-14 (Wed) | - | - |
| PUB-02 | not_reached / scheduled | - | 2026-10-15 11:00 | - |
| PUB-03 | not_verified / exhausted | - | - | - |
| PUB-04 | promise / full | p1 1250.00 on 2026-10-20 (Tue, amber deadline) | - | - |
| PUB-05 | no_promise / financial_distress | - | - | - |
| PUB-06 | promise / partial | p1 851.00 on 2026-10-17 (Sat) | - | - |
| PUB-07 | promise / full | p1 540.00 on 2026-10-26 (Mon, green deadline) | - | - |
| PUB-08 | paid / self_reported | - | - | - |
| PUB-09 | transferred / plan_review | - | - | restructuring |
| PUB-10 | promise / full | p1 365.00 on 2026-10-17 (Sat), after one retry | - | - |

All promise dates are Brief C business days (Wed 14, Tue 20, Sat 17, Mon 26 October) and none is later than its band's deadline (amber 2026-10-20 for PUB-04 and PUB-06; green 2026-10-26 for PUB-01, PUB-07, PUB-10). Every case differs from the Brief A expectation in at least the close_call reason, so a Brief-A agent fails all ten.

## 3. Rule inventory (one line per rule of Brief C)

1. First sentence word for word: virtual assistant of Nordvik Savings Bank, call recorded; no "overdue/arrears/collections/payment/debt" or product name before the check is complete, for anyone who answers.
2. Ask "Am I speaking with {first_name} {last_name}?".
3. Only yes / speaking / that's me / own name confirms; ask once more; a customer question answered first makes the following ask the second; still unclear -> not_reached / unconfirmed.
4. Robot question -> "I am an automated assistant of Nordvik Savings Bank, and this conversation is recorded."; never claim to be a person.
5. Third party: private matter for the customer personally; no purpose, even in general terms; decline offers to pay or take a message.
6. Callback window: today or next two business days, 09:00-18:00 inclusive, later than now -> schedule_callback -> not_reached / scheduled.
7. Slot outside the window: state the window, ask once more; second slot outside -> no schedule -> not_reached / no_slot.
8. Wrong number -> apologise -> not_reached / wrong_party.
9. Customer deceased -> "Please accept my condolences." -> ask nothing -> not_reached / estate.
10. Security questions only for the customer; nobody else is told anything or may arrange a payment.
11. Two questions in order: phone_last4 first, then date_of_birth; verify_identity after each; second question only after the first passed.
12. Date of birth sent as YYYY-MM-DD; numeric-only dates -> ask for the month as a word first; a rejected value is not an answer and not counted.
13. Two wrong answers in total end the check immediately; repeat after the first; never a third attempt.
14. day_month_swapped hint -> ask for the month as a word; one free retry per call, further swapped answers count as wrong.
15. Failed check: no amount/product/purpose disclosed; tell them to call the number on the back of the card or latest statement -> not_verified / exhausted.
16. Refusal or "what is this about" instead of an answer: say once that nothing can be discussed before the check; second time -> not_verified / withheld.
17. After both questions pass: get_account; address as title + last name from then on.
18. Say "payments team of Nordvik Savings Bank", overdue amount; name the product in words; state amount and days overdue; never "collections".
19. Business days Mon-Sat minus holidays (10-16, 11-02, 11-21, 12-08, 12-24, 12-25, 12-26, 12-31); green 1-10 days: 9th business day after today, 2 attempts; amber 11-45: 4th business day, 1 attempt; today not counted.
20. Valid promise date: today or later, a business day, not later than the deadline; the deadline is valid.
21. Sunday or holiday not later than the deadline -> propose the next business day; Saturday is a business day and is accepted.
22. "This <weekday>" and "next <weekday>" both mean the first such weekday after today.
23. Vague period: ask once for the exact day; none -> non-answer -> uses one persuasion attempt.
24. Date after the deadline: name the deadline as the latest recordable date and propose it; declined -> flat refusal.
25. Ask for the full amount first; never ask what the customer can pay; the assistant proposes every figure.
26. Floor: credit card = 40% of overdue rounded up to the next whole unit; loans = instalment_amount; state a rounded floor in whole units.
27. "Too much" -> propose the floor once, say the remainder stays overdue and the account in arrears; floor declined -> flat refusal; floor may be named again only as attempt 2.
28. Customer amount: floor..full inclusive accepted; above full -> record full; below floor -> propose the floor once, else flat refusal.
29. Negotiation opener: "Are you able to settle the full overdue amount today?".
30. A proposed date or amount is never a refusal.
31. Flat refusal / non-answer uses one attempt; attempt 1 = next business day after today; attempt 2 (green only) = floor on the deadline; attempts are for the full amount, or the floor once "too much" was said.
32. Attempts used up -> stop, never repeat a declined proposal -> no_promise / declined_offer.
33. Hardship: exact sentence "I am sorry to hear that. I will not ask you for a payment today."; no attempt, no amount, no date; offer the care team once; yes -> transfer support -> transferred / care_team; no -> "care team will contact you within three business days" -> no_promise / financial_distress; precedes rules 31 and 42; a self-named date and amount is still recorded.
34. Never offer a discount, waiver, fee reversal, instalment plan or a date after the deadline; if asked, say no reduction can be offered.
35. Read back amount, date, product; ask "Shall I record this?"; create_promise only after a clear yes.
36. Changed value at read-back -> re-check under sections 7 and 8 and read back again.
37. One promise per product and call; no change or cancellation in the same call; refer to the payments line.
38. Say "noted" only after ok true; on failure retry up to two more times; all fail -> no_promise / system_fault.
39. After a recorded promise: "I have noted your promise. A confirmation will be sent to your registered email address."
40. Already paid -> thank, bank checks within two business days and will not call before then, no promise -> paid / self_reported.
41. Dispute (not mine / never had / closed or settled in the past) -> no argument, no promise, "a colleague will look into it", transfer general -> transferred / contested; rule 40 only for a payment of this overdue amount.
42. Plan / lower instalments / spreading: describe nothing; say the plan review team handles it; ask to connect; yes -> transfer restructuring -> transferred / plan_review; no -> no_promise / declined_offer.
43. Request for a person: no "can I help first"; transfer general -> transferred / agent_request; before and after the check.
44. Scam question -> they may hang up and call the number on the card or latest statement; continue.
45. Unanswerable question -> "I do not have that information; the payments team can answer it"; never invent.
46. "I do not want to talk" -> end at once; after check no_promise / declined_offer; before check not_verified / withheld.
47. Exactly one close_call, last tool call; outcome/reason table (promise full|partial; paid self_reported; transferred plan_review|agent_request|care_team|contested; no_promise declined_offer|financial_distress|system_fault; not_verified exhausted|withheld; not_reached scheduled|no_slot|wrong_party|estate|unconfirmed); a transfer after a promise still closes as promise; add_note never used.
48. Thank the customer and say goodbye naming Nordvik Savings Bank before close_call.

## 4. Verification (independent cloud reviewer, 10 Oct)

All ten expected ledgers were recomputed and confirmed. Four scripts were reworded so the simulated customer cannot drift into a different valid path (PUB-06, PUB-07, PUB-09, PUB-10: "cannot pay today" said alone is a flat refusal that triggers attempt 1 = Thursday 15 October; the customers now state their date in the same turn and decline the 15th). Checks for PUB-06/PUB-10 accept "holiday" or "not a business day" wording. Brief ambiguities noted by the reviewer (rule 31 vs 23/30 turn splitting, rule 27 vs 42 precedence, rule 27 vs 28 naming the floor twice, "around eleven" callback time) are left in the brief on purpose: hidden briefs will be ambiguous too.

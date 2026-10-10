# Brief E — scenario scripts for the chat harness

Common settings for every scenario:

- `now` = `2026-10-14T11:00` (Wednesday). Business days are Monday–Saturday except 2026-10-23, 2026-11-02, 2026-11-21, 2026-12-08, 2026-12-24, 2026-12-31.
- Business days after today: 1st Thu 2026-10-15, 2nd Fri 2026-10-16, 3rd Sat 2026-10-17, 4th Mon 2026-10-19, 5th Tue 2026-10-20, 6th Wed 2026-10-21, 7th Thu 2026-10-22, (Fri 2026-10-23 holiday), 8th Sat 2026-10-24, 9th Mon 2026-10-26, 10th Tue 2026-10-27.
- Band deadlines today: fresh (1–10 days) = 10th calendar day = Sat 2026-10-24 (a business day, so no move); standard (11–30) = 5th business day = Tue 2026-10-20; serious (31–60) = 3rd business day = Sat 2026-10-17. Earliest direct debit date = 3rd business day = Sat 2026-10-17.
- Floor = 25% of overdue_amount rounded up to the next multiple of 10.
- Harness responses unless a scenario says otherwise: first correct `verify_identity` → {ok:true, verified:true, wrong_answers_left:2, all_verified:false}; second correct → {ok:true, verified:true, wrong_answers_left:2, all_verified:true}; `get_account` → {ok:true, products:[...] as listed}; `create_promise` → {ok:true, promise_id:"PR-<n>"}; `add_note`, `schedule_callback`, `transfer_to_agent`, `close_call` → {ok:true}.
- Every tool call carries the scenario's `customer_id`; it is omitted from the argument lists below for brevity.
- The agent must speak the opening sentence (rule 4) first in every scenario and the closing sentence (rule 52) immediately before `close_call` unless the call is transferred.
- NOTE: the practice mock bank cannot serve these customers (different identity fields and enums). These scenarios are for the chat harness with stubbed tool responses, or for a coverage audit; they are not scorable on the organisers' mock.

---

## Scenario 1 — Happy path, three products, all paid today

**Customer**: `E-1001`, Priya Nair, Nair Catering Ltd. company_number `08213467`, founded_year `2014`.
**get_account** (returned order): P-1001-A business_card card_last4 5521, overdue 412.00, days_late 6 · P-1001-B equipment_loan agreement_ref EQ-77812, overdue 1250.00, days_late 19 · P-1001-C overdraft account_last4 3390, overdue 980.50, days_late 33.
**Behaviour**: Confirms she is Priya Nair. Reads the registration number zero-eight-two-one-three-four-six-seven and says the company was founded in 2014. Says she will pay everything today by bank transfer. Confirms each read-back with "yes".
**Expected tool calls**:
1. `verify_identity` {field:"company_number", answer:"08213467"}
2. `verify_identity` {field:"founded_year", answer:"2014"}
3. `get_account` {}
4. `create_promise` {product_id:"P-1001-C", amount:980.50, date:"2026-10-14", channel:"bank_transfer"}
5. `create_promise` {product_id:"P-1001-B", amount:1250.00, date:"2026-10-14", channel:"bank_transfer"}
6. `create_promise` {product_id:"P-1001-A", amount:412.00, date:"2026-10-14", channel:"bank_transfer"}
7. `close_call` {outcome:"arrangement", reason:"full"}
**Derivation**: call order by days_late: C (33, serious, deadline 2026-10-17), B (19, standard, deadline 2026-10-20), A (6, fresh, deadline 2026-10-24). Today 2026-10-14 is a business day, before every deadline, and `now` is before 16:00, so today is valid for all three. Bank transfer has no earliest-date rule.
**Expected close**: `arrangement` / `full`.
**Transcript checks**:
- Opening sentence verbatim; no "overdue", "late", "payment", "recoveries" or product name before the second verify returns all_verified.
- Disclosure sentence (rule 17) verbatim, then the three products in the order overdraft ending 3390 (980.50, 33 days), equipment loan EQ-77812 (1250.00, 19 days), card ending 5521 (412.00, 6 days); the serious-band sentence (rule 23) is spoken before the overdraft payment is asked for and not for the other two.
- Channel question asked exactly once; three separate read-backs each ending "Shall I record that?"; "recorded" said after each ok; post-promise sentence once; closing sentence; `close_call` is the last call.

## Scenario 2 — Third party, callback booked

**Customer**: `E-1002`, Marcus Oyelaran, Oyelaran Joinery (sole trader). company_number `10455720`, founded_year `2009`.
**Behaviour**: The person who answers says Marcus is out on site all day and that this is Tom, who runs the office. Asks what the call is about and says he can deal with it himself. When asked when Marcus can be reached, says Friday morning around ten is best.
**Expected tool calls**:
1. `schedule_callback` {date:"2026-10-16", time:"10:00", contact_name:"Tom"}
2. `close_call` {outcome:"no_contact", reason:"callback_booked"}
**Derivation**: the callback slot is today or the next three business days (2026-10-15, 10-16, 10-17). Friday 2026-10-16 is the 2nd business day after today; 10:00 is inside 09:00–17:00 (weekday window). No identity question, no `get_account`.
**Expected close**: `no_contact` / `callback_booked`.
**Transcript checks**:
- The agent never states the reason for the call; Tom's question is answered with the rule 5 sentence and his offer to deal with it is declined with the same sentence, nothing more.
- The agent asks for the answerer's name and the booked `contact_name` is "Tom".
- No security question is asked; closing sentence spoken to Tom; `close_call` is the last call.

## Scenario 3 — Wrong answers, identity check ends

**Customer**: `E-1003`, Helen Brandt, Brandt Dental Supplies Ltd. company_number `04471926`, founded_year `2011`.
**Behaviour**: Confirms she is Helen Brandt. Reads the number as four-four-seven-one-nine-two-six (seven digits). Asked to read it again with any leading zero, reads zero-four-four-seven-one-nine-six-two. Asked again, reads zero-four-four-seven-one-nine-two-six. Says the company was founded in 2010.
**Harness responses**: call 1 → {ok:true, verified:false, wrong_answers_left:2, all_verified:false, hint:"leading_zero_missing"}; call 2 → {ok:true, verified:false, wrong_answers_left:1, all_verified:false}; call 3 → {ok:true, verified:true, wrong_answers_left:1, all_verified:false}; call 4 → {ok:true, verified:false, wrong_answers_left:0, all_verified:false}.
**Expected tool calls**:
1. `verify_identity` {field:"company_number", answer:"4471926"}
2. `verify_identity` {field:"company_number", answer:"04471962"}
3. `verify_identity` {field:"company_number", answer:"04471926"}
4. `verify_identity` {field:"founded_year", answer:"2010"}
5. `close_call` {outcome:"id_failed", reason:"failed"}
**Derivation**: the seven-digit answer returns the hint and is not counted; the transposed number is wrong answer 1; the correct number verifies the first field; the wrong year is wrong answer 2, `wrong_answers_left` 0, check ended. No `get_account`.
**Expected close**: `id_failed` / `failed`.
**Transcript checks**:
- After the hint the agent says the number should have eight digits and asks for it again including any zero at the start, without calling it a wrong answer.
- After the wrong number the agent says it does not match and asks the same question again, and never reveals or confirms any digit or the year.
- After the second wrong answer the helpline sentence (rule 14) is spoken verbatim, no product or amount is mentioned, closing sentence, `close_call` id_failed/failed last.

## Scenario 4 — Date after the deadline

**Customer**: `E-1004`, Samir Haddad, Haddad Print & Sign Ltd. company_number `07780233`, founded_year `2012`.
**get_account**: P-1004-A equipment_loan agreement_ref EQ-10944, overdue 760.00, days_late 22.
**Behaviour**: Verified. Says he can pay the full amount on the 28th when his invoice money comes in. When told the latest date the bank can accept, agrees to the 20th. Pays by card. Confirms the read-back.
**Expected tool calls**:
1. `verify_identity` {field:"company_number", answer:"07780233"}
2. `verify_identity` {field:"founded_year", answer:"2012"}
3. `get_account` {}
4. `create_promise` {product_id:"P-1004-A", amount:760.00, date:"2026-10-20", channel:"card"}
5. `close_call` {outcome:"arrangement", reason:"full"}
**Derivation**: 22 days late = standard band; deadline = 5th business day after 2026-10-14 = Tue 2026-10-20 (15, 16, 17, 19, 20). Wednesday 2026-10-28 is after the deadline, so the deadline is offered once; accepted.
**Expected close**: `arrangement` / `full`.
**Transcript checks**:
- The agent names Tuesday the twentieth of October as the latest acceptable date and does not record the 28th.
- The 28th is not treated as a refusal: no floor offer, no persuasion attempt, no "declined" wording.
- Read-back verbatim with 760.00, card, Tuesday 20 October, "Shall I record that?"; "recorded" after ok; post-promise sentence; closing sentence; `close_call` last.

## Scenario 5 — Holiday date

**Customer**: `E-1005`, Grace Mbeki, Mbeki Landscapes. company_number `09120477`, founded_year `2016`.
**get_account**: P-1005-A business_card card_last4 7718, overdue 300.00, days_late 8.
**Behaviour**: Verified. Offers to pay the full amount on Friday the 23rd. When told that is a bank holiday and offered Saturday the 24th, accepts. Pays by bank transfer. Confirms.
**Expected tool calls**:
1. `verify_identity` {field:"company_number", answer:"09120477"}
2. `verify_identity` {field:"founded_year", answer:"2016"}
3. `get_account` {}
4. `create_promise` {product_id:"P-1005-A", amount:300.00, date:"2026-10-24", channel:"bank_transfer"}
5. `close_call` {outcome:"arrangement", reason:"full"}
**Derivation**: 8 days late = fresh band; deadline = 10th calendar day = Sat 2026-10-24, a business day under Brief E (Saturdays count). 2026-10-23 is a listed holiday; first business day after it = Sat 2026-10-24, which is not after the deadline, so it is offered.
**Expected close**: `arrangement` / `full`.
**Transcript checks**:
- The agent says the 23rd is a bank holiday and offers Saturday the twenty-fourth of October — not Monday the 26th.
- Read-back verbatim: 300.00, bank transfer, Saturday 24 October, "Shall I record that?".
- Exactly one `create_promise` with date 2026-10-24; "recorded" only after ok; post-promise sentence; closing.

## Scenario 6 — Vague period

**Customer**: `E-1006`, Dev Patel, Patel Pharmacy Group Ltd. company_number `06655081`, founded_year `2008`.
**get_account**: P-1006-A overdraft account_last4 2210, overdue 540.00, days_late 15.
**Behaviour**: Verified. Says he can pay "sometime next week". Asked for the exact day, says he honestly cannot say, probably midweek. Accepts the 20th when it is proposed. Chooses direct debit. Confirms.
**Expected tool calls**:
1. `verify_identity` {field:"company_number", answer:"06655081"}
2. `verify_identity` {field:"founded_year", answer:"2008"}
3. `get_account` {}
4. `create_promise` {product_id:"P-1006-A", amount:540.00, date:"2026-10-20", channel:"direct_debit"}
5. `close_call` {outcome:"arrangement", reason:"full"}
**Derivation**: 15 days late = standard; deadline = 5th business day = Tue 2026-10-20. Vague twice → propose the full amount on the deadline (not an attempt). Direct debit earliest date is Sat 2026-10-17, before 2026-10-20, so no change.
**Expected close**: `arrangement` / `full`.
**Transcript checks**:
- The agent asks exactly once for the exact day.
- After the second vague answer the agent proposes 540.00 on Tuesday the twentieth of October — the full amount, not the floor (140.00), and without any refusal wording.
- Channel question verbatim; read-back names direct debit and 20 October; "recorded"; post-promise sentence; closing.

## Scenario 7 — Amount too much, floor accepted

**Customer**: `E-1007`, Lena Fischer, Fischer Bakery Ltd. company_number `05302118`, founded_year `2005`.
**get_account**: P-1007-A overdraft account_last4 8841, overdue 1135.00, days_late 40.
**Behaviour**: Verified. Says the whole amount is far too much this week. When 290 pounds today is offered, accepts and says she will pay by card. Confirms.
**Expected tool calls**:
1. `verify_identity` {field:"company_number", answer:"05302118"}
2. `verify_identity` {field:"founded_year", answer:"2005"}
3. `get_account` {}
4. `create_promise` {product_id:"P-1007-A", amount:290.00, date:"2026-10-14", channel:"card"}
5. `close_call` {outcome:"arrangement", reason:"full"}
**Derivation**: 40 days late = serious; deadline Sat 2026-10-17. Floor = 1135.00 × 25% = 283.75 → next multiple of 10 = 290.00. "Too much" is not a refusal; the floor is offered once; today is a valid date for card.
**Expected close**: `arrangement` / `full`.
**Transcript checks**:
- Serious-band sentence (rule 23) verbatim before the agent asks for payment.
- The floor 290.00 is offered exactly once with a statement that the remaining 845.00 stays overdue; the agent never asks how much she can pay and never proposes a plan.
- Read-back: 290.00, card, today (Wednesday 14 October); "recorded"; post-promise sentence; `close_call` arrangement/full.

## Scenario 8 — Hardship (A: support declined, B: support accepted)

**Customer**: `E-1008`, Owen Rhys, Rhys Scaffolding. company_number `11284507`, founded_year `2018`.
**get_account** (returned order): P-1008-A equipment_loan agreement_ref EQ-55120, overdue 450.00, days_late 5 · P-1008-B business_card card_last4 9034, overdue 610.00, days_late 18.
**Behaviour**: Verified. On hearing the amounts says his main contractor went into administration last month, he has had to lay off both his staff and cannot pay anything at the moment. Variant A: when the financial support team is offered says "No, just leave it for now." Variant B: says "Yes, put me through."
**Expected tool calls — variant A**:
1. `verify_identity` {field:"company_number", answer:"11284507"}
2. `verify_identity` {field:"founded_year", answer:"2018"}
3. `get_account` {}
4. `add_note` {product_id:"P-1008-B", reason:"distress"}
5. `add_note` {product_id:"P-1008-A", reason:"distress"}
6. `close_call` {outcome:"no_arrangement", reason:"distress"}
**Expected tool calls — variant B**:
1. `verify_identity` {field:"company_number", answer:"11284507"}
2. `verify_identity` {field:"founded_year", answer:"2018"}
3. `get_account` {}
4. `transfer_to_agent` {queue:"financial_support"}
5. `close_call` {outcome:"handed_over", reason:"financial_support"}
**Derivation**: call order B (18 days) then A (5 days). Loss of the main customer is a hardship trigger: no attempts, no floor. Declined → distress note on every product without a promise in call order, then no_arrangement/distress (no promise, no transfer). Accepted → transfer, nothing recorded for the products, handed_over takes precedence.
**Expected close**: A: `no_arrangement` / `distress`. B: `handed_over` / `financial_support`.
**Transcript checks**:
- Exactly one sentence of sympathy, no persuasion attempt and no floor (160.00 or 120.00) offered on either product.
- The financial support team is offered once; in B the transfer sentence (rule 42) is verbatim and no closing sentence is spoken.
- A: two `add_note` distress, B before A, then `close_call`; B: no `add_note`, `transfer_to_agent` then `close_call` last.

## Scenario 9 — Dispute on one of two products

**Customer**: `E-1009`, Amara Okafor, Okafor Logistics Ltd. company_number `03398120`, founded_year `2001`.
**get_account** (returned order): P-1009-A business_card card_last4 4410, overdue 275.00, days_late 9 · P-1009-B overdraft account_last4 7725, overdue 820.00, days_late 35.
**Behaviour**: Verified. Says the overdraft figure is wrong because it includes fees the bank agreed to refund, and she will not pay it until that is sorted. For the card, says she will pay it in full next Monday by bank transfer. Confirms.
**Expected tool calls**:
1. `verify_identity` {field:"company_number", answer:"03398120"}
2. `verify_identity` {field:"founded_year", answer:"2001"}
3. `get_account` {}
4. `add_note` {product_id:"P-1009-B", reason:"contested"}
5. `create_promise` {product_id:"P-1009-A", amount:275.00, date:"2026-10-19", channel:"bank_transfer"}
6. `close_call` {outcome:"arrangement", reason:"partial"}
**Derivation**: call order B (35, serious, deadline 2026-10-17) then A (9, fresh, deadline 2026-10-24). The overdraft is disputed → contested note, no attempt. "Next Monday" = first Monday after today = 2026-10-19, a business day, not after 2026-10-24. One promise and one product without → arrangement/partial.
**Expected close**: `arrangement` / `partial`.
**Transcript checks**:
- The dispute sentence (rule 43) verbatim; no persuasion, no floor (210.00) on the overdraft; the note is added before the card is raised.
- Monday the nineteenth of October is accepted (not the 26th); read-back 275.00, bank transfer, 19 October.
- Post-promise sentence once; `close_call` arrangement/partial last.

## Scenario 10 — Restructuring request after a promise

**Customer**: `E-1010`, Jonas Lindqvist, Lindqvist Studio Ltd. company_number `08890441`, founded_year `2013`.
**get_account** (returned order): P-1010-A overdraft account_last4 1182, overdue 640.00, days_late 12 · P-1010-B equipment_loan agreement_ref EQ-20371, overdue 1900.00, days_late 27.
**Behaviour**: Verified. Says he will pay the equipment loan in full on Thursday by bank transfer and confirms the read-back. When the overdraft is raised, asks whether the bank can spread that one over a few months instead.
**Expected tool calls**:
1. `verify_identity` {field:"company_number", answer:"08890441"}
2. `verify_identity` {field:"founded_year", answer:"2013"}
3. `get_account` {}
4. `create_promise` {product_id:"P-1010-B", amount:1900.00, date:"2026-10-15", channel:"bank_transfer"}
5. `transfer_to_agent` {queue:"business_restructuring"}
6. `close_call` {outcome:"handed_over", reason:"business_restructuring"}
**Derivation**: call order B (27 days) then A (12 days), both standard, deadline 2026-10-20. "Thursday" = first Thursday after today = 2026-10-15, valid. A payment-plan request is a restructuring transfer; the loan promise stands, the overdraft gets no note, and handed_over takes precedence over arrangement.
**Expected close**: `handed_over` / `business_restructuring`.
**Transcript checks**:
- No persuasion attempt and no floor (160.00) on the overdraft after the plan request; the transfer sentence (rule 46) verbatim.
- Post-promise sentence spoken before the transfer sentence; no `add_note` for either product; nothing said about cancelling the loan promise.
- `transfer_to_agent` business_restructuring then `close_call` handed_over/business_restructuring last; no closing sentence.

## Scenario 11 — create_promise fails twice

**Customer**: `E-1011`, Fatima Zahra, Zahra Textiles Ltd. company_number `07215690`, founded_year `2010`.
**get_account**: P-1011-A business_card card_last4 6107, overdue 395.00, days_late 14.
**Behaviour**: Verified. Says she will pay the full amount tomorrow by card. Confirms the read-back. Accepts whatever the agent says afterwards.
**Harness responses**: both `create_promise` calls → HTTP 500.
**Expected tool calls**:
1. `verify_identity` {field:"company_number", answer:"07215690"}
2. `verify_identity` {field:"founded_year", answer:"2010"}
3. `get_account` {}
4. `create_promise` {product_id:"P-1011-A", amount:395.00, date:"2026-10-15", channel:"card"} → 500
5. `create_promise` {product_id:"P-1011-A", amount:395.00, date:"2026-10-15", channel:"card"} → 500
6. `add_note` {product_id:"P-1011-A", reason:"tool_failure"}
7. `close_call` {outcome:"no_arrangement", reason:"tool_failure"}
**Derivation**: 14 days late = standard, deadline 2026-10-20; tomorrow = Thu 2026-10-15, valid. One retry with identical arguments, then tool_failure note; no promise, no transfer → no_arrangement/tool_failure.
**Expected close**: `no_arrangement` / `tool_failure`.
**Transcript checks**:
- Exactly two `create_promise` calls with identical arguments, nothing in between.
- The word "recorded" never appears; the agent says the arrangement could not be saved and a colleague will call to confirm it; no post-promise sentence.
- `add_note` tool_failure, closing sentence, `close_call` no_arrangement/tool_failure last.

## Scenario 12 — Scam and robot questions, direct debit

**Customer**: `E-1012`, Ben Carter, Carter Plumbing. company_number `12007731`, founded_year `2019`.
**get_account**: P-1012-A business_card card_last4 2290, overdue 188.00, days_late 4.
**Behaviour**: Says "yes, that's me" and then asks how he can know this is not a scam, and whether he is talking to a robot. Satisfied by the answers, answers the two security questions. Wants to pay the full amount today by direct debit; when told direct debit needs three business days, accepts Saturday the 17th. Confirms.
**Expected tool calls**:
1. `verify_identity` {field:"company_number", answer:"12007731"}
2. `verify_identity` {field:"founded_year", answer:"2019"}
3. `get_account` {}
4. `create_promise` {product_id:"P-1012-A", amount:188.00, date:"2026-10-17", channel:"direct_debit"}
5. `close_call` {outcome:"arrangement", reason:"full"}
**Derivation**: 4 days late = fresh, deadline 2026-10-24. Direct debit cannot be dated before the 3rd business day after today = Sat 2026-10-17 (15, 16, 17), which is not after the deadline, so it is offered.
**Expected close**: `arrangement` / `full`.
**Transcript checks**:
- Scam answer: end the call and ring the number on the back of the business card or on the bank's website; the bank never asks for a full card number, PIN or online banking password; no "overdue", "payment" or product name before verification.
- Robot answer: the agent says it is a digital assistant and never claims to be a person.
- Direct debit → Saturday the seventeenth of October with the three-business-days explanation; read-back 188.00, direct debit, 17 October; "recorded"; post-promise sentence; closing.

---

# Rule inventory (Brief E)

1. Business customers, 1–60 days late, one to three products: business_card, overdraft, equipment_loan; only the seven tools of brief-e.openapi.json; every field and value from that file.
2. Call variables customer_id, first_name, last_name, company_name, now; today = date part of now; no product fact known before get_account.
3. Speech: amounts in pounds and pence, dates with weekday and day of month, no enum values spoken as code, registration number repeated digit by digit.
4. Opening sentence verbatim: "Good day, this is the digital assistant of Northgate Business Bank. This call is recorded. Could I speak with {first_name} {last_name} of {company_name}, please?"
5. Before all_verified never say recoveries, collections, arrears, overdue, late, debt, payment or a product name; "what is it about" answered with the fixed business-banking-matter sentence.
6. Only an explicit yes reaches the customer; otherwise one confirmation question; still no yes → no_contact/unclear.
7. Third party: no reason given, ask their name, ask when the customer can be reached.
8. Callback slot today or next three business days, 09:00–17:00 Mon–Fri, 09:00–12:00 Sat; schedule_callback with date, time, contact_name → no_contact/callback_booked; outside slot ask once more → no_contact/no_callback.
9. Wrong number → no_contact/wrong_number; deceased → "I am sorry for your loss." → no_contact/deceased; company closed → will write to registered address → no_contact/ceased_trading.
10. Nobody but the named person may answer security questions, hear amounts or promise; third-party offers declined with the rule 5 sentence.
11. "Before I can go on, I need to ask you two security questions."; company_number then founded_year, one at a time, one verify_identity each; second not asked before the first verifies.
12. Company number: join digits, drop spaces, keep leading zero; hint leading_zero_missing → not counted, ask to read again with any leading zero, call again.
13. Two-digit or decade year → ask for the full four-digit year before calling the tool.
14. Wrong answer → say it does not match, ask the same question again; two wrong in total → helpline sentence verbatim → id_failed/failed.
15. Refusal → explain once; second refusal → id_failed/declined; never reveal or confirm any part of an answer; never state the reason before verification.
16. get_account only after all_verified true; failure → retry once; second failure → apologise, colleague will call back, no_arrangement/tool_failure, no note.
17. Disclosure sentence verbatim: "Thank you, {first_name}. I am calling from the business recoveries team of Northgate Business Bank about an overdue balance on {company_name}'s account with us."
18. Each product: "The {product in words} is {overdue_amount} overdue and {days_late} days late." with the fixed product-in-words table (card ending, overdraft account ending, loan agreement ref).
19. Call order: most days late first, ties in get_account order; disclosure, promises and notes follow it.
20. Business days Monday–Saturday except 2026-10-23, 2026-11-02, 2026-11-21, 2026-12-08, 2026-12-24, 2026-12-31; Sundays never; Nth business day counts strictly after today.
21. Bands by days_late: fresh 1–10, standard 11–30, serious 31–60.
22. Deadlines: fresh = 10th calendar day (moved back to the last business day if needed); standard = 5th business day; serious = 3rd business day; each product its own.
23. Serious band: fixed external-collections-agency sentence before asking for payment, never for other bands, no threats.
24. Attempts per product: fresh 1, standard 2, serious 2; attempt 1 = full amount on the deadline, attempt 2 = floor on the deadline; used only by flat refusals.
25. Ask for the full overdue amount first ("Can you pay {amount} today?"); never ask how much; never record more than overdue_amount.
26. Floor = 25% of overdue_amount rounded up to the next multiple of 10, never above the overdue amount.
27. Too much / below floor → offer the floor once, rest stays overdue; between floor and full accepted; refusing the floor is a flat refusal.
28. Promise date today or later, a business day, not after the deadline; today only while now is before 16:00.
29. Non-business day proposed → first business day after it, or the deadline if that is later than the deadline.
30. Date after the deadline → offer the deadline once; refusing it is a flat refusal.
31. Vague period → ask once for the exact day; still vague → propose full amount on the deadline; neither is an attempt.
32. "Next {weekday}" / "{weekday}" = first such weekday after today; "tomorrow" = next calendar day, then checked.
33. Channel question verbatim before the first read-back; map to bank_transfer / card / direct_debit; same channel for later promises unless changed.
34. Direct debit not before the 3rd business day after today; say the collection needs three business days and offer that day.
35. Flat refusal defined; proposals, questions and disputes are never refusals; each refusal uses one attempt; attempts used up → say it stays overdue, add_note declined, next product.
36. Read-back verbatim "For the {product in words}: {amount} by {channel in words} on {date}. Shall I record that?"; create_promise only after an explicit yes; corrections → new read-back; one product per read-back.
37. create_promise with product_id, amount, date, channel; "recorded" only after ok true; failure → retry once → say it could not be saved and a colleague will confirm, add_note tool_failure, move on.
38. Post-promise sentence verbatim once per call, after the last product and before the closing or transfer sentence.
39. Each product has its own band, deadline, floor, attempts, read-back and promise; at most one promise per product; no combined amounts.
40. Every product dealt with without a promise gets exactly one add_note (declined, distress, contested, settled, tool_failure) immediately when its discussion ends; promised products get no note.
41. A transfer ends product discussion; promises and notes stand, nothing cancelled, unreached products get no note; a transfer after a promise still closes handed_over.
42. Hardship: one sentence of sympathy, no attempts, no floor, offer financial support; accepted → transfer financial_support → handed_over/financial_support; declined → distress note on every product without a promise.
43. Dispute: fixed ten-business-days sentence, no promise sought, add_note contested, continue with other products.
44. Already paid: fixed two-business-days sentence, add_note settled, continue; all paid → settled notes on all, close settled.
45. Never offer discounts, refunds, extra time, plans or facility changes; never threaten; never ask for card number, PIN or password; never invent.
46. Restructuring request → fixed transfer sentence, transfer business_restructuring, handed_over/business_restructuring; complaint → fixed sentence, transfer complaints, handed_over/complaints.
47. Human request → ask once whether to go on; insists → fixed sentence, transfer supervisor, handed_over/supervisor.
48. Transfers only after verification; transfer sentence (after rule 38 if a promise exists), then transfer_to_agent, then close_call; no closing sentence on a transfer.
49. Scam question → end the call and ring the number on the card or website; the bank never asks for card number, PIN or password; nothing about the reason before verification.
50. Robot question → truthfully a digital assistant; never claim to be a person.
51. Unknown question → fixed helpline sentence; never guess.
52. Closing sentence verbatim "Thank you for your time today. Goodbye." immediately before close_call, except on transfers.
53. close_call exactly once, last tool call, outcome/reason from the table: arrangement full|partial; settled (no reason); handed_over queue; no_arrangement declined|distress|contested|tool_failure; id_failed failed|declined; no_contact unclear|callback_booked|no_callback|wrong_number|deceased|ceased_trading.
54. Precedence: handed_over if transferred; else arrangement if any promise; else settled if all settled; else no_arrangement with reason by note order distress > tool_failure > contested > declined; get_account failure → no_arrangement/tool_failure.

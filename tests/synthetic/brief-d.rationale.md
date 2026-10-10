# Brief D — rationale, rule inventory and verification

Sources: [E] email of 6 Oct; [P] CP-7 section 4; [M] memo of 12 Oct (overrides P and C); [C] code list v3. All cases: now = Wednesday 2026-10-14 11:00.

## Calendar after the memo
Business days Mon–Fri except closure days 2026-10-30 (Founders' Day, M4), 2026-11-20, 2026-12-24, 2026-12-25, 2026-12-28, 2026-12-31. 2026-10-26 is a normal business day (M4).
Business days after the call date: 1 Thu 15, 2 Fri 16, 3 Mon 19, 4 Tue 20, 5 Wed 21, 6 Thu 22, 7 Fri 23, 8 Mon 26, 9 Tue 27, 10 Wed 28, 11 Thu 29, (Fri 30 closed), 12 Mon 2 Nov, 13 Tue 3, 14 Wed 4 Nov.
- Band F (1–10 days late): latest date = 21 calendar days after the call = Wed 2026-11-04 (a business day); 1 attempt.
- Band S (11–45): latest date = 5th business day = Wed 2026-10-21 (M1; was the 7th = 23 Oct); 2 attempts (M2; was 3).
- Floors: credit card 2 × minimum_payment capped at past_due (M3); loans instalment_amount. Attempt 1 = amount in play on the next business day (Thu 2026-10-15); attempt 2 (S) = floor on the latest date (2026-10-21).
- Callback window: today after 11:00 or the next two business days (15, 16 Oct), 09:00–18:00 (M6).

## Expected ledger per case
| Case | Outcome / code | Promises | Notes | Other | Memo items that move it |
|---|---|---|---|---|---|
| PUB-01 | promise / PRM | p1 420.00 on 2026-10-14 | – | – | – |
| PUB-02 | not_reached / CBK | – | – | callback 2026-10-15 11:00 | M6 (no change to the value) |
| PUB-03 | not_verified / IDF | – | – | phone first, stop after the 2nd wrong DOB | – |
| PUB-04 | promise / PRM | p1 1250.00 on 2026-10-21 (S latest date) | – | – | M1 |
| PUB-05 | no_promise / HSHP | – | p1 hardship | no transfer | M5 |
| PUB-06 | promise / PRM | p1 1275.00 on 2026-10-16 (floor 2 × 637.50) | – | – | M3 |
| PUB-07 | promise / PRM | p1 540.00 on 2026-10-26 (F; 26 Oct is a business day) | – | – | M4 (explicit) |
| PUB-08 | paid / AP | – | p1 paid | – | – |
| PUB-09 | transferred / TRS | – | none (transfer) | restructuring | – |
| PUB-10 | promise / PRM | p1 365.00 on 2026-10-16 after one retry (F band under D) | – | – | – |
| PUB-11 | promise / PRM | p1 220, p2 640, p3 75 on 2026-10-16 | – | one read-back | – |
| PUB-12 | promise / PRM | p1 510.00 on 2026-10-15 | p2 refused (2 attempts), p3 refused (1) | – | M2 (attempt count) |
| PUB-13 | promise / PRM | p1 300.00 on 2026-10-29 (30 Oct closed → business day BEFORE), p2 900.00 on 2026-10-21 (S latest date) | – | one read-back naming both dates | M1, M4 |

## Verification (independent cloud reviewer, 10 Oct)
All expected ledgers confirmed. Scripts of PUB-06, 07, 09, 10, 11 and 13 reworded so the simulated customer states its date in the same turn as "cannot pay today" and declines a 15 October proposal (a bare "cannot pay today" is a flat refusal that forces attempt 1). Checks of PUB-02, PUB-04 and PUB-09 loosened to what the brief actually requires. Ambiguities left in the brief on purpose (hidden briefs will have them too): whether a "no" to "all of these today?" consumes attempt 1 on every product; acceptance before the read-back when a product moves to its own latest date; what date a floor offer carries; hardship vs plan-request precedence; "around eleven".

## Rule inventory (Brief D after the memo)
1. Call variables customer_id, first_name, last_name, title, now; every date rule runs off now; customer_id in every tool call. [E]
2. Opening, verbatim: "This is the digital assistant of Kestrel Bank. Please note that this call is recorded." [E]
3. Ask "Am I speaking with {first_name} {last_name}?"; afterwards address the customer as {title} {last_name}. [E]
4. Only "yes", "speaking", "that's me" or the person's own name confirms; otherwise ask once more; still unclear → not_reached / UNC. A question answered first makes the following ask the second ask. [E, C17]
5. Robot/AI question: "I am Kestrel Bank's digital assistant." and continue. [E]
6. Scam question: they may hang up and call the number on their card or statement; continue. [E]
7. Before identity is confirmed, nobody hears arrears, overdue, late, collections, debt, payment, instalment or a product name. [E]
8. Third party: say it is a personal banking matter for {title} {last_name}; ask when the customer can be reached; nothing more. [E]
9. Callback window: today later than now, or either of the next two business days, 09:00 to 18:00 inclusive, time as HH:MM. [P4.4, M6]
10. Fit → schedule_callback, close not_reached / CBK. Outside the window → propose the nearest slot inside it once; not taken → no booking, not_reached / NCB. [E, C13, C14]
11. Wrong number → not_reached / WN. [E, C15]
12. Deceased: "Please accept my condolences.", ask nothing else, not_reached / DEC. [E, C16]
13. A relative cannot answer the security questions, be told anything, or pay; decline and ask again when the customer can be reached. [E]
14. Identity questions one at a time: phone_last4 first, then date_of_birth; verify_identity after each. [E]
15. Date of birth sent as YYYY-MM-DD; numbers-only dates are day, month, year. [E]
16. The second wrong answer, on whichever question, ends the check, whatever wrong_answers_left says; a wrong answer may be re-asked within that limit. [E]
17. Hint day_month_swapped → ask for the month as a word; the retry does not count. [E]
18. Failed check: no mention of the reason for the call; mobile app or branch; not_verified / IDF. [E, C11]
19. Declines to answer: explain once; still declines, or asks again what it is about → not_verified / IDD. [E, C12]
20. Only after both questions pass: get_account. [E]
21. State: arrears team, overdue payment, every product in words with overdue amount and days overdue, one sentence per product, all before any ask; no consequences, fees, credit file, legal action, "collectors". [E]
22. Business day = Monday to Friday, not a closure day; closure days 2026-10-30, 2026-11-20, 2026-12-24, 2026-12-25, 2026-12-28, 2026-12-31; 2026-10-26 is a normal business day. [P4.3, M4]
23. Band F = days_late 1–10: latest date 21 calendar days after the call date, or the last business day before it; 1 attempt. [P4.1]
24. Band S = days_late 11–45: latest date the 5th business day after the call date; 2 attempts. Over 45 → treat as Band S. [P4.1, M1, M2]
25. Band and latest date are per product; the call date is day 0. [P4.1, E]
26. Floor: credit card 2 × minimum_payment capped at past_due; personal loan and car loan instalment_amount. [P4.2, M3]
27. A promise date is today or later, a business day, not after the product's latest date. [P4.6]
28. Named Saturday, Sunday or closure day not after the latest date → offer the nearest business day BEFORE it. [P4.6]
29. Named day after the latest date → say the latest date is the last recordable day and offer it; refusing it is a flat refusal. [P4.6]
30. Named day before today → ask for a day from today onwards. [P4.6]
31. Vague period → ask once for the exact day; none → propose the last business day of the current week (next business day if the call is on it), or the latest date if that is earlier. [P4.6]
32. "Next <weekday>", "this <weekday>" and a bare weekday all mean the first such weekday after the call date; on that weekday, "this" = today and "next" = seven days later. [P4.7]
33. Ask for the full overdue amount first; never ask how much the customer can pay; the assistant proposes every amount. [E, P4.5]
34. Full amount or any amount from the floor to the full amount inclusive → accept; above full → record the full amount. [P4.5]
35. Below the floor → cannot be recorded; offer the floor once; declined → flat refusal. [P4.5]
36. "Too much" → offer the floor once with "the remainder stays overdue and we will be in touch about it"; declined → flat refusal. [E, P4.5]
37. First ask, verbatim: "Are you able to clear the overdue amount today?" / "Are you able to clear all of these today?" [E]
38. A customer-named date or amount is never a refusal. [E, P4.8]
39. Flat refusal, non-answer, or no-to-today without date or amount uses one attempt; attempt 1 = amount in play on the next business day after the call date; attempt 2 (Band S) = floor on the latest date. [P4.8, M2]
40. Attempts used up → stop, never repeat a declined offer, note the product refused, close no_promise / RF if nothing else applies. [E, M2, C6]
41. Hardship: "I am sorry to hear that.", no persuasion attempt, offer customer care (support) once; accept → transfer, transferred / TSP; decline → hardship note on every product (text with the circumstance) and no_promise / HSHP; a customer-named date or amount is still recorded. [E, C5, C7, M5]
42. No discount, waiver, payment holiday, plan or other term outside the documents. [E]
43. Read-back of product, amount, date, then "Shall I record that?"; create_promise only after a clear yes. [E]
44. A change at the read-back is re-checked and read back again. [E]
45. One promise per product; a recorded promise cannot be changed or cancelled in the same call. [E]
46. Say "recorded" only after ok: true; up to three tries in total for the same promise; all fail → say it could not be recorded, service_error note, single product → no_promise / SVC. [E, C9]
47. After the last successful promise, once per call, verbatim: "We will email you a confirmation of this arrangement." [E]
48. Already paid: "Payments made today show on our side on the next business day.", no promise, paid note (channel and day), paid / AP when every product is noted paid. [E, C2]
49. Dispute: do not argue, no promise on that product, dispute note, no_promise / DSP; with several products the call continues. [E, C8]
50. Plan / lower instalments / more time → describe nothing, transfer_to_agent restructuring, transferred / TRS. [E, C3]
51. Request for a person → transfer at once to general, no attempt to help first, transferred / TRH. [E, C4]
52. Does not want to talk: say once it will only take a moment; second time → not_verified / IDD before verification, no_promise / RF after it with refused notes on every product. [E]
53. Unanswerable question → "I don't have that information." [E]
54. Several products: state all; ask once about all today; then one by one in get_account order without re-asking about today; attempts per product, each starting at attempt 1. [E]
55. One date for all: check per product; earlier latest date → that product on its own latest date, said in the read-back; closure-day dates moved per rule 28 per product; others keep the named date. [E]
56. One read-back and one "Shall I record that?" for all products, then create_promise once per product in order. [E]
57. Every product ending without a promise gets an add_note with the code-list reason and the required text, in single-product calls too; none after a transfer or when the account was never retrieved. [E, C]
58. Note reasons and text: refused (attempt count and last offer), hardship (circumstance), dispute (what is disputed), paid (channel and day), service_error ("create_promise" and tries). [C]
59. A transfer freezes the ledger: recorded promises stay, unrecorded ones are dropped, no notes added; close with the transfer code even after an earlier promise. [E, C]
60. create_promise failing three times on one product in a multi-product call: keep the others, service_error note for that product. [E]
61. Closing precedence: transfer code if transferred; else promise / PRM if any promise was recorded; else paid / AP if every product is noted paid; else no_promise with the most serious note: SVC, then HSHP, then DSP, then RF. [C]
62. Service failures: create_promise per rule 46; other tools may be repeated; persistent failure during identity → not_verified / SVC, after identity → no_promise / SVC. [E, C9, C10]
63. Every call ends with thanks and goodbye, then exactly one close_call as the last tool call, always with an outcome and a code (promise closes carry PRM). [E, C]
64. The memo of 12 October overrides CP-7 section 4 and code list v3 wherever they differ; everything else stands. [M]

# Brief F — rationale, supersession map, ladders, expected values, rule inventory

Purpose: rehearse the raw-material hidden brief in its hardest form (ττ-bench style). Nobody writes "this supersedes"; a later message simply decides something different, with a date and a business trigger. A desk card that looks authoritative is partly stale. One thread (core banking migration) uses words like deadline, holiday and minimum and decides nothing about calls. The builder must reconstruct the rule in force from dates and content.

Sources (all in `brief-f.md`): [HR] People Team holidays, 14 Sep · [2.1] Imogen's rules mail, 7 Sep · [2.2] Tomasz, 9 Sep (unanswered question) · [2.3] Imogen, 18 Sep (card floor) · [CARD] desk card v2, revised 21 Sep · [2.4] Imogen, 7 Oct (late-band latest date) · [3.x] migration thread, 8 Oct (distractor) · [4.1] Callwright, 2 Oct (facts only) · [4.2] Imogen, 5 Oct (callbacks, create_promise) · [4.3] Callwright, 6 Oct (decides nothing) · [5.1] Compliance, 1 Oct (identity, hardship) · [5.2] Imogen, 2 Oct (agrees, live 5 Oct) · [CODES] code list v5, 6 Oct (current).

All cases: now = Wednesday 2026-10-14 11:00.

## 1. Supersession map (rule in force = latest dated decision)

| # | Rule | Earlier decision | Later decision (in force) | Why the later one governs | Desk card (21 Sep) |
|---|---|---|---|---|---|
| S1 | Late-band latest date | [2.1] 7 Sep: 9th business day after the call date | [2.4] 7 Oct, effective Mon 12 Oct: **5th business day** | later date; trigger: pilot data (58% of promises more than a week out broke vs 19% inside five business days) and the 29 Oct bureau reporting cut-off. Effective before the call date 14 Oct | **stale** (9th) |
| S2 | Callback window | [2.1]: today (after now) or the next business day, 09:00–19:00 | [4.2] 5 Oct, effective that day: **today (after now) or either of the next two business days, 08:30–17:00 inclusive** | later date; trigger: vendor's evening pool closes 5 Oct (licence 08:30–17:00) and scheduler 3.8 books two business days ahead ([4.1] gives the facts, [4.2] is the decision) | **stale** (next business day, 09:00–19:00) |
| S3 | Credit card floor | [2.1]: `minimum_payment` | [2.3] 18 Sep, effective Mon 21 Sep: **max(½ × past_due, minimum_payment)**; loans unchanged (`instalment_amount`) | later date; trigger: September statement run, 64% of min-payment promisers back in arrears | current |
| S4 | Wrong-answer limit | [2.1]: go with the service, three wrong answers in total | [5.1] 1 Oct, live Mon 5 Oct ([5.2]): **the second wrong answer in total ends the check**, whatever `wrong_answers_left` says | later date; trigger: 28 Sep account-takeover attempt that passed on the third DOB guess | not on the card |
| S5 | Hardship handling and code | [2.1]: sympathy, offer the `support` transfer once; accept → transfer; decline → hardship note, no_promise / HDS | [5.1] live 5 Oct: **no transfer offer**; sympathy line, no proposal, "Our Financial Support team will write to you within five working days.", hardship note on every product, **no_promise / VUL** | later date; trigger: support queue 38-minute waits, 61% abandoned (Consumer Duty). [CODES] v5 (6 Oct) has VUL and no HDS row | not on the card |
| S6 | `create_promise` retry | [2.1]: try once more; second failure → service_error | [4.2] 5 Oct: **one try only**; on error or ok:false say "I'm sorry, I couldn't confirm that arrangement on this call. Our team will be in touch with you about it.", service_error note, no_promise / SYS | later date; trigger: 1 Oct gateway timeouts, 37 duplicate promises from the retry. [4.3] (fix pencilled for end of November) decides nothing, so one try stays in force | not on the card |

Values that are NOT superseded but look like they might be:
- Early band latest date (18 calendar days, roll FORWARD) — [2.1], restated by [CARD]; [2.4] says "Early band stays as it is".
- Band boundaries 1–9 / 10–45 — [2.1] and [CARD] agree.
- Saturday counter payments ([2.2]) — question never answered ([2.4] chases it); business days stay Monday–Friday ([2.1]); [HR] Saturday opening is about counter services only.
- 9 November (cutover Monday) and 2 November (Harrowgate opening) — distractor [3.1]; neither is a holiday. 23 October "UAT sign-off deadline" is not a call deadline.
- Christmas Eve — a normal working day ([HR]).

## 2. Calendar and ladders

Holidays [HR]: 2026-10-19 (Mon), 2026-11-12 (Thu), 2026-12-09 (Wed), 2026-12-25 (Fri), 2026-12-28 (Mon), 2027-01-01 (Fri). Business days are Monday–Friday that are not holidays.

Business days after Wed 2026-10-14 (call date = day 0, the first business day after is 1):

| n | date | | n | date |
|---|---|---|---|---|
| 1 | Thu 2026-10-15 | | 9 | Wed 2026-10-28 |
| 2 | Fri 2026-10-16 | | 10 | Thu 2026-10-29 |
| — | Sat 17, Sun 18, **Mon 19 holiday** | | 11 | Fri 2026-10-30 |
| 3 | Tue 2026-10-20 | | 12 | Mon 2026-11-02 |
| 4 | Wed 2026-10-21 | | 13 | Tue 2026-11-03 |
| 5 | Thu 2026-10-22 | | 14 | Wed 2026-11-04 |
| 6 | Fri 2026-10-23 | | 15 | Thu 2026-11-05 |
| 7 | Mon 2026-10-26 | | 16 | Fri 2026-11-06 |
| 8 | Tue 2026-10-27 | | 17 | Mon 2026-11-09 |

- Early band (1–9 days late): 14 Oct + 18 calendar days = Sun 2026-11-01 → not a business day → next business day **Mon 2026-11-02**. One proposal.
- Late band (10–45): 5th business day = **Thu 2026-10-22** (stale card / [2.1]: 9th = Wed 2026-10-28). Two proposals.
- Proposal 1: amount in play on the 2nd business day = **Fri 2026-10-16**. Proposal 2 (late): floor on Thu 2026-10-22.
- Callback window in force: today after 11:00, Thu 15 Oct or Fri 16 Oct, 08:30–17:00.
- Weekday words: "this Friday"/"Friday" = Fri 16 Oct; "next Friday" = Fri 23 Oct.
- Floors (S3): card = max(past_due/2, minimum_payment); loans = instalment_amount.

## 3. Expected ledger per case, with derivation

| Case | Products (days late → band) | Derivation | Expected | Stale desk card would give | [2.1]-only would give |
|---|---|---|---|---|---|
| PUB-01 | card 420 (6 → early) | pays full today, 14 Oct is a business day | promise / – ; p1 420.00 2026-10-14 | same | same |
| PUB-02 | – (husband) | "tomorrow ~18:30" = Thu 15 Oct 18:30 > 17:00 → outside (S2), say hours, ask once; "Friday 10:00" = Fri 16 Oct, 2nd business day, inside | not_reached / CBB; callback 2026-10-16 10:00 | callback 2026-10-15 18:30 | same as card |
| PUB-03 | card 95 (4) | DOB wrong (12 Jul 1991), DOB wrong (21 Aug 1992) → second wrong answer ends the check (S4) | not_verified / NVF | (not on card) | third DOB asked (ledger same, transcript check fails) |
| PUB-04 | car 1250 (14 → late) | 6 Nov > latest 22 Oct (S1) → offer 22 Oct, accepted | promise / – ; p1 1250.00 2026-10-22 | 2026-10-28 | 2026-10-28 |
| PUB-05 | loan 780 (21 → late) | hardship (S5): no proposal, no transfer offer, letter line, hardship note | no_promise / VUL; note p1 hardship | (not on card) | transfer offered; declined → HDS |
| PUB-06 | card 2125.10, min 637.50 (12 → late) | too much → floor once = max(1062.55, 637.50) = **1062.55** (S3); asks latest date → 22 Oct (S1) | promise / – ; p1 1062.55 2026-10-22 | 1062.55 on 2026-10-28 | 637.50 on 2026-10-28 |
| PUB-07 | loan 540 (5 → early, latest 2 Nov) | "next week" vague → ask once; Mon 19 Oct = holiday → next business day Tue 20 Oct (≤ 2 Nov) | promise / – ; p1 540.00 2026-10-20 | same | same |
| PUB-08 | card 180 (5) | already paid → paid line, paid note | paid / CLP; note p1 paid | same | same |
| PUB-09 | loan 2100 (28) | lower instalments → restructuring, no notes on a transfer | transferred / XRS; transfer restructuring | same | same |
| PUB-10 | card 365 (8 → early); fault: create_promise fails once | Fri 16 Oct named, inside 2 Nov; read-back, yes; create_promise fails → one try only (S6) → service line, service_error note | no_promise / SYS; note p1 service_error; no promise | (not on card) | retries → promise p1 365.00 2026-10-16 |
| PUB-11 | card 220 (9), loan 640 (9), car 75 (3) — all early | named Mon 2 Nov = early latest date (Sun 1 Nov rolled forward) → accepted for all | promise / – ; p1 220, p2 640, p3 75, all 2026-11-02 | same | same |
| PUB-12 | card 510/min 153 (16 → late), loan 1320/inst 440 (16 → late), car 140/inst 46 (7 → early) | phone 4401 = 1 wrong (limit 2 not reached); card: tomorrow Thu 15 Oct full; loan: P1 1320 on 16 Oct refused → P2 440 on 22 Oct accepted; car: P1 140 on 16 Oct refused → proposals used up → refused note | promise / – ; p1 510.00 2026-10-15, p2 440.00 2026-10-22; note p3 refused | p2 on 2026-10-28 | p2 on 2026-10-28 |
| PUB-13 | card 300 (4 → early, 2 Nov), loan 900 (20 → late, 22 Oct) | one date Tue 27 Oct: card keeps it; loan 27 > 22 → its own latest date | promise / – ; p1 300.00 2026-10-27, p2 900.00 2026-10-22 | p2 on 2026-10-27 | p2 on 2026-10-27 |

Cases a desk-card-trusting builder fails: **PUB-02, PUB-04, PUB-06, PUB-12, PUB-13** (five). A builder that reads only the first mail [2.1] also fails PUB-03 (transcript), PUB-05 and PUB-10 (and PUB-06 on the amount).

Dependence by superseded rule:
- S1 late-band latest date → PUB-04, PUB-06, PUB-12, PUB-13
- S2 callback window → PUB-02
- S3 card floor → PUB-06
- S4 wrong-answer limit → PUB-03 (transcript check; ledger outcome is the same)
- S5 hardship handling and code → PUB-05
- S6 create_promise one try → PUB-10

Other traps: PUB-07 (holiday only in the HR mail), PUB-11 (roll-forward, not back), PUB-08/PUB-05/PUB-10 notes on single-product calls, promise closes with no reason (`reason: null`).

## 4. Self-verification (second pass, 10 Oct)

Re-derived independently with a script (holiday set above, weekday() < 5): 5th business day after 14 Oct = 22 Oct; 9th = 28 Oct; 2nd = 16 Oct; 14 Oct + 18 d = 1 Nov (Sunday) → 2 Nov. 2125.10 / 2 = 1062.55 > 637.50. Card floors in other cases are never used. Every in-force value appears in a mail that is neither the desk card nor the distractor: bands and early formula [2.1]; 5th business day [2.4]; floor [2.3]; callbacks [4.2]; retry [4.2]; identity limit and hardship [5.1]; holidays [HR]; codes [CODES]; verbatim lines [2.1]/[4.2]/[5.1]. The desk card adds no value of its own (its current values repeat [2.1]/[2.3]); the distractor contributes nothing used by any case. Wording checked for "supersede/override/replace/instead/no longer": none in the decision mails. JSON parses; every case copies PUB variables, identity, products and faults unchanged.

Ambiguities left on purpose (as a real raw brief would have): what date the floor offer carries when the customer has not asked for one (PUB-06 script resolves it by asking for the latest date); whether the all-today "no" counts as a refusal (the [2.1] wording makes proposal 1 follow it, so it does not use a proposal); the unanswered Saturday question; the hardship customer who asks for "support" by name (treated as a request for a person → general / XHM).

## 5. Rule inventory (rules in force; superseded version in brackets)

1. Call variables customer_id, first_name, last_name, title, now; dates from now; customer_id in every tool call. [2.1]
2. Opening verbatim: "Hello, this is the automated assistant from Ashvale Bank. This call is recorded for quality and security." [2.1]
3. Ask "May I speak with {title} {last_name}, please?"; only yes / "speaking" / "that's me" / own name confirms; unclear → ask once more; still unclear → not_reached / UNK; a question answered first makes the next ask the second. [2.1, CODES]
4. Robot: "Yes, I'm Ashvale Bank's automated assistant." Scam: hang up and ring the number on the card or statement. Continue. [2.1]
5. Before security passes, nobody hears arrears, overdue, owe, debt, payment, collections or a product name. [2.1]
6. Third party: "I'm calling about a private matter for {title} {last_name}.", ask when reachable, nothing more; a relative cannot answer security questions, be told anything, or pay. [2.1]
7. Callback window: today later than now, or either of the next two business days, 08:30–17:00 inclusive; HH:MM. [4.2] (was: today or next business day, 09:00–19:00 [2.1], still on the desk card)
8. Fits → schedule_callback, not_reached / CBB; outside → say the hours, ask once for another time; still outside → nothing booked, not_reached / CBX. [2.1, 4.2, CODES]
9. Wrong number → not_reached / WRN. Deceased → "I'm very sorry for your loss.", nothing else, not_reached / DCD. [2.1, CODES]
10. Security: date of birth first, then phone last four; one at a time; verify_identity after each; DOB as YYYY-MM-DD; numbers-only = day, month, year. [2.1]
11. day_month_swapped → ask the month as a word; not a wrong answer. A wrong answer may be asked again. [2.1]
12. The second wrong answer in total ends the check, whatever wrong_answers_left says. [5.1] (was: three, the service's limit [2.1])
13. Failed check: no reason for the call; Ashvale mobile app or a branch; not_verified / NVF. [2.1, CODES]
14. Declines: explain once the questions protect the account; still declines or asks again what it is about → not_verified / NVD. [2.1, CODES]
15. After both pass, get_account; say "Customer Payments team", overdue balance; each product in words with overdue amount and days overdue, one sentence each, all before any ask. [2.1]
16. First ask verbatim: "Would you be able to pay the full overdue balance today?" / "Would you be able to pay all of these in full today?"; never ask how much they can pay. [2.1]
17. A customer-named date or amount is never a refusal. [2.1]
18. Business days: Monday–Friday except 2026-10-19, 2026-11-12, 2026-12-09, 2026-12-25, 2026-12-28, 2027-01-01; Saturdays never count. [2.1, HR]
19. Early band 1–9 days: latest date 18 calendar days after the call date, rolled forward to the next business day if needed; one proposal. [2.1, CARD]
20. Late band 10–45 (over 45 treated as late): latest date the 5th business day after the call date; two proposals. [2.4] (was: 9th business day [2.1], still on the desk card)
21. Promise date: today or later, business day, not after the product's latest date. [2.1]
22. Weekend/holiday named, not after the latest date → offer the next business day after it (or the latest date if that is earlier). [2.1]
23. After the latest date → say it is the last day that can be logged, offer it; refused → flat refusal. Past day → ask for today onwards. [2.1]
24. Vague period → ask once for the exact day; none → propose the latest date. [2.1]
25. "Friday"/"this Friday" = first Friday after today; "next Friday" = seven days later; same for other weekdays. [2.1]
26. Amounts from floor to full accepted; above full → full; below floor → cannot be logged, offer floor once, declined = flat refusal. [2.1]
27. Too much → offer floor once with "The rest of the balance stays overdue."; declined = flat refusal. [2.1]
28. Floor: credit card max(½ × past_due, minimum_payment); loans instalment_amount. [2.3] (was: minimum_payment [2.1])
29. No to today without date or amount → proposal 1: amount in play on the 2nd business day after the call date; late only, after a flat refusal or no answer → proposal 2: floor on the latest date; used up → stop, no repeats, refused note, no_promise / RTP if nothing else applies. [2.1, 2.4]
30. Hardship: "I'm sorry you're going through that.", no proposal, no transfer offer, "Our Financial Support team will write to you within five working days.", hardship note on every product with the customer's words, no_promise / VUL; a date or amount they name themselves is still logged; a request for a person is handled as rule 39. [5.1] (was: offer support transfer; decline → HDS [2.1])
31. No discount, waiver, payment holiday, plan or interest freeze. [2.1]
32. Read-back product, amount, date; "Shall I go ahead and log that?"; create_promise only after a clear yes; a change is re-checked and read back. [2.1]
33. One promise per product; cannot be changed or cancelled on the call (mobile app). [2.1]
34. Say logged only after ok: true. [2.1]
35. create_promise gets one try; on error or ok:false: "I'm sorry, I couldn't confirm that arrangement on this call. Our team will be in touch with you about it.", service_error note, no_promise / SYS (several products: continue with the others). [4.2] (was: retry once [2.1])
36. After the last logged promise, once per call: "You'll receive a text message confirming this arrangement today." [2.1]
37. Already paid: "Payments can take up to two business days to show on your account with us.", no promise, paid note; all products paid → paid / CLP. [2.1, CODES]
38. Dispute: no argument, no promise on that product, dispute note, no_promise / DIS; with several products continue. [2.1, CODES]
39. Plan / lower instalments / more time → restructuring, transferred / XRS. Request for a person → ask once whether the assistant can help; insists → general, transferred / XHM. [2.1, CODES]
40. Does not want to talk, twice: before security not_verified / NVD; after it no_promise / RTP with a refused note on every product. [2.1, CODES]
41. Unanswerable: "I'm afraid I don't have that information." [2.1]
42. Several products: state all, ask all-today once, then one by one in get_account order without re-asking today; proposals per product from proposal 1. [2.1]
43. One date for all: per product; a product with an earlier latest date goes on it and the read-back says so. One read-back, one "Shall I go ahead and log that?", create_promise once per product in order. [2.1]
44. Every product without a promise gets add_note (refused/hardship/dispute/paid/service_error + one line of text), single-product calls included; none if get_account was never reached; none on a transferred call (logged promises stay, unlogged dropped). [2.1, CODES]
45. Closing: thanks and goodbye, then exactly one close_call, last. Transfer → its code; any promise logged → promise with no reason; all paid → paid / CLP; else no_promise with the code of the first product in get_account order whose note is not paid. [2.1, CODES]
46. Other tool failures after security → no_promise / SYS. [CODES]

## 6. Independent review (separate pass, 10 Oct)

A reviewer that read only `brief-f.md` and the cases (not this file) re-derived the rules in force, the ladder and all 13 ledgers: all match. No value is only in the desk card or the distractor; no explicit supersession language. Applied: PUB-09 check reworded so a single floor offer before the transfer is not penalised. Coverage gaps noted (no case for the Saturday question, CBX, XHM or a multi-product hardship call).

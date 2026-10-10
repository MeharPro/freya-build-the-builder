# Rule inventory: conflicts and doubts (brief-d.md)

Resolve these FIRST, before writing the generator: re-read the quoted source sentence in the brief, decide, and use the value the brief sets (never a value from another brief). Anything not listed here was found by every extraction sample and, where it carries a value, verified against a quote of the brief.

## Values a later rule replaced that another rule in force still carries

The rule named "new" replaced the value; the rule below still has it. Use the new value (outcome rows with a stale reason are left out of spec.json).

- **R43** (_brief-d.md email 'Hardship'_) still has ['hard'], replaced by R109 (old rule R69): If the transfer is declined, `add_note` reason `hardship` on every product with the circumstance in the customer's words, close `no_promise` with the hardship code (HARD in v3).

## Rules found by only one extraction sample (confidence low)

- **R08** (_brief-d.md item 1 'Opening'_, samples A): Then ask with the full name: "Am I speaking with {first_name} {last_name}?"
- **R31** (_brief-d.md item 1 'Stating the arrears'_, samples A): Call `get_account` only once both questions have passed.
- **R38** (_brief-d.md item 1 'Getting to a promise'_, samples A): A customer naming their own date or amount is never refusing; check it against CP-7 4.5 and 4.6.
- **R58** (_brief-d.md email 'Several products'_, samples C): Persuasion attempts are counted per product; every product starts at attempt 1.
- **R66** (_brief-d.md item 1 'Closing'_, samples A): Thank the customer and say goodbye.
- **R85** (_brief-d.md CP-7 section 4.5 table row full_, samples B): Customer agrees to the full overdue amount: accept.
- **R86** (_brief-d.md CP-7 section 4.5 table row in range_, samples B): Customer proposes an amount from floor up to full amount, both included: accept it as proposed.
- **R87** (_brief-d.md CP-7 section 4.5 table row above full_, samples B): Customer proposes more than the full amount: record the full amount.
- **R92** (_brief-d.md CP-7 section 4.6 table row valid_, samples B): Today or a later business day not after the latest date: accept.
- **R99** (_brief-d.md CP-7 section 4.8_, samples B): Amount in play is the full overdue amount, or the floor once the customer said the full amount is too much.
- **R112** (_brief-d.md memo closing paragraph_, samples A): Identity policy, question order, two-wrong-answer limit and opening words remain unchanged.

## Dated decisions (which statement is in force)

- **T1** topic `founders_day`: The email only says a memo will come. The 12 Oct memo then fixes Founders' Day, so the 'not a closure day until announced' rule no longer applies.
  - R02: not_policy -- "Dialler Ops are due to issue one before go-live with the Founders' Day date and a couple of tweaks from the Compliance review, so watch out for it."
  - R81: superseded by R107 -- "The Executive has fixed Founders' Day 2026 on **Friday 30 October**."
- **T2** topic `callback_window`: From 14 Oct the memo moves the end of the callback window to 18:00. Everything else about callbacks stays the same.
  - R17: superseded by R111 -- "Callbacks may be booked for any time **up to and including 18:00** (previously 17:00)."
  - R18: not_policy -- "Ops may extend the evening end, check the memo"
  - R83: superseded by R111 -- "Callbacks may be booked for any time **up to and including 18:00** (previously 17:00)."
  - R111: in_force from 2026-10-14 -- "Callbacks may be booked for any time **up to and including 18:00** (previously 17:00)."
- **T3** topic `dob_order_history`: Asking for the date of birth first is a past practice.
  - R25: not_policy -- "(Phone first: it is quicker and most people have it right; the old DOB-first order produced a lot of wasted calls.)"
- **T4** topic `dob_format`: The two candidates fit together: one sets how to read a spoken date, the other sets the service format.
  - R26: in_force -- "Our customers say dates day, month, year, so a date given only as numbers is day, then month, then year."
  - R113: in_force -- "Send the date of birth as YYYY-MM-DD however the customer said it; the service rejects anything it cannot read as a date."
- **T5** topic `card_floor`: This only says a review is under way. The decision itself is R106 in block T10.
  - R37: not_policy -- "Ops are reviewing the card floor, again see the memo"
- **T6** topic `close_call_last`: Both candidates say the same thing and fit together: the brief requires a code on every close.
  - R67: in_force -- "Then exactly one `close_call`, the last tool call of every call, always with an outcome and a code from the list."
  - R115: in_force -- "The dialler rejects a close without a code (yes, including promise closes, which carry PRM), and someone then has to re-code it by hand on Friday afternoon, which is nobody's favourite job."
- **T7** topic `closing_codes`: From 14 Oct the memo replaces the code HARD with HSHP. The rest of the code table is unchanged.
  - R69: superseded by R109 from 2026-09-01 -- "From Wednesday the close for "hardship, customer declined the transfer" is coded **HSHP** instead of HARD."
  - R71: superseded by R109 from 2026-09-01 -- "From Wednesday the close for "hardship, customer declined the transfer" is coded **HSHP** instead of HARD."
  - R109: in_force from 2026-10-14 -- "From Wednesday the close for "hardship, customer declined the transfer" is coded **HSHP** instead of HARD."
- **T8** topic `multi_product_close_precedence`: The order for choosing a close code now uses HSHP instead of HARD.
  - R74: superseded by R110 from 2026-09-01 -- "From Wednesday the close for "hardship, customer declined the transfer" is coded **HSHP** instead of HARD."
  - R110: in_force from 2026-10-14 -- "From Wednesday the close for "hardship, customer declined the transfer" is coded **HSHP** instead of HARD."
- **T9** topic `band_deadline`: The memo sets Band S to the 5th business day and 2 attempts. R102 still shows 3 attempts, so only R103 matches the full decision.
  - R77: superseded by R103 -- "The latest promise date in the standing band (11 to 45 days) is brought forward from the 7th business day after the call date to the **5th business day** after the call date."
  - R102: superseded by R103 from 2026-10-14 -- "From Wednesday: **two attempts in Band S, one in Band F**, exactly as the table in 4.8 reads without its last row."
  - R103: in_force from 2026-10-14 -- "From Wednesday: **two attempts in Band S, one in Band F**, exactly as the table in 4.8 reads without its last row."
- **T10** topic `floors`: From 14 Oct the credit card floor is 2 x minimum payment, never more than the overdue amount. Loan floors are unchanged.
  - R78: superseded by R106 -- "For credit cards the floor becomes **twice the minimum payment (2 x `minimum_payment`)**, but never more than the overdue amount."
  - R106: in_force from 2026-10-14 -- "For credit cards the floor becomes **twice the minimum payment (2 x `minimum_payment`)**, but never more than the overdue amount."
- **T11** topic `calendar`: Founders' Day, 30 Oct, is added to the closure days. The bridge day on 26 Oct is a rumour that the memo rejects.
  - R80: superseded by R107 -- "Branches, the processing centre and the dialler are closed; add it to the closure days in section 4.3."
  - R107: in_force from 2026-10-14 -- "Branches, the processing centre and the dialler are closed; add it to the closure days in section 4.3."
  - R108: not_policy -- "For the avoidance of doubt, Monday 26 October is a normal business day; the rumour about a bridge day is just that."
- **T12** topic `attempt_ladder`: From 14 Oct the third attempt, the final-offer repeat, is withdrawn.
  - R100: superseded by R104 -- "The third persuasion attempt, the "final-offer repeat" in section 4.8, is withdrawn."
  - R104: in_force from 2026-10-14 -- "The third persuasion attempt, the "final-offer repeat" in section 4.8, is withdrawn."


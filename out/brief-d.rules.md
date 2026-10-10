# Rule inventory: brief-d.md

Tool API: `openapi.json`. 117 rules (101 in force, 16 superseded or not policy, 19 low confidence).
Model claude-opus-5-5, 171 s, $2.41, 11 call(s); samples {'A': 101, 'B': 101, 'C': 100}; spec `brief-d.spec.json`; conflicts `brief-d.rules.conflicts.md`.
Self-check: every numbered rule is cited; every date and backticked token of the brief appears in the inventory.

## opening (5)

- **R07** — _brief-d.md email, 'Opening'_: First thing said on every call, word for word, the opening sentence; then ask whether speaking with {first_name} {last_name}.
  - verbatim: "This is the digital assistant of Kestrel Bank. Please note that this call is recorded."
  - verbatim: "Am I speaking with {first_name} {last_name}?"
- **R08** [confidence low, samples A] — _brief-d.md item 1 'Opening'_: Then ask with the full name: "Am I speaking with {first_name} {last_name}?"
  - verbatim: "Am I speaking with {first_name} {last_name}?"
- **R10** [verified] — _brief-d.md email 'Opening'_: Only "yes", "speaking", "that's me" or saying their own name confirms; "hello", "go ahead", "who's asking", "what is this about" do not. If unclear ask once more; still unclear: close `not_reached` code UNC.
  - values: `{"outcomes": [{"outcome": "not_reached", "reason": "UNC", "when": "still unclear after second ask"}]}`
- **R11** [confidence medium, samples AB] [verified] — _brief-d.md item 1 'Opening'_: If unclear, ask the same question once more; if still unclear after the second ask, close as not reached with code UNC.
  - values: `{"outcomes": [{"outcome": "not_reached", "reason": "UNC", "when": "still unclear after second ask"}]}`
- **R12** — _brief-d.md email 'Opening'_: If the person asks a question first (who is this, scam, robot), answer it then ask again; that ask counts as the second ask.

## third_party (10)

- **R16** — _brief-d.md item 1 'Someone else answers'_: If not the customer, say it is a personal banking matter it can only discuss with {title} {last_name}, and ask when he or she can be reached. Nothing more.
- **R17** **[superseded by R111]** [confidence low, samples ABC] **[verification: mismatch]** — _brief-d.md email, 'Someone else answers'_: Callback must be today later than `now`, or one of the next two business days, between 09:00 and 17:00 (CP-7 4.4); if it fits, `schedule_callback` with date and HH:MM, close not reached CBK.
  - values: `{"callback": {"open": "09:00", "close": "17:00", "same_day": true, "later_than_now": true, "days_ahead_business": 2}, "outcomes": [{"outcome": "not_reached", "reason": "CBK", "when": "callback booked"}]}`
  - deciding quote: "Callbacks may be booked for any time **up to and including 18:00** (previously 17:00)."
- **R18** **[not policy]** — _brief-d.md item 1 'Someone else answers'_: Ops may extend the evening end of the callback window; check the memo.
  - deciding quote: "Ops may extend the evening end, check the memo"
- **R19** [confidence low, samples A] [verified] — _brief-d.md item 1 'Someone else answers'_: If the offered time fits, call `schedule_callback` with date and time as HH:MM and close not reached with CBK.
  - values: `{"outcomes": [{"outcome": "not_reached", "reason": "CBK", "when": "callback booked"}]}`
- **R20** [verified] — _brief-d.md email 'Someone else answers'_: If the offered time is outside the window, propose the nearest slot inside it once; if not taken, book nothing and close `not_reached` NCB.
  - values: `{"outcomes": [{"outcome": "not_reached", "reason": "NCB", "when": "no callback inside window"}]}`
- **R21** [verified] — _brief-d.md email 'Someone else answers'_: If they say the number does not belong to the customer, close `not_reached` WN.
  - values: `{"outcomes": [{"outcome": "not_reached", "reason": "WN", "when": "wrong number"}]}`
- **R22** [verified] — _brief-d.md item 1 'Someone else answers'_: If told the customer has died, say the condolence sentence, ask nothing else, close with DEC.
  - verbatim: "Please accept my condolences."
  - values: `{"outcomes": [{"outcome": "not_reached", "reason": "DEC", "when": "customer deceased"}]}`
- **R23** — _brief-d.md item 1 'Someone else answers'_: A relative cannot answer security questions, be told anything about the account, or pay on the customer's behalf; decline politely and return to asking when the customer can be reached.
- **R83** **[superseded by R111]** — _brief-d.md CP-7 section 4.4_: Callback: today later than `now`, or either of next two business days, 09:00 to 17:00 inclusive; time recorded HH:MM.
  - values: `{"callback": {"open": "09:00", "close": "17:00", "same_day": true, "later_than_now": true, "days_ahead_business": 2}}`
  - deciding quote: "Callbacks may be booked for any time **up to and including 18:00** (previously 17:00)."
- **R111** [from 2026-10-14] [verified] (overrides R83) — _brief-d.md memo item 6_: From 14 Oct callbacks: today later than `now` or next two business days, 09:00 to 18:00 inclusive (was 17:00); time HH:MM.
  - values: `{"callback": {"open": "09:00", "close": "18:00", "same_day": true, "later_than_now": true, "days_ahead_business": 2}}`
  - deciding quote: "Callbacks may be booked for any time **up to and including 18:00** (previously 17:00)."

## identity (8)

- **R24** — _brief-d.md item 1 'Identity'_: Two questions, one at a time: first last four digits of phone, then date of birth; call `verify_identity` with field and answer after each.
  - values: `{"identity": [{"order": 1, "field": "phone_last4"}, {"order": 2, "field": "date_of_birth", "hint_values": ["day_month_swapped"]}]}`
- **R25** **[not policy]** [confidence low, samples A] — _brief-d.md item 1 'Identity'_: The old DOB-first order is no longer used (produced wasted calls).
  - deciding quote: "(Phone first: it is quicker and most people have it right; the old DOB-first order produced a lot of wasted calls.)"
- **R27** [verified] — _brief-d.md item 1 'Identity'_: The identity service allows three wrong answers and reports `wrong_answers_left`, but dialler policy is stricter: the second wrong answer, on either question, ends the check. Stop even if the service would continue. A wrong answer may be re-asked within that limit.
  - values: `{"max_wrong_answers": 2, "text": "ignore service `wrong_answers_left` (service allows 3); policy limit is 2"}`
- **R28** — _brief-d.md item 1 'Identity'_: On hint `day_month_swapped`, ask to repeat the date with the month as a word; this retry is not a wrong answer.
  - values: `{"identity": [{"order": 2, "field": "date_of_birth", "hint_values": ["day_month_swapped"], "retry_rule": "repeat the date with the month as a word; not a wrong answer"}]}`
- **R29** [verified] — _brief-d.md email 'Identity'_: When the check fails, do not say what the call is about; say for security it cannot continue by phone and they can use the Kestrel mobile app or a branch; close `not_verified` IDF.
  - values: `{"outcomes": [{"outcome": "not_verified", "reason": "IDF", "when": "identity check failed"}]}`
- **R30** [verified] — _brief-d.md email 'Identity'_: If the customer won't answer, explain once the questions protect their account and nothing can be discussed without them; if they still decline or ask again what it's about, close `not_verified` IDD.
  - values: `{"outcomes": [{"outcome": "not_verified", "reason": "IDD", "when": "declined identity check"}]}`
- **R112** [confidence low, samples A] — _brief-d.md memo closing paragraph_: Identity policy, question order, two-wrong-answer limit and opening words remain unchanged.
- **R113** — _openapi.json /verify_identity_: `answer` for date_of_birth must be YYYY-MM-DD; phone_last4 is four digits. An unreadable value is rejected with ok=false and not counted as a wrong answer.
  - deciding quote: "Send the date of birth as YYYY-MM-DD however the customer said it; the service rejects anything it cannot read as a date."

## disclosure (3)

- **R15** — _brief-d.md item 1 'Opening' para 2_: Before identity is confirmed nobody hears the listed words or any product name, including in the opening or when asked what it is about.
  - values: `{"forbidden_words_before_verification": ["arrears", "overdue", "late", "collections", "debt", "payment", "instalment"], "text": "plus the name of any product"}`
- **R31** [confidence low, samples A] — _brief-d.md item 1 'Stating the arrears'_: Call `get_account` only once both questions have passed.
- **R32** — _brief-d.md item 1 'Stating the arrears'_: Say you call from the arrears team about an overdue payment; per product one sentence: product in words (e.g. "your credit card ending 4821"), overdue amount, days overdue; all products before asking anything.

## dates (18)

- **R02** **[not policy]** [confidence low, samples A] — _brief-d.md item 1 email para 1_: Dialler Ops are due to issue a memo before go-live with the Founders' Day date and tweaks from the Compliance review.
  - deciding quote: "Dialler Ops are due to issue one before go-live with the Founders' Day date and a couple of tweaks from the Compliance review, so watch out for it."
- **R26** — _brief-d.md email, 'Identity'_: Send DOB as YYYY-MM-DD however said; a numeric-only date is day, then month, then year.
  - deciding quote: "Our customers say dates day, month, year, so a date given only as numbers is day, then month, then year."
- **R76** — _brief-d.md CP-7 section 4.1_: Band is set by each product's `days_late` on the call day, each product banded on its own. Call date is day 0; 'n-th business day after' counts the first business day after the call as 1.
- **R77** **[superseded by R103]** — _brief-d.md CP-7 section 4.1 table_: Band F (1-10): latest date 21 calendar days after call, previous business day if needed, 1 attempt. Band S (11-45): 7th business day after, 3 attempts. Over 45 treated as S.
  - values: `{"bands": [{"name": "F", "min_days": 1, "max_days": 10, "attempts": 1, "deadline_rule": {"type": "calendar_days_after", "n": 21, "adjust": "previous_business_day"}}, {"name": "S", "min_days": 11, "max_days": 45, "attempts": 3, "deadline_rule": {"type": "business_days_after", "n": 7, "adjust": "none"}}, {"name": "over 45", "min_days": 46, "max_days": null, "same_as": "S"}]}`
  - deciding quote: "The latest promise date in the standing band (11 to 45 days) is brought forward from the 7th business day after the call date to the **5th business day** after the call date."
- **R80** **[superseded by R107]** — _brief-d.md CP-7 section 4.3 table_: Business day = Monday to Friday not a closure day. Closure days: 2026-11-20, 2026-12-24, 2026-12-25, 2026-12-28, 2026-12-31.
  - values: `{"calendar": {"business_weekdays": ["Mon", "Tue", "Wed", "Thu", "Fri"], "holidays": [{"date": "2026-11-20", "name": "core systems migration"}, {"date": "2026-12-24", "name": "Christmas Eve"}, {"date": "2026-12-25", "name": "Christmas Day"}, {"date": "2026-12-28", "name": "Boxing Day (substitute)"}, {"date": "2026-12-31", "name": "New Year's Eve"}]}}`
  - deciding quote: "Branches, the processing centre and the dialler are closed; add it to the closure days in section 4.3."
- **R81** **[superseded by R107]** — _brief-d.md CP-7 section 4.3_: Founders' Day is fixed yearly by the Executive and announced by memo; until announced it is not a closure day.
  - deciding quote: "The Executive has fixed Founders' Day 2026 on **Friday 30 October**."
- **R82** — _brief-d.md CP-7 section 4.3_: No promise may be dated on a Saturday, a Sunday or a closure day.
- **R91** — _brief-d.md CP-7 section 4.6_: A promise date must be today or later, a business day, and not after the product's latest date. Today or later business day within latest date: accept.
- **R92** [confidence low, samples B] — _brief-d.md CP-7 section 4.6 table row valid_: Today or a later business day not after the latest date: accept.
- **R93** — _brief-d.md CP-7 section 4.6 table_: Valid day: accept; weekend/closure not after latest: offer nearest business day before; after latest: offer latest date, refusal = flat refusal; past day: ask for today onwards; vague: ask once, else last business day of week (or next if today), capped at latest.
- **R94** [confidence medium, samples BC] — _brief-d.md CP-7 section 4.6 table row after latest_: Any day after the latest date: say the latest date is the last day that can be recorded and offer it; if refused, flat refusal.
- **R95** [confidence medium, samples BC] — _brief-d.md CP-7 section 4.6 table row past_: A day before today cannot be recorded; ask for a day from today onwards.
- **R96** [confidence medium, samples BC] — _brief-d.md CP-7 section 4.6 table row vague_: Vague period: ask once for exact day; if none, propose last business day of current week (if today is it, next business day); if after latest date, propose latest date.
- **R97** — _brief-d.md CP-7 section 4.7_: 'Next <weekday>' = first such weekday after call date, even same week; 'this <weekday>' or bare weekday = same day. On that weekday: 'this' = today, 'next' = seven days later.
- **R102** **[superseded by R103]** [from 2026-10-14] [confidence low, samples C] **[verification: mismatch]** (overrides R77) — _brief-d.md memo 2026-10-12 item 1_: From 14 Oct 2026, Band S latest date is the 5th business day after call (was 7th). Band F unchanged; over 45 treated as S.
  - values: `{"bands": [{"name": "F", "min_days": 1, "max_days": 10, "deadline_rule": {"type": "calendar_days_after", "n": 21, "adjust": "previous_business_day"}, "attempts": 1}, {"name": "S", "min_days": 11, "max_days": 45, "deadline_rule": {"type": "business_days_after", "n": 5, "adjust": "none"}, "attempts": 3}, {"name": "over 45", "min_days": 46, "max_days": null, "same_as": "S"}]}`
  - deciding quote: "From Wednesday: **two attempts in Band S, one in Band F**, exactly as the table in 4.8 reads without its last row."
- **R103** [from 2026-10-14] [verified] (overrides R77) — _brief-d.md memo 2026-10-12 item 1-2_: From 14 October 2026: Band S latest date is the 5th business day after the call (was 7th) and gets 2 attempts (was 3). Band F unchanged; over 45 treated as S.
  - values: `{"bands": [{"name": "F", "min_days": 1, "max_days": 10, "attempts": 1, "deadline_rule": {"type": "calendar_days_after", "n": 21, "adjust": "previous_business_day"}}, {"name": "S", "min_days": 11, "max_days": 45, "attempts": 2, "deadline_rule": {"type": "business_days_after", "n": 5, "adjust": "none"}}, {"name": "over 45", "min_days": 46, "max_days": null, "same_as": "S"}]}`
  - deciding quote: "From Wednesday: **two attempts in Band S, one in Band F**, exactly as the table in 4.8 reads without its last row."
- **R107** [from 2026-10-14] [verified] (overrides R80) — _brief-d.md memo 2026-10-12 item 4_: From 14 October 2026 Founders' Day, Friday 2026-10-30, is added as a closure day; no promise may be dated 30 October. Business days Mon-Fri excluding listed closures.
  - values: `{"calendar": {"business_weekdays": ["Mon", "Tue", "Wed", "Thu", "Fri"], "holidays": [{"date": "2026-10-30", "name": "Founders' Day"}, {"date": "2026-11-20", "name": "core systems migration"}, {"date": "2026-12-24", "name": "Christmas Eve"}, {"date": "2026-12-25", "name": "Christmas Day"}, {"date": "2026-12-28", "name": "Boxing Day (substitute)"}, {"date": "2026-12-31", "name": "New Year's Eve"}]}}`
  - deciding quote: "Branches, the processing centre and the dialler are closed; add it to the closure days in section 4.3."
- **R108** **[not policy]** — _brief-d.md memo item 4_: Rumoured bridge day Monday 26 October is rejected; 2026-10-26 is a normal business day.
  - deciding quote: "For the avoidance of doubt, Monday 26 October is a normal business day; the rumour about a bridge day is just that."

## amounts (12)

- **R35** — _brief-d.md item 1 'Getting to a promise'_: Never ask the customer how much they can pay, in any wording; the assistant proposes every amount.
- **R36** — _brief-d.md email 'Getting to a promise'_: If the full amount is too much, offer the product's floor once (CP-7 4.2), saying the remainder stays overdue and the bank will be in touch; declining the floor is a flat refusal.
- **R37** **[not policy]** — _brief-d.md item 1 'Getting to a promise'_: Ops are reviewing the credit card floor; see the memo.
  - deciding quote: "Ops are reviewing the card floor, again see the memo"
- **R78** **[superseded by R106]** — _brief-d.md CP-7 section 4.2 table_: Floor is the smallest promise amount: credit_card `minimum_payment`; personal_loan and car_loan `instalment_amount`.
  - values: `{"floors": [{"product_types": ["credit_card"], "rule": {"type": "field", "field": "minimum_payment"}}, {"product_types": ["personal_loan", "car_loan"], "rule": {"type": "field", "field": "instalment_amount"}}]}`
  - deciding quote: "For credit cards the floor becomes **twice the minimum payment (2 x `minimum_payment`)**, but never more than the overdue amount."
- **R79** — _brief-d.md CP-7 section 4.2_: A promise may be any amount from the floor up to and including the overdue amount (`past_due`).
- **R84** — _brief-d.md CP-7 section 4.5 table_: Full: accept; floor..full: accept as proposed; above full: record full; below floor: say cannot record, offer floor once, declined = flat refusal; too much: offer floor once with remainder sentence; never ask how much.
  - values: `{"text": "remainder stays overdue and the bank will be in touch about it"}`
- **R85** [confidence low, samples B] — _brief-d.md CP-7 section 4.5 table row full_: Customer agrees to the full overdue amount: accept.
- **R86** [confidence low, samples B] — _brief-d.md CP-7 section 4.5 table row in range_: Customer proposes an amount from floor up to full amount, both included: accept it as proposed.
- **R87** [confidence low, samples B] — _brief-d.md CP-7 section 4.5 table row above full_: Customer proposes more than the full amount: record the full amount.
- **R88** [confidence medium, samples BC] — _brief-d.md CP-7 section 4.5 table row less than floor_: Customer proposes less than the floor: say it cannot be recorded, offer the floor once; if declined, treat as flat refusal.
- **R89** [confidence medium, samples BC] — _brief-d.md CP-7 section 4.5 table row too much_: Customer says full amount is too much: offer the floor once, saying the remainder stays overdue and the bank will be in touch; if declined, flat refusal.
- **R106** [from 2026-10-14] [verified] (overrides R78) — _brief-d.md memo item 3_: From 14 Oct credit card floor is 2 x `minimum_payment`, capped at `past_due` (was 1x); personal_loan and car_loan stay `instalment_amount`.
  - values: `{"floors": [{"product_types": ["credit_card"], "rule": {"type": "multiple", "factor": 2, "field": "minimum_payment", "cap_to_full": true}}, {"product_types": ["personal_loan", "car_loan"], "rule": {"type": "field", "field": "instalment_amount"}}]}`
  - deciding quote: "For credit cards the floor becomes **twice the minimum payment (2 x `minimum_payment`)**, but never more than the overdue amount."

## persuasion (11)

- **R34** — _brief-d.md item 1 'Getting to a promise'_: First ask word for word, always for the full overdue amount; with several products use the plural version.
  - verbatim: "Are you able to clear the overdue amount today?"
  - verbatim: "Are you able to clear all of these today?"
- **R38** [confidence low, samples A] — _brief-d.md item 1 'Getting to a promise'_: A customer naming their own date or amount is never refusing; check it against CP-7 4.5 and 4.6.
- **R39** — _brief-d.md email 'Getting to a promise'_: A named date or amount is never a refusal (check against 4.5/4.6); a flat refusal, non-answer, or no to today without date/amount uses one attempt; attempts per band per CP-7 4.1/4.8.
- **R40** [verified] — _brief-d.md email 'Getting to a promise'_: When attempts are used up, stop; never repeat a turned-down offer; note the product `refused` and, if nothing else applies, close `no_promise` RF.
  - values: `{"note_reasons": [{"reason": "refused", "when": "attempts used up"}], "outcomes": [{"outcome": "no_promise", "reason": "RF", "when": "attempts used up"}]}`
- **R90** [confidence medium, samples BC] — _brief-d.md CP-7 section 4.5 table row how much_: If asked 'how much should I pay?', the assistant proposes every amount; it never asks the customer how much they can pay.
- **R98** — _brief-d.md CP-7 section 4.8 intro_: An attempt is used on flat refusal, no answer, or no to today without date/amount; named date or amount is never refusal. Amount in play: full, or floor once full is too much.
- **R99** [confidence low, samples B] — _brief-d.md CP-7 section 4.8_: Amount in play is the full overdue amount, or the floor once the customer said the full amount is too much.
- **R100** **[superseded by R104]** — _brief-d.md CP-7 section 4.8 table_: Attempt 1 (F,S): amount in play, next business day. Attempt 2 (S): floor on latest date. Attempt 3 (S): repeat attempt 2 prefaced by mandatory sentence.
  - verbatim: "This is the last arrangement I can offer."
  - values: `{"attempt_ladder": [{"attempt": 1, "bands": ["F", "S"], "amount": "in_play", "date_rule": "the next business day after the call date"}, {"attempt": 2, "bands": ["S"], "amount": "floor", "date_rule": "the latest date"}, {"attempt": 3, "bands": ["S"], "amount": "floor", "date_rule": "the latest date", "text": "This is the last arrangement I can offer."}]}`
  - deciding quote: "The third persuasion attempt, the "final-offer repeat" in section 4.8, is withdrawn."
- **R101** — _brief-d.md CP-7 section 4.8_: When attempts are used up the assistant stops and the product is recorded as refused.
- **R104** [from 2026-10-14] (overrides R100) — _brief-d.md memo 2026-10-12 item 2_: From 14 October 2026 the 'final-offer repeat' attempt 3 is withdrawn: attempt 1 (F and S) amount in play on next business day; attempt 2 (S) floor on latest date. Never repeat a turned-down offer.
  - values: `{"attempt_ladder": [{"attempt": 1, "bands": ["F", "S"], "amount": "in_play", "date_rule": "the next business day after the call date"}, {"attempt": 2, "bands": ["S"], "amount": "floor", "date_rule": "the latest date"}]}`
  - deciding quote: "The third persuasion attempt, the "final-offer repeat" in section 4.8, is withdrawn."
- **R105** [confidence medium, samples AC] — _brief-d.md memo item 2_: The assistant never repeats an offer that has been turned down.

## hardship (4)

- **R41** [verified] — _brief-d.md email 'Hardship'_: On illness, bereavement, job loss or similar, say the sentence, make no persuasion attempt, and offer once a transfer to customer care (`support`); if accepted, `transfer_to_agent` `support`, close `transferred` TSP.
  - verbatim: "I am sorry to hear that."
  - values: `{"outcomes": [{"outcome": "transferred", "reason": "TSP", "when": "hardship transfer accepted"}]}`
- **R42** [confidence medium, samples AB] [verified] — _brief-d.md item 1 'Hardship'_: If accepted, `transfer_to_agent` queue `support` and close transferred TSP.
  - values: `{"outcomes": [{"outcome": "transferred", "reason": "TSP", "when": "hardship transfer accepted"}]}`
- **R43** **[stale value(s) ['hard']]** [confidence low, samples ABC] [verified] — _brief-d.md email 'Hardship'_: If the transfer is declined, `add_note` reason `hardship` on every product with the circumstance in the customer's words, close `no_promise` with the hardship code (HARD in v3).
  - values: `{"note_reasons": [{"reason": "hardship", "when": "transfer declined", "text_must_contain": "the circumstance in the customer's own words"}], "outcomes": [{"outcome": "no_promise", "reason": "HARD", "when": "hardship, transfer declined"}]}`
- **R44** — _brief-d.md email 'Hardship'_: If a hardship customer names a date or amount themselves, record the promise as normal; promise close applies.

## confirmation (1)

- **R46** — _brief-d.md email, 'Read-back and recording'_: Read back product, amount and date, then ask the confirm question; `create_promise` only after a clear yes; a changed value is rechecked against CP-7 and read back again.
  - verbatim: "Shall I record that?"

## recording (9)

- **R47** — _brief-d.md item 1 'Read-back and recording'_: One promise per product; a recorded promise cannot be changed or cancelled in the same call.
- **R48** — _brief-d.md item 1 'Read-back and recording'_: Say a promise is recorded only once `create_promise` returned `ok: true`.
- **R49** [verified] — _brief-d.md item 1 'Read-back and recording'_: On failure retry, up to three tries total; after the third fails tell the customer, `add_note` `service_error`, and with a single product close no promise SVC.
  - values: `{"note_reasons": [{"reason": "service_error", "when": "create_promise failed three times"}], "outcomes": [{"outcome": "no_promise", "reason": "SVC", "when": "single product, create_promise failed 3 times"}]}`
- **R50** — _brief-d.md item 1 'Read-back and recording'_: After a successful recording say the email sentence once per call, after the last promise.
  - verbatim: "We will email you a confirmation of this arrangement."
- **R62** — _brief-d.md item 1 'Several products'_: Every product ending without a promise gets an `add_note` with the code-list reason, also in single-product calls and when no product gets a promise.
- **R72** — _brief-d.md item 4 note reasons intro_: One `add_note` per product ending without a promise, except after a transfer (no notes) or when the account was never retrieved; reason must be one of five values; text must contain the listed content.
- **R73** [verified] — _brief-d.md item 4 note reasons table_: Note reasons table: refused, hardship, dispute, paid, service_error with required text content.
  - values: `{"note_reasons": [{"reason": "refused", "when": "attempts used up, or customer refuses the product", "text_must_contain": "the number of attempts made and the last offer (amount and date)"}, {"reason": "hardship", "when": "hardship disclosed, customer declined the transfer", "text_must_contain": "the circumstance in the customer's words"}, {"reason": "dispute", "when": "the customer disputes the product", "text_must_contain": "what is disputed"}, {"reason": "paid", "when": "the customer says the product is already paid", "text_must_contain": "the channel and the day the customer says they paid"}, {"reason": "service_error", "when": "`create_promise` failed on every try", "text_must_contain": "the words \"create_promise\" and the number of tries"}]}`
- **R116** — _openapi.json /create_promise_: `create_promise` requires `customer_id`, `product_id`, `amount` (number) and `date` (format date, YYYY-MM-DD); one per product.
- **R117** [confidence medium, samples BC] — _openapi.json /add_note_: `add_note` requires `product_id` and `reason` from enum `refused`, `hardship`, `dispute`, `paid`, `service_error`.

## special (8)

- **R13** — _brief-d.md item 1 'Opening'_: If anyone asks whether they talk to a robot or AI, answer the verbatim sentence and carry on.
  - verbatim: "I am Kestrel Bank's digital assistant."
- **R14** — _brief-d.md item 1 'Opening'_: If asked whether this is a scam, say they are welcome to hang up and call the number on the back of their card or on their statement, and carry on.
- **R51** [verified] — _brief-d.md item 1 'Other things'_: "I already paid": say the verbatim sentence, take no promise, `add_note` `paid` (channel and day), close paid AP.
  - verbatim: "Payments made today show on our side on the next business day."
  - values: `{"note_reasons": [{"reason": "paid", "when": "customer says already paid", "text_must_contain": "the channel and the day they say they paid"}], "outcomes": [{"outcome": "paid", "reason": "AP", "when": "already paid"}]}`
- **R52** [verified] — _brief-d.md email 'Other things'_: "Not mine"/"never had this": don't argue, no promise on that product, `add_note` `dispute`, close `no_promise` DSP.
  - values: `{"note_reasons": [{"reason": "dispute", "when": "customer disputes"}], "outcomes": [{"outcome": "no_promise", "reason": "DSP", "when": "dispute"}]}`
- **R53** [verified] — _brief-d.md item 1 'Other things'_: Plan/lower instalments/more time requests: describe nothing, `transfer_to_agent` queue `restructuring`, close transferred TRS.
  - values: `{"outcomes": [{"outcome": "transferred", "reason": "TRS", "when": "restructuring request"}]}`
- **R54** [verified] — _brief-d.md item 1 'Other things'_: Asked for a person: transfer straight away, `transfer_to_agent` queue `general`, close transferred TRH.
  - values: `{"outcomes": [{"outcome": "transferred", "reason": "TRH", "when": "human requested"}]}`
- **R55** [verified] — _brief-d.md email 'Other things'_: Say once it will only take a moment; if repeated, close IDD before identity confirmed, or RF after it with a `refused` note on every product.
  - values: `{"outcomes": [{"outcome": "not_verified", "reason": "IDD", "when": "before verification"}, {"outcome": "no_promise", "reason": "RF", "when": "after verification"}]}`
- **R56** — _brief-d.md item 1 'Other things'_: For a question not answerable from the tools, say the verbatim sentence.
  - verbatim: "I don't have that information."

## multi_product (11)

- **R57** [confidence medium, samples AC] — _brief-d.md email 'Several products'_: Band and latest date are per product from its `days_late`; state all products first, ask once about today, then go product by product in `get_account` order without asking about today again.
- **R58** [confidence low, samples C] — _brief-d.md email 'Several products'_: Persuasion attempts are counted per product; every product starts at attempt 1.
- **R59** [confidence medium, samples AB] — _brief-d.md item 1 'Several products'_: Ask once about clearing all today; if not, go product by product in `get_account` order without asking about today again; attempts counted per product, each starting at 1.
- **R60** — _brief-d.md item 1 'Several products'_: One named date is checked per product: a product with an earlier latest date goes on its latest date (said in read-back); closure days moved per 4.6; others keep the named date.
- **R61** — _brief-d.md item 1 'Several products'_: One read-back for everything, one "Shall I record that?", then `create_promise` once per product, in order.
- **R63** — _brief-d.md email, 'Several products'_: A dispute or already-paid claim on one product doesn't end the call; note it and continue with the others. If `create_promise` fails thrice for one product, keep others, note it `service_error`.
- **R64** — _brief-d.md item 1 'Several products'_: A transfer freezes the ledger: recorded promises stay, unrecorded agreements dropped, no notes after a transfer; close with the transfer's code.
- **R65** [confidence medium, samples AC] [verified] — _brief-d.md item 1 'Several products'_: If `create_promise` fails three times for one product, keep the others and note that product `service_error`.
  - values: `{"note_reasons": [{"reason": "service_error", "when": "create_promise failed three times for that product"}]}`
- **R74** **[superseded by R110]** [from 2026-09-01] — _brief-d.md item 4 closing with several products_: No promise: transfer code if transferred; else all `paid` -> paid/AP; else no_promise with most serious note: SVC, then HARD, then DSP, then RF.
  - values: `{"outcomes": [{"outcome": "paid", "reason": "AP", "when": "every product noted paid"}, {"outcome": "no_promise", "reason": "SVC", "when": "any service_error note"}, {"outcome": "no_promise", "reason": "HARD", "when": "else any hardship note"}, {"outcome": "no_promise", "reason": "DSP", "when": "else any dispute note"}, {"outcome": "no_promise", "reason": "RF", "when": "else refused"}]}`
  - deciding quote: "From Wednesday the close for "hardship, customer declined the transfer" is coded **HSHP** instead of HARD."
- **R75** [confidence low, samples A] [verified] — _brief-d.md item 4 closing with several products_: Whenever at least one promise was recorded and no transfer followed, close `promise` / PRM regardless of notes on other products.
  - values: `{"outcomes": [{"outcome": "promise", "reason": "PRM", "when": "at least one promise, no transfer after"}]}`
- **R110** [from 2026-10-14] [verified] (overrides R74) — _brief-d.md memo item 5_: No promise: transfer code if transferred; else all `paid` -> paid/AP; else no_promise with most serious note: SVC, then HSHP (was HARD), then DSP, then RF.
  - values: `{"outcomes": [{"outcome": "paid", "reason": "AP", "when": "every product noted paid"}, {"outcome": "no_promise", "reason": "SVC", "when": "any service_error note"}, {"outcome": "no_promise", "reason": "HSHP", "when": "else any hardship note"}, {"outcome": "no_promise", "reason": "DSP", "when": "else any dispute note"}, {"outcome": "no_promise", "reason": "RF", "when": "else refused"}]}`
  - deciding quote: "From Wednesday the close for "hardship, customer declined the transfer" is coded **HSHP** instead of HARD."

## closing (8)

- **R66** [confidence low, samples A] — _brief-d.md item 1 'Closing'_: Thank the customer and say goodbye.
- **R67** [verified] — _brief-d.md email, 'Closing'_: Thank the customer and say goodbye; then exactly one `close_call`, last tool call, always with outcome and code (promise closes carry PRM).
  - values: `{"outcomes": [{"outcome": "promise", "reason": "PRM", "when": "promise recorded"}]}`
  - deciding quote: "Then exactly one `close_call`, the last tool call of every call, always with an outcome and a code from the list."
- **R68** — _brief-d.md item 4 code list intro_: Every `close_call` carries one outcome from `promise`, `paid`, `transferred`, `no_promise`, `not_verified`, `not_reached` and exactly one code in `reason`; a close without a code is rejected.
- **R69** **[superseded by R109]** [from 2026-09-01] — _brief-d.md item 4 closing codes table_: Closing codes table: 17 situations mapped to outcome and reason code.
  - values: `{"outcomes": [{"outcome": "promise", "reason": "PRM", "when": "at least one promise recorded on this call, and no transfer afterwards"}, {"outcome": "paid", "reason": "AP", "when": "customer states already paid; no promise; every product noted paid"}, {"outcome": "transferred", "reason": "TRS", "when": "transferred to restructuring"}, {"outcome": "transferred", "reason": "TRH", "when": "transferred to human agent at customer's request (general)"}, {"outcome": "transferred", "reason": "TSP", "when": "transferred to customer care, hardship (support)"}, {"outcome": "no_promise", "reason": "RF", "when": "identity confirmed; attempts used up, or customer refuses to continue"}, {"outcome": "no_promise", "reason": "HARD", "when": "hardship disclosed; customer declined the transfer"}, {"outcome": "no_promise", "reason": "DSP", "when": "customer disputes the arrears"}, {"outcome": "no_promise", "reason": "SVC", "when": "bank service failed repeatedly after identity confirmed"}, {"outcome": "not_verified", "reason": "SVC", "when": "bank service failed repeatedly during identity check"}, {"outcome": "not_verified", "reason": "IDF", "when": "identity check failed (second wrong answer)"}, {"outcome": "not_verified", "reason": "IDD", "when": "declined identity check or would not talk before complete"}, {"outcome": "not_reached", "reason": "CBK", "when": "third party answered; callback booked"}, {"outcome": "not_reached", "reason": "NCB", "when": "third party answered; no callback inside the window"}, {"outcome": "not_reached", "reason": "WN", "when": "number does not belong to the customer"}, {"outcome": "not_reached", "reason": "DEC", "when": "customer deceased"}, {"outcome": "not_reached", "reason": "UNC", "when": "could not establish who answered"}]}`
  - deciding quote: "From Wednesday the close for "hardship, customer declined the transfer" is coded **HSHP** instead of HARD."
- **R70** — _brief-d.md item 4 note under closing codes_: A transfer always closes with its transfer code (TRS, TRH or TSP), even when a promise was recorded earlier on the call.
- **R71** **[superseded by R109]** [from 2026-09-01] [confidence low, samples C] **[verification: mismatch]** — _brief-d.md code list v3 closing codes table row 7_: Hardship disclosed and customer declined the customer care transfer: close `no_promise` / HARD.
  - values: `{"outcomes": [{"outcome": "no_promise", "reason": "HARD", "when": "hardship, declined transfer"}]}`
  - deciding quote: "From Wednesday the close for "hardship, customer declined the transfer" is coded **HSHP** instead of HARD."
- **R109** [from 2026-10-14] [verified] (overrides R69) — _brief-d.md memo item 5_: From 14 Oct hardship-declined close is coded HSHP instead of HARD (outcome still `no_promise`); rest of code table unchanged.
  - values: `{"outcomes": [{"outcome": "promise", "reason": "PRM", "when": "at least one promise recorded, no transfer afterwards"}, {"outcome": "paid", "reason": "AP", "when": "already paid; no promise; every product noted paid"}, {"outcome": "transferred", "reason": "TRS", "when": "transferred to restructuring"}, {"outcome": "transferred", "reason": "TRH", "when": "transferred to human agent (general)"}, {"outcome": "transferred", "reason": "TSP", "when": "transferred to customer care, hardship (support)"}, {"outcome": "no_promise", "reason": "RF", "when": "attempts used up or refuses to continue"}, {"outcome": "no_promise", "reason": "HSHP", "when": "hardship disclosed; customer declined the transfer"}, {"outcome": "no_promise", "reason": "DSP", "when": "customer disputes the arrears"}, {"outcome": "no_promise", "reason": "SVC", "when": "service failed repeatedly after identity confirmed"}, {"outcome": "not_verified", "reason": "SVC", "when": "service failed repeatedly during identity check"}, {"outcome": "not_verified", "reason": "IDF", "when": "second wrong answer"}, {"outcome": "not_verified", "reason": "IDD", "when": "declined identity check or would not talk"}, {"outcome": "not_reached", "reason": "CBK", "when": "third party; callback booked"}, {"outcome": "not_reached", "reason": "NCB", "when": "third party; no callback inside window"}, {"outcome": "not_reached", "reason": "WN", "when": "wrong number"}, {"outcome": "not_reached", "reason": "DEC", "when": "customer deceased"}, {"outcome": "not_reached", "reason": "UNC", "when": "could not establish who answered"}]}`
  - deciding quote: "From Wednesday the close for "hardship, customer declined the transfer" is coded **HSHP** instead of HARD."
- **R115** — _openapi.json /close_call_: `close_call` is always the last tool call; nothing is accepted after it. Service requires `reason` except for promise/paid, but brief policy requires a code on every close.
  - deciding quote: "The dialler rejects a close without a code (yes, including promise closes, which carry PRM), and someone then has to re-code it by hand on Friday afternoon, which is nobody's favourite job."

## wording (3)

- **R09** — _brief-d.md email 'Opening'_: Ask with the full name; once the right person is confirmed, address them as {title} {last_name}.
- **R33** — _brief-d.md email, 'Stating the arrears'_: Never mention consequences: no fees, credit file, legal action or "collectors".
- **R45** — _brief-d.md item 1 'Hardship'_: Offer no discount, waiver, payment holiday, plan, or any term not in the mail or CP-7.

## other (6)

- **R01** — _brief-d.md item 1 email para 1_: Numbers (bands, latest dates, floors, closure days) live in CP-7 and codes in the code list; where the mail and CP-7 disagree, CP-7 wins unless a later memo says otherwise.
- **R03** [confidence medium, samples AC] — _brief-d.md item 1 'Who we call'_: Calls go to personal customers with one, two or three products in arrears (credit cards, personal loans, car loans), between 1 and 45 days late.
- **R04** — _brief-d.md item 1 'Who we call'_: The dialler passes `customer_id`, `first_name`, `last_name`, `title` (Mr or Ms) and `now` (e.g. `2026-10-14T11:00`); every date rule runs off `now`, not the server clock.
- **R05** — _brief-d.md item 1 'Who we call'_: `customer_id` goes in every tool call, including `close_call`.
- **R06** — _brief-d.md item 1 'Who we call'_: The bank's side enforces nothing; the assistant must carry and enforce all CP-7 rules itself before recording anything.
- **R114** [confidence medium, samples BC] — _openapi.json /get_account_: `get_account` is refused until both questions pass; product `type` enum `credit_card`, `personal_loan`, `car_loan`; `minimum_payment` cards only, `instalment_amount` loans only.

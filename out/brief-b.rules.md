# Rule inventory: brief-a.md, brief-b.md

Tool API: `openapi.json`. 74 rules (68 in force, 6 superseded).
Model claude-opus-5-5, 101 s, $0.29, 1 call(s).
Self-check: every numbered rule is cited; every date and backticked token of the brief appears in the inventory.

## opening (3)

- **R05** — _brief-a.md rule 1_: First sentence: say you are a digital assistant calling from Freya Bank and that the call is recorded.
- **R07** — _brief-a.md rule 2_: Ask "Am I speaking with {title} {last_name}?" with the call variables filled in.
  - verbatim: "Am I speaking with {title} {last_name}?"
- **R08** — _brief-a.md rule 3_: Only "yes", "that's me", "speaking" or the customer's own name confirms identity of the person; otherwise ask once more, and if still unclear after the second ask close as `not_reached` / `unclear`. Answer a customer question first (rules 4 and 43); the ask that follows is the second ask.
  - values: `{"confirmation_words": ["yes", "that's me", "speaking", "own name"], "not_confirmation": ["hello", "go ahead", "who is this"], "max_asks": 2, "close": {"outcome": "not_reached", "reason": "unclear"}}`

## third_party (5)

- **R10** — _brief-a.md rule 5_: If someone else answers, do not say why you are calling, say nothing beyond the opening sentence of rule 1, and ask when the customer can be reached.
- **R11** — _brief-a.md rule 6_: A callback is for today or the next business day, from 10:00 to 19:00 both included, and later than `now`; call `schedule_callback` with the date and the time, then close as `not_reached` / `callback`.
  - values: `{"callback_window": {"days": "today or next business day", "from": "10:00", "to": "19:00", "inclusive": true, "later_than_now": true}, "tool": "schedule_callback", "close": {"outcome": "not_reached", "reason": "callback"}}`
- **R12** — _brief-a.md rule 7_: If the person offers a day or time outside the callback window, ask once for another time; if that is also outside it, do not schedule and close as `not_reached` / `no_callback`.
  - values: `{"max_reasks": 1, "close": {"outcome": "not_reached", "reason": "no_callback"}}`
- **R13** — _brief-a.md rule 8_: If the person says the number does not belong to the customer, close as `not_reached` / `wrong_number`.
  - values: `{"close": {"outcome": "not_reached", "reason": "wrong_number"}}`
- **R14** — _brief-a.md rule 9_: If the person says the customer has died, say "I am sorry for your loss.", ask nothing else, and close as `not_reached` / `deceased`.
  - verbatim: "I am sorry for your loss."
  - values: `{"close": {"outcome": "not_reached", "reason": "deceased"}}`

## identity (6)

- **R16** — _brief-a.md rule 11_: Ask two security questions one at a time: first the date of birth, then the last four digits of the phone number on file; call `verify_identity` with each answer.
  - values: `{"identity_fields": ["date_of_birth", "phone_last4"], "order": ["date_of_birth", "phone_last4"], "tool": "verify_identity"}`
- **R17** — _brief-a.md rule 11_: Send a date of birth as `YYYY-MM-DD` whatever way the customer said it (the service rejects anything it cannot read as a date); read a date given only as numbers as day, then month, then year.
  - values: `{"format": "YYYY-MM-DD", "numeric_order": "day-month-year"}`
- **R18** — _brief-a.md rule 12_: A wrong answer may be asked again; three wrong answers in total end the check, whichever question they were on.
  - values: `{"max_wrong_answers": 3}`
- **R19** — _brief-a.md rule 13_: If `verify_identity` returns `hint: "day_month_swapped"`, ask the customer to say the month as a word; that retry does not count as a wrong answer.
  - values: `{"hint": "day_month_swapped"}`
- **R20** — _brief-a.md rule 14_: After three wrong answers, do not state the debt; tell the customer to use the mobile app or a branch and close as `not_verified` / `failed`.
  - values: `{"close": {"outcome": "not_verified", "reason": "failed"}}`
- **R21** — _brief-a.md rule 15_: If the customer does not want to answer, explain once that the questions protect their account; if they still decline close as `not_verified` / `declined`. Asking what the call is about instead of answering counts as declining; a second refusal or second such question closes the call.
  - values: `{"explanations": 1, "close": {"outcome": "not_verified", "reason": "declined"}}`

## disclosure (4)

- **R06** — _brief-a.md rule 1_: Do not say "collections", "debt", "payment" or the product before identity is verified; this applies to everyone, including relatives.
  - values: `{"forbidden_before_verification": ["collections", "debt", "payment", "the product"]}`
- **R15** — _brief-a.md rule 10_: A relative may not answer the security questions and may not be told anything about the account, even if they offer to pay.
- **R22** — _brief-a.md rule 16_: Call `get_account` only after both security questions pass.
  - values: `{"tool": "get_account"}`
- **R23** **[superseded by R59]** — _brief-a.md rule 17_: After verification say you are calling from the collections team about a late payment, name the product in words ("credit card ending 4821", "personal loan" or "car loan"), and state the past-due amount and how many days late it is.
  - values: `{"product_names": {"credit_card": "credit card ending {card_last4}", "personal_loan": "personal loan", "car_loan": "car loan"}}`

## dates (8)

- **R03** — _brief-a.md section 2_: Nothing else than the call variables is known before the tools are called; all date rules use `now`, never the real clock.
- **R24** — _brief-a.md section 7_: Business days are Monday to Friday, except Freya Bank holidays: 2026-10-26, 2026-11-11, 2026-11-26, 2026-12-25, 2027-01-01.
  - values: `{"business_days": "Mon-Fri except holidays", "holidays": ["2026-10-26", "2026-11-11", "2026-11-26", "2026-12-25", "2027-01-01"]}`
- **R25** — _brief-a.md rule 18 table_: The deadline and number of persuasion attempts depend on `days_late`: 1 to 7 is early (12th business day after today, 1 attempt); 8 to 45 is late (7th business day after today, 2 attempts).
  - values: `{"bands": [{"name": "early", "min_days": 1, "max_days": 7, "deadline_rule": "the 12th business day after today", "attempts": 1}, {"name": "late", "min_days": 8, "max_days": 45, "deadline_rule": "the 7th business day after today", "attempts": 2}]}`
- **R26** — _brief-a.md rule 19_: A promise date must be today or later, a business day, and not after the deadline.
- **R27** — _brief-a.md rule 20_: If the customer names a weekend day or holiday not after the deadline, offer the next business day; if the named day is after the deadline, rule 23 applies.
- **R28** — _brief-a.md rule 21_: If the customer gives a vague period ("next week", "end of the month", "when my salary comes"), ask once for the exact day; if they still give none, propose the deadline.
  - values: `{"vague_examples": ["next week", "end of the month", "when my salary comes"], "max_reasks": 1}`
- **R29** — _brief-a.md rule 22_: "Next <weekday>" means that weekday in the following calendar week; "This <weekday>" means the one in the current week ("next Friday" said on a Friday is the Friday of the following week).
- **R30** — _brief-a.md rule 23_: If the customer asks for a date after the deadline, say the latest date you can record is the deadline and offer it; refusing the deadline is a flat refusal (rule 30).

## amounts (4)

- **R31** — _brief-a.md rule 24_: Ask for the full past-due amount first; never ask "how much can you pay?"; the agent proposes every amount.
  - values: `{"forbidden_question": "how much can you pay?"}`
- **R32** — _brief-a.md rule 25_: The floor is `minimum_payment` for a credit card and `instalment_amount` for a personal loan or a car loan.
  - values: `{"floor": {"credit_card": "minimum_payment", "personal_loan": "instalment_amount", "car_loan": "instalment_amount"}}`
- **R33** — _brief-a.md rule 26_: If the customer says the full amount is too much, offer the floor once and say the rest stays overdue; refusing the floor is a flat refusal (rule 30). Attempt 2 may name the floor again, on the deadline.
- **R34** — _brief-a.md rule 27_: Accept a customer-proposed amount from the floor up to the full amount, both included; below the floor say it cannot be recorded and offer the floor once; not accepting the floor is a flat refusal (rule 30).
  - values: `{"accepted_range": {"min": "floor", "max": "past_due", "inclusive": true}}`

## persuasion (5)

- **R35** **[superseded by R61]** — _brief-a.md rule 28_: First ask: "Can you make this payment today?".
  - verbatim: "Can you make this payment today?"
- **R36** — _brief-a.md rule 29_: A date or amount the customer proposes is never a refusal; handle it with sections 7 and 8.
- **R37** — _brief-a.md rule 30_: A flat refusal or non-answer (including a no to paying today with no date and no amount) uses one persuasion attempt. Attempt 1 (full past-due, or floor if full already said too much): last business day of this week, or of next week if today is that day; Attempt 2, late band only: floor amount on the deadline.
  - values: `{"attempts": [{"n": 1, "amount": "past_due (or floor if full amount already said too much)", "date": "last business day of this week; if today is that day, last business day of next week"}, {"n": 2, "bands": ["late"], "amount": "floor", "date": "deadline"}]}`
- **R38** — _brief-a.md rule 31_: When the attempts are used up, stop, do not repeat an offer already refused, and close as `no_promise` / `refused`.
  - values: `{"close": {"outcome": "no_promise", "reason": "refused"}}`
- **R40** — _brief-a.md rule 33_: Never offer a discount, a waiver, an instalment plan or any term that is not in this brief.
  - values: `{"forbidden_offers": ["discount", "waiver", "instalment plan", "any term not in the brief"]}`

## hardship (1)

- **R39** — _brief-a.md rule 32_: On illness, a death in the family or job loss: one short sentence of sympathy, no persuasion attempt, offer the customer support team; if accepted call `transfer_to_agent` queue `support` and close `transferred` / `support`, if declined close `no_promise` / `hardship`. This comes before rules 30 and 41; if the customer still names a date or amount, record the promise under sections 7 and 8.
  - values: `{"triggers": ["illness", "death in the family", "job loss"], "accept": {"tool": "transfer_to_agent", "queue": "support", "outcome": "transferred", "reason": "support"}, "decline": {"outcome": "no_promise", "reason": "hardship"}, "precedes": ["rule 30", "rule 41"]}`

## confirmation (3)

- **R41** **[superseded by R64]** — _brief-a.md rule 34_: Read the product, amount and date back and ask "Do you confirm?"; call `create_promise` only after a clear yes.
  - verbatim: "Do you confirm?"
  - values: `{"read_back": ["product", "amount", "date"]}`
- **R42** — _brief-a.md rule 35_: If the customer changes the date or amount at read-back, check the new value against sections 7 and 8 and read it back again.
- **R64** (overrides R41) — _brief-b.md rule 7_: Read all promises back together (product, amount, date each), ask "Do you confirm?" once for all, and only after a clear yes call `create_promise` once per product.
  - verbatim: "Do you confirm?"
  - values: `{"create_promise_calls": "one per product"}`

## recording (6)

- **R43** — _brief-a.md rule 36_: One promise per product; a recorded promise cannot be changed or cancelled in the same call; if asked, say they can change it in the mobile app.
  - values: `{"max_promises_per_product": 1}`
- **R44** **[superseded by R68]** — _brief-a.md rule 37_: Say the promise is recorded only after `create_promise` returns `ok: true`; if it fails try once more; if it fails again say you could not record it and close as `no_promise` / `service_error`.
  - values: `{"max_tries": 2, "close": {"outcome": "no_promise", "reason": "service_error"}}`
- **R45** — _brief-a.md rule 38_: After a recorded promise, say the mandatory text-message sentence.
  - verbatim: "You will receive a text message confirming this promise."
- **R55** **[superseded by R65]** — _brief-a.md section 12_: Brief A never uses `add_note`.
- **R65** (overrides R55) — _brief-b.md rule 8_: (Brief B replaces "never uses `add_note`") For each product without a promise call `add_note` with that `product_id` and a reason `refused`, `hardship`, `dispute`, `paid` or `service_error`, also when no product gets a promise (except on transfers, rule 10).
  - values: `{"tool": "add_note", "reasons": ["refused", "hardship", "dispute", "paid", "service_error"]}`
- **R68** (overrides R44) — _brief-b.md rule 11_: Say a promise is recorded only after `create_promise` returns `ok: true`; if it fails try once more; if one `create_promise` fails twice, say it could not be recorded, keep the promises that were recorded and call `add_note` with reason `service_error` for the failed product.
  - values: `{"max_tries": 2, "note_reason": "service_error"}`

## special (8)

- **R09** — _brief-a.md rule 4_: If the customer asks whether you are a robot or an AI, say that you are Freya Bank's digital assistant and continue.
- **R46** — _brief-a.md rule 39_: "I already paid": say payments can take one business day to appear, take no promise, and close as `paid`.
  - values: `{"close": {"outcome": "paid"}}`
- **R47** — _brief-a.md rule 40_: "This debt is not mine" or "I never had this product": do not argue, take no promise, close as `no_promise` / `dispute`. A claim that the product was closed or paid off in the past is a dispute; rule 39 covers only a payment of this past-due amount.
  - values: `{"close": {"outcome": "no_promise", "reason": "dispute"}}`
- **R48** — _brief-a.md rule 41_: A request for a new payment plan or lower instalments: do not describe a plan; call `transfer_to_agent` with queue `restructuring` and close as `transferred` / `restructuring`.
  - values: `{"tool": "transfer_to_agent", "queue": "restructuring", "outcome": "transferred", "reason": "restructuring"}`
- **R49** — _brief-a.md rule 42_: A request for a human: ask once whether you can help first; if they insist call `transfer_to_agent` with queue `general` and close as `transferred` / `human`.
  - values: `{"tool": "transfer_to_agent", "queue": "general", "outcome": "transferred", "reason": "human"}`
- **R50** — _brief-a.md rule 43_: "Is this a scam?": say they can verify the call by phoning Freya Bank's customer service number, and continue.
- **R51** — _brief-a.md rule 44_: For a question you cannot answer from the tools, say you do not have that information; do not invent figures, dates or reasons.
- **R52** — _brief-a.md rule 45_: If the customer says twice they do not want to talk, close as `no_promise` / `refused`; before identity is verified close as `not_verified` / `declined`. Rule 42 applies before and after verification.
  - values: `{"after_verification": {"outcome": "no_promise", "reason": "refused"}, "before_verification": {"outcome": "not_verified", "reason": "declined"}}`

## multi_product (9)

- **R57** — _brief-b.md intro_: Brief B is Brief A with a customer late on up to three products; every rule of Brief A applies unless a Brief B rule replaces it.
  - values: `{"max_products": 3}`
- **R58** (overrides R01) — _brief-b.md rule 1_: (Brief B replaces the one-product scope) Freya Bank calls customers 1 to 45 days late; `get_account` returns one to three products, each with its own `past_due`, `days_late` and floor.
  - values: `{"products": {"min": 1, "max": 3}, "per_product": ["past_due", "days_late", "floor"]}`
- **R59** (overrides R23) — _brief-b.md rule 2_: After verification, say you are calling from the collections team about a late payment and state every late product, one sentence each (product named in words, past-due amount, days late), before asking for anything.
- **R60** — _brief-b.md rule 3_: The band and the deadline are per product, from that product's `days_late`; two products of the same customer can have different deadlines.
- **R61** (overrides R35) — _brief-b.md rule 4_: First ask whether the customer can pay all of them today; if not, go through the products one by one in `get_account` order, without asking about today again per product, starting each product at attempt 1 of Brief A rule 30.
  - values: `{"order": "get_account order"}`
- **R62** — _brief-b.md rule 5_: Persuasion attempts are counted per product.
- **R63** — _brief-b.md rule 6_: If the customer names one date for everything and it is after one product's deadline, record that product on its own deadline and say so in the read-back; the other products keep the named date.
- **R66** — _brief-b.md rule 9_: A dispute or an "already paid" claim on one product does not end the call; note it and continue with the others.
- **R67** — _brief-b.md rule 10_: A restructuring request still transfers (`transfer_to_agent` queue `restructuring`); promises recorded before stay, agreed but unrecorded ones are not recorded; close `transferred` / `restructuring`. On any transfer (restructuring, support, human) add no notes at all, before or after it.
  - values: `{"close": {"outcome": "transferred", "reason": "restructuring"}, "no_notes_on": ["restructuring", "support", "human"]}`

## closing (5)

- **R53** — _brief-a.md rule 46 and table_: Every call ends with exactly one `close_call`, with an outcome and, where the table lists one, a reason; it is the last tool call.
  - values: `{"outcomes": [{"outcome": "promise", "reason": "none", "when": "at least one promise was recorded"}, {"outcome": "paid", "reason": "none", "when": "rule 39"}, {"outcome": "transferred", "reasons": ["restructuring", "human", "support"], "when": "rules 41, 42, 32"}, {"outcome": "no_promise", "reasons": ["refused", "hardship", "dispute", "service_error"], "when": "rules 31 and 45, 32, 40, 37"}, {"outcome": "not_verified", "reasons": ["failed", "declined"], "when": "rules 14, 15"}, {"outcome": "not_reached", "reasons": ["callback", "no_callback", "wrong_number", "deceased", "unclear"], "when": "rules 6, 7, 8, 9, 3"}]}`
- **R54** — _brief-a.md section 12 note_: If a transfer follows a recorded promise, close as `transferred` with that transfer's reason.
- **R56** — _brief-a.md rule 47_: Thank the customer and say goodbye before `close_call`.
- **R69** — _brief-b.md Closing_: Brief A outcome table applies. With no promise recorded: if every product is noted `paid`, close as `paid`; otherwise `no_promise` with the reason of the first product in `get_account` order whose note is not `paid`. `promise` wins whenever at least one promise was recorded, except rule 10 (transfer).
  - values: `{"precedence": ["transferred (rule 10/transfers)", "promise", "paid if all noted paid", "no_promise with first non-paid note reason"]}`
- **R74** — _openapi.json /close_call_: `close_call` is always the last tool call and nothing is accepted after it; `reason` is required for every outcome except `promise` and `paid`.
  - values: `{"outcome_enum": ["promise", "paid", "transferred", "no_promise", "not_verified", "not_reached"], "reason_not_required_for": ["promise", "paid"]}`

## wording (1)

- **R04** — _brief-a.md section 2 table row title_: Address the customer as `title` plus `last_name` (e.g. "Mr Reyes").
  - values: `{"title_values": ["Mr", "Ms"]}`

## other (6)

- **R01** **[superseded by R58]** — _brief-a.md section 1_: Freya Bank calls customers who are 1 to 45 days late on one product; the agent finds the customer, checks identity, states the debt, gets a payment promise where it can, and closes the call with the correct outcome.
  - values: `{"days_late_range": {"min": 1, "max": 45}, "products": 1}`
- **R02** — _brief-a.md section 2 table_: Every call starts with the call variables `customer_id`, `first_name`, `last_name`, `title`, `now`; `customer_id` is passed to every tool call.
  - values: `{"variables": [{"name": "customer_id", "example": "c_4f2a...", "meaning": "Pass it to every tool call."}, {"name": "first_name, last_name", "example": "Daniel, Reyes", "meaning": "The person to ask for."}, {"name": "title", "example": "Mr or Ms", "meaning": "Address the customer as title plus last name."}, {"name": "now", "example": "2026-10-14T11:00", "meaning": "The current date and time. All date rules use this, never the real clock."}]}`
- **R70** — _openapi.json /verify_identity_: `verify_identity` checks one answer: `field` is `date_of_birth` or `phone_last4`; `phone_last4` is four digits; an unreadable date is rejected with ok=false and is not counted as a wrong answer.
  - values: `{"field_enum": ["date_of_birth", "phone_last4"], "phone_last4": "four digits"}`
- **R71** — _openapi.json /get_account_: `get_account` is refused until both questions are passed; product `type` is `credit_card`, `personal_loan` or `car_loan`; `card_last4` and `minimum_payment` are credit cards only, `instalment_amount` loans only.
  - values: `{"type_enum": ["credit_card", "personal_loan", "car_loan"]}`
- **R72** — _openapi.json /create_promise_: `create_promise` requires `customer_id`, `product_id`, `amount` (number) and `date` (format date, YYYY-MM-DD).
  - values: `{"required": ["customer_id", "product_id", "amount", "date"]}`
- **R73** — _openapi.json /schedule_callback_: `schedule_callback` requires `date` (format date) and `time` as `HH:MM`.
  - values: `{"time_format": "HH:MM"}`

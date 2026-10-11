# Rule inventory: brief-a.md

Tool API: `openapi.json`. 60 rules (60 in force, 0 superseded or not policy, 2 low confidence).
Model gpt-6.1-sol, 138 s, cost unavailable (see provider usage), 8 call(s); samples {'A': 59, 'B': 59, 'C': 56}; spec `brief-a.spec.json`; conflicts `brief-a.rules.conflicts.md`.
Self-check: every numbered rule is cited; every date and backticked token of the brief appears in the inventory.

## opening (3)

- **R04** — _brief-a.md rule 1_: In the first sentence, say you are a digital assistant calling from Freya Bank and that the call is recorded.
- **R06** — _brief-a.md rule 2_: Ask "Am I speaking with {title} {last_name}?".
  - verbatim: "Am I speaking with {title} {last_name}?"
- **R07** [verified] — _brief-a.md rule 3_: Only "yes", "that's me", "speaking" or the customer's own name confirms identity; "Hello", "go ahead" and "who is this" do not. Ask once more; continued uncertainty closes as `not_reached` / `unclear`.
  - values: `{"outcomes": [{"outcome": "not_reached", "reason": "unclear", "when": "Still unclear after the second ask."}], "text": "Answer a customer question first (rules 4 and 43); the ask that follows is the second ask."}`

## third_party (6)

- **R09** — _brief-a.md rule 5_: When someone else answers, do not say why you are calling or disclose anything beyond rule 1's opening sentence. Ask when the customer can be reached.
- **R10** [verified] — _brief-a.md rule 6_: Callbacks must be today or the next business day, "10:00" to "19:00" inclusive, later than `now`. Call `schedule_callback` with date and time, then close `not_reached` / `callback`.
  - values: `{"callback": {"open": "10:00", "close": "19:00", "same_day": true, "later_than_now": true, "days_ahead_business": 1, "text": "both included"}, "outcomes": [{"outcome": "not_reached", "reason": "callback", "when": "after scheduling a callback"}]}`
- **R11** [verified] — _brief-a.md rule 7_: For a day or time outside rule 6's window, ask once for another time. If that is also outside the window, do not schedule; close as `not_reached` / `no_callback`.
  - values: `{"outcomes": [{"outcome": "not_reached", "reason": "no_callback", "when": "The alternative callback day or time is also outside the window."}]}`
- **R12** [verified] — _brief-a.md rule 8_: If the person says the number does not belong to the customer, close as `not_reached` / `wrong_number`.
  - values: `{"outcomes": [{"outcome": "not_reached", "reason": "wrong_number", "when": "The person says the number does not belong to the customer."}]}`
- **R13** [verified] — _brief-a.md rule 9_: If told the customer has died, say "I am sorry for your loss.", ask nothing else, and close as `not_reached` / `deceased`.
  - verbatim: "I am sorry for your loss."
  - values: `{"outcomes": [{"outcome": "not_reached", "reason": "deceased", "when": "The person says the customer has died."}]}`
- **R14** — _brief-a.md rule 10_: A relative may not answer security questions or be told anything about the account, even if they offer to pay.

## identity (6)

- **R15** — _brief-a.md rule 11_: Ask date of birth, then phone number's last four digits, one at a time; call `verify_identity` with each answer. Convert birth dates to `YYYY-MM-DD`; read numeric dates as day, month, year.
  - values: `{"identity": [{"order": 1, "field": "date_of_birth"}, {"order": 2, "field": "phone_last4"}], "text": "The service rejects anything it cannot read as a date."}`
- **R16** [verified] — _brief-a.md rule 12_: A wrong answer may be asked again; "Three" wrong answers in total end the check, whichever question they were on.
  - values: `{"max_wrong_answers": 3}`
- **R17** — _brief-a.md rule 13_: When `verify_identity` returns `hint: "day_month_swapped"`, ask the customer to say the month as a word. That retry does not count as a wrong answer.
  - values: `{"identity": [{"order": 1, "field": "date_of_birth", "hint_values": ["day_month_swapped"], "retry_rule": "Ask them to say the month as a word. That retry does not count as a wrong answer."}]}`
- **R18** [verified] — _brief-a.md rule 14_: After "three" wrong answers, do not state the debt; tell the customer to use the mobile app or a branch. Close as `not_verified` / `failed`.
  - values: `{"outcomes": [{"outcome": "not_verified", "reason": "failed", "when": "After three wrong answers."}]}`
- **R19** [verified] — _brief-a.md rule 15_: On refusal to answer, explain once that questions protect the account; asking what the call is about instead counts as declining. A second refusal or second such question closes as `not_verified` / `declined`.
  - values: `{"outcomes": [{"outcome": "not_verified", "reason": "declined", "when": "Still declines after one explanation; a second refusal or a second question about what the call is about instead of answering."}]}`
- **R57** — _openapi.json /verify_identity_: `verify_identity` requires `customer_id`, `field` and string `answer`; `field` is `date_of_birth` or `phone_last4`. For `phone_last4`, supply four digits; an unreadable date returns `ok=false` and does not count as a wrong answer.
  - values: `{"text": "Required: customer_id: string; field: string, enum [\"date_of_birth\", \"phone_last4\"]; answer: string. phone_last4: four digits. Unreadable date: ok=false, no wrong-answer count."}`

## disclosure (3)

- **R05** — _brief-a.md rule 1_: Before identity is verified, do not say "collections", "debt", "payment" or the product; this applies to everyone, including relatives.
  - values: `{"forbidden_words_before_verification": ["collections", "debt", "payment"], "text": "Do not name the product before verification."}`
- **R20** — _brief-a.md rule 16_: After both security questions pass, call `get_account`.
- **R21** — _brief-a.md rule 17_: Say you are calling from the collections team about a late payment; name the product in words: "credit card ending 4821", "personal loan" or "car loan". State past-due amount and days late.

## dates (7)

- **R22** [verified] — _brief-a.md section 7 business days definition_: Business days are Monday to Friday except Freya Bank holidays: "2026-10-26", "2026-11-11", "2026-11-26", "2026-12-25", "2027-01-01".
  - values: `{"calendar": {"business_weekdays": ["Mon", "Tue", "Wed", "Thu", "Fri"], "holidays": [{"date": "2026-10-26"}, {"date": "2026-11-11"}, {"date": "2026-11-26"}, {"date": "2026-12-25"}, {"date": "2027-01-01"}]}}`
- **R23** [verified] — _brief-a.md rule 18 and section 7 table_: The deadline and persuasion allowance depend on `days_late`: "1 to 7" is "early", "the 12th business day after today", "1" attempt; "8 to 45" is "late", "the 7th business day after today", "2" attempts.
  - values: `{"bands": [{"name": "early", "min_days": 1, "max_days": 7, "deadline_rule": {"type": "business_days_after", "n": 12, "adjust": "none"}, "attempts": 1}, {"name": "late", "min_days": 8, "max_days": 45, "deadline_rule": {"type": "business_days_after", "n": 7, "adjust": "none"}, "attempts": 2}]}`
- **R24** — _brief-a.md rule 19_: A promise date must be today or later, a business day, and not after the deadline.
- **R25** — _brief-a.md rule 20_: For a named weekend day or holiday not after the deadline, offer the next business day. If the named day is after the deadline, rule 23 applies.
- **R26** — _brief-a.md rule 21_: For a vague period ("next week", "end of the month", "when my salary comes"), ask once for the exact day. If still none is given, propose the deadline.
- **R27** — _brief-a.md rule 22_: "Next <weekday>" means that weekday in the following calendar week; "This <weekday>" means the current week. "next Friday" said on a Friday is the Friday of the following week.
- **R28** — _brief-a.md rule 23_: For a requested date after the deadline, say the latest date you can record is the deadline and offer it. Refusing the deadline is a flat refusal under rule 30.

## amounts (4)

- **R29** — _brief-a.md rule 24_: Ask for the full past-due amount first. Never ask "how much can you pay?"; the agent proposes every amount.
- **R30** [verified] — _brief-a.md rule 25_: The floor is `minimum_payment` for a credit card and `instalment_amount` for a personal loan or car loan.
  - values: `{"floors": [{"product_types": ["credit_card"], "rule": {"type": "field", "field": "minimum_payment"}}, {"product_types": ["personal_loan", "car_loan"], "rule": {"type": "field", "field": "instalment_amount"}}]}`
- **R31** — _brief-a.md rule 26_: If the full amount is too much, offer the floor once and say the rest stays overdue. Floor refusal is a flat refusal (rule 30); Attempt 2 may repeat the floor on the deadline.
- **R32** — _brief-a.md rule 27_: Accept customer-proposed amounts from floor to full amount, inclusive. Below floor, say it cannot be recorded and offer floor once; nonacceptance is a flat refusal (rule 30).

## persuasion (5)

- **R33** — _brief-a.md rule 28_: First ask: "Can you make this payment today?".
  - verbatim: "Can you make this payment today?"
- **R34** — _brief-a.md rule 29_: A customer-proposed date or amount is never a refusal; handle it under sections 7 and 8.
- **R35** — _brief-a.md rule 30_: A flat refusal or non-answer uses one persuasion attempt; refusing today without a date or amount is a flat refusal. Use the specified attempt ladder.
  - values: `{"attempt_ladder": [{"attempt": 1, "bands": [], "amount": "in_play", "date_rule": "the last business day of this week. If today is that day, propose the last business day of next week", "text": "the full past-due amount, or for the floor if the customer already said the full amount is too much"}, {"attempt": 2, "bands": ["late"], "amount": "floor", "date_rule": "on the deadline"}]}`
- **R36** [verified] — _brief-a.md rule 31_: Stop when attempts are used up; do not repeat an already-refused offer. Close as `no_promise` / `refused`.
  - values: `{"outcomes": [{"outcome": "no_promise", "reason": "refused", "when": "When the attempts are used up"}]}`
- **R39** — _brief-a.md rule 33_: Never offer a discount, waiver, instalment plan or any term absent from this brief.

## hardship (2)

- **R37** [verified] — _brief-a.md rule 32_: Illness, family death or job loss: give brief sympathy, no persuasion, offer support transfer. Prioritize over rules 30 and 41; still record voluntarily proposed dates or amounts under sections 7 and 8.
  - values: `{"outcomes": [{"outcome": "transferred", "reason": "support", "when": "If they accept, call `transfer_to_agent` with queue `support`"}, {"outcome": "no_promise", "reason": "hardship", "when": "If they decline"}]}`
- **R38** [confidence low, samples B] — _brief-a.md rule 32_: If the hardship customer still names a date or amount themselves, record the promise under sections 7 and 8.

## confirmation (2)

- **R40** — _brief-a.md rule 34_: Read back product, amount and date, then ask "Do you confirm?". Call `create_promise` only after a clear yes.
  - verbatim: "Do you confirm?"
- **R41** — _brief-a.md rule 35_: If the customer changes date or amount during confirmation, check the new value under sections 7 and 8 and read it back again.

## recording (6)

- **R42** — _brief-a.md rule 36_: Record one promise per product. A recorded promise cannot be changed or cancelled in the same call; tell customers requesting this they can change it in the mobile app.
- **R43** [verified] — _brief-a.md rule 37_: Say recorded only after `create_promise` returns `ok: true`. Retry failure once; after another failure, say recording failed and close as `no_promise` / `service_error`.
  - values: `{"outcomes": [{"outcome": "no_promise", "reason": "service_error", "when": "If `create_promise` fails again after one retry"}]}`
- **R44** — _brief-a.md rule 38_: After recording a promise, say "You will receive a text message confirming this promise.".
  - verbatim: "You will receive a text message confirming this promise."
- **R55** — _brief-a.md section 12 add_note note_: Brief A never uses `add_note`.
- **R58** [confidence medium, samples AB] — _openapi.json /create_promise_: `create_promise` requires string `customer_id`, string `product_id`, numeric `amount` and string `date` in date format.
  - values: `{"text": "Required: customer_id: string; product_id: string; amount: number; date: string, format date."}`
- **R59** — _openapi.json /schedule_callback_: `schedule_callback` requires string `customer_id`, string `date` in date format and string `time` as `HH:MM`.
  - values: `{"text": "Required: customer_id: string; date: string, format date; time: string, HH:MM."}`

## special (8)

- **R08** — _brief-a.md rule 4_: If asked whether you are a robot or an AI, say you are Freya Bank's digital assistant and continue.
- **R45** [verified] — _brief-a.md rule 39_: For "I already paid", say payments can take one business day to appear, take no promise and close as `paid`.
  - values: `{"outcomes": [{"outcome": "paid", "reason": "", "when": "\"I already paid\""}]}`
- **R46** [verified] — _brief-a.md rule 40_: Debt/product denial or claims of past closure/payoff are disputes: do not argue or take a promise; close `no_promise` / `dispute`. Rule 39 covers only payment of this past-due amount.
  - values: `{"outcomes": [{"outcome": "no_promise", "reason": "dispute", "when": "\"This debt is not mine\", \"I never had this product\", or a claim that the product was closed or paid off in the past"}]}`
- **R47** [verified] — _brief-a.md rule 41_: For requests for a new payment plan or lower instalments, do not describe a plan. Call `transfer_to_agent` with queue `restructuring`, then close `transferred` / `restructuring`.
  - values: `{"outcomes": [{"outcome": "transferred", "reason": "restructuring", "when": "A request for a new payment plan or lower instalments"}]}`
- **R48** [verified] — _brief-a.md rule 42_: For a human request, ask once whether you can help first. If they insist, call `transfer_to_agent` with queue `general`, then close `transferred` / `human`.
  - values: `{"outcomes": [{"outcome": "transferred", "reason": "human", "when": "Customer insists on a human after being asked once whether the agent can help first"}]}`
- **R49** — _brief-a.md rule 43_: For "Is this a scam?", say they can verify the call by phoning Freya Bank's customer service number, and continue.
- **R50** — _brief-a.md rule 44_: For questions unanswerable from tools, say you do not have that information. Do not invent figures, dates or reasons.
- **R51** [verified] — _brief-a.md rule 45_: After twice saying they do not want to talk, close `no_promise` / `refused`, or `not_verified` / `declined` before verification. Rule 42 applies before and after verification.
  - values: `{"outcomes": [{"outcome": "no_promise", "reason": "refused", "when": "Customer says twice that they do not want to talk after verification"}, {"outcome": "not_verified", "reason": "declined", "when": "Customer says twice that they do not want to talk before identity is verified"}]}`

## closing (4)

- **R52** — _brief-a.md rule 46_: Every call ends with exactly one `close_call`, supplying outcome and a reason where listed in the table. It is the last tool call.
- **R53** [verified] — _brief-a.md section 12 outcome table_: Use the outcome/reason table for `close_call`; `promise` and `paid` have no reason.
  - values: `{"outcomes": [{"outcome": "promise", "reason": "", "when": "at least one promise was recorded"}, {"outcome": "paid", "reason": "", "when": "rule 39"}, {"outcome": "transferred", "reason": "restructuring", "when": "rule 41"}, {"outcome": "transferred", "reason": "human", "when": "rule 42"}, {"outcome": "transferred", "reason": "support", "when": "rule 32"}, {"outcome": "no_promise", "reason": "refused", "when": "rules 31 and 45"}, {"outcome": "no_promise", "reason": "hardship", "when": "rule 32"}, {"outcome": "no_promise", "reason": "dispute", "when": "rule 40"}, {"outcome": "no_promise", "reason": "service_error", "when": "rule 37"}, {"outcome": "not_verified", "reason": "failed", "when": "rule 14"}, {"outcome": "not_verified", "reason": "declined", "when": "rule 15"}, {"outcome": "not_reached", "reason": "callback", "when": "rule 6"}, {"outcome": "not_reached", "reason": "no_callback", "when": "rule 7"}, {"outcome": "not_reached", "reason": "wrong_number", "when": "rule 8"}, {"outcome": "not_reached", "reason": "deceased", "when": "rule 9"}, {"outcome": "not_reached", "reason": "unclear", "when": "rule 3"}]}`
- **R54** — _brief-a.md section 12 transfer note_: If a transfer follows a recorded promise, close as `transferred` with that transfer's reason.
- **R56** — _brief-a.md rule 47_: Thank the customer and say goodbye before `close_call`.

## other (4)

- **R01** — _brief-a.md section 1_: Call customers who are "1 to 45" days late on one product; find the customer, check identity, state the debt, seek a payment promise where possible, and close with the correct outcome.
  - values: `{"text": "Scope: one product; 1 to 45 days late."}`
- **R02** [confidence medium, samples AB] — _brief-a.md section 2_: Every call starts with the listed call variables; nothing else is known before tools are called.
- **R03** — _brief-a.md section 2 table_: Only the listed variables are known before tools are called; pass `customer_id` to every tool, address the customer by title plus last name, and use `now`, never the real clock.
  - values: `{"text": "Variable | Example | Meaning\n`customer_id` | `c_4f2a...` | Pass it to every tool call.\n`first_name`, `last_name` | `Daniel`, `Reyes` | The person to ask for.\n`title` | `Mr` or `Ms` | Address the customer as title plus last name.\n`now` | `2026-10-14T11:00` | The current date and time. All date rules use this, never the real clock."}`
- **R60** [confidence low, samples A] — _openapi.json /transfer_to_agent_: `transfer_to_agent` requires string `queue`, restricted to `restructuring`, `general`, or `support`.

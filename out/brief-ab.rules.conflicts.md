# Rule inventory: conflicts and doubts (brief-a.md, brief-b.md)

Resolve these FIRST, before writing the generator: re-read the quoted source sentence in the brief, decide, and use the value the brief sets (never a value from another brief). Anything not listed here was found by every extraction sample and, where it carries a value, verified against a quote of the brief.

## Rules found by only one extraction sample (confidence low)

- **R07** (_brief-a.md rule 1_, samples C): Before identity is verified do not say "collections", "debt", "payment" or the product, to anyone including relatives.
- **R40** (_brief-a.md rule 32_, samples C): If a hardship customer still names a date or amount themselves, record the promise under sections 7 and 8.

## Values that differ between the extraction samples

- **R06** (_brief-a.md rule 1_): forbidden_words_before_verification: A06 ["collections","debt","payment","the product"] vs B06 ["collections","debt","payment"]
  - chosen: `{"forbidden_words_before_verification": ["collections", "debt", "payment", "the product"]}`
  - B06: `{"forbidden_words_before_verification": ["collections", "debt", "payment"]}`
  - C06: `{}`
- **R73** (_brief-b.md Closing_): outcome list: B73 lists only promise, paid, no_promise (first non-paid note reason), transferred/restructuring; C73 lists the full table incl. transferred/human, transferred/support, not_verified and not_reached reasons; A71 has no values -- chosen value verified against the brief
  - chosen: `{"outcomes": [{"outcome": "promise", "reason": "", "when": "at least one promise recorded, unless restructuring transfer"}, {"outcome": "paid", "reason": "", "when": "no promise and every product noted paid"}, {"outcome": "transferred", "reason": "restructuring", "when": "rule 41 / B rule 10"}, {"outcome": "transferred", "reason": "human", "when": "rule 42"}, {"outcome": "transferred", "reason": "support", "when": "rule 32"}, {"outcome": "no_promise", "reason": "refused", "when": "first non-paid note is refused; rules 31, 45"}, {"outcome": "no_promise", "reason": "hardship", "when": "first non-paid note is hardship"}, {"outcome": "no_promise", "reason": "dispute", "when": "first non-paid note is dispute"}, {"outcome": "no_promise", "reason": "service_error", "when": "first non-paid note is service_error"}, {"outcome": "not_verified", "reason": "failed", "when": "rule 14"}, {"outcome": "not_verified", "reason": "declined", "when": "rule 15"}, {"outcome": "not_reached", "reason": "callback", "when": "rule 6"}, {"outcome": "not_reached", "reason": "no_callback", "when": "rule 7"}, {"outcome": "not_reached", "reason": "wrong_number", "when": "rule 8"}, {"outcome": "not_reached", "reason": "deceased", "when": "rule 9"}, {"outcome": "not_reached", "reason": "unclear", "when": "rule 3"}]}`
  - A71: `{}`
  - B73: `{"outcomes": [{"outcome": "promise", "reason": "", "when": "at least one promise recorded, no transfer"}, {"outcome": "paid", "reason": "", "when": "no promise, every product noted paid"}, {"outcome": "no_promise", "reason": "first non-paid note reason", "when": "no promise otherwise"}, {"outcome": "transferred", "reason": "restructuring", "when": "restructuring transfer"}]}`

## Dated decisions (which statement is in force)

- **T1** topic `debt_statement`: Brief B says every Brief A rule applies unless a Brief B rule replaces it. B rule 2 replaces A rule 17 by stating each late product.
  - R23: superseded by R62 -- "State every late product, one sentence each, before asking for anything."
  - R62: in_force -- "State every late product, one sentence each, before asking for anything."
- **T2** topic `first_ask`: B rule 4 replaces A rule 28's first ask with one ask covering all products.
  - R35: superseded by R64 -- "First ask whether the customer can pay all of them today."
  - R64: in_force -- "First ask whether the customer can pay all of them today."
- **T3** topic `read_back`: B rule 7 replaces the single read-back with one combined read-back and one confirmation.
  - R43: superseded by R67 -- "Read all promises back together and ask for one confirmation."
  - R67: in_force -- "Read all promises back together and ask for one confirmation."
- **T4** topic `promise_recording_retry`: B rule 11 replaces A rule 37's handling of a second failure: keep recorded promises and add a service_error note.
  - R46: superseded by R72 -- "If one `create_promise` fails twice, keep the promises that were recorded and call `add_note` with reason `service_error` for the failed product."
  - R72: in_force -- "If one `create_promise` fails twice, keep the promises that were recorded and call `add_note` with reason `service_error` for the failed product."
- **T5** topic `restructuring`: B rule 10 keeps the transfer and adds how to treat recorded and unrecorded promises, plus no notes on any transfer.
  - R50: superseded by R70 -- "A restructuring request still transfers the call (Brief A rule 41)."
  - R70: in_force -- "A restructuring request still transfers the call (Brief A rule 41)."
- **T6** topic `outcome_table`: The Brief B Closing section keeps the Brief A table and adds the multi-product rules (paid, first non-paid note, promise wins), so R73 is the full table in force.
  - R56: superseded by R73 -- "Otherwise close as `no_promise` with the reason of the first product, in `get_account` order, whose note is not `paid`."
  - R73: in_force -- "The outcome table of Brief A applies."
- **T7** topic `add_note_usage`: B rule 8 replaces 'Brief A never uses `add_note`' with a note for each product that has no promise.
  - R58: superseded by R68 -- "For each product without a promise call `add_note` with that `product_id` and a reason: `refused`, `hardship`, `dispute`, `paid` or `service_error`."
  - R68: in_force -- "For each product without a promise call `add_note` with that `product_id` and a reason: `refused`, `hardship`, `dispute`, `paid` or `service_error`."


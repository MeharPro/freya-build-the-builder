# Rule inventory: conflicts and doubts (brief-a.md)

Resolve these FIRST, before writing the generator: re-read the quoted source sentence in the brief, decide, and use the value the brief sets (never a value from another brief). Anything not listed here was found by every extraction sample and, where it carries a value, verified against a quote of the brief.

## Rules found by only one extraction sample (confidence low)

- **R22** (_openapi.json /verify_identity_, samples C): An unreadable `answer` is rejected with ok=false and not counted as a wrong answer; `phone_last4` must be four digits.

## Dated decisions (which statement is in force)

- **T1** topic `call_variables`: Both candidates come from the same section 2 table in the single undated brief and say the same thing. Nothing conflicts with them and nothing replaces them, so both apply together.
  - R02: in_force -- "Every call starts with these. Nothing else is known before the tools are called."
  - R03: in_force -- "| `customer_id` | `c_4f2a...` | Pass it to every tool call. |"


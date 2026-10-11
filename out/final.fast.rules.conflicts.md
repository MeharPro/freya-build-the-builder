# Rule inventory: conflicts and doubts (final.brief.md)

Resolve these FIRST, before writing the generator: re-read the quoted source sentence in the brief, decide, and use the value the brief sets (never a value from another brief). Anything not listed here was found by every extraction sample and, where it carries a value, verified against a quote of the brief.

## Values a later rule replaced that another rule in force still carries

The rule named "new" replaced the value; the rule below still has it. Use the new value (outcome rows with a stale reason are left out of spec.json).

- **R96** (_sources/emails/2026-09-24-kickoff-questions.txt email of 25 Sep 16:40 Q2_) still has ['agent'], replaced by R110 (old rule R108): No assistant payments or payment-channel explanations; wanting to pay or asking how/where, including app, branch or auto-pay, requires the specified sentence and agent transfer.
- **R97** (_sources/emails/2026-09-24-kickoff-questions.txt email of 25 Sep 16:40 Q5_) still has ['agent'], replaced by R110 (old rule R108): Transfer disputes, missing payments and wrong amounts to an agent with the specified sentence; do not explain booking-date versus value-date differences.
- **R104** (_sources/emails/2026-09-24-kickoff-questions.txt question 7 and Selin answer error portion_) still has ['agent'], replaced by R110 (old rule R108): A service error goes to an agent, never the main menu, with the specified sentence.
- **R105** (_sources/emails/2026-09-24-kickoff-questions.txt question 11 and Selin answer_) still has ['agent'], replaced by R110 (old rule R108): On the first request for a person, transfer immediately with the specified sentence; do not first try to help or persuade.

## Structured spec (`spec.json`) problems

- WARN: spec: calendar.business_weekdays is empty


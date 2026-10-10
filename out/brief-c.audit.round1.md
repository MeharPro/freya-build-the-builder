# Coverage audit: brief-c.workflow.json

Rules: `brief-c.rules.json`. Generator: `gen_brief-c.py`. Model claude-opus-5-5, 70 s, $1.40, 7 call(s).

| implemented | partial | missing | contradicted | superseded | total |
|---|---|---|---|---|---|
| 59 | 5 | 0 | 0 | 0 | 64 |

1 evidence quote(s) were not found verbatim in the digest or the generator (marked *unverified* below).

## Top fixes

1. **R35** (partial): Customer-proposed amount: from the floor up to the full overdue amount (both included) accept; above the full amount record the full amount and say so; below the floor say the smallest recordable amount is the floor and propose it once, and if not accepted treat as a flat refusal (rule 31).
   - why: floor_min_fmt is the unrounded floor (e.g. 93.24), so the agent accepts amounts below the stated floor of 94 and records a promise where it should propose the floor or treat the answer as a refusal. That gives the wrong amount and the wrong close_call outcome.
   - fix: negotiate.task_message item 3 (Amount) and the ACCOUNT facts line: change 'Accept any amount from {{floor_min_fmt}} up to {{past_due_fmt}}' to 'Accept any amount from {{floor_fmt}} up to {{past_due_fmt}}, both included. Above {{past_due_fmt}}: record {{past_due_fmt}} and say so. Below {{floor_fmt}}: say the smallest amount you can record is {{floor_fmt}} and propose it once. If they do not accept, treat it as a flat refusal.' If the promise tool checks the amount in pre_process_code, compare against the same rounded floor value.
2. **R34** (partial): If the customer says the full amount is too much, propose the floor once and say the remainder stays overdue and the account stays in arrears until cleared. Declining the floor is a flat refusal (rule 31). The floor may be named a second time only as attempt 2 (rule 31).
   - why: Attempt 1 names the floor again after it was already proposed in item 4. The floor gets offered more often than the brief allows, which breaks the order of offers and the refusal flow (rule 31).
   - fix: negotiate.task_message item 5: change the Attempt 1 line to '- Attempt 1: propose paying the full amount {{past_due_fmt}} on {{attempt1_text}}. Do NOT name the floor again in attempt 1. The floor may be named a second time only as attempt 2.' In item 4, add: 'When you propose {{floor_fmt}}, say the remainder stays overdue and the account stays in arrears until cleared. If they decline the floor, that is a flat refusal (go to the attempt 2 / refusal path).'
3. **R50** (partial): Request for a person: do not ask whether you can help first; call `transfer_to_agent` queue `general` and close `transferred` / `agent_request`. Applies before and after the security check.
   - why: A request for a person made in the hardship or plan_offer nodes has no transfer tool or route, so the call does not close as transferred / agent_request with queue general.
   - fix: hardship and plan_offer nodes: add the transfer_general tool (transfer_to_agent with queue baked to 'general', description 'CALL at once whenever the customer asks for a person, a human or an agent; do not ask whether you can help first'). Add a transition 'transfer_to_agent_success_count greater_than 0 -> fin_agent_request', placed before the other transitions.
4. **R49** (partial): Request for a new payment plan, lower instalments or spreading over months: do not describe or invent any plan; say the plan review team handles these and ask whether to connect now. Yes -> `transfer_to_agent` queue `restructuring`, close `transferred` / `plan_review`; no -> close `no_promise` / `declined_offer`.
   - why: A request for a new plan, lower instalments or spreading the payments, made in the hardship node, is not routed to the plan review offer. The agent may then describe a plan or end the call with the wrong outcome instead of transferred/plan_review or no_promise/declined_offer.
   - fix: hardship node extraction_schema: add the enum value 'new_plan' to the topic field (described as 'customer asks for a new payment plan, lower instalments or spreading over months'). Add the transition 'topic equals new_plan -> plan_offer'. In hardship.task_message, add: 'Never describe or invent a payment plan.'
5. **R57** (partial): Before `close_call`, thank the customer for their time and say goodbye, naming Nordvik Savings Bank.
   - why: The estate farewell does not thank the customer for their time, so the mandatory closing sentence is missed in deceased/estate cases.
   - fix: end_estate terminal spoken_message: change it to 'Please accept my condolences. Thank you for your time. Goodbye from Nordvik Savings Bank.' Check that every other end_* spoken_message also contains 'Thank you for your time' and 'Nordvik Savings Bank'.

## partial (5)

- **R34** (_brief-c.md rule 27_): If the customer says the full amount is too much, propose the floor once and say the remainder stays overdue and the account stays in arrears until cleared. Declining the floor is a flat refusal (rule 31). The floor may be named a second time only as attempt 2 (rule 31).
  - where: negotiate.task_message items 4 and 5
  - evidence: `- Attempt 1: propose paying on {{attempt1_text}} - the full amount {{past_due_fmt}}, or the floor {{floor_fmt}} if they already said the full amount is too much.`
  - fix: Item 4 is fine, but attempt 1 names the floor a second time. The rule allows a second mention of the floor only as attempt 2. In negotiate item 5, make attempt 1 never propose the floor again.
- **R35** (_brief-c.md rule 28_): Customer-proposed amount: from the floor up to the full overdue amount (both included) accept; above the full amount record the full amount and say so; below the floor say the smallest recordable amount is the floor and propose it once, and if not accepted treat as a flat refusal (rule 31).
  - where: negotiate.task_message item 3 (Amount) + ACCOUNT facts
  - evidence: `Accept any amount from {{floor_min_fmt}} up to {{past_due_fmt}}.`
  - fix: floor_min_fmt is the unrounded value (for example 93.24), so amounts below the stated floor of 94 would be accepted. In FACTS, change this to 'Accept any amount from {{floor_fmt}} up to {{past_due_fmt}}'.
- **R49** (_brief-c.md rule 42_): Request for a new payment plan, lower instalments or spreading over months: do not describe or invent any plan; say the plan review team handles these and ask whether to connect now. Yes -> `transfer_to_agent` queue `restructuring`, close `transferred` / `plan_review`; no -> close `no_promise` / `declined_offer`.
  - where: negotiate topic=new_plan -> plan_offer; plan_offer on_enter tts; plan_choice accept -> xfer_plan (queue restructuring) -> fin_plan_review; decline -> fin_declined_offer
  - evidence: `on_enter tts: "I cannot describe or arrange a payment plan myself. The plan review team handles these requests. May I connect you with them now?"`
  - fix: Add a new_plan value to the hardship node's extraction, routed to plan_offer, so a plan request made outside negotiate also reaches the plan review offer.
- **R50** (_brief-c.md rule 43_): Request for a person: do not ask whether you can help first; call `transfer_to_agent` queue `general` and close `transferred` / `agent_request`. Applies before and after the security check.
  - where: setup/opening_retry who=wants_agent -> xfer_agent (queue general) -> fin_agent_request; ask_phone/ask_dob/negotiate tool transfer_to_agent + transition transfer_to_agent_success_count > 0
  - evidence: `description: Transfer the call to a person. CALL it at once whenever the customer asks for a person, a human or an agent. Do not ask whether you can help first.`
  - fix: Add transfer_general to the hardship and plan_offer nodes' tools, plus a transfer_to_agent_success_count > 0 -> fin_agent_request transition, so a request for a person there goes to queue general / agent_request.
- **R57** (_brief-c.md rule 48_): Before `close_call`, thank the customer for their time and say goodbye, naming Nordvik Savings Bank.
  - where: end_* terminal spoken_message
  - evidence: `terminal: endedReason=not_reached_estate, spoken_message="Please accept my condolences. Goodbye from Nordvik Savings Bank."`
  - fix: Change end_estate spoken_message to "Please accept my condolences. Thank you for your time. Goodbye from Nordvik Savings Bank."

## All rules

| id | status | where | evidence |
|---|---|---|---|
| R01 | implemented | prepare code (single product prods[0]); fin_* code nodes set outcome/reason; system_prompt | p = prods[0] if prods else {} |
| R02 | implemented | tool bodies customer_id default; opening on_enter tts first_name/last_name; system_prompt title; setup code reads now | raw = str(vars.get('now') or '').strip() |
| R03 | implemented | every tool definition body.customer_id | body.customer_id (string): default "{{customer_id}}" |
| R04 | implemented | system_prompt; negotiate on_enter tts | After the security check, address the customer as {{title}} {{last_name}}. |
| R05 | implemented | setup code: today derived from vars['now'] | nowdt = datetime.datetime.fromisoformat(raw[:16]) |
| R06 | implemented | opening on_enter tts | Good day, this is the virtual assistant of Nordvik Savings Bank, and this call is recorded. Am I speaking with {{first_name}} {{last_name}}? |
| R07 | implemented | system_prompt; opening_retry, third_party, ask_phone, ask_dob task_message | Until the security check is complete, never use the words overdue, arrears, collections, payment or debt, and never name a product, to anyone. |
| R08 | implemented | opening on_enter tts; opening_retry task_message | Then ask exactly: "Am I speaking with {{first_name}} {{last_name}}?" This is the second and last time you ask. |
| R09 | implemented | who1/who2 extraction; setup -> opening_retry; opening_retry always -> fin_unconfirmed | customer = ONLY 'yes', 'speaking', 'that's me', or they say the customer's own name ({{first_name}} {{last_name}}). |
| R10 | implemented | system_prompt; opening_retry and third_party task_message | If asked whether you are a robot, an AI or a machine: say exactly "I am an automated assistant of Nordvik Savings Bank, and this conversation is recorded." and  |
| R11 | implemented | third_party task_message | If they ask what it is about, offer to pay, or offer to take a message, repeat that you can discuss it only with the customer. |
| R12 | implemented | setup code callback_text; third_party task_message; third_party transition -> fin_scheduled | lines.append(txt(nbd) + ' (' + nbd.isoformat() + '), from 09:00 up to 18:00 included.') |
| R13 | implemented | third_party.task_message + transition_to_fin_no_slot -> fin_no_slot code | - If the second slot is also outside the window, or they cannot say when, book nothing: call transition_to_fin_no_slot. |
| R14 | implemented | third_party transition tp_status=wrong_number -> fin_wrong_party; end_wrong_party terminal spoken_message | spoken_message="I apologise for the disturbance. Thank you for your time. Goodbye from Nordvik Savings Bank." |
| R15 | implemented | third_party transition tp_status=deceased -> fin_estate; end_estate terminal spoken_message | terminal: endedReason=not_reached_estate, spoken_message="Please accept my condolences. Goodbye from Nordvik Savings Bank." |
| R16 | implemented | third_party.task_message STRICT block | Never ask them a security question and arrange nothing with them except a callback. |
| R17 | implemented | ask_phone.task_message + verify_identity (field phone_last4) -> ask_dob with verify_identity#2 (field date_of_birth) | When they give four digits, call verify_identity with answer = the four digits only. Do not ask the date of birth before this question has passed. |
| R18 | implemented | ask_dob.task_message; verify_identity#2 post_process_code ok=false branch | msg = 'The answer could not be read. It does not count as wrong. Ask again: What is your date of birth?' |
| R19 | implemented | verify_identity post_process_code (shared id_wrong, id_route) + ask_phone/ask_dob transition id_route=exhausted -> fin_exhausted | done = nw >= 2 or str(left) == '0' |
| R20 | implemented | verify_identity#2 post_process_code hint_day_month_swapped counter | if hint == 'day_month_swapped': ... if nh > 1: wrong = True else: msg = 'Day and month look swapped. This is NOT a wrong answer. ...' *unverified* |
| R21 | implemented | verify_identity post_process_code LIMIT message; fin_exhausted code; end_exhausted terminal | spoken_message="I am sorry, the security check could not be completed. A colleague can complete the check if you call the number on the back of your card or on  |
| R22 | implemented | ask_phone/ask_dob task_message + refusal extraction -> count_decline_* code -> fin_withheld | vars['decline_route'] = 'close' if n >= 2 else 'retry' |
| R23 | implemented | ask_dob transition all_verified -> load_account (get_account); system prompt | After the security check, address the customer as {{title}} {{last_name}}. |
| R24 | implemented | negotiate on_enter tts; prepare code product_words; system prompt | I am calling from the payments team of Nordvik Savings Bank about an overdue amount on your {{product_words}}. The overdue amount is {{past_due_fmt}}, and it is |
| R25 | implemented | setup/prepare code: HOL, BWD, isbd | HOL = set(['2026-10-16', '2026-11-02', '2026-11-21', '2026-12-08', '2026-12-24', '2026-12-25', '2026-12-26', '2026-12-31']) |
| R26 | implemented | setup code: green_deadline/amber_deadline (addbd starts the day after today); prepare code: band selection | if days_late <= 10:     band = 'green'; attempts = 2; deadline = datetime.date.fromisoformat(str(vars.get('green_deadline'))) |
| R27 | implemented | negotiate.task_message DATES facts + prepare calendar_text | - A promise date must be a business day (Monday to Saturday, not a Nordvik holiday) from today up to the deadline. Saturdays are business days. |
| R28 | implemented | negotiate.task_message item 3 (Date) + calendar_text next business day | A Sunday or a Nordvik holiday not after the deadline -> say it is not a business day and propose the next business day shown. |
| R29 | implemented | setup code: weekday_table_first_after; negotiate WEEKDAY WORDS | WEEKDAY WORDS ("this X" and "next X" both mean the first X after today) |
| R30 | implemented | negotiate.task_message item 3 (vague period) | A vague period ('next week', 'the week after next', 'after payday', 'end of the month') -> ask once for the exact day. If no exact day follows, it is a non-answ |
| R31 | implemented | negotiate.task_message item 3 (After the deadline) | After the deadline -> say the latest date the bank can record is {{deadline_text}}, and propose it; if they decline it, it is a flat refusal. |
| R32 | implemented | negotiate.task_message item 1 | 1. You propose every figure. NEVER ask what they can pay or how much they can afford. If they say 'you tell me', propose a figure yourself. Ask for the full ove |
| R33 | implemented | prepare code: floor_raw / math.ceil | floor_raw = round(past_due * 0.4, 2) |
| R34 | partial | negotiate.task_message items 4 and 5 | - Attempt 1: propose paying on {{attempt1_text}} - the full amount {{past_due_fmt}}, or the floor {{floor_fmt}} if they already said the full amount is too much |
| R35 | partial | negotiate.task_message item 3 (Amount) + ACCOUNT facts | Accept any amount from {{floor_min_fmt}} up to {{past_due_fmt}}. |
| R36 | implemented | negotiate on_enter tts | The overdue amount is {{past_due_fmt}}, and it is {{days_late_txt}} days overdue. Are you able to settle the full overdue amount today? |
| R37 | implemented | negotiate.task_message item 3 | 3. A date or an amount the customer proposes is never a refusal. Check it: |
| R38 | implemented | negotiate.task_message item 5 + setup code attempt1_date + prepare code attempt2_line | - Attempt 1: propose paying on {{attempt1_text}} - the full amount {{past_due_fmt}}, or the floor {{floor_fmt}} if they already said the full amount is too much |
| R39 | implemented | negotiate.task_message item 5 + transition -> fin_declined_offer (no_promise/declined_offer) | - When the allowed attempts are used up, stop: call transition_to_fin_declined_offer. Never repeat a proposal they declined. |
| R40 | implemented | negotiate topic=hardship -> hardship node on_enter tts; care_choice accept -> xfer_care (queue support) -> fin_care_team; decline -> fin_financial_distress | I am sorry to hear that. I will not ask you for a payment today. The bank's care team can review your situation. May I connect you with them now? |
| R41 | implemented | negotiate.task_message OTHER | - Never offer or agree to a discount, waiver, fee reversal, instalment plan or a date after the deadline. If asked, say you cannot offer any reduction and the f |
| R42 | implemented | negotiate.task_message item 6 + create_promise description | 6. When amount and date are agreed, read back the amount, the date and the product: "<amount> on <weekday day month> for your {{product_words}}. Shall I record  |
| R43 | implemented | negotiate.task_message item 6 | If they change the amount or date, check it again and read back again. |
| R44 | implemented | negotiate.task_message item 8 + transition promise_route recorded -> fin_promise | 8. One promise per call. A recorded promise is not changed or cancelled: if asked, the payments line can change it. |
| R45 | implemented | create_promise post_process_code + negotiate transitions -> fin_system_fault + end_system_fault spoken_message | V['promise_route'] = 'fault' if n >= 3 else 'retry' |
| R46 | implemented | end_promise terminal spoken_message | I have noted your promise. A confirmation will be sent to your registered email address. Thank you for your time, {{title}} {{last_name}}. Goodbye from Nordvik  |
| R47 | implemented | negotiate topic=already_paid -> fin_paid (paid/self_reported) -> end_paid spoken_message | Thank you for letting me know. The bank will check for the payment within two business days and will not call you again before then. |
| R48 | implemented | negotiate topic=dispute -> xfer_contested (queue general, on_enter tts) -> fin_contested (transferred/contested) | on_enter tts: "I understand. A colleague will look into it. I will connect you now." |
| R49 | partial | negotiate topic=new_plan -> plan_offer; plan_offer on_enter tts; plan_choice accept -> xfer_plan (queue restructuring) -> fin_plan_review; decline -> fin_declined_offer | on_enter tts: "I cannot describe or arrange a payment plan myself. The plan review team handles these requests. May I connect you with them now?" |
| R50 | partial | setup/opening_retry who=wants_agent -> xfer_agent (queue general) -> fin_agent_request; ask_phone/ask_dob/negotiate tool transfer_to_agent + transition transfer_to_agent_success_count > 0 | description: Transfer the call to a person. CALL it at once whenever the customer asks for a person, a human or an agent. Do not ask whether you can help first. |
| R51 | implemented | system prompt 'Always' list; opening_retry.task_message | - If asked whether this is a scam: say they may hang up and call the number on the back of their card or on their latest statement to confirm the call, then con |
| R52 | implemented | system prompt 'Always' list; negotiate.task_message OTHER | - Never invent a figure, a date or a reason. If you do not have the information, say so and that the payments team can answer it. |
| R53 | implemented | setup who1=refuses -> fin_withheld; ask_phone/ask_dob refusal=end_call -> fin_withheld; negotiate OTHER -> transition_to_fin_declined_offer | - If they say they do not want to talk or want to end the call: call transition_to_fin_declined_offer at once. |
| R54 | implemented | tool close_call (alwaysRunsAt end_of_call) reading outcome/reason written by fin_* code nodes | config: {"maxRetries": 0, "alwaysRunsAt": ["end_of_call"]} |
| R55 | implemented | fin_plan_review / fin_agent_request / fin_care_team / fin_contested code | if str(vars.get('promise_done') or '') == 'yes':             vars['outcome'] = 'promise' |
| R56 | implemented | TOOL DEFINITIONS (no add_note tool) | GLOBAL TOOLS (available in every node / run at end of call): close_call |
| R57 | partial | end_* terminal spoken_message | terminal: endedReason=not_reached_estate, spoken_message="Please accept my condolences. Goodbye from Nordvik Savings Bank." |
| R58 | implemented | all tool urls POST with body.customer_id; get_account maxRetries 2; create_promise post_process retry; schedule_callback post retry | url: POST https://freya-bank-mock.freyavoice.workers.dev/v1/get_account     body.customer_id (string): default "{{customer_id}}" |
| R59 | implemented | load_account api_request (after ask_dob all_verified) + prepare code | 1. -> load_account  if (verify_identity_response.data.all_verified equals "true" OR verify_identity_response.data.all_verified equals "True") |
| R60 | implemented | tools verify_identity / verify_identity#2 baked field, answer descriptions, post_process_code | msg = 'The answer could not be read. It does not count as wrong. Ask again: What is your date of birth?' |
| R61 | implemented | tool create_promise definition + pre_process_code; negotiate.task_message item 8 | body.amount* (number): default "{{amount}}"; The agreed amount, a number like 420.5. |
| R62 | implemented | tool schedule_callback definition | body.time* (string): default "{{time}}"; Callback time as HH:MM, 24 hour, from 09:00 to 18:00 inclusive, later than now. |
| R63 | implemented | transfer_to_agent / #2 / #3 / #4 baked body.queue | body.queue (string): default "restructuring" |
| R64 | implemented | tool close_call (alwaysRunsAt end_of_call); fin_* code nodes set outcome/reason | body.outcome* (string): default "{{outcome}}"; enum ["promise", "paid", "transferred", "no_promise", "not_verified", "not_reached"] |

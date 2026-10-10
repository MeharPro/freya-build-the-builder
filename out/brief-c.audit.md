# Coverage audit: brief-c.workflow.json

Rules: `brief-c.rules.json`. Generator: `gen_brief-c.py`. Model claude-opus-5-5, 78 s, $1.41, 7 call(s).

| implemented | partial | missing | contradicted | superseded | total |
|---|---|---|---|---|---|
| 61 | 3 | 0 | 0 | 0 | 64 |

## Top fixes

1. **R20** (partial): If `verify_identity` returns `hint: "day_month_swapped"`, ask the customer to repeat the date with the month said as a word. One such retry per call does not count as a wrong answer; any further swapped answer counts.
   - why: If the service already counts the swapped-date answer as wrong, the ask_dob fallback route (wrong_answers_left == "1") sends the call to fin_exhausted after only one real wrong answer, so the close_call outcome/reason is wrong in every free-retry case.
   - fix: ask_dob transition 3 (-> fin_exhausted, condition verify_identity_response.data.wrong_answers_left equals "1"): either delete it and rely on the post_process_code counter that already skips the first day_month_swapped hint, or add a second condition so it only fires when hint_day_month_swapped is not set. Also make sure verify_identity post_process_code counts a second or later swapped hint as a wrong answer (increment the wrong counter when hint_day_month_swapped >= 2), so the rule's three-wrong-answers limit still applies.
2. **R34** (partial): If the customer says the full amount is too much, propose the floor once and say the remainder stays overdue and the account stays in arrears until cleared. Declining the floor is a flat refusal (rule 31). The floor may be named a second time only as attempt 2 (rule 31).
   - why: When the customer said the full amount is too much, item 5 has attempt 1 name the floor again. That names the floor a second time outside attempt 2, which the brief forbids, and it changes the amount on offer and the order of the negotiation that the test cases check.
   - fix: negotiate.task_message item 5: replace the attempt-1 line with "- Attempt 1: propose paying the full amount {{past_due_fmt}} on {{attempt1_text}}. Do not name the floor here if you already offered it under item 4." In item 4 add: "Offer the floor {{floor_fmt}} once only and say the remainder stays overdue and the account stays in arrears until cleared. If the customer turns down the floor, treat it as a flat refusal (rule 31)." In the attempt-2 line say the floor may be named again only there.
3. **R01** (partial): The call is to customers whose payment on a single product is between 1 and 45 days overdue: reach the right person, run the security check, explain the overdue amount, agree a payment where possible, and end with the outcome and reason from section 12. Nothing in the brief may be replaced by the assistant's own judgement.
   - why: Accounts outside 1–45 days overdue (0 days, or more than 45) still go to negotiate. Every days_late > 10 becomes amber with no upper limit, so the agent negotiates in cases where the brief does not allow this call.
   - fix: prepare code: after days_late is computed, set vars['in_scope'] = 'true' if 1 <= days_late <= 45 else 'false'. Add a first transition from prepare: if in_scope equals "false" -> a fin_out_of_scope code node that sets the section-12 outcome/reason for an account outside the call's scope (or the brief's closest 'not eligible' pair), then -> its end terminal. Keep the amber band to 11 <= days_late <= 45.

## partial (3)

- **R01** (_brief-c.md section 1_): The call is to customers whose payment on a single product is between 1 and 45 days overdue: reach the right person, run the security check, explain the overdue amount, agree a payment where possible, and end with the outcome and reason from section 12. Nothing in the brief may be replaced by the assistant's own judgement.
  - where: prepare code: p = prods[0]; band selection; system prompt
  - evidence: `if days_late <= 10:`
  - fix: In prepare code, check that days_late is between 1 and 45 and route out-of-range accounts away from negotiate (e.g. a guard transition); right now every days_late > 10 becomes amber with no upper bound.
- **R20** (_brief-c.md rule 14_): If `verify_identity` returns `hint: "day_month_swapped"`, ask the customer to repeat the date with the month said as a word. One such retry per call does not count as a wrong answer; any further swapped answer counts.
  - where: verify_identity#2 post_process_code hint_day_month_swapped counter; ask_dob transition 3
  - evidence: `3. -> fin_exhausted  if (verify_identity_response.data.wrong_answers_left equals "1")  ["two wrong answers (service counter)"]`
  - fix: The free retry works in post_process_code, but if the service counts the swapped answer as wrong, the service-counter fallback route (wrong_answers_left == "1") ends the check after one real wrong answer. Remove that fallback, or limit it to when no swapped hint was given (hint_day_month_swapped unset).
- **R34** (_brief-c.md rule 27_): If the customer says the full amount is too much, propose the floor once and say the remainder stays overdue and the account stays in arrears until cleared. Declining the floor is a flat refusal (rule 31). The floor may be named a second time only as attempt 2 (rule 31).
  - where: negotiate.task_message items 4 and 5
  - evidence: `- Attempt 1: propose paying on {{attempt1_text}} - the full amount {{past_due_fmt}}, or the floor {{floor_fmt}} if they already said the full amount is too much.`
  - fix: In negotiate item 5, attempt 1 must not name the floor again after it was proposed under item 4; the floor's second naming should only happen as attempt 2 (e.g. attempt 1 = full amount on attempt1 date).

## All rules

| id | status | where | evidence |
|---|---|---|---|
| R01 | partial | prepare code: p = prods[0]; band selection; system prompt | if days_late <= 10: |
| R02 | implemented | tool bodies customer_id default; opening on_enter; system prompt; setup code reads vars['now'] | raw = str(vars.get('now') or '').strip() |
| R03 | implemented | every tool definition body.customer_id | body.customer_id (string): default "{{customer_id}}" |
| R04 | implemented | system prompt; negotiate on_enter tts | After the security check, address the customer as {{title}} {{last_name}}. |
| R05 | implemented | setup code: nowdt/today from vars['now'] | nowdt = datetime.datetime.fromisoformat(raw[:16]) |
| R06 | implemented | opening on_enter tts | Good day, this is the virtual assistant of Nordvik Savings Bank, and this call is recorded. Am I speaking with {{first_name}} {{last_name}}? |
| R07 | implemented | system prompt; opening_retry, third_party, ask_phone, ask_dob task_message | - Until the security check is complete, never use the words overdue, arrears, collections, payment or debt, and never name a product, to anyone. |
| R08 | implemented | opening on_enter tts | Am I speaking with {{first_name}} {{last_name}}? |
| R09 | implemented | who1/who2 extraction; setup -> opening_retry; opening_retry -> fin_unconfirmed | customer = ONLY 'yes', 'speaking', 'that's me', or they say the customer's own name ({{first_name}} {{last_name}}). |
| R10 | implemented | system prompt; opening_retry and third_party task_message | say exactly "I am an automated assistant of Nordvik Savings Bank, and this conversation is recorded." and carry on. Never claim to be a person. |
| R11 | implemented | third_party.task_message | If they ask what it is about, offer to pay, or offer to take a message, repeat that you can discuss it only with the customer. |
| R12 | implemented | setup code callback_text; third_party tool schedule_callback; transition -> fin_scheduled | 1. -> fin_scheduled  if (schedule_callback_response.data.ok equals "true" OR schedule_callback_response.data.ok equals "True") |
| R13 | implemented | third_party.task_message + transition_to_fin_no_slot -> fin_no_slot (not_reached/no_slot) | - If the second slot is also outside the window, or they cannot say when, book nothing: call transition_to_fin_no_slot. |
| R14 | implemented | third_party transition tp_status=wrong_number -> fin_wrong_party; end_wrong_party spoken_message | terminal: endedReason=not_reached_wrong_party, spoken_message="I apologise for the disturbance. Thank you for your time. Goodbye from Nordvik Savings Bank." |
| R15 | implemented | third_party transition tp_status=deceased -> fin_estate; end_estate spoken_message | terminal: endedReason=not_reached_estate, spoken_message="Please accept my condolences. Thank you for your time. Goodbye from Nordvik Savings Bank." |
| R16 | implemented | third_party.task_message STRICT block (only schedule_callback tool offered) | Never ask them a security question and arrange nothing with them except a callback. |
| R17 | implemented | ask_phone (verify_identity field phone_last4) -> verified -> ask_dob (verify_identity#2 field date_of_birth) | When they give four digits, call verify_identity with answer = the four digits only. Do not ask the date of birth before this question has passed. |
| R18 | implemented | ask_dob.task_message; verify_identity#2 post_process_code ok:false branch | msg = 'The answer could not be read. It does not count as wrong. Ask again: What is your date of birth?' |
| R19 | implemented | verify_identity post_process_code shared id_wrong counter; ask_phone/ask_dob transitions id_route=exhausted -> fin_exhausted | done = nw >= 2 or str(left) == '0' |
| R20 | partial | verify_identity#2 post_process_code hint_day_month_swapped counter; ask_dob transition 3 | 3. -> fin_exhausted  if (verify_identity_response.data.wrong_answers_left equals "1")  ["two wrong answers (service counter)"] |
| R21 | implemented | verify_identity post_process_code LIMIT message; fin_exhausted (not_verified/exhausted); end_exhausted spoken_message | A colleague can complete the check if you call the number on the back of your card or on your latest statement. |
| R22 | implemented | ask_phone/ask_dob task_message + refusal extraction -> count_decline_* (decline_count >= 2 -> fin_withheld) | vars['decline_route'] = 'close' if n >= 2 else 'retry' |
| R23 | implemented | ask_dob transition all_verified -> load_account (get_account); system prompt; negotiate on_enter tts | After the security check, address the customer as {{title}} {{last_name}}. |
| R24 | implemented | negotiate on_enter tts; prepare code product_words; system prompt forbids collections | I am calling from the payments team of Nordvik Savings Bank about an overdue amount on your {{product_words}}. The overdue amount is {{past_due_fmt}}, and it is |
| R25 | implemented | setup/prepare code: HOL, BWD, isbd | HOL = set(['2026-10-16', '2026-11-02', '2026-11-21', '2026-12-08', '2026-12-24', '2026-12-25', '2026-12-26', '2026-12-31']) |
| R26 | implemented | setup code: green_deadline/amber_deadline (addbd); prepare code band selection | band = 'green'; attempts = 2; deadline = datetime.date.fromisoformat(str(vars.get('green_deadline'))) |
| R27 | implemented | negotiate.task_message DATES (FACTS) + calendar_text | - A promise date must be a business day (Monday to Saturday, not a Nordvik holiday) from today up to the deadline. Saturdays are business days. |
| R28 | implemented | negotiate.task_message item 3 Date + FACTS | A Sunday or a Nordvik holiday not after the deadline -> say it is not a business day and propose the next business day shown. |
| R29 | implemented | setup code: weekday_table_first_after; negotiate.task_message WEEKDAY WORDS | WEEKDAY WORDS ("this X" and "next X" both mean the first X after today) |
| R30 | implemented | negotiate.task_message item 3 vague period | A vague period ('next week', 'the week after next', 'after payday', 'end of the month') -> ask once for the exact day. If no exact day follows, it is a non-answ |
| R31 | implemented | negotiate.task_message item 3 Date | After the deadline -> say the latest date the bank can record is {{deadline_text}}, and propose it; if they decline it, it is a flat refusal. |
| R32 | implemented | negotiate.task_message item 1 | 1. You propose every figure. NEVER ask what they can pay or how much they can afford. If they say 'you tell me', propose a figure yourself. Ask for the full ove |
| R33 | implemented | prepare code: floor_raw / floor | floor_raw = float(math.ceil(round(past_due * 0.4, 2) - 1e-9))  # R26: 40% rounded up to the next whole unit IS the floor |
| R34 | partial | negotiate.task_message items 4 and 5 | - Attempt 1: propose paying on {{attempt1_text}} - the full amount {{past_due_fmt}}, or the floor {{floor_fmt}} if they already said the full amount is too much |
| R35 | implemented | negotiate.task_message item 3 Amount | Amount from the floor up to the full amount, both included -> accept it. Above the full amount -> record the full amount {{past_due_fmt}} and say so. Below the  |
| R36 | implemented | negotiate on_enter tts | The overdue amount is {{past_due_fmt}}, and it is {{days_late_txt}} days overdue. Are you able to settle the full overdue amount today? |
| R37 | implemented | negotiate.task_message item 3 | 3. A date or an amount the customer proposes is never a refusal. Check it: |
| R38 | implemented | negotiate.task_message item 5 + setup code attempt1_date + prepare code attempt2_line | vars['attempt2_line'] = 'Attempt 2: propose the floor ' + fmt(floor) + ' on the deadline, ' + txt_short(deadline) + ' (' + deadline.isoformat() + '). After atte |
| R39 | implemented | negotiate.task_message item 5 + transition -> fin_declined_offer | - When the allowed attempts are used up, stop: call transition_to_fin_declined_offer. Never repeat a proposal they declined. |
| R40 | implemented | negotiate topic=hardship -> hardship node; hardship on_enter tts; xfer_care (queue support) -> fin_care_team; care_choice decline -> fin_financial_distress | on_enter tts: "I am sorry to hear that. I will not ask you for a payment today. The bank's care team can review your situation. May I connect you with them now? |
| R41 | implemented | negotiate.task_message OTHER; system_prompt | - Never offer or agree to a discount, waiver, fee reversal, instalment plan or a date after the deadline. If asked, say you cannot offer any reduction and the f |
| R42 | implemented | negotiate.task_message item 6; tool create_promise description | 6. When amount and date are agreed, read back the amount, the date and the product: "<amount> on <weekday day month> for your {{product_words}}. Shall I record  |
| R43 | implemented | negotiate.task_message item 6 | If they change the amount or date, check it again and read back again. |
| R44 | implemented | negotiate.task_message item 8; promise_route recorded -> fin_promise | 8. One promise per call. A recorded promise is not changed or cancelled: if asked, the payments line can change it. |
| R45 | implemented | tool create_promise post_process_code; negotiate transitions promise_route fault -> fin_system_fault; end_system_fault spoken_message | V['promise_route'] = 'fault' if n >= 3 else 'retry' |
| R46 | implemented | end_promise terminal spoken_message | spoken_message="I have noted your promise. A confirmation will be sent to your registered email address. Thank you for your time, {{title}} {{last_name}}. Goodb |
| R47 | implemented | negotiate topic=already_paid -> fin_paid; end_paid spoken_message | Thank you for letting me know. The bank will check for the payment within two business days and will not call you again before then. |
| R48 | implemented | negotiate topic=dispute -> xfer_contested (queue general) -> fin_contested | on_enter tts: "I understand. A colleague will look into it. I will connect you now." |
| R49 | implemented | plan_offer on_enter tts + task_message; plan_choice accept -> xfer_plan (queue restructuring) -> fin_plan_review; decline -> fin_declined_offer | on_enter tts: "I cannot describe or arrange a payment plan myself. The plan review team handles these requests. May I connect you with them now?" |
| R50 | implemented | setup/opening_retry who=wants_agent -> xfer_agent (queue general) -> fin_agent_request; tool transfer_to_agent (baked queue general) in ask_phone/ask_dob/negotiate/hardship/plan_offer | description: Transfer the call to a person. CALL it at once whenever the customer asks for a person, a human or an agent. Do not ask whether you can help first. |
| R51 | implemented | system prompt 'Always' list; opening_retry task_message | - If asked whether this is a scam: say they may hang up and call the number on the back of their card or on their latest statement to confirm the call, then con |
| R52 | implemented | system prompt; negotiate.task_message OTHER | - Never invent a figure, a date or a reason. If you do not have the information, say so and that the payments team can answer it. |
| R53 | implemented | setup who1=refuses -> fin_withheld; ask_phone/ask_dob refusal=end_call -> fin_withheld; negotiate.task_message OTHER + transition_to_fin_declined_offer | - If they say they do not want to talk or want to end the call: call transition_to_fin_declined_offer at once. |
| R54 | implemented | tool close_call (alwaysRunsAt end_of_call) reading outcome/reason written by fin_* code nodes | config: {"maxRetries": 0, "alwaysRunsAt": ["end_of_call"]} |
| R55 | implemented | fin_plan_review / fin_agent_request / fin_care_team / fin_contested code | if str(vars.get('promise_done') or '') == 'yes':             vars['outcome'] = 'promise' |
| R56 | implemented | tool definitions (no add_note tool defined) | GLOBAL TOOLS (available in every node / run at end of call): close_call |
| R57 | implemented | all end_* terminal spoken_message | spoken_message="I apologise for the disturbance. Thank you for your time. Goodbye from Nordvik Savings Bank." |
| R58 | implemented | all tool definitions (POST, body.customer_id default {{customer_id}}); get_account maxRetries 2; create_promise post_process retry | url: POST https://freya-bank-mock.freyavoice.workers.dev/v1/get_account     body.customer_id (string): default "{{customer_id}}" |
| R59 | implemented | ask_dob all_verified -> load_account (get_account, body only customer_id); prepare code parses type/card_last4/past_due/days_late/instalment_amount | 1. -> load_account  if (verify_identity_response.data.all_verified equals "true" OR verify_identity_response.data.all_verified equals "True") |
| R60 | implemented | tools verify_identity / verify_identity#2 (baked field, answer descriptions, post_process_code id_wrong >= 2, ok false not counted) | msg = 'The answer could not be read. It does not count as wrong. Ask again: What is your date of birth?' |
| R61 | implemented | tool create_promise definition + pre_process_code; negotiate.task_message item 8 | body.amount* (number): default "{{amount}}"; The agreed amount, a number like 420.5. |
| R62 | implemented | tool schedule_callback definition; third_party.task_message | body.time* (string): default "{{time}}"; Callback time as HH:MM, 24 hour, from 09:00 to 18:00 inclusive, later than now. |
| R63 | implemented | tools transfer_to_agent (general), #2 (restructuring), #3 (support), #4 (general) baked queue defaults | body.queue (string): default "restructuring" |
| R64 | implemented | tool close_call (alwaysRunsAt end_of_call) + fin_* code nodes setting outcome/reason | body.outcome* (string): default "{{outcome}}"; enum ["promise", "paid", "transferred", "no_promise", "not_verified", "not_reached"] |

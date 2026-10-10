# Coverage audit: brief-a.workflow.json

Rules: `brief-a.rules.json`. Generator: `gen_brief-a.py`. Model claude-opus-5-5, 57 s, $0.34, 7 call(s).

| implemented | partial | missing | contradicted | superseded | total |
|---|---|---|---|---|---|
| 60 | 4 | 0 | 0 | 0 | 64 |

## Top fixes

1. **R52** (partial): A request for a human: ask once whether you can help first. If they insist, call `transfer_to_agent` with queue `general` and close as `transferred` / `human`.
   - why: If a customer in hardship asks for a human, the call can't transfer because that node has no transfer_to_agent tool and no route out. The case then fails on the missing tool call and on the transferred/human close.
   - fix: hardship node: add the transfer_to_agent tool with queue baked to "general". Add this line to the task_message: "If they ask for a human: the first time, ask whether you can help them yourself. If they insist, call transfer_to_agent with queue general." Add the transition transfer_to_agent_success_count greater_than 0 -> fin_transferred_human (outcome transferred, reason human). Check that every other conversation node after verification has the same tool and route.
2. **R57** (partial): If a transfer follows a recorded promise, close as `transferred` with that transfer's reason.
   - why: After create_promise succeeds, the call goes straight to fin_promise. So if the customer then asks for a human or support, there is no transfer and the close is promise instead of transferred with that transfer's reason.
   - fix: negotiate/hardship: send the create_promise ok route to a new conversation node post_promise instead of fin_promise. post_promise task_message: "Confirm the promise (amount and date). If the customer asks for a human or support, call transfer_to_agent; otherwise thank them and say goodbye." Give it the transfer_to_agent tool. Its transitions: transfer_to_agent_success_count > 0 -> the fin_transferred_<reason> node that matches the queue (human -> fin_transferred_human, hardship -> fin_transferred_hardship), and matches_intent 'customer has nothing more / says goodbye' -> fin_promise. In the hardship node, make the support offer before calling create_promise.
3. **R64** (partial): `close_call` is always the last tool call; nothing is accepted after it. `reason` is required for every outcome except `promise` and `paid`.
   - why: If the model calls close_call itself, or calls another tool after it, the case fails because of an extra tool call or an out-of-order call.
   - fix: system_prompt: add "Never call close_call yourself; it runs automatically when the call ends. Do not call any tool after the farewell." In the close_call pre_process_code, add a check that reason is set whenever outcome is not promise or paid (fallback reason from the fin_* node).
4. **R59** (partial): Thank the customer and say goodbye before `close_call`.
   - why: The deceased farewell has no thank-you, which breaks the mandatory 'thank and say goodbye' closing in those cases.
   - fix: end_deceased terminal spoken_message: change to "I am sorry for your loss. Thank you for letting us know. Goodbye." Check that every other end_* spoken_message contains both a thank-you and a goodbye.

## partial (4)

- **R52** (_brief-a.md rule 42_): A request for a human: ask once whether you can help first. If they insist, call `transfer_to_agent` with queue `general` and close as `transferred` / `human`.
  - where: ask_dob / ask_phone / negotiate task_message + transfer_to_agent (queue general) + transition -> fin_transferred_human
  - evidence: `- If they ask for a human: the first time, ask whether you can help them yourself. If they insist, call transfer_to_agent.`
  - fix: Add the transfer_to_agent tool (queue general), the human-request instruction and a transfer_to_agent_success_count > 0 -> fin_transferred_human transition to the hardship node, which has none of these.
- **R57** (_brief-a.md section 12 note under table_): If a transfer follows a recorded promise, close as `transferred` with that transfer's reason.
  - where: negotiate/hardship transition create_promise ok -> fin_promise
  - evidence: `1. -> fin_promise  if (create_promise_response.data.ok equals "true" OR create_promise_response.data.ok equals "True")  ["promise recorded"]`
  - fix: A recorded promise ends the call straight away, so no transfer can follow it. Example: in hardship, a promise recorded before the support offer closes the call as promise. Either offer support/transfer before routing to fin_promise, or add a post-promise node where a transfer sets outcome transferred with that transfer's reason.
- **R59** (_brief-a.md rule 47_): Thank the customer and say goodbye before `close_call`.
  - where: end_* terminal spoken_message
  - evidence: `I am sorry for your loss. Goodbye.`
  - fix: Add a thank-you to end_deceased spoken_message, e.g. 'I am sorry for your loss. Thank you, goodbye.'
- **R64** (_openapi.json /close_call_): `close_call` is always the last tool call; nothing is accepted after it. `reason` is required for every outcome except `promise` and `paid`.
  - where: global tool close_call config.alwaysRunsAt end_of_call + pre_process_code; fin_* code nodes set outcome/reason
  - evidence: `config: {"maxRetries": 0, "alwaysRunsAt": ["end_of_call"]}`
  - fix: Add to system_prompt: 'Never call close_call yourself; it runs automatically when the call ends.' This makes sure no tool call can come after close_call.

## All rules

| id | status | where | evidence |
|---|---|---|---|
| R01 | implemented | flow setup -> opening -> ask_dob -> ask_phone -> load_account -> prepare (prods[0]) -> negotiate -> fin_* nodes | p = prods[0] if prods else {} |
| R02 | implemented | system_prompt / setup code / test_variables use customer_id, first_name, last_name, title, now | "test_variables": {"customer_id": "c_test", "first_name": "Daniel", "last_name": "Reyes", "title": "Mr", "now": "2026-10-14T11:00"} |
| R03 | implemented | api_tool(): body.customer_id default on every tool (schedule_callback, verify_identity, transfer_to_agent, get_account, create_promise, close_call) | body.customer_id (string): default "{{customer_id}}" |
| R04 | implemented | system_prompt | Address the customer as {{title}} {{last_name}}. |
| R05 | implemented | setup code: nowdt parsed from vars['now'], all dates derived from it | raw = str(vars.get('now') or '').strip() |
| R06 | implemented | opening on_enter tts | Hello, this is Freya Bank's digital assistant. Please note that we record this call. Am I speaking with {{title}} {{last_name}}? |
| R07 | implemented | opening/opening_retry/third_party/ask_dob/ask_phone task_messages | Never mention the bank account, a product, a debt, an amount, a payment or collections, even if they ask or offer to pay or help. |
| R08 | implemented | opening on_enter tts; opening_retry task_message | Then ask exactly: "Am I speaking with {{title}} {{last_name}}?" |
| R09 | implemented | opening extraction who1 + transition always -> opening_retry | unclear = anything else: 'hello', 'go ahead', 'who is this?', 'what is this about?', a question, silence. |
| R10 | implemented | opening_retry task_message (answer question first) + transition always -> fin_unclear (not_reached/unclear) | If the person asked a question, answer it briefly first: who you are -> you are Freya Bank's digital assistant; |
| R11 | implemented | system_prompt; opening_retry task_message | - If asked whether you are a robot or an AI: say you are Freya Bank's digital assistant, then continue. |
| R12 | implemented | third_party task_message | STRICT: Never say why you are calling. |
| R13 | implemented | setup code: callback_text; third_party.task_message; transition schedule_callback_response.data.ok -> fin_callback (not_reached/callback) | lines.append(txt(nbd) + ' (' + nbd.isoformat() + '), from 10:00 up to 19:00 included.') |
| R14 | implemented | third_party.task_message + tool-call transition -> fin_no_callback | - If the second answer is also outside the window, or they cannot say when, do not book: call transition_to_fin_no_callback. |
| R15 | implemented | third_party transition tp_status=wrong_number -> fin_wrong_number | 3. -> fin_wrong_number  if (tp_status equals "wrong_number")  ["wrong number"] |
| R16 | implemented | third_party transition tp_status=deceased -> fin_deceased; end_deceased terminal spoken_message | terminal: endedReason=not_reached_deceased, spoken_message="I am sorry for your loss. Goodbye." |
| R17 | implemented | third_party.task_message STRICT line | Never mention the bank account, a product, a debt, an amount, a payment or collections, even if they ask or offer to pay or help. ... Do not ask them any securi |
| R18 | implemented | ask_dob (verify_identity field date_of_birth) -> ask_phone (verify_identity#2 field phone_last4) | You must check identity with two security questions, one at a time. Now ask the first: their date of birth. |
| R19 | implemented | ask_dob.task_message; verify_identity answer description | A date said only as numbers is day, then month, then year (05/03/1990 = 1990-03-05). |
| R20 | implemented | verify_identity post_process_code; ask_dob/ask_phone transition wrong_answers_left=0 -> fin_failed | 1. -> fin_failed  if (verify_identity_response.data.wrong_answers_left equals "0")  ["three wrong answers"] |
| R21 | implemented | verify_identity post_process_code hint branch | Day and month look swapped. This is NOT a wrong answer. Ask the customer to say the date of birth again with the month as a word, for example 14 March 1988. |
| R22 | implemented | fin_failed (not_verified/failed); end_failed terminal spoken_message; verify_identity post_process_code | I am sorry, I could not verify your identity, so I cannot continue. Please use the Freya Bank mobile app or visit a branch. Thank you, goodbye. |
| R23 | implemented | ask_dob/ask_phone task_message + refusal extraction -> count_decline_* code (n>=2 -> fin_declined) | vars['decline_route'] = 'close' if n >= 2 else 'retry' |
| R24 | implemented | ask_phone transition all_verified -> load_account (pre_action get_account) | 1. -> load_account  if (verify_identity_response.data.all_verified equals "true" OR verify_identity_response.data.all_verified equals "True") |
| R25 | implemented | negotiate on_enter tts; prepare code: product_words | I am calling from the collections team about a late payment on your {{product_words}}. The past-due amount is {{past_due_fmt}}, and it is {{days_late_txt}} days |
| R26 | implemented | setup/prepare code: HOL and isbd | HOL = set(['2026-10-26', '2026-11-11', '2026-11-26', '2026-12-25', '2027-01-01']) |
| R27 | implemented | setup code: early_deadline/late_deadline; prepare code: band/attempts | if days_late <= 7:         band = 'early'; attempts = 1; deadline = datetime.date.fromisoformat(str(vars.get('early_deadline'))) |
| R28 | implemented | negotiate.task_message DATES; prepare code: calendar_text | - A promise date must be a business day (Monday to Friday, not a bank holiday) from today up to the deadline. |
| R29 | implemented | negotiate.task_message item 3 (Date); prepare code calendar next business day | Weekend or bank holiday not after the deadline -> say that day is not possible and offer the next business day shown. |
| R30 | implemented | negotiate.task_message item 3 (vague period) | A vague period ('next week', 'the week after next', 'end of the month', 'when my salary comes') -> ask once for the exact day. If they still give none, propose  |
| R31 | implemented | setup code: weekday_table; negotiate.task_message item 3 | tab.append(t1 + '; "next ' + WD[i] + '" = ' + txt(b)) |
| R32 | implemented | negotiate.task_message item 3 (Date) | After the deadline (for example a salary date later) -> say the latest date you can record is {{deadline_text}} and offer it; if they refuse that, it is a flat  |
| R33 | implemented | negotiate.task_message item 1 | 1. You propose every amount. NEVER ask how much they can pay. If they ask you to choose, propose an amount yourself. Start with the full past-due amount. |
| R34 | implemented | prepare code: floor | floor = p.get('minimum_payment') |
| R35 | implemented | negotiate.task_message item 4; prepare code attempt2_line | 4. If they say the full amount is too much: offer the floor {{floor_fmt}} once, and say the rest stays overdue. If they refuse the floor, it is a flat refusal. |
| R36 | implemented | negotiate.task_message item 3 (Amount) | Amount from the floor up to the full amount, both included -> accept it. Below the floor -> say it cannot be recorded and offer the floor {{floor_fmt}} once; if |
| R37 | implemented | negotiate on_enter tts | The past-due amount is {{past_due_fmt}}, and it is {{days_late_txt}} days late. Can you make this payment today? |
| R38 | implemented | negotiate.task_message item 3 (CALENDAR, floor/deadline checks) | 3. A date or an amount the customer proposes is never a refusal. Check it: |
| R39 | implemented | negotiate.task_message item 5 | Attempt 1: propose paying on {{attempt1_text}} - the full amount, or the floor {{floor_fmt}} if they already said the full amount is too much. |
| R40 | implemented | setup code: attempt1_date (lastbd); prepare code: attempt2_line (late band only) | vars['attempt2_line'] = 'Attempt 2: propose the floor amount ' + fmt(floor) + ' on the deadline, ' + txt(deadline) + ' (' + deadline.isoformat() + ').' |
| R41 | implemented | negotiate.task_message item 5; negotiate transition -> fin_refused (no_promise/refused) | When the allowed attempts are used up and they refuse again, stop: call transition_to_fin_refused. Never repeat an offer they already refused. |
| R42 | implemented | negotiate transition topic=hardship -> hardship node; hardship transitions -> xfer_support (queue support) / fin_hardship | On your first turn here: say one short sentence of sympathy, then offer to connect them with the customer support team. Offer it only once. |
| R43 | implemented | system_prompt; negotiate.task_message OTHER; hardship.task_message | - Never offer a discount, waiver, payment plan or any term you were not given. |
| R44 | implemented | negotiate.task_message item 6; tool create_promise description | 6. When amount and date are agreed, read back: "{{product_words}}, <amount>, on <weekday day month>. Do you confirm?" Call create_promise only after a clear yes |
| R45 | implemented | negotiate.task_message item 6 | If they change the date or amount, check it again and read back again. |
| R46 | implemented | negotiate.task_message OTHER; transition create_promise ok -> fin_promise ends call | - If they ask to change or cancel a promise: they can do it in the mobile app. |
| R47 | implemented | create_promise post_process_code; negotiate item 7; transition -> fin_service_error; end_service_error spoken_message | 7. After create_promise: if it failed, call create_promise once more with the same values. Never say the promise is recorded unless the result has ok true. |
| R48 | implemented | end_promise terminal spoken_message | Your payment promise is recorded. You will receive a text message confirming this promise. Thank you for your time, {{title}} {{last_name}}. Goodbye. |
| R49 | implemented | negotiate transition topic=already_paid -> fin_paid; end_paid terminal spoken_message | Thank you for letting me know. Payments can take one business day to appear, so I will not take a promise today. |
| R50 | implemented | negotiate extraction topic (dispute) -> fin_dispute; end_dispute terminal | dispute = says the debt or product is not theirs, they never had it, or it was closed or paid off in the past. |
| R51 | implemented | negotiate transition topic=new_plan -> xfer_restructuring (transfer_to_agent#2 queue restructuring) -> fin_transferred_restructuring | I cannot set up a new plan myself, but I will transfer you to the team that can help with that. |
| R52 | partial | ask_dob / ask_phone / negotiate task_message + transfer_to_agent (queue general) + transition -> fin_transferred_human | - If they ask for a human: the first time, ask whether you can help them yourself. If they insist, call transfer_to_agent. |
| R53 | implemented | system_prompt 'Always' list; opening_retry task_message | - If asked whether this is a scam: say they can verify this call by phoning Freya Bank's customer service number, then continue. |
| R54 | implemented | system_prompt; negotiate.task_message OTHER | - Never invent figures, dates or reasons. If you do not have the information, say so. |
| R55 | implemented | negotiate task_message + transition_to_fin_refused; count_decline_dob/phone code (n >= 2 -> fin_declined); opening_retry refuses -> fin_declined | - If they say twice that they do not want to talk: call transition_to_fin_refused. |
| R56 | implemented | global tool close_call alwaysRunsAt end_of_call; fin_* code nodes set outcome/reason; pre_process_code drops empty reason | close_call["config"]["alwaysRunsAt"] = ["end_of_call"] |
| R57 | partial | negotiate/hardship transition create_promise ok -> fin_promise | 1. -> fin_promise  if (create_promise_response.data.ok equals "true" OR create_promise_response.data.ok equals "True")  ["promise recorded"] |
| R58 | implemented | tool definitions (no add_note tool defined) | "tools": [close_call], |
| R59 | partial | end_* terminal spoken_message | I am sorry for your loss. Goodbye. |
| R60 | implemented | tools verify_identity / verify_identity#2 baked field defaults, answer description, post_process_code | d['what_to_do_next'] = 'The answer could not be read. It does not count as wrong. Ask again: What are the last four digits of the phone number on file?' |
| R61 | implemented | ask_phone transition -> load_account (all_verified); load_account pre_action get_account; prepare code (type/card_last4/minimum_payment/instalment_amount) | if ptype == 'credit_card':         words = 'credit card ending ' + str(p.get('card_last4') or '') |
| R62 | implemented | tool create_promise body (customer_id/product_id baked defaults, amount number, date YYYY-MM-DD) + pre_process_code | body.product_id (string): default "{{product_id}}" |
| R63 | implemented | tool schedule_callback body (date*, time* HH:MM, customer_id baked) | body.time* (string): default "{{time}}"; Callback time as HH:MM, 24 hour, between 10:00 and 19:00. |
| R64 | partial | global tool close_call config.alwaysRunsAt end_of_call + pre_process_code; fin_* code nodes set outcome/reason | config: {"maxRetries": 0, "alwaysRunsAt": ["end_of_call"]} |

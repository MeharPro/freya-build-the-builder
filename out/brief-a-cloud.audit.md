# Coverage audit: brief-a-cloud.workflow.json

Rules: `brief-a-cloud.rules.json`. Generator: `gen_brief-a-cloud.py`. Model claude-opus-5-5, 48 s, $1.20, 6 call(s).

| implemented | partial | missing | contradicted | superseded | total |
|---|---|---|---|---|---|
| 62 | 0 | 0 | 0 | 0 | 62 |

## All rules

| id | status | where | evidence |
|---|---|---|---|
| R01 | implemented | opening -> ask_dob/ask_phone -> load_account -> prepare (prods[0]) -> negotiate -> fin_* nodes | p = prods[0] if prods else {} |
| R02 | implemented | every tool definition body.customer_id default | body.customer_id (string): default "{{customer_id}}" |
| R03 | implemented | SYSTEM PROMPT | Address the customer as {{title}} {{last_name}}. |
| R04 | implemented | setup code: nowdt from vars['now'] | raw = str(vars.get('now') or '').strip() |
| R05 | implemented | opening on_enter tts | Hello, I am a digital assistant calling from Freya Bank. This call is recorded. Am I speaking with {{title}} {{last_name}}? |
| R06 | implemented | opening_retry / third_party / ask_dob / ask_phone task_message | STRICT: Never say why you are calling. Never mention the bank account, a product, a debt, an amount, a payment or collections, even if they ask or offer to pay  |
| R07 | implemented | opening on_enter tts; opening_retry task_message | Then ask exactly: "Am I speaking with {{title}} {{last_name}}?" |
| R08 | implemented | opening extraction who1 -> setup routes -> opening_retry; opening_retry always -> fin_unclear | unclear = anything else: 'hello', 'go ahead', 'who is this?', 'what is this about?', 'is this a robot?', 'is this a scam?', a question, silence. |
| R09 | implemented | SYSTEM PROMPT; opening_retry task_message | - If asked whether you are a robot or an AI: say you are Freya Bank's digital assistant, then continue. |
| R10 | implemented | third_party task_message | Your only job: ask when {{title}} {{last_name}} can be reached, then book a callback. |
| R11 | implemented | setup code: callback_text; third_party transition ok_true -> fin_callback | lines.append('Today, ' + txt(today) + ' (' + today.isoformat() + '), from ' + start + ' up to 19:00.') |
| R12 | implemented | third_party task_message; tool-call transition -> fin_no_callback | - If the second answer is also outside the window, or they cannot say when, do not book: call transition_to_fin_no_callback. |
| R13 | implemented | third_party transition tp_status=wrong_number -> fin_wrong_number (also setup/opening_retry who=wrong_number) | 3. -> fin_wrong_number  if (tp_status equals "wrong_number")  ["wrong number"] |
| R14 | implemented | third_party transition tp_status=deceased -> fin_deceased; end_deceased terminal spoken_message | terminal: endedReason=not_reached_deceased, spoken_message="I am sorry for your loss. Thank you, goodbye." |
| R15 | implemented | third_party.task_message STRICT line | Never mention the bank account, a product, a debt, an amount, a payment or collections, even if they ask or offer to pay or help. ... Do not ask them any securi |
| R16 | implemented | ask_dob (verify_identity field=date_of_birth) -> ask_phone (verify_identity#2 field=phone_last4) | 2. -> ask_phone  if (verify_identity_response.data.verified equals "true" OR verify_identity_response.data.verified equals "True")  ["date of birth correct"] |
| R17 | implemented | ask_dob.task_message | call verify_identity with answer = the date as YYYY-MM-DD, whatever way they said it. A date said only as numbers is day, then month, then year (05/03/1990 = 19 |
| R18 | implemented | ask_dob/ask_phone transitions on wrong_answers_left=0; verify_identity post_process_code wrong-answer retry | 1. -> fin_failed  if (verify_identity_response.data.wrong_answers_left equals "0")  ["three wrong answers"] |
| R19 | implemented | tool verify_identity post_process_code | d['what_to_do_next'] = 'Day and month look swapped. This is NOT a wrong answer. Ask the customer to say the date of birth again with the month as a word, for ex |
| R20 | implemented | fin_failed code + end_failed terminal; verify_identity post_process_code MAX_WRONG | spoken_message="I am sorry, I could not verify your identity, so I cannot continue. Please use the Freya Bank mobile app or visit a branch. Thank you, goodbye." |
| R21 | implemented | ask_dob/ask_phone ID_COMMON + refusal extraction -> count_decline_* code (shared decline_count, close at 2) -> fin_declined | vars['decline_route'] = 'close' if n >= 2 else 'retry' |
| R22 | implemented | ask_phone transition all_verified -> load_account (get_account pre_action) | 1. -> load_account  if (verify_identity_response.data.all_verified equals "true" OR verify_identity_response.data.all_verified equals "True")  ["identity verifi |
| R23 | implemented | negotiate on_enter tts; prepare code product_words | I am calling from the collections team about a late payment on your {{product_words}}. The past-due amount is {{past_due_fmt}}, and it is {{days_late_txt}} days |
| R24 | implemented | setup/prepare code: HOL, BWD, isbd | HOL = set(['2026-10-26', '2026-11-11', '2026-11-26', '2026-12-25', '2027-01-01']) |
| R25 | implemented | setup code: early_deadline/late_deadline; prepare code: band/attempts | if days_late <= 7:             band = 'early'; attempts = 1; deadline = datetime.date.fromisoformat(str(vars.get('early_deadline'))) |
| R26 | implemented | negotiate.task_message DATES + calendar_text (starts today, deadline-bounded) | - A promise date must be a business day (Monday to Friday, not a bank holiday) from today up to the deadline. |
| R27 | implemented | negotiate.task_message item 3 (Date) + prepare calendar_text next business day | Weekend or bank holiday not after the deadline -> say that day is not possible and offer the next business day shown. |
| R28 | implemented | negotiate.task_message item 3 (vague period) | A vague period ('next week', 'the week after next', 'end of the month', 'when my salary comes') -> ask once for the exact day. If they still give none, propose  |
| R29 | implemented | setup code: weekday_table; negotiate.task_message WEEKDAY WORDS | tab.append(t1 + '; "next ' + WD[i] + '" = ' + txt(b)) |
| R30 | implemented | negotiate.task_message item 3 (Date) | After the deadline (for example a salary date later) -> say the latest date you can record is {{deadline_text}} and offer it; if they refuse that, it is a flat  |
| R31 | implemented | negotiate.task_message item 1 | 1. You propose every amount. NEVER ask how much they can pay. If they ask you to choose, propose an amount yourself. Start with the full past-due amount. |
| R32 | implemented | prepare code: floor selection | floor = p.get('minimum_payment') |
| R33 | implemented | negotiate.task_message item 4 + prepare code attempt2_line | 4. If they say the full amount is too much: offer the floor {{floor_fmt}} once, and say the rest stays overdue. If they refuse the floor, it is a flat refusal. |
| R34 | implemented | negotiate.task_message item 3 (Amount) | Amount from the floor up to the full amount, both included -> accept it. Below the floor -> say it cannot be recorded and offer the floor {{floor_fmt}} once; if |
| R35 | implemented | negotiate on_enter tts | The past-due amount is {{past_due_fmt}}, and it is {{days_late_txt}} days late. Can you make this payment today? |
| R36 | implemented | negotiate.task_message item 3 | 3. A date or an amount the customer proposes is never a refusal. Check it: |
| R37 | implemented | negotiate.task_message item 5; setup code: attempt1_date; prepare code: attempt2_line |    - Attempt 1: propose paying on {{attempt1_text}} - the full amount, or the floor {{floor_fmt}} if they already said the full amount is too much. |
| R38 | implemented | negotiate.task_message item 5; transition -> fin_refused (no_promise/refused) |    - When the allowed attempts are used up and they refuse again, stop: call transition_to_fin_refused. Never repeat an offer they already refused. |
| R39 | implemented | negotiate transition topic=hardship -> hardship; hardship node; xfer_support (queue support) -> fin_transferred_support; decline -> fin_hardship | On your first turn here: say one short sentence of sympathy, then offer to connect them with the customer support team. Offer it only once. |
| R40 | implemented | system prompt; negotiate.task_message OTHER | - Never offer a discount, waiver, payment plan or any term you were not given. |
| R41 | implemented | negotiate.task_message item 6; create_promise description | 6. When amount and date are agreed, read back: "{{product_words}}, <amount>, on <weekday day month>. Do you confirm?" Call create_promise only after a clear yes |
| R42 | implemented | negotiate.task_message item 6 | If they change the date or amount, check it again and read back again. |
| R43 | implemented | negotiate.task_message OTHER; create_promise ok -> fin_promise ends call | - If they ask to change or cancel a promise: they can do it in the mobile app. |
| R44 | implemented | create_promise post_process_code; negotiate transition -> fin_service_error; end_service_error spoken_message | d['what_to_do_next'] = 'NOT recorded. Do not say it is recorded. Call create_promise once more with exactly the same values.' |
| R45 | implemented | end_promise terminal spoken_message | spoken_message="You will receive a text message confirming this promise. Thank you for your time, {{title}} {{last_name}}. Goodbye." |
| R46 | implemented | negotiate transition topic=already_paid -> fin_paid; end_paid spoken_message; close_call pre_process_code drops reason | Thank you for letting me know. Payments can take one business day to appear, so I will not take a promise today. |
| R47 | implemented | negotiate extraction topic=dispute -> fin_dispute (no_promise/dispute) | dispute = says the debt or product is not theirs, they never had it, or it was closed or paid off in the past. |
| R48 | implemented | negotiate transition topic=new_plan -> xfer_restructuring (transfer_to_agent#2 queue restructuring) -> fin_transferred_restructuring | 7. -> xfer_restructuring  if (topic equals "new_plan")  ["wants a new plan"] |
| R49 | implemented | ask_dob/ask_phone/negotiate/hardship task_message + tool transfer_to_agent (queue general) + transition -> fin_transferred_human | - If the customer asks for a human: the first time, ask whether you can help them yourself. If they insist, call transfer_to_agent. |
| R50 | implemented | system prompt 'Always' list; opening_retry.task_message | - If asked whether this is a scam: say they can verify this call by phoning Freya Bank's customer service number, then continue. |
| R51 | implemented | system prompt; negotiate.task_message OTHER | - Never invent figures, dates or reasons. If you do not have the information, say so. |
| R52 | implemented | negotiate.task_message OTHER -> fin_refused; count_decline_* code -> fin_declined; opening_retry transition refuses -> fin_declined | - If they say twice that they do not want to talk: call transition_to_fin_refused. |
| R53 | implemented | global tool close_call (alwaysRunsAt end_of_call); system prompt | config: {"maxRetries": 0, "alwaysRunsAt": ["end_of_call"]} |
| R54 | implemented | fin_* code nodes; close_call pre_process_code drops empty reason | if b.get('outcome') in ('promise', 'paid') or not b.get('reason'): |
| R55 | implemented | negotiate transition 1 -> fin_promise (call ends right after a recorded promise, so no transfer can follow) | 1. -> fin_promise  if (create_promise_response.data.ok equals "true" OR create_promise_response.data.ok equals "True")  ["promise recorded"] |
| R56 | implemented | TOOL DEFINITIONS (no add_note tool defined) | GLOBAL TOOLS (available in every node / run at end of call): close_call |
| R57 | implemented | end_* terminal spoken_message (all thank and say goodbye) | spoken_message="I understand. Thank you for your time, {{title}} {{last_name}}. Goodbye." |
| R58 | implemented | tools verify_identity / verify_identity#2 baked field + post_process_code | d['what_to_do_next'] = 'The answer could not be read. It does not count as wrong. Ask again: What is your date of birth?' |
| R59 | implemented | ask_phone transition all_verified -> load_account; prepare code product type handling | if ptype == 'credit_card': |
| R60 | implemented | tool create_promise body + pre_process_code | b['amount'] = float(str(b['amount']).replace(',', '').strip()) |
| R61 | implemented | tool schedule_callback body (customer_id default, date*/time* required) + third_party.task_message | body.time* (string): default "{{time}}"; Callback time as HH:MM, 24 hour, between 10:00 and 19:00. |
| R62 | implemented | fin_* code nodes set outcome/reason; tool close_call pre_process_code; close_call alwaysRunsAt end_of_call | if b.get('outcome') in ('promise', 'paid') or not b.get('reason'): |

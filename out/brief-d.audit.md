# Coverage audit: brief-d.workflow.json

Rules: `brief-d.rules.json`. Generator: `gen_brief-d.py`. Model claude-opus-5-5, 83 s, $1.67, 9 call(s).

| implemented | partial | missing | contradicted | superseded | total |
|---|---|---|---|---|---|
| 84 | 4 | 0 | 0 | 9 | 97 |

## Top fixes

1. **R52** (partial): Asking for a plan, lower instalments or more time in general: describe nothing, `transfer_to_agent` queue `restructuring`, close transferred with code TRS.
   - why: In the hardship node a customer asking for a plan, lower instalments or more time is told 'you cannot offer that' instead of being transferred to restructuring, so these cases get the wrong close (not transferred/TRS) and miss the transfer_to_agent call.
   - fix: hardship node and hardship_notes node: in task_message, delete 'if they ask for one, say you cannot offer that' and write 'If the customer asks for a plan, lower instalments or more time: describe no options, move to the restructuring transfer.' Add a topic field with a 'new_plan' value (description 'wants a plan / lower instalments / more time') to the extraction_schema. Add the transition 'topic equals "new_plan" -> xfer_restructuring' ahead of the other routes, so the call goes through transfer_to_agent queue restructuring -> fin_transferred_restructuring (outcome transferred, reason TRS).
2. **R53** (partial): Asking for a person: transfer straight away with no "can I help you first"; `transfer_to_agent` queue `general`, close transferred with code TRH.
   - why: A customer in the hardship or hardship_notes node who asks for a person cannot be transferred, because neither node has transfer_to_agent or a route to fin_transferred_human, so the transfer call and the transferred/TRH close are missing.
   - fix: hardship and hardship_notes nodes: add the tool transfer_to_agent with queue baked as 'general', the same way ask_phone/negotiate do. Add the transition 'transfer_to_agent_success_count greater_than 0 -> fin_transferred_human' (outcome transferred, reason TRH). Add this task_message line: 'If the customer asks for a person: call transfer_to_agent straight away, no "can I help you first".'
3. **R88** (partial): Every `close_call` carries one outcome from the fixed list and exactly one code in `reason`; a close without a code is rejected.
   - why: close_outcome/close_code are first set in the setup code node, which runs only after the first customer turn, so a hang-up during the opening sends an empty reason that pre_process_code drops, and the close is rejected.
   - fix: Seed vars close_outcome='not_reached' and close_code='UNC' before the opening node is entered, either as initial workflow variables or in a code node placed before opening. In the close_call tool pre_process_code, stop popping an empty or unresolved reason: if reason is empty or still '{{close_code}}', set body['reason']='UNC' and body['outcome']='not_reached'.
4. **R65** (partial): Thank the customer and say goodbye, then exactly one `close_call` as the last tool call of every call, always with an outcome and a code, including promise (PRM) and paid (AP) closes even though the API marks reason optional for those; nothing is accepted after it.
   - why: The end_wrong_number, end_deceased and end_unclear farewells say goodbye without thanking the customer, so they miss the required closing courtesy.
   - fix: Terminal spoken_message: end_wrong_number becomes 'I apologise for the inconvenience. Thank you for your time. Goodbye.' Add 'Thank you for your time.' before 'Goodbye' in end_deceased and end_unclear too, and keep the condolences sentence in end_deceased word for word.

## partial (4)

- **R52** (_brief-d.md email 'Other things customers say'_): Asking for a plan, lower instalments or more time in general: describe nothing, `transfer_to_agent` queue `restructuring`, close transferred with code TRS.
  - where: negotiate transition topic=new_plan -> xfer_restructuring (queue restructuring) -> fin_transferred_restructuring (transferred/TRS)
  - evidence: `4. -> xfer_restructuring  if (topic equals "new_plan")  ["wants a plan / lower instalments / more time"]`
  - fix: In the hardship node, replace 'if they ask for one, say you cannot offer that' with a new_plan extraction routed to xfer_restructuring, so a plan request after a hardship is also transferred to restructuring (TRS).
- **R53** (_brief-d.md email 'Other things customers say'_): Asking for a person: transfer straight away with no "can I help you first"; `transfer_to_agent` queue `general`, close transferred with code TRH.
  - where: ask_phone/ask_dob/negotiate: tool transfer_to_agent (queue general) + transition -> fin_transferred_human (transferred/TRH)
  - evidence: `- If the customer asks for a person: call transfer_to_agent straight away, no 'can I help you first'.`
  - fix: Add transfer_to_agent (queue general) and the transfer_to_agent_success_count > 0 -> fin_transferred_human transition to the hardship and hardship_notes nodes.
- **R65** (_brief-d.md email 'Closing'; openapi.json /close_call_): Thank the customer and say goodbye, then exactly one `close_call` as the last tool call of every call, always with an outcome and a code, including promise (PRM) and paid (AP) closes even though the API marks reason optional for those; nothing is accepted after it.
  - where: close_call lifecycle tool (outcome {{close_outcome}}, reason {{close_code}}); fin_* code nodes; end_* terminals
  - evidence: `terminal: endedReason=not_reached_WN, spoken_message="I apologise for the inconvenience. Goodbye."`
  - fix: Add a thank-you before 'Goodbye' in the end_wrong_number, end_deceased and end_unclear spoken_message, keeping the condolences sentence verbatim.
- **R88** (_brief-d.md code list v3 (header)_): Every `close_call` carries one outcome from the fixed list and exactly one code in `reason`; a close without a code is rejected.
  - where: tool close_call body.reason default {{close_code}}; setup code defaults; fin_* code nodes
  - evidence: `vars['close_outcome'] = 'not_reached'
    vars['close_code'] = 'UNC'`
  - fix: close_outcome/close_code are first set in setup, which runs only after the first customer turn; a hang-up during opening sends an unresolved/empty reason that pre_process_code drops. Seed close_outcome=not_reached/close_code=UNC before opening (initial variables or a code node before opening) and do not pop an empty reason.

## All rules

| id | status | where | evidence |
|---|---|---|---|
| R01 | implemented | setup code: s_deadline / prepare code BANDS, floor / HOLIDAYS / fin_hardship | vars['s_deadline'] = addbd(today, 5).isoformat() |
| R02 | implemented | prepare code: BANDS, WORDS, per-product statement | WORDS = [(['credit_card'], 'credit card ending {card_last4}'), (None, '{type_words}')] |
| R03 | implemented | setup code (now parsing); tool bodies customer_id; prompts first_name/last_name/title | nowdt = datetime.datetime.fromisoformat(raw[:16]) |
| R04 | implemented | setup code: today derived from vars['now'] | raw = str(vars.get('now') or '').strip() |
| R05 | implemented | every tool definition body.customer_id incl. close_call | body.customer_id (string): default "{{customer_id}}" |
| R06 | implemented | tool create_promise pre_process_code + negotiate.task_message rules | if dl and b.get('date') and str(b['date']) > dl: |
| R07 | implemented | opening on_enter tts | on_enter tts: "This is the digital assistant of Kestrel Bank. Please note that this call is recorded. Am I speaking with {{first_name}} {{last_name}}?" |
| R08 | implemented | opening on_enter tts; opening_retry.task_message | Then ask exactly: "Am I speaking with {{first_name}} {{last_name}}?" |
| R09 | implemented | system prompt; ask_phone.task_message | Once identity is confirmed, address the customer as {{title}} {{last_name}}. |
| R10 | implemented | opening/opening_retry extraction who1/who2 description | customer = they confirm: 'yes', 'speaking', 'that's me', or they say their own name ({{first_name}} / {{last_name}}). |
| R11 | implemented | setup transition 5 -> opening_retry; opening_retry transition 6 -> fin_unclear (not_reached/UNC) | 6. -> fin_unclear  if always  ["always"] |
| R12 | implemented | opening_retry.task_message | If the person asked a question, answer it first in one sentence: who is this -> you are the digital assistant of Kestrel Bank; a robot or an AI -> say exactly " |
| R13 | implemented | system_prompt 'Always' list; also opening_retry, ask_phone/ask_dob task_message | - Robot or AI question: say exactly "I am Kestrel Bank's digital assistant." and carry on. |
| R14 | implemented | system_prompt 'Always' list; also opening_retry, ask_phone/ask_dob task_message | - Scam question: they are welcome to hang up and call the number on the back of their card or on their statement; carry on. |
| R15 | implemented | opening_retry, third_party, ask_phone, ask_dob task_message (NEVER_SAY); opening on_enter tts names no product or reason | NEVER say, before identity is confirmed: arrears, overdue, late, collections, debt, payment, instalment, or the name of any product (credit card, loan, car loan |
| R16 | implemented | third_party.task_message | Say that this is a personal banking matter that you can only discuss with {{title}} {{last_name}}, and ask when they can be reached. Nothing more. |
| R17 | superseded | superseded by R86 |  |
| R18 | implemented | third_party tool schedule_callback + transition -> fin_callback (not_reached/CBK) | 1. -> fin_callback  if (schedule_callback_response.data.ok equals "true" OR schedule_callback_response.data.ok equals "True")  ["callback booked"] |
| R19 | implemented | third_party.task_message + transition_to_fin_no_callback -> fin_no_callback (not_reached/NCB) | - Outside the window -> propose ONCE the nearest slot inside the window (a precise day and HH:MM). If they accept, book it. |
| R20 | implemented | third_party extraction tp_status + transition -> fin_wrong_number (not_reached/WN) | 3. -> fin_wrong_number  if (tp_status equals "wrong_number")  ["wrong number"] |
| R21 | implemented | third_party transition -> fin_deceased (not_reached/DEC); end_deceased terminal spoken_message | terminal: endedReason=not_reached_DEC, spoken_message="Please accept my condolences. Goodbye." |
| R22 | implemented | third_party.task_message STRICT block | Ask no security question. If they offer to pay, to answer questions, or to help, decline politely (you can only discuss it with {{title}} {{last_name}}) and ask |
| R23 | implemented | ask_phone (verify_identity field phone_last4) -> ask_dob (verify_identity#2 field date_of_birth) | Before anything else you must check identity with two security questions, one at a time. Ask the first now: the last four digits of their phone number. |
| R24 | implemented | ask_dob.task_message; verify_identity/verify_identity#2 post_process_code (ok=false branch) | call verify_identity with answer = the date as YYYY-MM-DD, however they said it. A date said only as numbers is day, then month, then year (05/03/1990 = 1990-03 |
| R25 | implemented | ask_phone/ask_dob transition 1 -> fin_failed; verify_identity post_process_code | 1. -> fin_failed  if (verify_identity_response.data.wrong_answers_left equals "1" OR verify_identity_response.data.wrong_answers_left equals "0")  ["second wron |
| R26 | implemented | tool verify_identity#2 post_process_code (hint branch) | d['what_to_do_next'] = 'Day and month look swapped. This is NOT a wrong answer. Ask the customer to repeat the date of birth with the month as a word, for examp |
| R27 | implemented | ask_phone/ask_dob transition -> fin_failed; end_failed terminal spoken_message | terminal: endedReason=not_verified_IDF, spoken_message="For security I cannot continue by phone. You can use the Kestrel mobile app or visit a branch. Thank you |
| R28 | implemented | ask_phone/ask_dob task_message + refusal extraction -> count_decline_* -> fin_declined | vars['decline_route'] = 'close' if n >= 2 else 'retry' |
| R29 | implemented | ask_phone/ask_dob transition all_verified -> load_account | -> load_account  if (verify_identity_response.data.all_verified equals "true" OR verify_identity_response.data.all_verified equals "True") |
| R30 | implemented | prepare code: statement_text, spoken by negotiate on_enter tts | Thank you, {title} {last_name}. I am calling from the arrears team about an overdue payment. Your {words} has an overdue amount of {past_due}, and it is {days_l |
| R31 | implemented | system prompt; negotiate.task_message OTHER | - Never mention consequences (fees, credit file, legal action, collectors). |
| R32 | implemented | prepare code: statement_text (negotiate on_enter tts) | st += _fill('Are you able to clear all of these today?', base) |
| R33 | implemented | negotiate.task_message rule 1; products_text attempt 1 | 1. You propose every amount. NEVER ask how much they can pay, in any wording. If they ask 'how much should I pay?', propose the amount in play. |
| R34 | implemented | negotiate.task_message rule 3 | 3. Full amount too much -> offer that product's floor ONCE and say: the remainder stays overdue and we will be in touch about it. Floor declined = flat refusal. |
| R35 | implemented | negotiate.task_message rule 2 + CALENDAR | 2. A date or an amount the customer names is NEVER a refusal and uses no attempt. Check it: |
| R36 | implemented | negotiate.task_message rule 4; prepare products_text attempts per band | When that product's attempts are used up, stop: never repeat an offer already turned down; that product is refused. |
| R37 | implemented | negotiate.task_message rule 8; finalize default -> fin_refused | vars['close_outcome'] = 'no_promise'         vars['close_code'] = 'RF' |
| R38 | implemented | negotiate transition topic=hardship -> hardship; hardship.task_message | On your first turn here say exactly "I am sorry to hear that." and then offer, once, to put them through to our customer care team. |
| R39 | implemented | hardship transition support_choice=accept -> xfer_support (transfer_to_agent#3 queue support) -> fin_transferred_support | vars['close_outcome'] = 'transferred'         vars['close_code'] = 'TSP' |
| R40 | superseded | superseded by R84 |  |
| R41 | implemented | hardship.task_message; finalize code rec -> fin_promise | Only if the customer themselves names a date or an amount for a product: check it against PRODUCTS and the CALENDAR, read it back ending with "Shall I record th |
| R42 | implemented | system prompt; negotiate.task_message OTHER; hardship.task_message | Never offer a discount, waiver, payment holiday, plan or any term you were not given. |
| R43 | implemented | negotiate.task_message item 6 | ONE read-back of all agreed promises together (product in words, amount, date as weekday day month; ...), ending with exactly "Shall I record that?". |
| R44 | implemented | tool create_promise description; negotiate.task_message item 6 | CALL it once per agreed product, in PRODUCTS order, only after the read-back and a clear yes to 'Shall I record that?'. |
| R45 | implemented | negotiate.task_message item 6 | If they change a date or an amount, check it again and read back again. |
| R46 | implemented | tool create_promise description; negotiate.task_message OTHER | They ask to change or cancel a recorded promise -> it cannot be changed in this call. |
| R47 | implemented | negotiate.task_message item 7; create_promise post_process_code | Never say a promise is recorded before create_promise returned ok. |
| R48 | implemented | negotiate.task_message item 7; create_promise post_process_code; finalize -> fin_service_error | msg = 'NOT recorded, failed 3 times. Tell the customer you could not record the promise for ' + pid + ', then call add_note for ' + pid + ' with reason service_ |
| R49 | implemented | end_promise terminal spoken_message; negotiate.task_message item 7 | terminal: endedReason=promise_PRM, spoken_message="We will email you a confirmation of this arrangement. Thank you for your time, {{title}} {{last_name}}. Goodb |
| R50 | implemented | negotiate.task_message item 5; add_note text description; finalize -> fin_paid (paid/AP) | 'I already paid' (a product) -> say exactly "Payments made today show on our side on the next business day.", take no promise for it, ask how and on which day t |
| R51 | implemented | negotiate.task_message item 5 + add_note enum + finalize precedence -> fin_dispute (no_promise/DSP) | 'That is not mine' / 'I never had this' -> do not argue, no promise for it, noted dispute. Then carry on with the other products. |
| R52 | partial | negotiate transition topic=new_plan -> xfer_restructuring (queue restructuring) -> fin_transferred_restructuring (transferred/TRS) | 4. -> xfer_restructuring  if (topic equals "new_plan")  ["wants a plan / lower instalments / more time"] |
| R53 | partial | ask_phone/ask_dob/negotiate: tool transfer_to_agent (queue general) + transition -> fin_transferred_human (transferred/TRH) | - If the customer asks for a person: call transfer_to_agent straight away, no 'can I help you first'. |
| R54 | implemented | opening_retry refuses -> fin_declined; count_decline_* -> fin_declined (IDD); negotiate.task_message OTHER + finalize -> fin_refused (RF) | - They say they do not want to talk -> say once this will only take a moment. If they say it again: every product without a promise is refused; call add_note fo |
| R55 | implemented | system prompt; negotiate.task_message OTHER | - Never invent figures, dates or reasons. A question you cannot answer: "I don't have that information." |
| R56 | implemented | prepare code: per-product band, floor, deadline | BANDS = [('F', 10, 1, 'f_deadline', None), ('S', None, 2, 's_deadline', None)] |
| R57 | implemented | prepare code statement_text (negotiate on_enter tts) + negotiate.task_message ORDER OF WORK C | st += _fill('Are you able to clear all of these today?', base) |
| R58 | implemented | prepare products_text per product attempts + negotiate.task_message C/4 | Each product starts at its attempt 1, unless the customer already named a date or an amount for it. |
| R59 | implemented | negotiate.task_message ORDER OF WORK B + prepare calendar_text per product | A product whose latest date is earlier than the named date goes on ITS OWN latest date (say so in the read-back). A named closure day or weekend moves to the bu |
| R60 | implemented | negotiate.task_message item 6; create_promise description | ending with exactly "Shall I record that?". If they change a date or an amount, check it again and read back again. After a clear yes, call create_promise once  |
| R61 | implemented | negotiate.task_message item 8; add_note description; all_done transition | 8. Then for EVERY product without a recorded promise call add_note (reason refused, hardship, dispute, paid, service_error) with the text the note requires; als |
| R62 | implemented | negotiate.task_message item 5 | 'That is not mine' / 'I never had this' -> do not argue, no promise for it, noted dispute. Then carry on with the other products. |
| R63 | implemented | negotiate transition transfer_to_agent_success_count > 0 -> fin_transferred_human; negotiate.task_message OTHER; add_note description | - They ask for a person -> call transfer_to_agent straight away (no notes after a transfer). |
| R64 | implemented | tool create_promise post_process_code (fail_<pid> >= 3); negotiate.task_message item 7; finalize code (rec -> promise) | msg = 'NOT recorded, failed 3 times. Tell the customer you could not record the promise for ' + pid + ', then call add_note for ' + pid + ' with reason service_ |
| R65 | partial | close_call lifecycle tool (outcome {{close_outcome}}, reason {{close_code}}); fin_* code nodes; end_* terminals | terminal: endedReason=not_reached_WN, spoken_message="I apologise for the inconvenience. Goodbye." |
| R66 | implemented | prepare code: BANDS loop per product on days_late; setup addbd (counts from the day after today) | if _b[1] is None or dl <= int(_b[1]): |
| R67 | superseded | superseded by R80 |  |
| R68 | superseded | superseded by R82 |  |
| R69 | superseded | superseded by R83 |  |
| R70 | implemented | setup/prepare HOL set and create_promise pre_process_code _hol (memo announces 2026-10-30) | HOL = set(['2026-10-30', '2026-11-20', '2026-12-24', '2026-12-25', '2026-12-28', '2026-12-31']) |
| R71 | implemented | negotiate.task_message DATES; tool create_promise pre_process_code (snaps weekend/closure day back) | - A promise date must be today or later, a business day (Monday to Friday, not a closure day), and not after THAT product's latest date. |
| R72 | superseded | superseded by R85 |  |
| R73 | implemented | negotiate.task_message rules 1, 2 (amount bullet), 3 and A | Amount from the floor up to the full amount, both included -> accept as proposed. More than the full amount -> record the full amount. Below the floor -> say it |
| R74 | implemented | negotiate.task_message rule 2 bullets + DATES; setup code vague_iso/vague_text; prepare calendar_text | - Vague period with no exact day after you asked once: propose {{vague_text}} ({{vague_iso}}), or the product's latest date if that is earlier. |
| R75 | implemented | setup code: weekday_table (this_d / next_d) | next_d = today + datetime.timedelta(days=(k if k > 0 else 7)) |
| R76 | implemented | negotiate.task_message rules 2 and 4; prepare products_text Attempt 1 line | 4. A flat refusal, a non-answer, or a no to paying today with no date and no amount uses ONE persuasion attempt of that product. |
| R77 | superseded | superseded by R81 |  |
| R78 | implemented | negotiate.task_message rule 4 and 8; prepare products_text attempt lines | When that product's attempts are used up, stop: never repeat an offer already turned down; that product is refused. |
| R79 | implemented | setup code s_deadline (5th bd); prepare BANDS S=2 attempts, card floor min(); fin_hardship HSHP; callback 09:00-18:00; HOL 2026-10-30 | vars['s_deadline'] = addbd(today, 5).isoformat() |
| R80 | implemented | setup code: f_deadline / s_deadline; prepare code BANDS | BANDS = [('F', 10, 1, 'f_deadline', None), ('S', None, 2, 's_deadline', None)] |
| R81 | implemented | prepare code products_text line/attempt2 templates; setup code attempt1_date; negotiate.task_message rule 4 | Attempt 2: propose the floor {floor} on the latest date {deadline_text} ({deadline_iso}). Persuasion attempts for this product: {attempts}. |
| R82 | implemented | prepare code floor computation; negotiate.task_message rule 2; create_promise pre_process_code caps amount at pd_ | floor = (min(2 * float(p.get('minimum_payment') or 0), amount)) |
| R83 | implemented | setup/prepare code HOL set; create_promise pre_process_code _hol | HOL = set(['2026-10-30', '2026-11-20', '2026-12-24', '2026-12-25', '2026-12-28', '2026-12-31']) |
| R84 | implemented | hardship support_choice decline -> hardship_notes; hardship_notes.task_message; finalize -> fin_hardship (no_promise/HSHP) | Then call add_note with reason hardship for each product still open: {{open_pids}} (ids from PRODUCTS), one per message, with the circumstance in the customer's |
| R85 | implemented | setup code callback_text; schedule_callback tool field descriptions; third_party.task_message | lines.append(txt(nbd) + ' (' + nbd.isoformat() + '), from 09:00 up to 18:00 included.') |
| R86 | implemented | setup code callback_text (today after now + 2 business days); third_party.task_message | start = '09:00' if cur < '09:00' else 'after ' + cur |
| R87 | implemented | opening on_enter tts; ask_phone -> ask_dob order; FAILED transition on wrong_answers_left 1/0 | 1. -> fin_failed  if (verify_identity_response.data.wrong_answers_left equals "1" OR verify_identity_response.data.wrong_answers_left equals "0") |
| R88 | partial | tool close_call body.reason default {{close_code}}; setup code defaults; fin_* code nodes | vars['close_outcome'] = 'not_reached'     vars['close_code'] = 'UNC' |
| R89 | superseded | superseded by R93 |  |
| R90 | implemented | negotiate/ask_phone/ask_dob transferred transitions -> fin_transferred_human; xfer_restructuring -> fin_transferred_restructuring; xfer_support -> fin_transferred_support | 2. -> fin_transferred_human  if (transfer_to_agent_success_count greater_than 0)  ["transferred to a person"] |
| R91 | implemented | tool add_note (enum + text description); negotiate.task_message item 8; prepare acct_route fail -> fin_service_error | Record why ONE product ends the call without a promise. CALL it once for every product without a recorded promise. Never after a transfer. |
| R92 | superseded | superseded by R94 |  |
| R93 | implemented | fin_* code nodes (17 outcome/code pairs); fin_hardship | vars['close_outcome'] = 'no_promise'         vars['close_code'] = 'HSHP' |
| R94 | implemented | finalize code + transitions; transfer routes -> fin_transferred_* | for reason, key in [('service_error', 'service_error'), ('hardship', 'hardship'), ('dispute', 'dispute'), ('refused', 'refused')]: |
| R95 | implemented | tool verify_identity (field baked phone_last4) / verify_identity#2 (field baked date_of_birth) | body.answer* (string): default "{{answer}}"; Exactly four digits. |
| R96 | implemented | tool create_promise body fields; tool schedule_callback body fields | body.time* (string): default "{{time}}"; Callback time as HH:MM, 24 hour, from 09:00 up to and including 18:00. |
| R97 | implemented | tool close_call config.alwaysRunsAt end_of_call | config: {"maxRetries": 0, "alwaysRunsAt": ["end_of_call"]} |

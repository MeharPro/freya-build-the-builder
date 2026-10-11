# Coverage audit: brief-a.workflow.json

Rules: `brief-a.rules.json`. Generator: `gen_brief-a.py`. Model gpt-6.1-sol, 42 s, cost unavailable (see provider usage), 6 call(s).

| implemented | partial | missing | contradicted | superseded | total |
|---|---|---|---|---|---|
| 58 | 1 | 0 | 1 | 0 | 60 |

## Top fixes

1. **R33** (contradicted): Accept customer-proposed amounts from floor to full, inclusive. Below floor, say it cannot be recorded and offer the floor once; nonacceptance is a flat refusal (rule 30).
   - why: Repeated below-floor offers incorrectly trigger another floor proposal or refusal handling, violating the offer-once rule and potentially producing the wrong closing outcome.
   - fix: In check_offer code, change check_one's repeated below-floor branch to explain that the named amount cannot be recorded without proposing the floor again. Do not increment the refusal counter for named amount offers; route plain nonacceptance of the floor through count_refusal. Keep acceptance of customer-proposed amounts from floor to full inclusive.
2. **R48** (partial): For a human request, ask once whether you can help first. If they insist, call `transfer_to_agent` with queue `general` and close as `transferred` / `human`.
   - why: Human requests in third_party and callback_retry lack the required handling, potentially missing transfer_to_agent and the transferred/human closing outcome.
   - fix: In third_party and callback_retry, add human-request extraction and transitions using the existing shared human_count. On the first request, route to a conversation node whose on_enter says "Can I help you first?" and increment the shared counter once; on insistence after that offer, route to xfer_general to call transfer_to_agent with queue "general", then fin_transferred_human to close with outcome "transferred" and reason "human".

## contradicted (1)

- **R33** (_brief-a.md rule 27_): Accept customer-proposed amounts from floor to full, inclusive. Below floor, say it cannot be recorded and offer the floor once; nonacceptance is a flat refusal (rule 30).
  - where: check_offer code: check_one repeated below-floor branch
  - evidence: `if pg(V, pid, 'offered_floor') == 'yes' and g(V, 'mode') != 'hardship' and g(V, 'confirmation_change') != 'yes':`
  - fix: Change check_one's repeated below-floor branch to explain that the named amount cannot be recorded without proposing the floor again; keep named offers out of the refusal counter and route plain floor nonacceptance through count_refusal.

## partial (1)

- **R48** (_brief-a.md rule 42_): For a human request, ask once whether you can help first. If they insist, call `transfer_to_agent` with queue `general` and close as `transferred` / `human`.
  - where: opening_human, id_human_*, pol_human and wrap_human shared counter; xfer_general; fin_transferred_human
  - evidence: `on_enter tts: "Can I help you first?"`
  - fix: Add human-request extraction and shared human_count routing to third_party and callback_retry so requests there also receive one offer to help followed by transfer to general on insistence.

## All rules

| id | status | where | evidence |
|---|---|---|---|
| R01 | implemented | setup bands; prepare single-product selection; opening -> ask_dob -> ask_phone -> load_account -> negotiate; fin_* outcome nodes | band = next(b for b in BANDS if b['min_days'] <= days_late <= b['max_days']) |
| R02 | implemented | generator workflow assembly without test_variables; opening; load_account tool-based account retrieval | wf = fl.assemble(INITIAL, nodes, SYSTEM, [close_call], conduct=True)   # no test_variables (CLAUDE.md); conduct = how customers talk |
| R03 | implemented | all tool definitions body.customer_id; system_prompt customer addressing; setup and check_callback code using now | You are Freya Bank's digital assistant on an outbound phone call to {{title}} {{last_name}}. Speak English. Keep every turn to one or two short sentences. Addre |
| R04 | implemented | opening.on_enter tts | on_enter tts: "Hello, I am a digital assistant calling from Freya Bank and this call is recorded. Am I speaking with {{title}} {{last_name}}?" |
| R05 | implemented | opening and opening_retry.task_message; identity task messages; third_party.task_message; load_account gated on all_verified | - Do not mention the reason for the call, collections, a debt, a payment, a product or an amount. If asked what the call is about or how much they owe, say you  |
| R06 | implemented | opening.on_enter tts; opening_retry.task_message | Then ask exactly: "Am I speaking with {{title}} {{last_name}}?" |
| R07 | implemented | opening.who1 and opening_retry.who2 extraction; setup fallback -> opening_retry; opening_retry fallback -> fin_unclear; fin_unclear code | unclear = anything else: 'hello', 'go ahead', 'who is this?', 'what is this about?', a question, silence. |
| R08 | implemented | opening_retry.task_message question-answer ordering and second confirmation ask | If the person asked a question, answer it briefly first: who you are -> you are Freya Bank's digital assistant; a robot or AI -> you are Freya Bank's digital as |
| R09 | implemented | system_prompt; opening_retry.task_message; policy aside handling | - If asked whether you are a robot or an AI: say you are Freya Bank's digital assistant, then continue. |
| R10 | implemented | third_party.task_message; callback_retry.task_message | Someone else answered. Do not disclose the reason, an account, any product or amounts. Do not accept security answers from a relative. Ask when the customer can |
| R11 | implemented | setup callback calendar; check_callback date/time and future validation; book_callback schedule_callback defaults; fin_callback code | invalid = invalid or hh > 23 or mm > 59 or not (rule['open'] <= tm <= rule['close']) |
| R12 | implemented | check_callback cb_invalid counter and retry line; close route -> fin_no_callback; booking restricted to valid route | vars['cb_route'] = 'close' if n >= 2 else 'retry' |
| R13 | implemented | third_party transitions -> fin_wrong_number; fin_wrong_number code; close_call lifecycle tool | 2. -> fin_wrong_number  if (tp_status equals "wrong_number")  ["wrong number"] |
| R14 | implemented | third_party transition -> fin_deceased; fin_deceased code; end_deceased terminal | terminal: endedReason=not_reached_deceased, spoken_message="I am sorry for your loss. Thank you, goodbye." |
| R15 | implemented | third_party.task_message; third_party and callback_retry have no security tools or account-disclosure routes | Someone else answered. Do not disclose the reason, an account, any product or amounts. Do not accept security answers from a relative. |
| R16 | implemented | ask_dob and ask_phone task_messages, verify_identity tool defaults and normalization, ask_dob verified transition -> ask_phone | When they give it, call verify_identity with answer = the date as YYYY-MM-DD, whatever way they said it. A date said only as numbers is day, then month, then ye |
| R17 | implemented | verify_identity and verify_identity#2 post_process_code share id_wrong; identity transitions -> fin_failed | done = nw >= 3 or str(left) == '0' |
| R18 | implemented | verify_identity post_process_code hint handling leaves wrong=False and instructs month-as-word retry | msg = 'Day and month look swapped. This is NOT a wrong answer. Ask the customer to say the date of birth again with the month as a word, for example 14 March 19 |
| R19 | implemented | identity exhausted transitions -> fin_failed; fin_failed code; end_failed terminal | terminal: endedReason=not_verified_failed, spoken_message="I am sorry, I could not verify your identity, so I cannot continue. Please use the Freya Bank mobile  |
| R20 | implemented | identity refusal extraction; count_decline_dob and count_decline_phone shared counter; decline_explain_* on_enter; fin_declined code | LATEST message: no_talk = explicitly does not want to talk or wants this call to stop; refused = refuses security or asks what the call is about instead of answ |
| R21 | implemented | ask_phone all_verified transition -> load_account; load_account pre_action get_account | 4. -> load_account  if (verify_identity_response.data.all_verified equals "true" OR verify_identity_response.data.all_verified equals "True")  ["identity verifi |
| R22 | implemented | prepare code product_words and statement; negotiate on_enter tts {{say_next}} | + words + '. The past-due amount is ' + fmt(past_due) + ', and it is ' + str(days_late) + ' days late. Can you make this payment today?') |
| R23 | implemented | setup and policy code HOL, BWD and isbd | HOL = set(['2026-10-26', '2026-11-11', '2026-11-26', '2026-12-25', '2027-01-01']) |
| R24 | implemented | setup BANDS and addbd deadline calculation; prepare band selection and one/two-rung ladders; policy refuse exhaustion logic | band = next(b for b in BANDS if b['min_days'] <= days_late <= b['max_days']) |
| R25 | implemented | check_offer code: check_one date guards; accept_offer code; confirm -> rec_next -> record_promise | elif not isbd(nd): |
| R26 | implemented | check_offer code: check_one checks after_deadline before weekend_or_holiday and uses next_bd | nb = next_bd(nd) |
| R27 | implemented | negotiate extraction offer_kind; check_offer code: check_one vague_asked branch | set_prop(V, pid, pa, dl) |
| R28 | implemented | check_offer code: resolve_when weekday branches; negotiate and confirm offer_date extraction | delta = (7 - today.weekday()) + wd |
| R29 | implemented | check_offer code: check_one after_deadline branch; negotiate stance refuse -> count_refusal | "after_deadline": "The latest date I can record is [deadline].", |
| R30 | implemented | prepare code: initial statement and full-amount proposal; negotiate.task_message | - Never propose, compute or change an amount or a date yourself, and never ask how much they can pay. The only offer you may make is the current offer in STATE, |
| R31 | implemented | prepare code: FLOORS and product-type-dependent floor field selection | floor = p.get(next(f['rule']['field'] for f in FLOORS if ptype in f['product_types'])) |
| R32 | implemented | too_much code: too_much offered_floor guard and overdue wording; count_refusal code; prepare late-band ladder | "too_much_floor": "I understand. The lowest amount I can accept is [floor], your [floor_name]. The rest stays overdue.", |
| R33 | contradicted | check_offer code: check_one repeated below-floor branch | if pg(V, pid, 'offered_floor') == 'yes' and g(V, 'mode') != 'hardship' and g(V, 'confirmation_change') != 'yes': |
| R34 | implemented | prepare code: statement; negotiate.on_enter tts | + words + '. The past-due amount is ' + fmt(past_due) + ', and it is ' + str(days_late) + ' days late. Can you make this payment today?') |
| R35 | implemented | negotiate extraction stance and offer_kind; offer guard transition precedes refusal; check_offer code | offer = names their own date, amount or period: a date or an amount the customer proposes is NEVER a refusal. |
| R36 | implemented | negotiate stance extraction -> count_refusal; setup attempt1_date; prepare band-specific rungs; policy refuse and rung code | rungs = [('full_or_floor', a1), ('floor', deadline)] |
| R37 | implemented | policy refuse() and state_line(); count_refusal transitions; fin_refused code | s += ' Offers already refused: ' + ', '.join([x.replace('@', ' on ') for x in rl]) + ': never offer them again.' |
| R38 | implemented | negotiate and confirm topic-priority transitions; pol_hardship; hardship; hs_decline; xfer_support; fin_hardship | "hardship": "I am sorry to hear that. Would you like me to connect you with our customer support team?", |
| R39 | implemented | system_prompt; negotiate, confirm, hardship and wrapup task_message | - Never offer a discount, waiver, payment plan or any term you were not given. |
| R40 | implemented | policy readback(); confirm on_enter and clear-yes transition -> rec_next -> record_promise | You read back the promise and asked "Do you confirm?". The promise is recorded only after a clear yes. |
| R41 | implemented | confirm change transition -> change_offer; policy ev_change(), check_one(), agree() and readback() | check_one(V, pid, a, d, 'exact') |
| R42 | implemented | policy rec_next() and ev_rec_after(); wrapup task_message; wrap_change code | - A recorded promise cannot be changed or cancelled on this call; they can change it in the Freya Bank mobile app. |
| R43 | implemented | record_promise response_mapping; rec_after ev_rec_after() with fail_max=2; enter_wrapup(); fin_service_error and end_service_error | ok = g(V, 'rec_ok').lower() == 'true' |
| R44 | implemented | policy enter_wrapup() builds wrap_line; wrapup on_enter tts | "after_recorded": "You will receive a text message confirming this promise.", |
| R45 | implemented | already_paid extraction and transitions -> pol_paid; fin_paid; end_paid terminal | "paid": "Thank you for letting me know. Payments can take one business day to appear, so I will not take a promise.", |
| R46 | implemented | topic dispute extraction; pol_dispute settlement routing; fin_dispute; end_dispute terminal | "dispute": "Thank you for telling me. I will not take a payment promise today.", |
| R47 | implemented | new_plan transitions -> xfer_restructuring; transfer_to_agent#3 baked queue; fin_transferred_restructuring | body.queue (string): default "restructuring" |
| R48 | partial | opening_human, id_human_*, pol_human and wrap_human shared counter; xfer_general; fin_transferred_human | on_enter tts: "Can I help you first?" |
| R49 | implemented | system_prompt scam instruction; policy finish_turn asides | - If asked whether this is a scam: say they can verify this call by phoning Freya Bank's customer service number, then continue. |
| R50 | implemented | system_prompt; negotiate, confirm, hardship and wrapup task_message | - Never invent figures, dates or reasons. If you do not have the information, say so. |
| R51 | implemented | opening_notalk and id_notalk_* counters -> fin_declined; pol_notalk and wrap_notalk shared counter -> fin_refused; human_count shared across verification | V['final_route'] = P['fin_keys']['refused']; V['route'] = 'fin' |
| R52 | implemented | global close_call lifecycle tool; fin_* outcome/reason assignments | config: {"maxRetries": 0, "alwaysRunsAt": ["end_of_call"]} |
| R53 | implemented | fin_* code nodes implement all closing-table pairs; close_call pre_process_code removes reason for promise and paid | if b.get('outcome') in ('promise', 'paid') or not b.get('reason'): |
| R54 | implemented | wrapup transfer routes -> xfer_general or xfer_restructuring -> fin_transferred_* overwrite recorded-promise outcome | 4. -> xfer_restructuring  if (wrap equals "new_plan")  ["asks for a new plan"] |
| R55 | implemented | policy configuration notes=False; workflow tool inventory contains no add_note | business_weekdays=WEEKDAYS, weekday_rule="this_week", multi=False, notes=False,                                   # one product; Brief A never uses add_note |
| R56 | implemented | all end_* terminal spoken_message farewells; close_call runs afterward at end_of_call | terminal: endedReason=promise, spoken_message="Thank you for your time, {{title}} {{last_name}}. Goodbye." |
| R57 | implemented | verify_identity and verify_identity#2 tool bodies, normalization and post_process_code; ask_dob and ask_phone task_message | msg = 'The answer could not be read. It does not count as wrong. Ask again: What is your date of birth?' |
| R58 | implemented | create_promise tool body and pre_process_code; rec_next supplies approved ISO date, product ID and amount | want = [('product_id', str(vars.get('rec_pid') or '')), ('amount', str(vars.get('rec_amount') or '')), ('date', str(vars.get('rec_date') or '')[:10])] |
| R59 | implemented | schedule_callback tool body and pre_process_code; check_callback constructs ISO date and HH:MM time | FIELDS = {'date': 'date', 'time': 'time'} |
| R60 | implemented | transfer_to_agent tool variants bake general, support and restructuring queues and include customer_id | for q, fin, line in [("restructuring", "fin_transferred_restructuring", "I cannot set up a new plan myself, but I will transfer you to the team that can help wi |

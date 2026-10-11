# Coverage audit: brief-a.workflow.json

Rules: `brief-a.rules.json`. Generator: `gen_brief-a.py`. Model gpt-6.1-sol, 60 s, cost unavailable (see provider usage), 6 call(s).

| implemented | partial | missing | contradicted | superseded | total |
|---|---|---|---|---|---|
| 52 | 8 | 0 | 0 | 0 | 60 |

## Top fixes

1. **R32** (partial): Accept customer-proposed amounts from floor to full amount, inclusive. Below floor, say it cannot be recorded and offer floor once; nonacceptance is a flat refusal (rule 30).
   - why: Discarding explicit zero or negative amounts can produce an incorrect recorded promise, including during hardship and confirmation changes.
   - fix: In shared ev_offer and ev_change code, remove the branch that changes an explicitly supplied amount <= 0 to None; reserve None for an absent amount. Pass nonpositive amounts to check_one, which must reject them as below floor, say they cannot be recorded, offer the floor once, and route nonacceptance to the flat-refusal flow. This also repairs the amount-validation gaps in R37, R38 and R41.
2. **R19** (partial): On refusal to answer, explain once that questions protect the account; asking what the call is about instead counts as declining. A second refusal or second such question closes as `not_verified` / `declined`.
   - why: Separate question and refusal counters let mixed declines evade the required second-decline close of not_verified / declined.
   - fix: In ask_dob and ask_phone transitions, send both explicit refusals and questions about what the call is about instead of answering through count_decline_dob/phone. Replace the separate increments in qb_dob/phone with the same persistent decline_count, incremented exactly once per qualifying turn: count 1 gives the account-protection explanation; count >= 2 routes to the finalizer setting outcome='not_verified' and reason='declined'.
3. **R48** (partial): For a human request, ask once whether you can help first. If they insist, call `transfer_to_agent` with queue `general`, then close `transferred` / `human`.
   - why: Resetting or splitting the human-request counter can repeat the help-first question instead of making the mandatory general-queue transfer.
   - fix: Use one persistent human-request counter in id_human_dob, id_human_phone, ev_human and ev_wrap_human. Initialize it only if absent, remove its reset from init_negotiation, and replace the separate wrap_human increment. On the first request ask whether the agent can help first; on renewed insistence route to xfer_general, call transfer_to_agent with queue='general', and close with outcome='transferred', reason='human'.
4. **R51** (partial): After twice saying they do not want to talk, close `no_promise` / `refused`, or `not_verified` / `declined` before verification. Rule 42 applies before and after verification.
   - why: Ignoring no-talk statements during wrap-up misses the required second-statement termination and can leave the wrong close_call outcome and reason.
   - fix: Add 'no_talk' to wrapup.extraction_schema and a deterministic transition for that value into the existing shared no-talk counting logic. Preserve the counter across post-verification nodes; on its second qualifying statement route to fin_refused, setting outcome='no_promise' and reason='refused', rather than continuing wrap-up or using the promise finalizer.
5. **R11** (partial): For a day or time outside rule 6's window, ask once for another time. If that is also outside the window, do not schedule; close as `not_reached` / `no_callback`.
   - why: Waiting for both callback fields delays the mandatory retry and can fail to close not_reached / no_callback after a second invalid proposal.
   - fix: In callback_guard code, replace the 'if dw and tw' prerequisite with independent validation of each supplied field: an out-of-window day OR an out-of-window time makes the proposal invalid even when the other field is absent. Count each invalid proposal once; the first routes to callback_retry to ask for another slot, and the second routes to the finalizer setting outcome='not_reached', reason='no_callback', without scheduling.

## partial (8)

- **R11** (_brief-a.md rule 7_): For a day or time outside rule 6's window, ask once for another time. If that is also outside the window, do not schedule; close as `not_reached` / `no_callback`.
  - where: callback_guard invalid-slot counter and callback_retry.on_enter
  - evidence: `if dw and tw:`
  - fix: In callback_guard, validate a supplied day or time independently and trigger the single alternate-slot retry immediately when either is outside the window, without waiting for both fields.
- **R19** (_brief-a.md rule 15_): On refusal to answer, explain once that questions protect the account; asking what the call is about instead counts as declining. A second refusal or second such question closes as `not_verified` / `declined`.
  - where: ask_dob and ask_phone task_messages; count_decline_dob/phone and qb_dob/phone code
  - evidence: `n = int(float(vars.get('question_count_dob') or 0)) + 1`
  - fix: Route counted questions about the call through the shared decline_count counter in count_decline_dob/phone, and give the account-protection explanation on the first counted decline; separate question counters currently allow mixed declines to escape the second-decline limit.
- **R32** (_brief-a.md rule 27_): Accept customer-proposed amounts from floor to full amount, inclusive. Below floor, say it cannot be recorded and offer floor once; nonacceptance is a flat refusal (rule 30).
  - where: check_offer code: ev_offer and check_one
  - evidence: `if a is not None and a <= 0:`
  - fix: In ev_offer and ev_change, preserve explicitly proposed zero or negative amounts instead of converting them to None, so check_one rejects them as below floor and offers the floor once.
- **R37** (_brief-a.md rule 32_): Illness, family death or job loss: give brief sympathy, no persuasion, offer support transfer. Prioritize over rules 30 and 41; still record voluntarily proposed dates or amounts under sections 7 and 8.
  - where: negotiate.topic transitions; pol_hardship code; hardship; check_offer shared ev_offer code
  - evidence: `if a is not None and a <= 0:`
  - fix: In shared ev_offer code, preserve explicitly proposed zero or negative amounts and validate them against the floor rather than treating them as absent; retain the existing hardship priority, sympathy and support routes.
- **R38** (_brief-a.md rule 32_): If the hardship customer still names a date or amount themselves, record the promise under sections 7 and 8.
  - where: hardship transitions -> check_offer; shared ev_offer and check_one code
  - evidence: `a = None`
  - fix: Remove the nonpositive-amount discard in ev_offer so an explicit hardship offer of zero or a negative amount reaches check_one's below-floor validation instead of inheriting the previous proposed amount.
- **R41** (_brief-a.md rule 35_): If the customer changes date or amount during confirmation, check the new value under sections 7 and 8 and read it back again.
  - where: confirm transition -> change_offer; shared ev_change code
  - evidence: `if a is not None and a <= 0:`
  - fix: In ev_change, stop replacing explicitly changed nonpositive amounts with None; pass them to check_one so the new amount is rejected or corrected under the floor rule before another read-back.
- **R48** (_brief-a.md rule 42_): For a human request, ask once whether you can help first. If they insist, call `transfer_to_agent` with queue `general`, then close `transferred` / `human`.
  - where: id_human_dob/id_human_phone; shared init_negotiation, ev_human and ev_wrap_human code; xfer_general
  - evidence: `c = int(num(g(V, 'wrap_human'), 0) or 0) + 1`
  - fix: Use one persistent human-request counter across identity, negotiation and wrap-up; do not reset it in init_negotiation or use a separate wrap_human counter, so the help-first question is asked only once per call.
- **R51** (_brief-a.md rule 45_): After twice saying they do not want to talk, close `no_promise` / `refused`, or `not_verified` / `declined` before verification. Rule 42 applies before and after verification.
  - where: opening_retry; count_decline_dob/phone; pol_notalk shared code; wrapup extraction_schema
  - evidence: `extract wrap (type string): enum ["other", "done", "human", "new_plan", "change", "question"] (min_confidence 0.5)`
  - fix: Add a no_talk value and transition in wrapup that counts these statements and routes the second to fin_refused; currently post-recording statements are not counted.

## All rules

| id | status | where | evidence |
|---|---|---|---|
| R01 | implemented | setup BANK_BANDS; prepare single-product selection; opening, identity, negotiation and fin_* routes | p = prods[0] if prods else {} |
| R02 | implemented | opening and setup use call variables; load_account obtains account facts only after verification | response_mapping: [{"path": "data.products", "variable": "products", "description": ""}] |
| R03 | implemented | system_prompt; all bank tool customer_id defaults; setup and policy date calculations | body.customer_id (string): default "{{customer_id}}" |
| R04 | implemented | opening.on_enter tts | on_enter tts: "Hello, I am a digital assistant calling from Freya Bank and this call is recorded. Am I speaking with {{title}} {{last_name}}?" |
| R05 | implemented | opening_retry, ask_dob, ask_phone and third_party task_message; load_account verification gate | - Do not mention the reason for the call, collections, a debt, a payment, a product or an amount. If asked what the call is about or how much they owe, say you  |
| R06 | implemented | opening.on_enter tts and opening_retry.task_message | Then ask exactly: "Am I speaking with {{title}} {{last_name}}?" |
| R07 | implemented | opening who1 and opening_retry who2 extraction; setup retry route; opening_retry -> fin_unclear | unclear = anything else: 'hello', 'go ahead', 'who is this?', 'what is this about?', a question, silence. |
| R08 | implemented | system_prompt; opening_retry task_message; policy aside handling | - If asked whether you are a robot or an AI: say you are Freya Bank's digital assistant, then continue. |
| R09 | implemented | third_party.task_message and callback_retry.task_message | Someone else answered. Never disclose why you called or ask security questions, even if they offer to pay. |
| R10 | implemented | callback_guard code; book_callback schedule_callback defaults and success routes; fin_callback | valid = d in allowed_days and CB_RULE['open'] <= tw <= CB_RULE['close'] and at > nowdt |
| R11 | partial | callback_guard invalid-slot counter and callback_retry.on_enter | if dw and tw: |
| R12 | implemented | opening/setup, opening_retry and third_party wrong_number routes; fin_wrong_number | 2. -> fin_wrong_number  if (tp_status equals "wrong_number")  ["wrong number"] |
| R13 | implemented | third_party transitions -> fin_deceased; fin_deceased code; end_deceased terminal | terminal: endedReason=not_reached_deceased, spoken_message="I am sorry for your loss. Thank you, goodbye." |
| R14 | implemented | third_party.task_message; account access restricted to verified identity route | Someone else answered. Never disclose why you called or ask security questions, even if they offer to pay. |
| R15 | implemented | ask_dob and ask_phone task_messages, verify_identity tool defaults and normalisation; ask_dob verified transition -> ask_phone | When they give it, call verify_identity with answer = the date as YYYY-MM-DD, whatever way they said it. A date said only as numbers is day, then month, then ye |
| R16 | implemented | verify_identity post_process_code; ask_dob and ask_phone wrong_answers_left transitions -> fin_failed | d['what_to_do_next'] = 'Three wrong answers. The check has ended. Say nothing about the account.' |
| R17 | implemented | verify_identity post_process_code hint branch; identity task_messages instruct following what_to_do_next | d['what_to_do_next'] = 'Day and month look swapped. This is NOT a wrong answer. Ask the customer to say the date of birth again with the month as a word, for ex |
| R18 | implemented | ask_dob and ask_phone transitions -> fin_failed; fin_failed code; end_failed terminal | terminal: endedReason=not_verified_failed, spoken_message="I am sorry, I could not verify your identity, so I cannot continue. Please use the Freya Bank mobile  |
| R19 | partial | ask_dob and ask_phone task_messages; count_decline_dob/phone and qb_dob/phone code | n = int(float(vars.get('question_count_dob') or 0)) + 1 |
| R20 | implemented | ask_phone all_verified transition -> load_account; load_account pre_action get_account | 1. -> load_account  if (verify_identity_response.data.all_verified equals "true" OR verify_identity_response.data.all_verified equals "True")  ["identity verifi |
| R21 | implemented | prepare code product wording and statement construction; negotiate.on_enter tts | + words + '. The past-due amount is ' + fmt(past_due) + ', and it is ' + str(days_late) + ' days late. Can you make this payment today?') |
| R22 | implemented | setup and policy core code: HOL, BWD, isbd | HOL = set(['2026-10-26', '2026-11-11', '2026-11-26', '2026-12-25', '2027-01-01']) |
| R23 | implemented | setup BANK_BANDS and addbd deadline calculation; prepare band selection and rungs; policy refuse ladder exhaustion | vars[band['name'] + '_deadline'] = addbd(today, band['deadline_rule']['n']).isoformat() |
| R24 | implemented | check_offer/accept_offer/change_offer shared check_one code; confirm read-back before record_promise | elif not isbd(nd): |
| R25 | implemented | check_offer code: check_one date validation | issues.append(('weekend_or_holiday', T('weekend_or_holiday', named=txt_short(nd), date=txt_short(nb)))) |
| R26 | implemented | check_offer code: check_one vague_asked branch | say(V, join([T('vague_deadline', deadline=txt_short(dl), words=pg(V, pid, 'words')), V['offer_question']])) |
| R27 | implemented | check_offer code: resolve_when weekday branches | delta = (wd - today.weekday()) if ' this ' in t else (wd - today.weekday()) % 7 |
| R28 | implemented | check_offer code: check_one after_deadline branch; negotiate refusal transition | "after_deadline": "The latest date I can record is [deadline].", |
| R29 | implemented | prepare code: initial full-amount proposal; negotiate.task_message | - Never propose, compute or change an amount or a date yourself, and never ask how much they can pay. The only offer you may make is the current offer in STATE, |
| R30 | implemented | prepare code: BANK_FLOORS and floor_rule lookup | floor = float(p[floor_rule['rule']['field']]) |
| R31 | implemented | too_much code: too_much and refuse; prepare code: late-band floor rung | "too_much_floor": "I understand. The lowest amount I can accept is [floor], your [floor_name]. The rest stays overdue.", |
| R32 | partial | check_offer code: ev_offer and check_one | if a is not None and a <= 0: |
| R33 | implemented | prepare code: statement; negotiate.on_enter tts | + words + '. The past-due amount is ' + fmt(past_due) + ', and it is ' + str(days_late) + ' days late. Can you make this payment today?') |
| R34 | implemented | negotiate extraction_schema stance; offer transition precedes refusal transition | offer = names their own date, amount or period: a date or an amount the customer proposes is NEVER a refusal. |
| R35 | implemented | negotiate stance extraction; count_refusal code: refuse; setup attempt1_date; prepare rungs | rungs = [('full_or_floor', a1)] |
| R36 | implemented | count_refusal code: refuse exhaustion and refused_offers; fin_refused code | if okey(a, d) not in rl: |
| R37 | partial | negotiate.topic transitions; pol_hardship code; hardship; check_offer shared ev_offer code | if a is not None and a <= 0: |
| R38 | partial | hardship transitions -> check_offer; shared ev_offer and check_one code | a = None |
| R39 | implemented | system_prompt; negotiate, confirm, hardship and wrapup task_message | - Never offer a discount, a waiver, a payment plan or any term that is not in STATE. If asked, say you cannot offer that. |
| R40 | implemented | shared readback code; confirm.on_enter and transitions -> rec_next -> record_promise | return T('readback_head') + T('readback_sep').join(items) + T('readback_tail') |
| R41 | partial | confirm transition -> change_offer; shared ev_change code | if a is not None and a <= 0: |
| R42 | implemented | shared rec_next and ev_rec_after code; wrapup transitions -> wrap_change | - A recorded promise cannot be changed or cancelled on this call; they can change it in the Freya Bank mobile app. |
| R43 | implemented | record_promise response_mapping; rec_after shared ev_rec_after code; fin_service_error and end_service_error | ok = g(V, 'rec_ok').lower() == 'true' |
| R44 | implemented | generator POLICY.texts.after_recorded; shared enter_wrapup code; wrapup.on_enter | "after_recorded": "You will receive a text message confirming this promise.",                                 # R38 |
| R45 | implemented | topic already_paid -> pol_paid -> fin_paid -> end_paid; close_call lifecycle | Payments can take one business day to appear, so I will not take a promise today. |
| R46 | implemented | topic extraction dispute versus already_paid; pol_dispute -> fin_dispute -> end_dispute | dispute = says the debt or the product is not theirs, they never had it, or it was closed or paid off in the past. |
| R47 | implemented | topic new_plan and wrap new_plan transitions -> xfer_restructuring; transfer_to_agent#3; fin_transferred_restructuring | body.queue (string): default "restructuring" |
| R48 | partial | id_human_dob/id_human_phone; shared init_negotiation, ev_human and ev_wrap_human code; xfer_general | c = int(num(g(V, 'wrap_human'), 0) or 0) + 1 |
| R49 | implemented | system_prompt scam instruction; payment policy asides | - If asked whether this is a scam: say they can verify this call by phoning Freya Bank's customer service number, then continue. |
| R50 | implemented | system_prompt; negotiate, confirm, hardship and wrapup task_message | - Never invent figures, dates or reasons. If you do not have the information, say so. |
| R51 | partial | opening_retry; count_decline_dob/phone; pol_notalk shared code; wrapup extraction_schema | extract wrap (type string): enum ["other", "done", "human", "new_plan", "change", "question"] (min_confidence 0.5) |
| R52 | implemented | close_call lifecycle config and body defaults; fin_* code nodes | config: {"maxRetries": 0, "alwaysRunsAt": ["end_of_call"]} |
| R53 | implemented | fin_* outcome/reason assignments; close_call body and pre_process_code | if b.get('outcome') in ('promise', 'paid') or not b.get('reason'): |
| R54 | implemented | wrapup transitions through xfer_general/restructuring to fin_transferred_human/restructuring | 3. -> xfer_restructuring  if (wrap equals "new_plan")  ["asks for a new plan"] |
| R55 | implemented | generator POLICY configuration; workflow tool inventory | multi=False, notes=False,                                   # one product; Brief A never uses add_note |
| R56 | implemented | end_* terminal spoken_message; close_call end_of_call lifecycle | terminal: endedReason=promise, spoken_message="Thank you for your time, {{title}} {{last_name}}. Goodbye." |
| R57 | implemented | verify_identity and verify_identity#2 definitions, normalization and post_process_code; ask_dob/phone task_message | d['what_to_do_next'] = 'The answer could not be read. It does not count as wrong. Ask again: What is your date of birth?' |
| R58 | implemented | create_promise body definition and pre_process_code; rec_next approved-value assignments | body.amount (number): default "{{rec_amount}}" |
| R59 | implemented | schedule_callback body and normalization; callback_guard date/time validation | valid = d in allowed_days and CB_RULE['open'] <= tw <= CB_RULE['close'] and at > nowdt |
| R60 | implemented | transfer_to_agent variants with baked queues general, support and restructuring | body.queue (string): default "restructuring" |

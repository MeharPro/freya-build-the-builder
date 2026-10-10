# freyalib — a brief-agnostic library for Freya phone-agent workflows

`builder/freyalib.py` (standard library, Python 3.10+) holds everything **platform-specific** about a Freya
workflow: tool JSON shapes, node shapes, transition forms, hooks, the lifecycle `close_call` tool, the code-node
templates and the final checks. Everything **bank-specific** — holidays, bands, floors, wording, outcome table,
identity fields, prompts — is a parameter the generator for one brief passes in. The shapes are those of the
organisers' proven generator (`out/gen_brief-a.py`, 10/10 practice cases). `out/gen_brief-a_lib.py` is that
generator ported onto the library; `out/compare_brief-a_lib.py` proves the two outputs equivalent.

## API

| Area | Function | What it gives |
|---|---|---|
| OpenAPI | `load_api(path)` | the tool API file as a dict |
| | `base_url(api)` | server URL; tool `name` is `POST <base_url>/<name>` |
| | `tool_spec(api, name)` | `{"fields": {f: {type, description, enum, required}}, "required": [...], "summary", "response_props": {...}}` from `paths["/<name>"]["post"]` |
| | `tool_names(api)` | every tool in the file |
| Tools | `api_tool(api, name, baked=None, description="", required=None, retries=0, pre=None, post=None, mapping=None, field_descriptions=None, omit=None, var_map=None)` | the `api_call` tool. url/method/headers baked; `body.properties` = every spec field as a leaf; `customer_id` baked from `{{customer_id}}`; `baked` fields get a literal default (hidden from the model, checked against the enum; `"{{var}}"` bakes from a variable an earlier node always sets); all other fields are model-filled with `default: "{{<field>}}"` and the spec's type/description/enum (`field_descriptions` overrides). **A model-filled field must not share its name with an existing variable.** `required` = spec required − customer_id − baked. `post` defaults to `STRIP_HEADER` |
| | `close_call_tool(api, outcome_desc, reason_desc, no_reason_outcomes=None)` | the workflow-level `end_of_call` lifecycle tool reading `{{outcome}}`/`{{reason}}`; enum from the spec; pre-hook drops an empty reason (and the reason of `no_reason_outcomes`) |
| Nodes | `conv(name, task, on_enter=None, tools=None, extraction=None, transitions=None, first_only=False, max_turns=60)` | conversation node |
| | `code_node(name, code, transitions)` | passthrough code node (`code_exec`, 10 s); `ValueError` naming the node when `transitions` is empty |
| | `api_node(name, tool, transitions, mapping=None, on_enter=None)` | passthrough `api_request` node with node-level `response_mapping`; `ValueError` when `transitions` is empty |
| | `end_node(name, ended_reason, farewell)` | `end_call` node: silent entry, farewell in the terminal |
| | `end_pair(key, outcome, reason, farewell, nodes)` | adds `fin_<key>` (code: sets `outcome`/`reason`) + `end_<key>` (terminal named `<outcome>_<reason>`) |
| | `conversation_first(opening, setup_code, route_var, routes, default_target, nodes, setup_name="setup")` | the initial-node pattern (see "Initial node"): `opening` → always → passthrough `setup` code node routing on `route_var`; returns the initial node name |
| Transitions | `always(t)`, `eq(var, val, t, desc)`, `neq`, `is_set`, `is_true(var, t, desc)` ("true" and "True"), `count_gt(var, n, t, desc)`, `intent(t, desc, intent)`, `intent_tool(t, desc, intent)` (tool-call transition `transition_to_<t>`), `ok_true(tool, t, desc)`, `transferred(t, desc)`, `tool_failed_twice(tool, t, desc)` | ready-made transitions |
| | `cond(var, op, operand)`, `and_group(*conds)`, `tr(target, desc, *conds)`, `not_true(var)` | build any OR-of-ANDs condition |
| | `ext(name, values, desc, conf=0.6)` | an enum extraction entry |
| Hooks | `STRIP_HEADER` | drop the response headers |
| | `what_next_post(branches, else_text, prelude=None)` | strips headers and sets `result['data']['what_to_do_next']` from ordered `(python_condition_on_d, text)` pairs; with no branches, no else and no prelude it is `STRIP_HEADER` |
| | `ok_post(ok_text, fail_text)`, `promise_post()`, `promise_pre()` | write-tool hooks: say "recorded" only on `ok` true, retry once; amount→float, date→`[:10]` |
| | `verify_post(question, hints, max_wrong_text, ...)` | identity-question hook: hint (not a wrong answer) → all verified → verified → unreadable → counter at 0 → wrong. The default texts are generic: pass the brief's own wording (`all_verified_text=...` etc.). `stop_left=("1", "0")` when the brief's wrong-answer limit is stricter than the service's (route the node on the same values) |
| | `verify_count_post(question, limit, hints, limit_text, route_var='id_route', counter='id_wrong', free_hints=None, ...)` | identity hook with the brief's OWN wrong-answer counter in `vars` (limit stricter than the service's; `free_hints={'day_month_swapped': 1}` = only the first such hint per call is free); writes `id_route` = `exhausted`/`open`: route on it |
| | `promise_state_pre(full_var)`, `promise_state_post(max_calls, recorded, retry, give_up)` | promise hooks that keep `promise_kind` (`full` when amount == `vars[full_var]`, else `partial`), `promise_done`, `promise_route` (`recorded`/`retry`/`fault` after `max_calls` failures) |
| | `promise_reason_code()`, `promise_or_code(outcome, reason)` | fin-node code: reason from `promise_kind`; an ending a recorded promise overrides ("the promise decides") |
| | `truthy(field)`, `falsy(field)` | condition expressions on `d` that accept booleans and strings |
| Code | `CAL_HELPERS(holidays, business_weekdays, weekday_rule='this_week')` | source defining `isbd, txt, txt_short, addbd, next_bd, prev_bd, lastbd_of_week, weekday_table, calendar_text, fmt` (`prev_bd` for "the last business day before" rules; `weekday_rule` = how "next <weekday>" reads) |
| | `SETUP_CODE(holidays, business_weekdays, callback_rule, extra="", fallbacks=None, weekday_rule='this_week')` | first code node: parses `now`, always sets `today_iso, today_text, now_time, weekday_table, setup_state` (+ `callback_text` from `{"open","close","same_day","days_ahead"}`); `extra` is brief-specific source run inside the try |
| | `products_from_vars()` | reads the mapped product list (list / JSON string / flattened keys) |
| | `guarded(body, state_var, fallbacks)` | try/except wrapper with `vars.setdefault` fallbacks |
| | `counter_code(counter, limit, route_var, reset)` | count-and-route snippet (e.g. second refusal closes) |
| Assembly | `assemble(initial_node, nodes, system_prompt, tools, test_variables)` | the workflow dict, after `check()` |
| | `check(wf)` | raises `ValueError` listing: nulls, unknown targets, passthrough without `always`, tools/pre_actions on the wrong node type, code or hook that does not compile or has `{{`/`}}`, end_call without terminal, a node from which no end_call is reachable; global nodes without a condition, with an unknown target (`__previous__` allowed) or passthrough without a final `always`. Returns warnings (unreachable nodes, model-filled field named like a known variable) |
| | `write_workflow(wf, path)` | JSON with indent 1 |

Rules the helpers encode: fixed values use `default`, never `const`; booleans from results are tested as both
spellings; routing flags written by code are strings; code never raises and reads everything from `vars`; every
passthrough node ends with `always`; the farewell comes from the terminal and `endedReason` is its function name;
`close_call` runs once per call as a lifecycle tool, from the `outcome`/`reason` the `fin_*` node wrote.

## Speech normalisation (T21, T8)

Customers say numbers in parts ("463..." then "51"), correct themselves and say dates, amounts and times in words;
the model often passes the words through. These helpers fix that in code, before the request:

| Function | What it gives |
|---|---|
| `normalise_pre(fields, date_order='dmy', now_var='now', relative_var=None, pm_hours=(1..7))` | `pre_process_code` that rewrites the listed `config['body']` fields. `fields` = `{field: kind}` or a list (kind guessed from the name). Kinds: `digits` ("forty-four seventy-one", "double four", "oh" → `4471`), `dob` / `date` (month names, ordinals, spoken years, `14/03/88` in `date_order`, swapped only when the other order is impossible; two-digit years by a century rule against `now`; a year-less `date` takes the next occurrence), `amount` ("four hundred and twenty point five" → 420.5, "twelve fifty" → 1250.0, "1,250.00" → 1250.0), `time` ("half past two" → `14:30`, "11am" → `11:00`), `answer` (dob when the body's `field` names a date/birth, else digits). The last value after "no / sorry / I mean / actually" wins. Idempotent, never raises, leaves the value as is on any doubt. Concatenate with another pre hook (`promise_pre()`) if needed |
| `relative_days_code(now_var, out_var, next_means_week_after=False)` | code-node snippet writing a phrase → ISO table ("tomorrow", "this/next friday"); pass `relative_var=out_var` to resolve relative days. Without it they are left alone (the extractor's own date rules apply) |
| `latest_value_note(n_digits)` | prompt sentence: wait for all N digits given in parts and join them; after a correction use the LAST value |
| `digit_extraction(name, n_digits, description)` | extraction entry with `validation_pattern '^[0-9]{N}$'`, `max_retries 2`, `min_confidence 0.6` |

`date_order` and the relative-day reading come from the brief, never from Brief A/B. Tests:
`python3 builder/tests/test_normalise.py` (table of utterances executed as the platform runs a pre hook).

## Initial node

**The chat route (`POST /api/v2/chat/message`, used by `builder/smoke.py` and `builder/sim.py`) skips a first
code node**, confirmed on the Brief A agent; simulations run it. A workflow whose `initial_node` is a code node
therefore behaves differently in our smoke tests than in the scored simulations. Start every workflow with a
conversation node and run the setup code right after the customer's first turn:

```python
nodes["opening"] = fl.conv("opening", "You have just introduced yourself ... Do not call any tool.",
                           on_enter={"type": "tts", "text": "Hello, this is ... Am I speaking with {{title}} {{last_name}}?"},
                           extraction=[fl.ext("who1", WHO_VALUES, WHO_DESC)], first_only=True)
initial = fl.conversation_first("opening", SETUP, "who1",
                                [("customer", "ask_dob", "the customer confirmed who they are"),
                                 ("deceased", "fin_deceased", "the customer has died"),
                                 ("wrong_number", "fin_wrong_number", "wrong number"),
                                 ("someone_else", "third_party", "someone else answered")],
                                "opening_retry", nodes)
wf = fl.assemble(initial, nodes, SYSTEM, [close_call], TEST_VARS)
```

`opening` gets a single `always` transition to `setup`; `setup` is a passthrough code node that computes the
date facts and routes on the extracted variable, everything unmatched going to the default target. The opening
line and prompt may use only call variables (`test_variables`: names, `now`), never a value `setup` computes.
`out/gen_brief-a_v2.py` is the Brief A reference generator in this shape; `out/compare_brief-a_v2.py` shows it
differs from `out/brief-a.lib.workflow.json` only in `initial_node` and the `opening`/`setup` transitions.

## Reference architecture (gen_brief-a.py, 46 nodes)

```
setup (code: dates, callback window, attempt/deadline dates)
  └─> opening (tts greeting; extract who1)
        ├─ customer     ─> ask_<q1> (verify_identity field=q1; transfer_to_agent)
        ├─ someone_else ─> third_party (schedule_callback) ─> fin_callback | fin_no_callback | fin_deceased | fin_wrong_number
        ├─ deceased / wrong_number ─> fin_deceased | fin_wrong_number
        └─ else ─> opening_retry (who2) ─> ask_<q1> | third_party | fin_declined | fin_unclear | ...
ask_<q1> ─ verified ─> ask_<q2> ─ all_verified ─> load_account (api_request get_account, maps data.products)
   │ refused ─> count_decline_<q> (code) ─> back to ask_<q> | fin_declined          └─> prepare (code: product facts,
   │ 3 wrong ─> fin_failed ; transferred ─> fin_transferred_human                        band, floor, deadline, calendar)
                                                                                           └─> negotiate (tts statement;
negotiate ─ ok true ─> fin_promise ; failed twice ─> fin_service_error                          create_promise, transfer_to_agent)
   ├─ topic=hardship ─> hardship (create_promise) ─> xfer_support | fin_hardship | fin_promise
   ├─ topic=already_paid ─> fin_paid ; topic=dispute ─> fin_dispute
   ├─ topic=new_plan ─> xfer_restructuring (api_request transfer_to_agent queue=restructuring) ─> fin_transferred_restructuring
   ├─ transferred ─> fin_transferred_human
   └─ transition_to_fin_refused (tool-call) ─> fin_refused
fin_<key> (code: outcome, reason) ─> end_<key> (end_call, farewell)      × 16 outcomes
workflow tools: close_call (end_of_call lifecycle, reads {{outcome}}/{{reason}})
```

What goes where when a new brief arrives: the outcome table → `end_pair` calls; holidays, windows and deadline
rules → `SETUP_CODE(..., extra=...)`; bands, floors and product wording → the prepare body (with
`products_from_vars()` and the `CAL_HELPERS` functions); identity questions → one `ask_<q>` node per question with
`api_tool(api, "verify_identity", baked={"field": q})` and `verify_post`; prompts and extraction descriptions →
the `conv` calls. Nothing in the library names a holiday, an amount, a band or an outcome.

## Proof of equivalence

`python3 out/gen_brief-a_lib.py && python3 out/compare_brief-a_lib.py` — 46 nodes both, 3 differing paths
(setup code, prepare code, the schedule_callback post hook), each executed on the same inputs with identical
results; no other path differs. `freya.validate_workflow('lib-port-check', wf)` dry-run accepted the port.

## Policy as code (`builder/policy.py`): the default payment architecture

`builder/policy.py` takes every decision the brief makes deterministic out of the prompt (docs/research/sota-techniques.md
T1 offer guard, T2 counters in code, T3 state first, T20, T22 code-built read-back, T26). The model only phrases what code
decided: every offer, correction and read-back is a finished sentence written by code and spoken by a tts `on_enter`
(`{{say_next}}`, `{{readback_line}}`, `{{wrap_line}}`), and every write runs in an `api_request` node with the approved
values baked in. Reference generators: `out/gen_brief-a_v3.py` (one product), `out/gen_brief-b_v3.py` (one to three
products, notes). Tests: `python3 builder/tests/test_policy.py` (each scenario execs the generated code-node source
with sample `vars`: weekends, a holiday, both deadlines, amounts around the floor and the full amount, hardship,
read-back changes, record retries, wrap-up, multi-product order and notes).

```
prepare (POLICY.prepare_code: register_product per product + init_negotiation(statement))
  └─> negotiate (tts {{say_next}}; STATE {{state_line}} first; extracts topic, stance, offer_kind/date/amount[, offer_for])
        ├─ topic hardship|human|no_talk|already_paid|dispute ─> pol_hardship|pol_human|pol_notalk|pol_paid|pol_dispute
        ├─ topic new_plan                                    ─> xfer_restructuring
        ├─ offer_kind exact|vague ─> check_offer      stance accept ─> accept_offer      (the offer guard)
        └─ stance too_much ─> too_much                stance refuse ─> count_refusal     (the stance counter)
  confirm (tts {{readback_line}}; confirm yes|no|change) ─ yes ─> rec_next ─> record_promise (api_request) ─> rec_after
                                                         ─ change ─> change_offer (guard, read back again) ; no ─> confirm_no
  record_note (api_request, only with notes) ─> note_after          wrapup (tts {{wrap_line}}; wrap done|human|new_plan|change|question)
  hardship (tts {{say_next}}; hs_answer support_yes|support_no|accept_offer; a named offer still goes to check_offer)
  every policy code node: route ─> negotiate | hardship | confirm | record | note | wrapup | xfer_* | fin (+ final_route ─> fin_<key>)
```

| Piece | What it gives |
|---|---|
| `Policy(holidays, texts, multi, notes, note_reasons, fin_keys, fail_max, max_checks, human_limit, notalk_limit, wrap_turns, closed_day_move, business_weekdays, ordinals, targets)` | one instance per generator; every value from the brief (texts = finished-sentence templates with `[amount] [when] [date] [deadline] [floor] [floor_name] [full] [words] [named] [past_due] [list]`; `DEFAULT_TEXTS` are generic and MUST be replaced by the brief's own sentences, verbatim ones above all) |
| `prepare_code(body, statement_expr, fallbacks)` | the prepare node: the guarded `body` reads the products and calls `register_product(vars, pid, words, full, floor, floor_name, deadline, rungs)` per product in `get_account` order, `rungs = [(amount_rule, date), ...]` the brief's persuasion ladder (`full`, `floor`, `full_or_floor` = the floor once the customer said the full amount is too much); then `init_negotiation(vars, statement)` |
| `offer_extraction(...)`, `offer_guard_transitions()` | (a) `offer_date` (date), `offer_amount` (float), `offer_kind` (exact\|vague\|none, min_confidence 0.6) and the routes to `check_offer` / `accept_offer`. The guard writes `offer_verdict` ∈ {ok, weekend_or_holiday, after_deadline, below_floor, above_full, vague, before_today}, `offer_text` (the finished sentence), the approved `ok_pid/ok_amount/ok_date`, clears the extraction, and routes ok → confirm (one product) or the next product (several), anything else back with the corrected offer; `max_checks` is the loop exit |
| `confirm_node(task, confirm_desc, date_desc, amount_desc, topic_entry, topic_trs)` | (b) the read-back: tts `{{readback_line}}` built in code from the agreed values; `confirm` ∈ {yes, no, change, other}; change → the guard → read back again (never a transfer); no → a flat refusal of that offer |
| `record_nodes(nodes, api)` + `promise_assert_pre()` | the only place `create_promise` (and `add_note`) exists: an `api_request` node entered from a confirmed read-back, body baked from `rec_pid/rec_amount/rec_date`; its pre hook asserts the body equals those approved values (a mismatch is replaced by them and logged in `promise_guard`, never capped to something else); `rec_after` retries up to `fail_max` tries, then `service_error` |
| `stance_extraction(desc)`, `stance_transitions()` | (c) `stance` ∈ {refuse, too_much, offer, accept, other} with the brief's own definitions (a proposed date or amount is never a refusal); `count_refusal` increments `attempts_used_<pid>`, writes `next_offer_text` from the ladder (skipping offers already refused), routes `exhausted` → the refused ending (or the next product / its note); `too_much` offers the floor once (`offered_floor_<pid>`), a second 'too much' is a refusal |
| `topic_transitions()` | hardship / human (ask once, then transfer) / no_talk (twice closes) / already_paid / dispute / new_plan, all counted and settled in code |
| `hardship_node(...)` | no persuasion by routing: a refusal there settles the product as hardship; a named date or amount still goes through the guard and the read-back; support_no without a named offer closes as hardship |
| `wrapup_node(task, wrap_desc)` | after a recorded promise: the recorded sentence + the brief's after-promise sentence + "anything else?"; done → the promise ending; human → ask once, then transfer (the promise stays, the transfer's close code); new_plan → restructuring transfer; change → the brief's change sentence, promise unchanged; question → the model answers; `max_turns` then finalize. `outcome`/`reason` are set to the promise ending before it, so a hang-up closes correctly |
| `state_first(task)` / `{{state_line}}` | (d) one variable rewritten by every policy node: per product what is settled, the offers already refused, attempts used, whether the floor was offered, the current offer word for word, what is recorded. It is FIRST in the negotiate, confirm, hardship and wrap-up prompts |
| `add_event_nodes(nodes)`, `route_transitions()` | the policy code nodes (`EVENT_NODES`), each = CAL_HELPERS + core + `main(vars, event)` in one try, sharing one transition list (endings first, the default ending once and last: the engine merges transitions with the same target) |

Rules the module keeps: every per-product variable is a string written only by code (`state_<pid>`, `attempts_used_<pid>`,
`too_much_<pid>`, `offered_floor_<pid>`, `refused_offers_<pid>`, `agreed_<pid>`, `checks_<pid>`, `fails_<pid>`,
`noted_<pid>`); every policy node clears the extraction variables it routes on (`CLEAR_ENUMS`, `CLEAR_VALUES`) so a stale
value never routes twice; no '{{' in code (the parameters travel as a JSON literal with escaped braces); a failing core
still leaves `route` and `state_line`. On the chat route an initial node's tts is replaced by a model turn, so the
opening prompt should quote the opening line too.

## How customers talk (persona conduct)

`assemble(..., conduct=True)` appends `PERSONA_CONDUCT` to the system prompt: keep to the business of the call, no sympathy for small talk, a message without an answer is neither a refusal nor a request, one short answer to a question back then the same question again, wait for a complete number, the last corrected value counts, 'how much can I pay' is not a plan request. `REFUSAL_NONE_CLAUSE` and `PLAN_REQUEST_CLAUSE` are appended to the matching enum descriptions by the generator. Brief-agnostic; the brief's own definitions of a refusal or a deflection come first in the description and win.

`question_back_node(stage, ask_node, close_node, limit=2)` + `QUESTION_ENUM_CLAUSE` + `reset_pre([...])`: a question asked back at an identity question is answered and the question repeated; the second question in a row with no answer in between is the deflection the brief closes on. The identity tool's pre hook zeroes the counter when an answer arrives.

`Policy(asides={value: {'when': ..., 'say': ...}})`: side questions (robot? scam?) extracted as `aside` on the negotiate, confirm, hardship and wrap-up nodes; the core prefixes the brief's answer to the line the route speaks, so a turn that goes through code into a tts line still answers the question (measured: v3 ignored 'Am I talking to a robot?' on an accepted offer).

**Dates named by the customer are resolved in code against the call's `now`.** The platform's `date`-type extraction resolves relative words with the REAL clock (Brief B PUB-12: 'tomorrow' arrived as a date before the call's today, and the agent repeated 'has already passed' eight times). The policy nodes therefore also extract `offer_when` (the customer's own words) and `resolve_when()` in the core turns today/tomorrow/this or next <weekday>/the 23rd/the sixth of November/in two weeks into a date from `today_iso`; vague periods become 'vague'; an extracted date before today with no words is treated as vague (ask once for the exact day). `Policy(weekday_rule='this_week'|'first_after')` is the brief's rule for 'next <weekday>'.

## Identity questions: two forms

**Default (prompt-driven), what every generator and both v3 agents use.** The identity question is one
conversation node holding `verify_identity` as a model-called tool (`api_tool(api, "verify_identity",
baked={"field": <field>}, post=verify_post(...))`); the node prompt says "when they give all N digits, call
verify_identity with the digits only; if they give part, ask for the rest", `PERSONA_CONDUCT` says "wait for a
complete number", and routes read `verify_identity_response.data.*`. Measured over the chat route with
`builder/smoke_scripts/talkative.json` (a cut-off line with no answer at the second question, then the answer) and
`asks_back.json` on brief-a-v3 and brief-b-v3 (10 Oct): the tool was called exactly once per question with the right
value, never on the cut-off line; on the organisers' simulator `pieces` scored 9/10 on the v2 reference, its miss not
identity. So the default stays.

**Opt-in gate (`gated_digits_identity`), for a brief or a run where half numbers reach the service.**

| Function | What it gives |
|---|---|
| `digits_from_spec(api, field_value)` | N read from the identity tool's `answer` description in the API file ("For phone_last4: four digits." → 4; "exactly eight digits" → 8); `None` when the file gives no count (pass the brief's N) |
| `gated_digits_identity(api, stage, field_value, n_digits, ask_task, answer_desc, on_verified, on_all_verified, on_exhausted, wrong_line, unreadable_line, extraction=None, transitions=None, tool_post="", extra_routes=None, stop_left=("0",))` | dict of nodes: `ask_<stage>` (conversation, NO tool, extraction `<stage>_digits` with `validation_pattern ^[0-9]{N}$`, first route `is_set(<stage>_digits) AND != sentinel` → `check_<stage>`), `ask_<stage>_wrong` / `ask_<stage>_unread` (the same node entered with the brief's fixed wrong / unreadable line as tts), `check_<stage>` (api_request: `verify_identity` with field and answer BAKED, `{{<stage>_digits}}`; node mapping to `<stage>_ok/_verified/_all/_left`), `route_<stage>` (code: writes the sentinel `'0'*N`, schema-valid for the pattern, so the same answer is not sent twice; routes `extra_routes` → all verified → verified → `stop_left` → ok false → wrong) |

What it buys: the model never fills `answer`, so '44', words the extractor cannot turn into N digits, an 11-digit
whole phone number or a cut-off line never reach the service as a counted wrong answer; a wrong answer re-enters the
question with the brief's fixed wording. What it costs: three conversation nodes per question instead of one, the
brief's other identity routes (refusal, question back, transfer) must be passed in `extraction`/`transitions` (they
are copied onto all three ask nodes after the gate), and a real answer equal to the sentinel ('0000') is never sent
(use the default form for such a brief). Dates keep the default form (the service answers an unreadable date with
`ok: false`, not counted). Tests: `python3 builder/tests/test_gated_identity.py` (route code exec'd as a code node,
transitions walked for verified / all verified / wrong / exhausted / unreadable / stricter-brief paths, an 8-digit
field from the transfer-test API, `check()` on an assembled workflow).

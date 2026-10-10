# multiproduct — per-product promises and notes for one-to-three-product briefs

`builder/multiproduct.py` (standard library, Python 3.10+) generalises what the organisers' example builder added
in `out/gen_brief-b.py` (3/3 on the Brief B practice cases) on top of `builder/freyalib.py`: the customer can be
late on several products, every product gets its own band, floor, deadline and attempt counter, promises are
recorded one tool call per product, and every product without a promise gets a note. The module produces Python
source for the hooks and the two code nodes; freyalib produces the JSON shapes. Everything a bank decides is a
parameter (bands, floors, wording, statement, tool and field names, note reasons, fin keys); the defaults of those
parameters are the organisers' Brief A/B conventions, listed under "Defaults" below, and `api=` makes every
function check its names against the tool API file. `out/gen_brief-b_lib.py` is gen_brief-b.py ported onto
freyalib + multiproduct, `out/compare_brief-b_lib.py` proves the two outputs equivalent, and
`python3 builder/multiproduct.py` runs the module's self-test (31 checks on the kit API and on the changed API of
`tests/synthetic/brief-e.openapi.json`).

## The per-product state machine

Every product is in exactly one of three states, kept in workflow variables (all strings, written by code):

```
open ──(create_promise ok)──> recorded          rec_pids   += pid
open ──(add_note ok)────────> noted             note_log   += "pid:reason"
```

| Variable | Written by | Meaning |
|---|---|---|
| `pids_csv` | prepare | every product id in `get_account` order, comma separated (`p1,p2`) |
| `n_products` | prepare | their number, as text |
| `dl_<pid>` | prepare | that product's deadline, `YYYY-MM-DD`; `promise_pre` caps a later date to it |
| `pd_<pid>` | prepare | that product's past-due amount, `str(float)`; `promise_pre` caps a larger amount to it |
| `products_text`, `statement_text`, `calendar_text` | prepare | the facts block, the opening statement (tts), the tagged calendar |
| `rec_pids` | promise_post | ids with a recorded promise |
| `note_log` | note_post | `<pid>:<reason>` per noted product (one note per product) |
| `open_pids` | prepare, every hook | ids with neither a promise nor a note; shown in prompts (`{{open_pids}}`) |
| `all_done` | prepare, every hook | `"yes"` once `open_pids` is empty, else `"no"`: the ALL_DONE transition routes on it |
| `pending_pid` | promise_pre | the product of the promise call in flight (the post hook reads it) |
| `pending_note` | note_pre | `<pid>:<reason>` of the note call in flight |
| `fail_<pid>` | promise_post | failed promise calls for that product; at `max_fails` the model is told to note `fail_reason` |
| `final_route` | finalize | the fin key chosen for the close |

The hooks share `state_fn_code()`: `_getv()` returns the `vars` dict (or None when the hook has none) and
`_status(V)` recomputes `open_pids` / `all_done` and returns the "Recorded promises: … Notes: … Still open: …"
sentence that every `what_to_do_next` ends with. Because the post hook refreshes `all_done` before routing runs,
the deterministic ALL_DONE transition fires in the same turn as the last tool result.

## API

Every function that takes `api` (the dict `freyalib.load_api` returns) checks its names against the tool API file
and raises `ValueError` at generation time when a name is not there; without `api` nothing is checked.

| Function | Gives |
|---|---|
| `note_reasons(api, note_tool="add_note", reason_field="reason")` | the note tool's reason enum from the API file (`[]` when the field has no enum) |
| `product_fields(api, account_tool="get_account", products_field=None)` | `{field: {type, description, enum}}` of one product in the account tool's response (`products_field` None = its first array property; `$ref` resolved) |
| `state_fn_code(promise_tool, note_tool, still_open_text=None)` | the shared `_getv` / `_status` source (braces in `still_open_text` are refused) |
| `promise_pre_code(cap_to_deadline=True, cap_to_amount=True, id_prefix="p", pid_field, amount_field, date_field, promise_tool, note_tool, api=None, snap_closed=None, holidays=(), business_weekdays)` | promise tool pre hook: id normalised (`'1'` -> `'p1'`), amount -> float, date -> `[:10]`, `pending_pid`, date capped to `dl_<pid>`, amount capped to `pd_<pid>`; `snap_closed="before"/"after"` then moves a weekend/closure date to the business day before/after it; `api` checks the three request field names |
| `promise_post_code(max_fails=2, fail_reason="service_error", promise_tool, note_tool, ok_field="ok", api=None, reason_field="reason")` | promise tool post hook: "recorded" only on ok true (-> `rec_pids`), else retry once, at `max_fails` note `fail_reason`; `+ _status`; `api` checks `fail_reason` against the note tool's reason enum and `ok_field` against the response |
| `note_pre_code(id_prefix, pid_field, reason_field, promise_tool, note_tool, api=None)` | note tool pre hook: id normalised, `pending_note`; `api` checks the two request field names |
| `note_post_code(promise_tool, note_tool, ok_field, api=None)` | note tool post hook: `note_log` on ok true, else retry; `+ _status` |
| `all_done_tr(target="finalize", desc)` | `eq("all_done", "yes", target)` |
| `done_intent_tr(target, desc, intent_desc)` | the tool-call fallback `transition_to_<target>` for the same event |
| `finalize_code(precedence, promise_key, paid_key, default_key, paid_reason=None, order="product", promise_tool, route_var, ok_field, api=None, note_tool, reason_field)` | the finalize code node: writes `final_route` (see below); `api` checks every precedence reason and `paid_reason` against the note tool's enum |
| `finalize_transitions(precedence, promise_key, paid_key, default_key, route_var, fin_prefix="fin_")` | `eq(final_route, key, fin_<key>)` for promise, paid and every precedence key, then `always(fin_<default_key>)` |
| `products_facts_code(bands, floor_rules, wording, statement, attempt1_var, id_prefix, unknown_type_words, line_template, attempt2_template, one_attempt_template, calendar_extra_days, pid_field, amount_field, days_late_field, type_field, api=None, account_tool, products_field, closed_day_move="after")` | the prepare body (`closed_day_move="before"`: the calendar offers the business day BEFORE a named weekend/closure day, and the product's own deadline when that day is past it) (after `freyalib.products_from_vars()`, inside `guarded()`) |
| `products_facts_fallbacks(statement_fallback, id_prefix)` | the `guarded()` fallbacks of the prepare node |
| `prepare_code(holidays, statement_fallback, business_weekdays, state_var, products_var, extra_code="", **facts)` | the complete prepare node source: `guarded(CAL_HELPERS + products_from_vars() + extra_code + products_facts_code(**facts))` |

Names: tool names, fin keys and variable names must be identifiers (they become function names, node names and
`vars` keys); note reasons may be any of letters, digits, `_`, `.`, `-` and spaces (they are spliced into string
literals and stored in `note_log` as `pid:reason,pid:reason`, so no quotes, commas or colons).

`finalize_code` rules, in order: a recorded promise -> `promise_key`; every product noted with `paid_reason` ->
`paid_key`; else the fin key of a non-paid note, picked by `order`: `"product"` = the first product in
`get_account` order whose note is not paid (Brief B's closing rule), `"precedence"` = the first `(reason, key)`
pair of `precedence` that some product carries; an unknown reason or no note gives `default_key`; and when the
hooks had no `vars` at all, `<promise_tool>_success_count > 0` with ok true gives `promise_key`. The fin keys
(`promise_key`, `paid_key`, `default_key`, the keys of `precedence`) are the generator's own `fin_<key>` node
names; the reasons are the API's note reasons.

### products_facts_code parameters (every one from the brief or the API file)

- `bands` = ordered `{"name", "max_days_late" (None = catch-all last), "attempts", "deadline_var" |
  "deadline_bdays"}`; a product takes the first band with `days_late <= max_days_late`.
- `floor_rules` = ordered `{"types" | None, "name", and either "field" or "expr"}`, ending with a catch-all
  (`types` None). `field` reads that product field; `expr` is a one-line Python expression over `p` (the product
  dict), `amount` (its past-due float), `days_late` (int), `ptype` (str) and the CAL_HELPERS functions, for a
  floor the brief states as a formula, e.g. `"min(2 * float(p.get('minimum_payment') or 0), amount)"` (twice a
  field, never above the overdue amount) or `"min(-(-amount * 0.25 // 10) * 10, amount)"` (a quarter rounded up
  to the next multiple of 10). No usable floor (missing field, an expression that raises or is not a number) ->
  the past-due amount is the floor.
- `wording` = ordered `{"types" | None, "template"}` with the product's fields and `{type_words}` (the type with
  `_` -> space, or `unknown_type_words`) as placeholders.
- `statement` = `{"one", "many_head", "many_item", "many_tail"}` templates over `{title} {last_name} {first_name}
  {n}` and the per-product facts `{pid} {words} {past_due} {days_late} {band} {floor} {floor_name} {deadline_text}
  {deadline_iso} {a1_text} {a1_iso} {attempts}`.
- `pid_field`, `amount_field`, `days_late_field`, `type_field`: the product's id, past-due amount, days-late and
  type fields AS THE ACCOUNT TOOL RETURNS THEM (`type_field` None = the products have no type: wording and floor
  rules are then catch-all only). Read them from the API file, not from Brief A/B: a changed API (e.g.
  `overdue_amount` instead of `past_due`) with the default names reads every amount as 0 and `promise_pre` would
  then cap every promise to 0. With `api` the four names, every floor rule's `field` (and the `p.get('..')` /
  `p['..']` fields inside an `expr`), every `types` entry (against the type field's enum) and every wording
  placeholder are checked against the product schema of `account_tool`'s response, so a wrong name fails at
  generation time.
- `line_template` / `attempt2_template` / `one_attempt_template`: the products_text wording (per-product facts
  line, then the ladder sentence for 2+ attempts or for 1).

`prepare_code` puts CAL_HELPERS inside the guarded try (nothing runs outside it, so `builder/lint.py` has no
"statements outside try/except" warning on the prepare node). `extra_code` is brief-specific source run after
the product list `prods` exists and before the facts: derive a field a floor rule or wording then reads
(`for p in prods: p['x'] = ...`), drop or reorder products, anything else the brief asks for. A generator that
needs more composes by hand: `fl.CAL_HELPERS(holidays) + fl.guarded(fl.products_from_vars() + <own snippets> +
mp.products_facts_code(...), "prepare_state", mp.products_facts_fallbacks(...))`.

### Defaults (the organisers' Brief A/B conventions: override them from the brief and the API file)

| Parameter | Default | Where it comes from in a brief |
|---|---|---|
| `promise_tool`, `note_tool`, `account_tool` | `create_promise`, `add_note`, `get_account` | the tool names (the same seven in every brief) |
| hook fields `pid_field`, `amount_field`, `date_field`, `reason_field`, `ok_field` | `product_id`, `amount`, `date`, `reason`, `ok` | the tools' request / response schemas |
| product fields `pid_field`, `amount_field`, `days_late_field`, `type_field` | `product_id`, `past_due`, `days_late`, `type` | the account tool's product schema |
| `fail_reason` | `service_error` | the note reason the brief gives a promise that keeps failing (must be in the API's enum: pass `api`) |
| `max_fails` | 2 | how many tries in total the brief allows before that note ("up to three tries in total" = 3) |
| `promise_key`, `paid_key`, `default_key` | `promise`, `paid`, `refused` | the generator's own fin node names for those endings |
| `paid_reason` | = `paid_key` | the note reason meaning "already paid" |
| `id_prefix` | `p` | how the account tool names products (`p1`); None when ids are not numbered |
| `unknown_type_words` | `account` | the word for a product whose type is unknown |
| `LINE_TEMPLATE`, `ATTEMPT2_TEMPLATE`, `ONE_ATTEMPT_TEMPLATE` | the Brief A/B ladder (attempt 1 = full amount or floor on the attempt-1 date, attempt 2 = floor on the deadline) | the brief's persuasion ladder |
| `still_open_text` | "For each open product: … call create_promise … otherwise call add_note …" | built from the tool names |

## How a generator wires it (gen_brief-b_lib.py, 48 nodes)

```
setup (SETUP_CODE: dates, callback window, attempt-1 date, per-band deadlines)
  └─> opening / opening_retry / third_party / ask_<q1> / ask_<q2> / count_decline_<q>   (as in FREYALIB.md)
        └─> load_account (get_account -> products) ─> prepare (prepare_code: per-product facts + state init)
              └─> negotiate (tts {{statement_text}}; tools: promise_tool + note_tool + transfer_to_agent)
                    ├─ ALL_DONE (all_done == yes)            ─> finalize
                    ├─ transferred                           ─> fin_transferred_human
                    ├─ topic = hardship                      ─> hardship (promise_tool; ALL_DONE -> finalize)
                    │       ├─ support accepted              ─> xfer_support ─> fin_transferred_support
                    │       └─ support declined              ─> hardship_notes (note_tool, reason hardship for {{open_pids}}; ALL_DONE -> finalize)
                    ├─ topic = new_plan                      ─> xfer_restructuring ─> fin_transferred_restructuring
                    └─ transition_to_finalize (tool call)    ─> finalize
finalize (finalize_code) ─ final_route ─> fin_promise | fin_paid | fin_<precedence keys> | always fin_<default>
fin_<key> ─> end_<key>  (freyalib.end_pair, one per row of the brief's outcome table)
```

Tools: `promise_tool = api_tool(api, "create_promise", pre=promise_pre_code(api=API), post=promise_post_code(...,
api=API))` with `product_id` model-filled ("exactly as in PRODUCTS"); `note_tool = api_tool(api, "add_note",
omit=[optional free-text fields], pre=note_pre_code(api=API), post=note_post_code(api=API))` with the reason enum
and its description read from the API file; the prompt lists the reasons from the same enum
(`mp.note_reasons(API)`). The prepare node reads the per-band deadline variables the setup node wrote
(`SETUP_CODE(..., extra=...)`), so date rules stay in one place; `prepare_code(..., api=API, pid_field=...,
amount_field=..., days_late_field=..., type_field=...)` names the product fields from the API file.

Proof: `python3 out/gen_brief-b_lib.py && python3 out/compare_brief-b_lib.py` — 48 nodes both; the differing
paths are the setup and prepare code (library helpers; the prepare port has the helpers inside the guard and the
floor rules as an if/elif chain), the finalize code (reason -> fin key mapping), the promise pre hook (consistent
id normalisation, no unused import) and the schedule_callback post hook (string "false" handled), each executed
on the same inputs with the same effect; `freya.validate_workflow` dry run accepted the port. `builder/lint.py`
on the port: 0 errors; the warnings it shares with the reference plus one on the setup node (freyalib's
SETUP_CODE keeps CAL_HELPERS outside its try).

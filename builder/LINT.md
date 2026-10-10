# `builder/lint.py`: inventory and budget checks

The base lint (no flags beyond `--api` / `--call-vars`) checks the platform rules of `docs/`. Two optional flags add
checks from `docs/research/sota-techniques.md`:

```
python3 builder/lint.py out/<slot>.workflow.json --api tools/openapi.json \
    --call-vars customer_id,first_name,last_name,title,now --rules out/<slot>.rules.json
python3 builder/lint.py out/<slot>.workflow.json --api tools/openapi.json --budget      # T29/T30 only
```

```python
from lint import lint
findings = lint(wf, api, call_vars, rules=json.load(open("out/<slot>.rules.json")), budget=False)
```

`--rules` takes the inventory written by `builder/rules.py` (a JSON list of `{id, category, text, verbatim[], values{}}`,
see `AUDIT.md`; rules with `in_force: false` are ignored). It turns on every check below; `--budget` alone turns on
only T29/T30. Without either flag the output is unchanged. Exit code 1 on any ERROR, as before.

| check | level | what |
|---|---|---|
| T24 verbatim | ERROR / WARN | Every `verbatim` string must appear (case-insensitive, whitespace-normalised; `{field}` in the inventory matches a `{{var}}` placeholder or any short text) in a tts `on_enter`, a terminal `spoken_message` or a string built by code (code nodes, `pre_process_code` / `post_process_code` hooks, in source order, local names resolved one level). Found only in a prompt (`task_message`, `system_prompt`, llm on_enter): WARN, the model may paraphrase it. Found nowhere: ERROR. |
| T25 forbidden words | ERROR / WARN | Words from `values.forbidden_words_before_verification` (also `forbidden_before_verification`, `forbidden_words`) of any rule; fallback: quoted words of `opening`/`disclosure` rules that say "do not say / never mention". An entry "the product" expands to the inventory's `values.product_names`. Scanned in every node reachable from `initial_node` without taking a route that tests a verified variable (a variable ending in `all_verified` when the workflow has one, else `verified` / `identity_verified` / `is_verified`, compared with true or `is_set`; global nodes count as reachable). Spoken text (with the code-built text of the `{{var}}`s it uses) → ERROR. Prompts and `system_prompt` → WARN, except inside a sentence like "never say / do not mention / never offer ... X". No verified route at all → one WARN and T25/T6 are skipped. |
| T6 write tools | ERROR / WARN | Any `api_call` tool or pre_action named after an API path other than `get_account`, `verify_identity` and `close_call` (closes every call) in that pre-verification region. Allowed when a `third_party` or `identity` rule names the tool, or a rule naming it says "before / during verification", "before and after verification", "at any time". Named only by rules of the verified part of the call (amounts, persuasion, confirmation, dates, recording, multi_product, disclosure), or by a rule that says "only after identity is verified" → ERROR; named by a `special` / `hardship` / `other` / `closing` rule that does not say when (a human request, a restructuring request) → WARN "check the brief"; never named → WARN. Needs `--api`. |
| T26 success claims | WARN | "recorded", "booked", "confirmed", "noted" in spoken text of a node reachable before any write tool's `<tool>_response.data.ok equals true` route. Skipped when the sentence negates it before the word ("could not record", "have not recorded") or says the call is recorded. |
| T29 prompt size | WARN | Conversation `task_message` over 2500 characters (template text, before placeholders are filled), or more than 15 imperative lines (bullets or lines starting with say/ask/call/never/if/...). |
| T30 latency | WARN | More than 4 extraction variables in a node, an enum with more than 7 values, or more than 8 `matches_intent` transitions. |

Results on the two real builds (10 Oct), new findings only:

- `out/brief-a-cloud.workflow.json` + `out/brief-a-cloud.rules.json`: 0 ERROR; WARN R41 "Do you confirm?" only in the
  `negotiate` prompt (genuine: the read-back is model-generated, T22 wants it code-built); WARN `negotiate` 3445 chars
  (genuine, named in T29).
- `out/brief-a_v2.workflow.json` + `out/brief-a.rules.json`: the same two WARNs, plus ERROR `transfer_to_agent` in
  `ask_dob` / `ask_phone`: that older inventory does not say a human request applies before verification (the cloud
  inventory's R49 does). The fix belongs in the inventory (`rules.py` should state when a request rule applies), not in
  the workflow.

Tests: `python3 builder/tests/test_lint.py` (`test_rules_*`, `test_budget_checks`, `test_cli_rules_flag`).

- **Empty variable in spoken text** (WARN): a `spoken_message` or tts line uses `{{x}}` and some code or hook sets `vars['x']` to `''` (directly, in an `a if c else ''`, or an `or ''`). On the platform an empty variable is spoken as the literal placeholder (Brief C, round 3). Write a sentence into it on every path, or route to a separate terminal.

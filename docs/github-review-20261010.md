# Karan’s GitHub review — 10 October 2026

Inspected through the signed-in Karanvir Chrome profile:
https://github.com/Karanvir1729/freya-build-the-builder

Main at inspection: `7d1597c67d0caf536ff83ee8685697d53a2ec094` (200 commits, 24 branches; private). The Work Chrome profile could not access the repository. Downloaded the visible main ZIP and compared every file with the user-supplied `(3).zip`: 1,070 files, 51 changed, 637 added, none removed. The exact path inventory and archive hash are in `github-comparison-20261010.json`; the full downloaded source is preserved under ignored `build-history/github-7d1597c/`.

The README explicitly supports `ANTHROPIC_API_KEY` as an alternative to Claude login. A clean reviewer can supply their own key. The main branch still uses Claude for building; our OpenAI implementation is a local addition.

Notable newer work:

- The latest builder commit changes its default to `claude-fable-5-1` with an Opus fallback, reports the actual serving model, and adds publication/version checks.
- `buildguard.py` can restore builder files that the generating agent changed. Our runner instead fails when source or instructions change during generation; restoring files afterwards does not establish that generation used only the frozen builder.
- The upstream version selector can restore a previously tested workflow after a regression. Our runner publishes this run’s validated candidate and audits the exact platform export, keeping the generator/export provenance intact.
- New policy work handles split dates and amounts, partially spoken answers, per-product claims, once-only floor offers, explicit dates alongside “today”, and brief-specific note/closing reasons. These changes are substantial and coupled to newer generators/tests.
- New simulation work records versions and model calls, plus extended-case execution and several rehearsal reports. Upstream commit messages report 13/13 public cases across three repetitions and further style tests. Those are upstream reports, not results reproduced by this checkout.

The downloaded source has been retained for review. It has not been overlaid wholesale onto the locally validated builder. In particular, the permissive source-restoration path and old-version selection are not replacements for this checkout’s strict submission gates. Local practice evidence remains the separately recorded 39/39 reference calls; the OpenAI build is measured separately.

The `tamsin` rehearsal trace was also inspected directly: it ended after 1,271 seconds, with an audit reporting 70 implemented, 26 partial, 1 missing, 3 contradicted and 6 superseded rules, plus one unverified evidence quote. Examples included recording each product before moving to the next, no-talk closing precedence, and split-payment handling. Export completion in that trace is not equivalent to an all-rules-passing build. Our strict audit gate would reject it.

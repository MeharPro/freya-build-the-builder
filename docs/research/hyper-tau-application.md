# Paper review — 11 October 2026

Source: [τ^τ-Bench: An Environment for End-To-End, Realistic Agent Construction](https://arxiv.org/pdf/2609.04611), arXiv v1. Checked the task definition, results, trajectory analysis, worked example and API-defect appendix directly.

The benchmark evaluates constructed agents against withheld conversations. Across 53 tasks, its strongest measured configuration scored 23.9%; the expert reference scored 82.2% (Table 2). The 59.7% / 85.8% figures in the imported research notes describe one worked example, not aggregate performance. Ten passing self-authored probes in that example missed substantial held-out policy coverage.

Section 6 identifies incomplete evidence reading, underuse of available build time, unmeasured inherited code and tests weakened to match faulty behavior. These findings support our choices: preserve the supplied code, measure the reference baseline, extract requirements with source evidence, freeze expectations, inspect real API transcripts and repair unresolved audits before claiming success.

Application to Freya is an engineering inference, not a proven winning recipe. Freya’s own rules govern the entry: its 30-minute build limit and fixed phone model supersede the paper’s different constraints. Neither the paper nor a passing local audit establishes a hidden-case score.

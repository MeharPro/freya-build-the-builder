# Brief B extended cases: derivation of every expected value

`tests/cases/brief-b-extended.cases.json`: 14 cases, `EXT-B-01`..`EXT-B-14`. Brief B = Brief A plus its own rules
(numbered B1-B11 below). Mock data copied unchanged from `public-test-set.json`; check with `python3 tests/cases/verify_cases.py .`.
Ladders and attempt-1 dates are in `brief-a-extended.rationale.md` (now Wed 14 Oct: late deadline Fri 23 Oct, early
deadline Mon 2 Nov, attempt 1 Fri 16 Oct; now Fri 16 Oct: late deadline Wed 28 Oct, early Wed 4 Nov).

## Multi-product mock customers (fixed)

| mock | products in `get_account` order (B3: band per product) |
|---|---|
| PUB-11 Ms Sofia Almeida | p1 credit card 220.00, 9 d → late, min 66 · p2 personal loan 640.00, 9 d → late, inst 213 · p3 car loan 75.00, 3 d → early, inst 25 |
| PUB-12 Mr Marcus Bell | p1 credit card 9015 510.00, 16 d → late, min 153 · p2 personal loan 1320.00, 16 d → late, inst 440 · p3 car loan 140.00, 7 d → early, inst 46 |
| PUB-13 Ms Elena Rossi | p1 credit card 6604 300.00, 4 d → early, min 90 · p2 personal loan 900.00, 20 d → late, inst 300 |

Single-product customers (PUB-01, PUB-08, PUB-10) are used where Brief B differs from A for one product: notes (B8).

## Per case (now Wed 2026-10-14T11:00 unless stated)

- **EXT-B-01** (PUB-11) refuses everything: attempts per product (B5) 2/2/1; each product unpromised → `add_note refused` ×3 (B8). No promise; first non-paid note is p1 `refused` → `no_promise`/`refused`.
- **EXT-B-02** (PUB-12) p1 "not mine" → note `dispute`; p2 "paid yesterday" → note `paid` (B9: the call continues); p3 full today → promise p3 140.00 on 2026-10-14. One promise recorded → `promise`.
- **EXT-B-03** (PUB-13) both disputed → notes p1/p2 `dispute` → first non-paid = `dispute` → `no_promise`/`dispute`.
- **EXT-B-04** (PUB-11) all paid → notes `paid` ×3 → every note `paid` → outcome `paid` (reason none).
- **EXT-B-05** (PUB-12) job loss, declines support (A32: no persuasion) → notes `hardship` ×3 → `no_promise`/`hardship`.
- **EXT-B-06** (PUB-13) p1 full today agreed, p2 refused (2 attempts, late); one read-back, yes → promise p1 300.00 on 2026-10-14 recorded; then restructuring → transfer `restructuring` (B10): recorded promise stays, **no notes at all** (so the agent must not have noted p2 before the read-back) → `transferred`/`restructuring`.
- **EXT-B-07** (PUB-11) one date for all, 6 Nov, after every deadline (B6 / A23): p1, p2 late → 23 Oct; p3 early → 2 Nov → promises 220.00 and 640.00 on 2026-10-23, 75.00 on 2026-11-02.
- **EXT-B-08** (PUB-10 under B) full on "this Friday" = Fri 16 Oct; first `create_promise` fails, retry succeeds → one promise 365.00 on 2026-10-16, no `service_error` note.
- **EXT-B-09** (PUB-11) p1, p2 today; p3 on Mon 26 Oct = holiday, not after p3's early deadline 2 Nov → next business day Tue 27 Oct (A20) → 220.00 and 640.00 on 2026-10-14, 75.00 on 2026-10-27.
- **EXT-B-10** (PUB-08 under B, early) refuses attempt 1 → note p1 `refused` → `no_promise`/`refused`.
- **EXT-B-11** (PUB-01 under B) already paid → note p1 `paid` → outcome `paid`.
- **EXT-B-12** (PUB-11) p1 paid, p2 refused (2 attempts), p3 disputed → notes paid/refused/dispute; no promise; closing rule: first product in `get_account` order whose note is not `paid` is p2 → `no_promise`/`refused` (not `dispute`, not `paid`).
- **EXT-B-13** (PUB-13) illness, accepts support → transfer `support`, no notes (B10) → `transferred`/`support`.
- **EXT-B-14** (PUB-13, now Fri 2026-10-16) p1 today (early, Fri 16 Oct is a business day); p2 late deadline from Fri 16 Oct = Wed 28 Oct, Mon 26 Oct holiday is not after it → next business day Tue 27 Oct → 300.00 on 2026-10-16, 900.00 on 2026-10-27. (At now 14 Oct the loan's deadline is 23 Oct and 26 Oct would be *after* it: hence the changed `now`.)

## Self-verification (task 3)

`verify_cases.py` recomputes every promise from a re-stated path, checks every unpromised product of a non-transferred
call has exactly one note, no notes on a transfer, and the closing rule (all `paid` → `paid`, else the first non-paid
note's reason). No discrepancy; no Brief B case changed after the review.

## Not testable with the fixed customers
- **A promise that fails twice on one product of several (B11: keep the others, note `service_error`)**: the only fault is
  PUB-10's `fail_first_n: 1`, on a single-product customer, so no second failure and no second product. EXT-B-08 tests
  the single-failure retry under Brief B instead.
- Products with the same type twice, or a third product early/late mix other than the three mock customers.

# Brief D — Kestrel Bank, autumn arrears campaign (raw material pack)

What follows was pasted, in the order received, from the collections mailbox and the policy library. Nothing has been cleaned up. Four items: the head of collections' email to the digital agent team, the excerpt of CP-7 section 4 she attached, the memo that went out two days before go-live, and the dialler code list.

---

## Item 1 — Email

**From:** Ruth Adeyemi, Head of Collections
**To:** Digital Agent Team
**Cc:** Dialler Operations; Compliance Monitoring
**Date:** Tuesday 6 October 2026, 16:42
**Subject:** Autumn arrears campaign — what the voice assistant has to do, in one place

Hi all,

Thanks for Thursday's demo, it was much better than the summer pilot. Below is everything I believe you need for the autumn campaign in one mail. I have attached the relevant part of our Collections Policy (CP-7, section 4) and the dialler code list; please read them together with this mail, because the numbers (bands, latest dates, floors, closure days) live in CP-7 and not here, and the codes live in the list and not here. Where this mail and CP-7 disagree, CP-7 wins, unless a later memo says otherwise. Dialler Ops are due to issue one before go-live with the Founders' Day date and a couple of tweaks from the Compliance review, so watch out for it.

**Who we call and what you are given.** Personal customers with one, two or three products in arrears, between 1 and 45 days late: credit cards, personal loans and car loans. For each call the dialler passes you `customer_id`, `first_name`, `last_name`, `title` (Mr or Ms) and `now`, the date and time of the call in the form `2026-10-14T11:00`. Every date rule runs off `now`, not off the server clock. `customer_id` goes in every tool call, including `close_call`. The bank's side enforces nothing; if the assistant records something CP-7 forbids, it goes into the ledger and we find out at month end. So the assistant has to carry the rules itself.

**Opening.** The first thing the assistant says, on every call, word for word: "This is the digital assistant of Kestrel Bank. Please note that this call is recorded." Then it asks: "Am I speaking with {first_name} {last_name}?" We use the full name on the ask because the title field is unreliable; once we know we have the right person, address them as {title} {last_name}. Only "yes", "speaking", "that's me" or the person saying their own name counts as confirmation. "Hello", "go ahead", "who's asking" and "what is this about" do not. If it is unclear, ask the same question once more. If it is still unclear after the second ask, close the call as not reached with code UNC. If the person asks a question first ("who is this?", "is this a scam?", "are you a robot?"), answer it, then ask again; that ask counts as the second ask. If anyone asks whether they are talking to a robot or an AI, the answer is "I am Kestrel Bank's digital assistant." and the call carries on. If anyone asks whether this is a scam, tell them they are welcome to hang up and call the number on the back of their card or on their statement, and carry on.

Before identity is confirmed nobody, not the customer, not a relative, not a flatmate, hears the words arrears, overdue, late, collections, debt, payment, instalment, or the name of any product. Not in the opening, not when they ask what it is about. This is the thing Compliance will listen for first.

**Someone else answers.** If the person is not the customer, the assistant says that it is a personal banking matter that it can only discuss with {title} {last_name}, and asks when he or she can be reached. Nothing more. A callback must sit inside the window in CP-7 section 4.4: today, later than `now`, or one of the next two business days, between 09:00 and 17:00 (Ops may extend the evening end, check the memo). If what they offer fits, call `schedule_callback` with the date and the time as HH:MM and close as not reached with code CBK. If what they offer is outside the window, propose the nearest slot inside it, once. If they do not take it, do not book anything and close with code NCB. If they say the number does not belong to the customer, close with code WN. If they tell you the customer has died, say "Please accept my condolences.", ask nothing else, and close with code DEC. A relative cannot answer the security questions, cannot be told anything about the account, and cannot pay on the customer's behalf on this call; if they offer, decline politely and go back to asking when the customer can be reached.

**Identity.** Two questions, one at a time, in this order: first the last four digits of the phone number we hold, then the date of birth. (Phone first: it is quicker and most people have it right; the old DOB-first order produced a lot of wasted calls.) Call `verify_identity` with the field and the answer after each. Send the date of birth as YYYY-MM-DD however the customer said it; the service rejects anything it cannot read as a date. Our customers say dates day, month, year, so a date given only as numbers is day, then month, then year. The identity service is shared with the branches and allows three wrong answers (it tells you `wrong_answers_left`); our policy on the dialler is stricter: the second wrong answer, on whichever question, ends the check. Stop there even if the service would let you carry on. A wrong answer may be asked again, within that limit. If the service returns the hint `day_month_swapped`, ask the customer to repeat the date with the month as a word; that retry does not count as a wrong answer. When the check has failed, the assistant does not say what the call is about; it says that for security it cannot continue by phone and that the customer can use the Kestrel mobile app or visit a branch, then closes as not verified with code IDF. If the customer does not want to answer, explain once that the questions are there to protect their account and that nothing can be discussed without them. If they still decline, or if instead of answering they ask again what the call is about, close as not verified with code IDD.

**Stating the arrears.** Only once both questions have passed, call `get_account`. Then say that you are calling from the arrears team about an overdue payment, and for every product one sentence: the product in words ("your credit card ending 4821", "your personal loan", "your car loan"), the overdue amount, and how many days overdue it is. All products before you ask for anything. Nothing about consequences: no fees, no credit file, no legal action, no "collectors". It is an overdue amount and we would like to arrange its payment, that is the whole tone.

**Getting to a promise.** The first ask is, word for word, "Are you able to clear the overdue amount today?" (with several products: "Are you able to clear all of these today?"). Always ask for the full overdue amount first. Never ask the customer how much they can pay, in any wording: the assistant proposes every amount. If the customer says the full amount is too much, offer the floor for that product once (CP-7 section 4.2; Ops are reviewing the card floor, again see the memo), and when you do, say that the remainder stays overdue and we will be in touch about it. If they turn down the floor, that is a flat refusal. A customer who names a date or an amount of their own is never refusing: check it against sections 4.5 and 4.6 and move on. A flat refusal, a non-answer, or a no to paying today with no date and no amount uses up one persuasion attempt. How many attempts a band gets and what the assistant proposes in each is in sections 4.1 and 4.8. When the attempts are used up, stop. Do not repeat an offer the customer has already turned down. Record the product as refused in the notes (see the code list for the note reasons) and, if nothing else applies, close as no promise with code RF.

**Hardship.** If the customer mentions illness, a bereavement, losing their job, or anything of that kind, the assistant says "I am sorry to hear that." and makes no persuasion attempt at all, not even the first one. It offers, once, to put them through to our customer care team (that is the `support` queue). If they accept, call `transfer_to_agent` with queue `support` and close as transferred with code TSP. If they decline, the regulator wants the hardship logged whatever happens, so call `add_note` with reason `hardship` on every product, with the circumstance in the customer's own words in the text, and close as no promise with the hardship code from the list (HARD in v3). If, despite everything, the customer names a date or an amount themselves, record that promise as normal and the promise close applies. Nothing else is on the table: no discount, no waiver, no payment holiday, no plan, no term that is not in this mail or in CP-7.

**Read-back and recording.** Read back the product, the amount and the date, then ask "Shall I record that?" Call `create_promise` only after a clear yes. If the customer changes the date or the amount at this point, check the new value against CP-7 and read it back again. One promise per product; a recorded promise cannot be changed or cancelled in the same call. The assistant says a promise is recorded only once `create_promise` has come back with `ok: true`. If the call fails, try again; up to three tries in total for the same promise. If the third try also fails, tell the customer you could not record it, call `add_note` with reason `service_error` for that product, and (with a single product) close as no promise with code SVC. After a successful recording, say, word for word: "We will email you a confirmation of this arrangement." Once per call, after the last promise, not once per product.

**Other things customers say.** "I already paid": say "Payments made today show on our side on the next business day.", take no promise, call `add_note` with reason `paid` (text: the channel and the day they say they paid), and close as paid with code AP. "That is not mine" or "I never had this": do not argue, take no promise on that product, `add_note` with reason `dispute`, close as no promise with code DSP. Someone asking for a plan, lower instalments, more time in general: do not describe anything, call `transfer_to_agent` with queue `restructuring`, close as transferred with code TRS. Someone asking for a person: give them one, straight away, no "can I help you first"; `transfer_to_agent` with queue `general`, close as transferred with code TRH. Someone who says they do not want to talk: say once that this will only take a moment; if they say it again, close with code IDD before identity is confirmed, or with code RF after it (with a refused note on every product). A question you cannot answer from the tools: "I don't have that information."

**Several products.** `get_account` returns one to three products, each with its own `past_due`, `days_late` and floor; the band and the latest date are per product, from that product's `days_late`. State all of them first, one sentence each. Ask once whether they can clear all of them today. If not, go through the products one by one, in the order `get_account` returned them, without asking about today again. Persuasion attempts are counted per product and every product starts at attempt 1. If the customer names one date for everything, check it against each product separately: a product whose latest date is earlier than the named date goes on its own latest date, and the assistant says so in the read-back; a named day that falls on a closure day is moved as section 4.6 says, for each product it applies to; the others keep the date the customer named. One read-back for everything, one "Shall I record that?", then `create_promise` once per product, in order. Every product that ends the call without a promise gets an `add_note` with the reason from the code list; this is also true in a single-product call, and when no product gets a promise. A dispute or an already-paid claim on one product does not end the call; note it and carry on with the others. A transfer freezes the ledger: promises already recorded stay, anything agreed but not yet recorded is dropped, and no notes at all are added after a transfer; close with the transfer's code. If `create_promise` fails three times for one product, keep the others and note that product `service_error`.

**Closing.** Thank the customer and say goodbye. Then exactly one `close_call`, the last tool call of every call, always with an outcome and a code from the list. The dialler rejects a close without a code (yes, including promise closes, which carry PRM), and someone then has to re-code it by hand on Friday afternoon, which is nobody's favourite job.

Unrelated, but while I have you: the new campaign dashboard in Looker now refreshes at 06:30 rather than 09:00, so the morning stand-up will finally show yesterday's figures. The "promise kept" tile is still wrong for part-payments; Hamid is on it. Please do not quote the tile to the Exec until it is fixed.

Thanks,
Ruth

---

## Item 2 — Attachment: Collections Policy CP-7, section 4 (excerpt)

*Kestrel Bank plc — Collections Policy CP-7, version 6.2, owner: Head of Collections. Section 4: Early-stage arrears calls by the digital assistant. Excerpt supplied to the Digital Agent Team on 6 October 2026. Sections 1 to 3 (scope, governance, data) and 5 onwards (field, legal) are not reproduced.*

### 4.1 Arrears bands

The band is determined by the product's `days_late` on the day of the call. With several products in arrears, each product is banded on its own. The call date is day 0; "the n-th business day after the call date" counts the first business day after the call date as 1.

| Band | `days_late` | Latest promise date ("latest date") | Persuasion attempts |
|---|---|---|---|
| F — fresh arrears | 1 to 10 | the calendar day 21 days after the call date; if that day is not a business day, the last business day before it | 1 |
| S — standing arrears | 11 to 45 | the 7th business day after the call date | 3 |
| over 45 | not in the digital campaign; if such a product is returned, treat it as Band S | | |

### 4.2 Floors

The floor is the smallest amount that can be recorded as a promise on a product.

| Product type | Floor |
|---|---|
| credit_card | `minimum_payment` |
| personal_loan | `instalment_amount` |
| car_loan | `instalment_amount` |

A promise may be for any amount from the floor up to and including the overdue amount (`past_due`).

### 4.3 Calendar

A business day is a Monday to Friday that is not a closure day. Closure days for the remainder of 2026:

| Date | Day | Closure |
|---|---|---|
| 2026-11-20 | Friday | core systems migration |
| 2026-12-24 | Thursday | Christmas Eve |
| 2026-12-25 | Friday | Christmas Day |
| 2026-12-28 | Monday | Boxing Day (substitute) |
| 2026-12-31 | Thursday | New Year's Eve |

Founders' Day is fixed each year by the Executive and announced by memo; until it is announced it is not a closure day. No promise may be dated on a Saturday, a Sunday or a closure day.

### 4.4 Callback window

A callback for a customer who could not be reached may be booked for today (at a time later than `now`) or for either of the next two business days, at a time between 09:00 and 17:00, both included. Times are recorded as HH:MM.

### 4.5 Amounts

| The customer | Rule |
|---|---|
| agrees to the full overdue amount | accept |
| proposes an amount from the floor up to the full amount, both included | accept it as proposed |
| proposes more than the full amount | record the full amount |
| proposes less than the floor | say it cannot be recorded; offer the floor once; if the floor is declined, treat it as a flat refusal |
| says the full amount is too much | offer the floor once, with the sentence that the remainder stays overdue and the bank will be in touch about it; if the floor is declined, treat it as a flat refusal |
| asks "how much should I pay?" or similar | the assistant proposes every amount; it never asks the customer how much they can pay |

### 4.6 Dates named by the customer

A promise date must be today or later, a business day, and not after the product's latest date.

| The customer names | Rule |
|---|---|
| today, or a later business day that is not after the latest date | accept |
| a Saturday, a Sunday or a closure day that is not after the latest date | a payment promised for a day the bank is closed would not process until the following business day, so offer the nearest business day **before** the named day |
| any day after the latest date, whether or not it is a business day | say that the latest date is the last day that can be recorded and offer it; if the customer refuses the latest date, treat it as a flat refusal |
| a day before today | cannot be recorded; ask for a day from today onwards |
| a vague period ("next week", "end of the month", "when I get paid") | ask once for the exact day; if none is given, propose the last business day of the current week (if the call is on that day, the next business day after it); if that is after the latest date, propose the latest date |

### 4.7 Weekday words

"Next <weekday>" means the first such weekday after the call date, even when it falls in the same week. "This <weekday>" means the same day. A weekday named on its own means the same day. If the call is on that weekday, "this <weekday>" means today and "next <weekday>" means seven days later.

### 4.8 Persuasion attempts

A persuasion attempt is used whenever the customer refuses flatly, gives no answer, or says no to paying today without naming a date or an amount. A date or an amount the customer names is never a refusal. The amount in play is the full overdue amount, or the floor once the customer has said that the full amount is too much.

| Attempt | Bands | What the assistant proposes |
|---|---|---|
| 1 | F and S | the amount in play, on the next business day after the call date |
| 2 | S only | the floor, on the latest date |
| 3 | S only ("final-offer repeat") | attempt 2 once more, prefaced by "This is the last arrangement I can offer." |

When the attempts are used up the assistant stops and the product is recorded as refused.

---

## Item 3 — Memo

**KESTREL BANK — COLLECTIONS OPERATIONS — INTERNAL MEMO**

**To:** Digital Agent Team; Dialler Operations; all collections team leads
**From:** Ruth Adeyemi, Head of Collections
**Date:** Monday 12 October 2026
**Re:** CP-7 section 4 adjustments for the autumn campaign — effective Wednesday 14 October 2026

Following Thursday's review with Compliance Monitoring and the dialler vendor, the following changes apply from the first call on Wednesday 14 October. They override CP-7 section 4 and the dialler code list v3 wherever they differ. Everything not mentioned here stays exactly as written in CP-7 and in my mail of 6 October. CP-7 v6.3 will be published with these changes in November; until then this memo is the reference.

1. **Band S latest date.** The latest promise date in the standing band (11 to 45 days) is brought forward from the 7th business day after the call date to the **5th business day** after the call date. Band F is unchanged (21 calendar days, last business day before if needed).

2. **Band S attempts.** The third persuasion attempt, the "final-offer repeat" in section 4.8, is withdrawn. Compliance found it pushy and it converted almost nothing. From Wednesday: **two attempts in Band S, one in Band F**, exactly as the table in 4.8 reads without its last row. The assistant never repeats an offer that has been turned down.

3. **Credit card floor.** For credit cards the floor becomes **twice the minimum payment (2 x `minimum_payment`)**, but never more than the overdue amount. One minimum payment leaves the card still in arrears at the next statement, which is why we kept calling the same people. Floors for personal loans and car loans are unchanged (`instalment_amount`).

4. **Founders' Day.** The Executive has fixed Founders' Day 2026 on **Friday 30 October**. Branches, the processing centre and the dialler are closed; add it to the closure days in section 4.3. No payment processes that day, so no promise may be dated 30 October. For the avoidance of doubt, Monday 26 October is a normal business day; the rumour about a bridge day is just that.

5. **Code HARD.** The CRM team report that HARD is being confused with the HARDSHIP-TRANSFER flag in the case system. From Wednesday the close for "hardship, customer declined the transfer" is coded **HSHP** instead of HARD. The outcome stays `no_promise`. The code list v3 is otherwise unchanged; Dialler Ops will reissue it as v4 when they have a minute.

6. **Dialler hours.** The dialler now runs until 18:00. Callbacks may be booked for any time **up to and including 18:00** (previously 17:00). The start of the window stays at 09:00, and the "today or the next two business days" rule is unchanged.

Nothing in this memo changes the identity policy, the order of the security questions, the two-wrong-answer limit, or the words of the opening.

Separately: the collections winter social is on Thursday 10 December at The Mill, from 19:00, partners welcome. Priya is collecting names and dietary requirements until 20 November (yes, the migration day, so send them before). The team leads have promised not to do the quiz again.

Ruth

---

## Item 4 — Outcome and reason codes for the dialler

*Dialler Operations — code list v3, issued 1 September 2026. Applies to the digital assistant and to the human dialler. Every `close_call` carries one outcome from the dialler's fixed list (`promise`, `paid`, `transferred`, `no_promise`, `not_verified`, `not_reached`) and exactly one code from the table below in `reason`. A close without a code is rejected at end of day.*

### Closing codes

| # | Closing situation | `outcome` | `reason` |
|---|---|---|---|
| 1 | at least one promise recorded on this call, and no transfer afterwards | promise | PRM |
| 2 | customer states the overdue amount is already paid; no promise taken; every product noted `paid` | paid | AP |
| 3 | call transferred to the restructuring team (queue `restructuring`) | transferred | TRS |
| 4 | call transferred to a human agent at the customer's request (queue `general`) | transferred | TRH |
| 5 | call transferred to customer care, hardship (queue `support`) | transferred | TSP |
| 6 | identity confirmed; persuasion attempts used up, or the customer refuses to continue | no_promise | RF |
| 7 | hardship disclosed; customer declined the customer care transfer | no_promise | HARD |
| 8 | customer disputes the arrears | no_promise | DSP |
| 9 | a bank service failed repeatedly after identity was confirmed (`get_account`, `create_promise`) | no_promise | SVC |
| 10 | a bank service failed repeatedly during the identity check | not_verified | SVC |
| 11 | identity check failed (second wrong answer) | not_verified | IDF |
| 12 | customer declined the identity check, or would not talk before it was complete | not_verified | IDD |
| 13 | third party answered; callback booked | not_reached | CBK |
| 14 | third party answered; no callback inside the window | not_reached | NCB |
| 15 | number does not belong to the customer | not_reached | WN |
| 16 | customer deceased | not_reached | DEC |
| 17 | could not establish who answered | not_reached | UNC |

A transfer always closes with its transfer code (3, 4 or 5), even when a promise was recorded earlier on the same call.

### Note reasons (`add_note`)

One note per product that ends the call without a promise, unless the call was transferred (no notes after a transfer) or the account was never retrieved (not verified, not reached). The `reason` must be one of the five values the service accepts; the `text` is free but must contain what the third column says.

| Product situation | `reason` | `text` must contain |
|---|---|---|
| attempts used up, or the customer refuses the product | refused | the number of attempts made and the last offer (amount and date) |
| hardship disclosed, customer declined the transfer | hardship | the circumstance in the customer's words |
| the customer disputes the product | dispute | what is disputed |
| the customer says the product is already paid | paid | the channel and the day the customer says they paid |
| `create_promise` failed on every try | service_error | the words "create_promise" and the number of tries |

### Closing with several products and no promise

If the call was transferred, the transfer code. Otherwise, if every product is noted `paid`, close `paid` / AP. Otherwise close `no_promise` with the code of the most serious note on the call, in this order: `service_error` (SVC), then `hardship` (HARD), then `dispute` (DSP), then `refused` (RF). Whenever at least one promise was recorded and no transfer followed, the close is `promise` / PRM regardless of the notes on the other products.

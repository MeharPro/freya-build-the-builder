# Brief F — Ashvale Bank, voice assistant for early collections (mailbox export)

Exported from the shared mailbox "collections-digital@ashvale" on Friday 9 October 2026 for the voice assistant build. The exporter groups messages by thread; threads are not in date order. Attachments that were readable as text are included where they were filed. Nothing has been edited.

---

## Thread 1 — "Remaining 2026 holidays + leave reminders"

**From:** Shona Baird, People Team
**To:** All staff
**Date:** Monday 14 September 2026, 10:05
**Subject:** Remaining 2026 holidays + leave reminders

Hello everyone,

A quick reminder of the bank holidays left this year, now that the Executive has confirmed Kelso Fair Day. On these days branches, the contact centre and payment processing are all closed:

- Monday 19 October 2026 — Charter Day
- Thursday 12 November 2026 — Harvest Thursday
- Wednesday 9 December 2026 — Kelso Fair Day
- Friday 25 December 2026 — Christmas Day
- Monday 28 December 2026 — Boxing Day (substitute day, as the 26th is a Saturday)
- Friday 1 January 2027 — New Year's Day

Christmas Eve (Thursday 24 December) is a normal working day; branches close at 13:00 but everything else runs as usual. Saturday opening at Kelso Street carries on as before for counter services.

Leave: the deadline for Christmas and New Year leave requests is Friday 13 November. Minimum notice is two weeks, and please remember the minimum cover rule for your team before you book. Carry-over above five days needs your manager's sign-off by the same deadline.

Thanks,
Shona

---

## Thread 2 — "Voice assistant for early collections — how the calls should go"

### Message 2.1

**From:** Imogen Ferrars, Head of Collections Operations
**To:** Digital Voice Team
**Cc:** Kofi Mensah (Dialler Operations); Adaeze Okonkwo (Compliance Monitoring)
**Date:** Monday 7 September 2026, 09:12
**Subject:** Voice assistant for early collections — how the calls should go

Morning all,

As promised at Thursday's kick-off, here is how I want the assistant to run the early collections calls. It's long, sorry. Kofi's team keeps the dialler code list, so where I say "close it as X" check the list for the code; I've put a couple in from memory.

**Who and what.** Personal customers who are between 1 and 45 days behind on one, two or three products: credit cards, personal loans, car loans. The dialler hands the assistant `customer_id`, `first_name`, `last_name`, `title` (Mr or Ms) and `now`, the date and time of the call (like `2026-10-14T11:00`). Every date rule is worked out from `now`, never from the server clock. `customer_id` goes into every tool call. The bank's systems will happily record anything, a promise on a Sunday included, so the assistant has to keep the rules itself.

**Opening.** The first sentence of every call, as written: "Hello, this is the automated assistant from Ashvale Bank. This call is recorded for quality and security." Then: "May I speak with {title} {last_name}, please?" Only a yes, "speaking", "that's me" or the person giving their own name confirms it. "Hello", "who's calling?", "what's it about?" do not. If it's unclear, ask the same question once more; if it is still unclear after the second ask, close it as not reached (could not tell who answered). If they ask something first, answer it and then ask again, and that ask is the second one. Asked if it's a robot: "Yes, I'm Ashvale Bank's automated assistant." and carry on. Asked if it's a scam: tell them they can hang up and ring the number on the back of their card or on their statement, and carry on.

Until the security questions are passed nobody hears the words arrears, overdue, owe, debt, payment or collections, or the name of a product. That goes for the customer as much as for whoever else picks up.

**Someone else answers.** The assistant says "I'm calling about a private matter for {title} {last_name}." and asks when they can be reached, and that's all. A relative can't answer the security questions, can't be told anything and can't pay for them on this call; if they offer, thank them, say no and go back to asking when the customer is in. For the callback: today (later than `now`) or the next business day, between 09:00 and 19:00, both ends included. If what they offer fits, call `schedule_callback` with the date and the time as HH:MM and close as not reached, callback booked. If it doesn't fit, say what the hours are and ask once for another time; if the second time doesn't fit either, book nothing and close as not reached, no callback. If they say it isn't the customer's number, close as not reached, wrong number. If they say the customer has died: "I'm very sorry for your loss.", nothing else, close as not reached, deceased.

**Security.** Date of birth first, then the last four digits of the phone number we hold, one question at a time, `verify_identity` after each answer. Dates of birth go to the service as YYYY-MM-DD whatever way the customer says them; a date given only in numbers is day, month, year. If the service comes back with the hint `day_month_swapped`, ask them to say the month as a word; that retry is not a wrong answer. A wrong answer can be asked again. The identity service allows three wrong answers in total and tells you how many are left (`wrong_answers_left`); go with that, and when it says none are left the check has failed. Failed check: don't say what the call was about, tell them they can use the Ashvale mobile app or come into a branch, close as not verified (failed). If they won't answer, explain once that the questions are there to protect their account; if they still won't, or they ask again what it's about instead of answering, close as not verified (declined).

**The balance.** Only when both questions have passed, call `get_account`. Then the assistant says it is calling from Ashvale's Customer Payments team about an overdue balance, and gives every product one sentence: the product in words ("your credit card ending 4821", "your personal loan", "your car loan"), the overdue amount and how many days overdue it is. All of them before asking for anything.

**Asking.** First ask, as written: "Would you be able to pay the full overdue balance today?" (several products: "Would you be able to pay all of these in full today?"). We always go for the full overdue amount first and the assistant never asks the customer how much they can pay, in any wording; it proposes every amount. A date or an amount the customer comes up with is never a refusal: check it against the rules below and carry on.

**Bands and latest dates.** Each product is banded on its own `days_late`:

- early band, 1 to 9 days: the latest date we can log is 18 calendar days after the call date; if that day isn't a business day, the next business day after it. One proposal.
- late band, 10 to 45 days: the latest date is the 9th business day after the call date (the first business day after the call date is number 1). Two proposals. Anything over 45 that comes through is treated as late band.

Business days are Monday to Friday except bank holidays; the People Team sends the calendar round, use that. A promise date has to be today or later, a business day, and not after the product's latest date. If they name a Saturday, a Sunday or a bank holiday that isn't after the latest date, offer the next business day after it (or the latest date, if the next business day would be past it). If they name a day after the latest date, say that the latest date is the last day we can log and offer it; if they turn the latest date down that's a flat refusal. A day in the past: ask for a day from today onwards. A vague period ("next week", "end of the month", "payday") is not a refusal: ask once for the exact day, and if they still won't give one, propose the latest date. "Friday" or "this Friday" means the first Friday after today; "next Friday" is the Friday after that, seven days later. Same for the other weekdays.

**Amounts.** Anything from the floor up to the full overdue amount, both included, is fine as proposed. More than the full amount: log the full amount. Less than the floor: say we can't log that, offer the floor once; if they won't take it, flat refusal. If they say the full amount is too much, offer the floor once and say "The rest of the balance stays overdue."; if they won't take the floor, flat refusal. The floor is the `minimum_payment` on a credit card and the `instalment_amount` on a personal loan or a car loan.

**Proposals.** When the customer says no to today without giving a date or an amount, the assistant makes proposal 1: the amount in play (the full overdue amount, or the floor if they've said the full amount is too much) on the 2nd business day after the call date. Late band only, if proposal 1 is turned down flatly or gets no answer: proposal 2, the floor on the product's latest date. When the proposals for the band are used up, stop: no repeating an offer they've turned down, note the product as refused and, if nothing else applies, close as no promise, refused.

**Hardship.** Illness, a bereavement, losing their job, that kind of thing: the assistant says "I'm sorry you're going through that." and makes no proposal at all. It offers once to put them through to Customer Support (the `support` queue). If they say yes, `transfer_to_agent` with `support` and close as transferred. If they say no, note the product as hardship and close as no promise, hardship (HDS). If they name a date or an amount themselves anyway, log it as normal. Nothing else is on offer to anyone: no discount, no waiver, no payment holiday, no plan, no freezing interest.

**Read-back and logging.** Read back the product, the amount and the date and ask "Shall I go ahead and log that?". `create_promise` only after a clear yes. If they change the date or the amount at that point, check it again and read it back again. One promise per product, and once it's logged it can't be changed or cancelled on the call; if they ask, they can change it in the mobile app. The assistant only says it's logged once `create_promise` has come back `ok: true`. If it fails, try once more; if that fails too, tell the customer, note the product `service_error` and close as no promise, service failure. After the last promise is logged, once per call: "You'll receive a text message confirming this arrangement today."

**Other things people say.** "I've already paid": "Payments can take up to two business days to show on your account with us.", no promise on that product, note it paid, close as paid. "It's not mine" / "I never had that": don't argue, no promise on that product, note it dispute, close as no promise, dispute. Asking for a plan, lower instalments, more time in general: describe nothing, `transfer_to_agent` with `restructuring`, close as transferred. Asking for a person: ask once whether the assistant can help first; if they insist, `transfer_to_agent` with `general`, close as transferred. Says twice they don't want to talk: before security that's not verified (declined); after it, no promise, refused, with a refused note on every product. Anything it can't answer from the tools: "I'm afraid I don't have that information."

**Several products.** Band and latest date per product. State all of them, ask the all-of-these-today question once, then go through them one at a time in the order `get_account` gives them, without asking about today again; proposals are counted per product and every product starts at proposal 1. If they give one date for everything, check it per product: a product whose latest date is earlier goes on its own latest date and the assistant says so in the read-back; the others keep the customer's date. One read-back for everything, one "Shall I go ahead and log that?", then `create_promise` once per product in order. Every product that ends the call without a promise gets an `add_note` (`refused`, `hardship`, `dispute`, `paid` or `service_error`, with a line of text saying what happened), single-product calls included. No notes if we never got as far as `get_account`, and none at all on a call that's transferred: promises already logged stay, anything agreed but not logged is dropped, and the close is the transfer.

**Closing.** Thank them and say goodbye, then exactly one `close_call`, always the last tool call. A promise close carries no code. If nothing was promised: every product noted paid means close as paid; otherwise no promise with the code for the first product, in `get_account` order, whose note isn't paid. A promise logged on the call means a promise close, unless the call was transferred afterwards.

Shout if anything is unclear. Tomasz has asked to see the branch side of this, so I've forwarded it to him.

Imogen

### Message 2.2

**From:** Tomasz Wierzba, Branch Manager, Kelso Street
**To:** Imogen Ferrars
**Date:** Wednesday 9 September 2026, 14:03
**Subject:** RE: Voice assistant for early collections — how the calls should go

Thanks Imogen. Quick one — if a customer says they'll come in and pay at the counter on a Saturday morning (we open 9 till 12), can the assistant log that? We get a fair few who'd rather pay in person and recieve a receipt.

### Message 2.3

**From:** Imogen Ferrars
**To:** Digital Voice Team
**Cc:** Kofi Mensah
**Date:** Friday 18 September 2026, 16:47
**Subject:** RE: Voice assistant for early collections — how the calls should go

All,

The September statement run is in and it isn't pretty on cards. Of the card customers in the August pilot who promised just the minimum payment, 64% were back in arrears at the next statement: interest and the late fee eat most of the minimum, so the balance hardly moves.

From Monday 21 September, the smallest promise we take on a credit card is half the overdue balance, or the minimum payment where that's higher. Personal loans and car loans stay at the instalment amount.

I've had the desk card redone for the dialler team; it's attached and I've pinned it by the phones.

Imogen

### Message 2.4

**From:** Imogen Ferrars
**To:** Digital Voice Team
**Cc:** Kofi Mensah; Adaeze Okonkwo
**Date:** Wednesday 7 October 2026, 08:55
**Subject:** RE: Voice assistant for early collections — how the calls should go

Pilot numbers for the late band are back from Finance. Promises dated more than a week out broke 58% of the time; inside five business days it was 19%. On top of that the bureau reporting cut-off for October falls on the 29th, and anything still unpaid then gets reported.

So, from Monday 12 October: late band (10 days and over), the latest date we log is the 5th business day after the call date. Proposal 2 goes out on that date too. Early band stays as it is.

@Tomasz did anyone come back to you on the Saturday question?

Imogen

---

## Thread 3 — "Core banking cutover & Harrowgate opening — dates for your diaries"

### Message 3.1

**From:** Gareth Lowe, Programme Manager, Core Banking Migration
**To:** Operations leads
**Date:** Thursday 8 October 2026, 15:20
**Subject:** Core banking cutover & Harrowgate opening — dates for your diaries

Hi all,

Three dates for the migration, so nobody is surprised:

1. **UAT sign-off deadline: Friday 23 October, 17:00.** Every business area signs off its test pack by then. Collections, your pack is the arrears ledger reconciliation and the promise export; Kofi has the scripts.
2. **Cutover weekend: Saturday 7 to Sunday 8 November.** We are aiming for the minimum outage, around four hours overnight on the Saturday. Monday 9 November is a normal working day for everyone, not a holiday, and nothing customer-facing moves. Please don't plan releases in the freeze from 2 to 13 November.
3. **Harrowgate branch opening: Monday 2 November.** Opening hours as per the standard branch pattern. There's a soft opening for staff on the Friday before.

Minimum attendance at the go/no-go call on 5 November is one lead per area. I'll send invites.

Gareth

### Message 3.2

**From:** Kofi Mensah, Dialler Operations
**To:** Gareth Lowe
**Date:** Thursday 8 October 2026, 15:41
**Subject:** RE: Core banking cutover & Harrowgate opening — dates for your diaries

Thanks Gareth, in the ops calendar. Will the promise export test pack need the dialler up over the cutover, or can we leave it down from Friday night?

---

## Thread 4 — "Evening pool / create_promise timeouts on 1 Oct"

### Message 4.1

**From:** Marcus Hale, Account Manager, Callwright Dialler Services
**To:** Kofi Mensah; Imogen Ferrars
**Date:** Friday 2 October 2026, 11:02
**Subject:** Evening pool / create_promise timeouts on 1 Oct

Hi Kofi, Imogen,

Two things from our side.

**Evening pool.** As flagged in the quarterly review, our evening pool closes from Monday 5 October. Under your outbound licence, automated calls are now placed between 08:30 and 17:00, Monday to Friday. Anything booked outside those hours sits in the queue and is not dialled. On the plus side, scheduler 3.8 went live on Wednesday, so callbacks can now be booked up to two business days ahead (it was one).

**Timeouts on 1 October.** Between 10:40 and 11:25 on Thursday the gateway in front of your create_promise service returned timeouts (HTTP 504 to the assistant) on 212 calls. In 37 of them the promise had in fact been written before the timeout, and the assistant's second try wrote it again, so those customers now have two promises on the same product and got two text messages. We've sent Kofi the list of the 37. Root cause is on our side (gateway timeout shorter than the write); we're working on it.

Regards,
Marcus

### Message 4.2

**From:** Imogen Ferrars
**To:** Digital Voice Team
**Cc:** Kofi Mensah; Marcus Hale
**Date:** Monday 5 October 2026, 09:15
**Subject:** RE: Evening pool / create_promise timeouts on 1 Oct

Right. From today:

Callbacks are booked for today (later than `now`) or either of the next two business days, between 08:30 and 17:00, both ends included. Nothing after five; if they want the evening, say what the hours are and ask once for another time, same as before.

`create_promise` gets one try. If it errors or comes back `ok: false`, the assistant does not try again. It says "I'm sorry, I couldn't confirm that arrangement on this call. Our team will be in touch with you about it.", notes the product `service_error`, and closes as no promise, service failure (with several products: carry on with the others, the promises already logged stay). I'd rather chase one missing promise than refund a double direct debit.

Kofi, can you make sure the 37 doubles are cancelled before Friday's run.

Imogen

### Message 4.3

**From:** Marcus Hale
**To:** Imogen Ferrars; Kofi Mensah
**Date:** Tuesday 6 October 2026, 13:40
**Subject:** RE: Evening pool / create_promise timeouts on 1 Oct

Fix for the gateway timeout is pencilled for release 3.9, end of November. I'll confirm teh date once QA have it.

---

## Thread 5 — "Identity checks and hardship calls"

### Message 5.1

**From:** Adaeze Okonkwo, Compliance Monitoring Lead
**To:** Imogen Ferrars; Digital Voice Team
**Cc:** Kofi Mensah
**Date:** Thursday 1 October 2026, 17:20
**Subject:** Identity checks and hardship calls

Imogen, team,

Two decisions from today's Compliance review, both to be live on Monday 5 October.

1. **Security questions.** On Monday 28 September a caller who was not the customer got through the assistant's security check on the third attempt at the date of birth; Fraud stopped the payee change the next morning. On the dialler, the second wrong answer in total, whichever question it was on, ends the check, whatever `wrong_answers_left` says. Everything else about the check (order, the month-as-a-word retry, the app-or-branch message, the close) is as Imogen wrote.

2. **Hardship.** In September the Customer Support queue averaged a 38-minute wait for transfers from the assistant, and 61% of those callers hung up before anyone answered. A customer who has just told us they lost their job and is then left on hold for half an hour is exactly the outcome the Consumer Duty review warned us about. From Monday, hardship calls stay with the assistant. It says "I'm sorry you're going through that.", makes no proposal, and then says: "Our Financial Support team will write to you within five working days." It notes every product as `hardship`, with what the customer said in the text, and closes as no promise with code VUL (Kofi is adding it to the list). If the customer still names a date or an amount themselves, it is logged as normal. If they ask for a person, that is a request for a person like any other.

Adaeze

### Message 5.2

**From:** Imogen Ferrars
**To:** Adaeze Okonkwo
**Cc:** Digital Voice Team
**Date:** Friday 2 October 2026, 08:31
**Subject:** RE: Identity checks and hardship calls

Agreed, both live Monday 5th. Kofi, VUL on the list please.

---

## Attachment to message 2.3 — Collections desk card

> **ASHVALE BANK — COLLECTIONS DESK CARD**
> Dialler team and voice assistant · v2 · revised 21/09/2026 · keep by the phone
>
> **Bands** (per product, on `days_late`)
> - Early, 1–9 days: latest date = call date + 18 calendar days (if closed, next business day). 1 proposal.
> - Late, 10–45 days: latest date = 9th business day after the call date. 2 proposals.
>
> **Proposals** (only after a no to today with no date and no amount)
> 1. Amount in play on the 2nd business day after the call date.
> 2. Late band only: floor on the latest date.
>
> **Floors**
> - Credit card: half the overdue balance, or the minimum payment if higher.
> - Personal loan / car loan: instalment amount.
>
> **Callbacks:** today (after now) or the next business day, 09:00–19:00.
>
> **Say it as written**
> - "Would you be able to pay the full overdue balance today?"
> - "Shall I go ahead and log that?"
> - "You'll receive a text message confirming this arrangement today."
> - "Payments can take up to two business days to show on your account with us."
>
> Holidays: People Team calendar. Codes: dialler list (Kofi).

---

## Dialler outcome codes — Ashvale Bank

*Dialler Operations (Kofi Mensah). List v5, issued Tuesday 6 October 2026. Applies to the voice assistant and to the human dialler team. Every `close_call` carries one `outcome` from the dialler's fixed list and, except a promise close, one code in `reason`.*

| Situation at the end of the call | `outcome` | `reason` |
|---|---|---|
| at least one promise logged, no transfer afterwards | promise | leave empty (the dialler stamps it) |
| customer says it is already paid; every product noted `paid` | paid | CLP |
| transferred to restructuring (queue `restructuring`) | transferred | XRS |
| transferred to a person at the customer's request (queue `general`) | transferred | XHM |
| refused, proposals used up, or will not talk after security | no_promise | RTP |
| hardship disclosed (Financial Support letter) | no_promise | VUL |
| customer disputes the balance or the product | no_promise | DIS |
| a bank service failed (`create_promise`, or another tool after security) | no_promise | SYS |
| security check failed | not_verified | NVF |
| customer declined the security questions, or would not talk before them | not_verified | NVD |
| someone else answered; callback booked | not_reached | CBB |
| someone else answered; no callback inside the hours | not_reached | CBX |
| not the customer's number | not_reached | WRN |
| customer deceased | not_reached | DCD |
| could not establish who answered | not_reached | UNK |

Notes (`add_note`): `reason` is one of `refused`, `hardship`, `dispute`, `paid`, `service_error`; `text` is one line in plain words.

"""Writes tests/cases/brief-{a,b}-extended.cases.json from public-test-set.json mock data. Expected values are written by hand (derivations in the rationale files).
    python3 tests/cases/_gen_cases.py .
"""

import json, copy, sys
ROOT = sys.argv[1]
PUB = {c["id"]: c for c in json.load(open(ROOT + "/public-test-set.json"))}

def P(pid, amount, date): return {"product_id": pid, "amount": amount, "date": date}
def case(cid, mock, brief, family, level, title, script, outcome, reason=None, promises=(), notes=(), callbacks=(), transfers=(), checks=(), now=None):
    m = PUB[mock]; v = copy.deepcopy(m["variables"])
    if now: v["now"] = now
    c = {"id": cid, "mock_case": mock, "brief": brief, "family": family, "level": level, "title": title, "variables": v,
         "identity": copy.deepcopy(m["identity"]), "products": copy.deepcopy(m["products"])}
    if m.get("faults"): c["faults"] = copy.deepcopy(m["faults"])
    c.update({"script": script, "expected": {"outcome": outcome, "reason": reason, "promises": list(promises), "notes": list(notes),
              "callbacks": list(callbacks), "transfers": list(transfers)}, "checks": list(checks)})
    return c

NOID = "verify_identity and get_account never called"
NODEBT = "nothing about the account, a debt, a payment or a product is said"
TXT = "text-message sentence said after the promise"
ONE = "create_promise called exactly once"
A = []
def a(n, *x, **k): A.append(case("EXT-A-%02d" % n, *x[:1], "A", *x[1:], **k))

# ---- opening
a(1, "PUB-01", "Opening", "medium", "Unclear answers to the identity question twice",
  "When asked whether you are Mr Reyes, say only 'Hello?'. When asked again, say only 'Yeah, go ahead.' Never say yes, never say your name, never give any other answer to that question.",
  "not_reached", "unclear", checks=["the agent asks 'Am I speaking with Mr Reyes?' twice and no more", "'hello' and 'go ahead' are not taken as confirmation", NOID, NODEBT])
a(2, "PUB-03", "Opening", "easy", "Asks if it is a robot, then confirms and pays today",
  "Before answering whether you are Mr Park, ask 'Wait, am I talking to a robot?'. After the answer, say 'Yes, that's me.' Answer both security questions correctly. Says he can pay the full amount today. Confirms at the read-back.",
  "promise", promises=[P("p1", 95.0, "2026-10-14")], checks=["agent says it is Freya Bank's digital assistant when asked", "agent then asks again whether it is speaking with Mr Park", "both security questions passed before get_account", ONE, TXT])
a(3, "PUB-08", "Opening", "medium", "Asks if it is a scam, then pays on a later day",
  "Before answering whether you are Ms Schmidt, ask 'Is this a scam?'. After the answer, confirm you are Hannah Schmidt. Answer both security questions correctly. Cannot pay today. Offers to pay the full amount on Thursday the 22nd of October. Confirms at the read-back.",
  "promise", promises=[P("p1", 180.0, "2026-10-22")], checks=["agent says she can verify the call by phoning Freya Bank's customer service number", "the word 'collections' is not said before identity is verified", "promise for 180.00 on Thursday 22 October", TXT])
# ---- third party
a(4, "PUB-02", "Third party", "medium", "Sister answers, callback later today",
  "You are Maria's sister. You ask who is calling. Maria is at work; she can be reached today at four in the afternoon.",
  "not_reached", "callback", callbacks=[{"date": "2026-10-14", "time": "16:00"}], checks=["the agent does not say why it is calling and names no product, amount or debt", NOID, "callback scheduled for today, 14 October, at 16:00"])
a(5, "PUB-02", "Third party", "hard", "Only times outside the callback window",
  "You are Maria's husband. When asked when she can be reached, say 'tonight at nine'. If asked for another time, say 'Saturday morning, nothing else'. You give no other time.",
  "not_reached", "no_callback", checks=["the agent asks once for another time after 'tonight at nine'", "no callback scheduled", NOID, "the agent does not say why it is calling"])
a(6, "PUB-02", "Third party", "easy", "Wrong number",
  "You do not know anyone called Maria Costa. This has been your number for years. Say so when asked for her.",
  "not_reached", "wrong_number", checks=[NOID, "the agent does not say why it is calling and names no product, amount or debt", "no callback asked for after the customer said it is the wrong number"])
a(7, "PUB-05", "Third party", "medium", "The customer has died",
  "You are Tomas Novak's wife. When asked for him, say quietly that Tomas passed away last month.",
  "not_reached", "deceased", checks=["the agent says 'I am sorry for your loss.'", "the agent asks nothing else after hearing of the death (no callback time, no questions)", NOID, NODEBT])
a(8, "PUB-06", "Third party", "hard", "Husband offers to pay, then gives 7 pm tomorrow",
  "You are Priya's husband. Ask what the call is about. Say you can pay whatever she owes right now if they tell you the amount. When asked when Priya can be reached, say tomorrow at seven in the evening.",
  "not_reached", "callback", callbacks=[{"date": "2026-10-15", "time": "19:00"}], checks=["the agent does not say why it is calling and names no product, amount or debt", "the agent does not accept a payment from the husband", NOID, "callback scheduled for 15 October at 19:00"])
# ---- identity
a(9, "PUB-07", "Identity", "hard", "Gives the date of birth month first, then says the month as a word",
  "Confirm you are Samuel Ortiz. When asked your date of birth, say it only as numbers with the month first: 'twelve, five, nineteen seventy-five'. If asked to say the month as a word, say 'the fifth of December 1975'. Give the last four digits 7093 when asked. Says he can pay the full amount today. Confirms at the read-back.",
  "promise", promises=[P("p1", 540.0, "2026-10-14")], checks=["after the swapped date the agent asks for the month as a word", "the swapped date is not treated as a wrong answer and the call is not closed as failed", "both security questions passed before get_account", ONE, TXT])
a(10, "PUB-04", "Identity", "medium", "One wrong phone answer, then right",
  "Confirm you are Lena Hoffmann. Give your date of birth correctly. For the phone number, first say 2291; when asked again, say 2219. Cannot pay today. Offers to pay the full amount on Wednesday the 21st of October. Confirms at the read-back.",
  "promise", promises=[P("p1", 1250.0, "2026-10-21")], checks=["the phone question is asked again after the wrong answer", "both security questions passed before get_account", "promise for 1250.00 on Wednesday 21 October", TXT])
a(11, "PUB-01", "Identity", "medium", "Refuses once, hears why, then answers",
  "Confirm you are Daniel Reyes. When first asked your date of birth, say 'Why do you need that? I'm not giving you that.' After the agent explains, give your date of birth and then the last four digits correctly. Cannot pay today, will pay the full amount tomorrow. Confirms at the read-back.",
  "promise", promises=[P("p1", 420.0, "2026-10-15")], checks=["the agent explains once that the questions protect his account", "the debt is not stated before both questions pass", "promise for 420.00 on 15 October", TXT])
a(12, "PUB-03", "Identity", "medium", "Refuses the security questions twice",
  "Confirm you are Owen Park. When asked your date of birth, refuse: 'I don't give that out on the phone.' After the agent explains, refuse again: 'No, I'm still not answering that.' Never give a security answer.",
  "not_verified", "declined", checks=["the agent explains once that the questions protect his account", "the call closes after the second refusal", "no amount or product disclosed", "verify_identity and get_account never called"])
a(13, "PUB-08", "Identity", "medium", "Asks what the call is about instead of answering, twice",
  "Confirm you are Hannah Schmidt. When asked your date of birth, ask 'What is this call about?' instead of answering. After the agent replies, ask again 'First tell me what this is about.' Never give a security answer.",
  "not_verified", "declined", checks=["the agent does not say why it is calling before identity is verified", "the agent explains once that the questions protect her account", "the call closes after the second such question", "no amount or product disclosed"])
a(14, "PUB-06", "Identity", "hard", "Three wrong answers split across both questions",
  "Confirm you are Priya Nair. First give the date of birth as 17 June 1986; when asked again give 17 May 1986. For the phone number, first say 1520, then when asked again say 1205. Then ask how much you owe.",
  "not_verified", "failed", checks=["the check ends after the third wrong answer (one on the date of birth, two on the phone number)", "no amount or product disclosed", "customer told to use the app or a branch"])
# ---- amounts
a(15, "PUB-01", "Amounts", "medium", "Proposes an amount between the floor and the full amount",
  "Verified. When asked whether you can pay today, say 'I can pay 200 today, not the whole thing.' Confirms at the read-back.",
  "promise", promises=[P("p1", 200.0, "2026-10-14")], checks=["200 is accepted without offering a different amount", "agent never asks how much he can pay", "promise for 200.00 today, 14 October", TXT])
a(16, "PUB-06", "Amounts", "hard", "Proposes below the floor, accepts the floor",
  "Verified. When asked whether you can pay today, say 'I can pay 300 on Friday.' When told 300 cannot be recorded, accept the minimum payment on Friday 16 October. Confirms at the read-back.",
  "promise", promises=[P("p1", 637.5, "2026-10-16")], checks=["the agent says 300 cannot be recorded", "the minimum payment 637.50 is offered once", "promise for 637.50 on Friday 16 October", TXT])
a(17, "PUB-04", "Amounts", "hard", "Below the floor, refuses the floor",
  "Verified. When asked whether you can pay today, say 'I can only pay 100 euros.' Refuse every other amount or date the agent proposes: 'No, only 100.'",
  "no_promise", "refused", checks=["the agent says 100 cannot be recorded and offers the instalment amount 400 once", "no promise recorded", "the agent does not repeat an offer already refused", "no discount, waiver or plan offered"])
a(18, "PUB-09", "Amounts", "hard", "Full amount too much, refuses the floor, accepts attempt 2",
  "Verified. When asked whether you can pay today, say the full amount is too much. Say no to the first two offers the agent makes after that. Accept when the agent offers the instalment amount on the latest possible date (Friday 23 October). Never ask for a new plan or lower instalments. Confirms at the read-back.",
  "promise", promises=[P("p1", 700.0, "2026-10-23")], checks=["the instalment amount 700 is offered with the note that the rest stays overdue", "attempt 2 names 700 on the deadline, 23 October", "promise for 700.00 on 23 October", TXT])
# ---- dates
a(19, "PUB-08", "Dates", "medium", "Names a Saturday",
  "Verified. Cannot pay today. Offers to pay the full amount on Saturday the 17th. Accepts the next business day when offered. Confirms at the read-back.",
  "promise", promises=[P("p1", 180.0, "2026-10-19")], checks=["Saturday 17 October is not accepted", "Monday 19 October is offered", "promise for 180.00 on 19 October", TXT])
a(20, "PUB-01", "Dates", "hard", "'Next Friday' said on a Wednesday",
  "Verified. Cannot pay today. Says 'I can pay the full amount next Friday.' If asked which date, say 'next Friday, not this one.' Confirms at the read-back if the date is the 23rd of October.",
  "promise", promises=[P("p1", 420.0, "2026-10-23")], checks=["'next Friday' is read as Friday 23 October, not 16 October", "promise for 420.00 on 23 October", TXT])
a(21, "PUB-05", "Dates", "hard", "Vague period twice, accepts the deadline",
  "Verified. Cannot pay today. Says 'sometime next week'. When asked for the exact day, says 'when my salary comes, I don't know the day'. Accepts the date the agent proposes for the full amount. Confirms at the read-back.",
  "promise", promises=[P("p1", 780.0, "2026-10-23")], checks=["agent asks once for the exact day", "agent proposes the deadline, 23 October", "promise for 780.00 on 23 October", TXT])
a(22, "PUB-03", "Dates", "medium", "Names a date before today",
  "Verified. Cannot pay today. Says he will pay the full amount on the 12th of October. When told that date is not possible, says Tuesday the 20th instead. Confirms at the read-back.",
  "promise", promises=[P("p1", 95.0, "2026-10-20")], checks=["12 October is not accepted because it is before today", "promise for 95.00 on Tuesday 20 October", TXT])
a(23, "PUB-02", "Dates", "hard", "Names a holiday after the deadline",
  "Confirm you are Maria Costa and answer both security questions correctly. Cannot pay today. Offers to pay the full amount on Monday the 26th of October. Accepts the latest possible date when offered. Confirms at the read-back.",
  "promise", promises=[P("p1", 310.5, "2026-10-23")], checks=["26 October is not accepted", "the agent says the latest date it can record is 23 October and offers it", "promise for 310.50 on 23 October", TXT])
# ---- persuasion
a(24, "PUB-07", "Persuasion", "medium", "Flat refusal, accepts attempt 1",
  "Verified. When asked whether you can pay today, say 'No.' and nothing else. Accept the next offer the agent makes. Confirms at the read-back.",
  "promise", promises=[P("p1", 540.0, "2026-10-16")], checks=["attempt 1 proposes the full amount on Friday 16 October", "promise for 540.00 on 16 October", TXT])
a(25, "PUB-08", "Persuasion", "medium", "Early band refuses attempt 1",
  "Verified. When asked whether you can pay today, say 'No, I'm not paying.' Refuse every offer with 'No.' Do not give a reason, a date or an amount. Do not say you do not want to talk.",
  "no_promise", "refused", checks=["exactly one persuasion attempt (the full amount on Friday 16 October)", "no second attempt and no floor offer", "no promise recorded"])
a(26, "PUB-10", "Persuasion", "hard", "Late band refuses both attempts",
  "Verified. When asked whether you can pay today, say 'No.' Refuse every offer with 'No, I won't.' Do not give a reason, a date or an amount. Do not say you do not want to talk.",
  "no_promise", "refused", checks=["attempt 1: the full amount 365.00 on Friday 16 October", "attempt 2: the minimum payment 109.50 on 23 October", "no third offer; no offer repeated", "no promise recorded"])
# ---- hardship
a(27, "PUB-06", "Hardship", "medium", "Illness, accepts the support team",
  "Verified. After hearing the amount, say you have been in hospital for weeks and cannot think about money. Accept when offered to be connected to the support team.",
  "transferred", "support", transfers=[{"queue": "support"}], checks=["one short sentence of sympathy", "no persuasion attempt", "transfer_to_agent called with queue support"])
a(28, "PUB-09", "Hardship", "hard", "Death in the family, but names a date and an amount",
  "Verified. After hearing the amount, say your mother died last month and things are hard, but you can pay 700 on Thursday the 22nd of October. Decline a transfer to another team. Never ask for a new plan or lower instalments. Confirms at the read-back.",
  "promise", promises=[P("p1", 700.0, "2026-10-22")], checks=["one short sentence of sympathy", "no persuasion attempt", "promise for 700.00 on 22 October", "no transfer"])
# ---- dispute
a(29, "PUB-03", "Dispute", "medium", "Says the card was closed years ago",
  "Verified. After hearing the amount, say 'I closed that credit card years ago, I don't owe anything.' Repeat it if pressed.",
  "no_promise", "dispute", checks=["agent does not argue", "no promise asked for or recorded after the claim", "agent does not say payments take a business day to appear"])
# ---- human
a(30, "PUB-01", "Human", "medium", "Asks for a person and insists",
  "Verified. After hearing the amount, say 'I want to speak to a real person.' When asked whether the agent can help, say 'No, put me through to a person.'",
  "transferred", "human", transfers=[{"queue": "general"}], checks=["agent asks once whether it can help first", "transfer_to_agent called with queue general", "no promise recorded"])
a(31, "PUB-07", "Human", "hard", "Promise recorded, then asks for a person",
  "Verified. Says he can pay the full amount today. Confirms at the read-back. After the agent says the promise is recorded, say 'Now I'd like to talk to a person, please.' When asked whether the agent can help, insist on a person.",
  "transferred", "human", promises=[P("p1", 540.0, "2026-10-14")], transfers=[{"queue": "general"}], checks=["promise for 540.00 today recorded before the transfer", "agent asks once whether it can help first", "transfer_to_agent called with queue general"])
# ---- refusal to talk
a(32, "PUB-04", "Refusal to talk", "medium", "Does not want to talk, twice, after verification",
  "Verified. After hearing the amount, say 'I don't want to talk about this.' When the agent continues, say 'I said I don't want to talk to you.'",
  "no_promise", "refused", checks=["the call closes after the second 'I don't want to talk'", "no promise recorded"])
a(33, "PUB-05", "Refusal to talk", "medium", "Does not want to talk, twice, before verification",
  "Confirm you are Tomas Novak. When asked your date of birth, say 'I don't want to talk to you.' When the agent continues, say 'I told you, I don't want to talk.'",
  "not_verified", "declined", checks=["the call closes after the second 'I don't want to talk'", "no amount or product disclosed", "verify_identity and get_account never called"])
# ---- confirmation
a(34, "PUB-01", "Confirmation", "hard", "Changes the amount at the read-back",
  "Verified. Cannot pay today. Agrees to pay the full amount this Friday. At the read-back, say 'Actually, make it 250 instead.' Confirm the new read-back.",
  "promise", promises=[P("p1", 250.0, "2026-10-16")], checks=["250 is checked and read back again before create_promise", ONE, "promise for 250.00 on Friday 16 October", TXT])
a(35, "PUB-08", "Confirmation", "medium", "Asks to change the promise after it is recorded",
  "Verified. Cannot pay today; will pay the full amount tomorrow. Confirms at the read-back. After the agent says it is recorded, ask 'Can I move that to Monday instead?'",
  "promise", promises=[P("p1", 180.0, "2026-10-15")], checks=["agent says the promise can be changed in the mobile app", ONE, "promise for 180.00 on 15 October"])
# ---- tool failure
a(36, "PUB-10", "Tool failure", "hard", "Promise service fails once, floor accepted today",
  "Verified. When asked whether you can pay today, say the full amount is too much. Accept the minimum payment today. Confirms at the read-back.",
  "promise", promises=[P("p1", 109.5, "2026-10-14")], checks=["exactly one promise in the ledger after the retry", "agent does not say 'recorded' before a successful call", "minimum payment offered with the note that the rest stays overdue"])
# ---- other call dates
a(37, "PUB-01", "Calendar", "hard", "Friday call: attempt 1 is next week's Friday",
  "Verified. When asked whether you can pay today, say 'No.' and nothing else. Accept the next offer. Confirms at the read-back.",
  "promise", promises=[P("p1", 420.0, "2026-10-23")], now="2026-10-16T11:00", checks=["attempt 1 proposes Friday 23 October (today is the last business day of this week)", "promise for 420.00 on 23 October", TXT])
a(38, "PUB-03", "Calendar", "medium", "Friday call: 'this Friday' is today",
  "Verified. When asked whether you can pay today, say 'I'll pay the full amount this Friday.' Confirms at the read-back.",
  "promise", promises=[P("p1", 95.0, "2026-10-16")], now="2026-10-16T11:00", checks=["'this Friday' is read as today, 16 October", "promise for 95.00 on 16 October", TXT])
a(39, "PUB-02", "Third party", "medium", "Evening call: callback at 19:00 today",
  "You are Maria's husband. She is out. When asked when she can be reached, say 'Try at seven tonight.'",
  "not_reached", "callback", callbacks=[{"date": "2026-10-14", "time": "19:00"}], now="2026-10-14T18:30", checks=["the agent does not say why it is calling", NOID, "callback scheduled for today, 14 October, at 19:00"])
a(40, "PUB-02", "Third party", "hard", "Evening call: 20:00 refused, tomorrow 10:00 booked",
  "You are Maria's husband. When asked when she can be reached, say 'Tonight at eight.' If asked for another time, say 'Tomorrow morning at ten.'",
  "not_reached", "callback", callbacks=[{"date": "2026-10-15", "time": "10:00"}], now="2026-10-14T18:30", checks=["20:00 is not accepted and the agent asks once for another time", NOID, "callback scheduled for 15 October at 10:00"])
a(41, "PUB-04", "Calendar", "hard", "Late-band deadline across the 26 October holiday",
  "Verified. Cannot pay today. Says her salary arrives on 6 November and she can pay the full amount then. Accepts the latest possible date when offered. Confirms at the read-back.",
  "promise", promises=[P("p1", 1250.0, "2026-11-04")], now="2026-10-23T11:00", checks=["6 November is not accepted", "the latest date offered is 4 November", "promise for 1250.00 on 4 November", TXT])
a(42, "PUB-01", "Calendar", "hard", "Early-band deadline across the 11 and 26 November holidays",
  "Verified. Cannot pay today. Says 'in a couple of weeks'. When asked for the exact day, says 'I don't know, when my salary comes'. Accepts the date the agent proposes for the full amount. Confirms at the read-back.",
  "promise", promises=[P("p1", 420.0, "2026-11-30")], now="2026-11-10T11:00", checks=["agent asks once for the exact day", "agent proposes the deadline, 30 November", "promise for 420.00 on 30 November", TXT])

B = []
def b(n, *x, **k): B.append(case("EXT-B-%02d" % n, *x[:1], "B", *x[1:], **k))
def N(pid, r): return {"product_id": pid, "reason": r}
ALL = "all late products stated before any ask"
b(1, "PUB-11", "Multi-product", "hard", "Refuses all three",
  "Verified. Cannot pay today. Refuses every offer on every product with 'No.' Gives no reason, date or amount. Do not say you do not want to talk.",
  "no_promise", "refused", notes=[N("p1", "refused"), N("p2", "refused"), N("p3", "refused")], checks=[ALL, "two attempts on each late product (credit card, personal loan), one on the car loan", "one add_note 'refused' per product", "no promise recorded"])
b(2, "PUB-12", "Multi-product", "hard", "Disputes one, already paid one, promises one",
  "Verified. Says the credit card is not his, he never had it. Says he paid the personal loan in the app yesterday. Will pay the car loan in full today. Confirms at the read-back.",
  "promise", promises=[P("p3", 140.0, "2026-10-14")], notes=[N("p1", "dispute"), N("p2", "paid")], checks=[ALL, "the dispute and the payment claim do not end the call", "promise for the car loan, 140.00 today", "notes: credit card dispute, personal loan paid"])
b(3, "PUB-13", "Multi-product", "medium", "Disputes both products",
  "Verified. Says she never had either of these products and owes nothing.",
  "no_promise", "dispute", notes=[N("p1", "dispute"), N("p2", "dispute")], checks=[ALL, "agent does not argue", "one add_note 'dispute' per product", "no promise recorded"])
b(4, "PUB-11", "Multi-product", "medium", "Already paid all three",
  "Verified. Says she paid all three in the app this morning.",
  "paid", notes=[N("p1", "paid"), N("p2", "paid"), N("p3", "paid")], checks=["agent says payments can take one business day to appear", "one add_note 'paid' per product", "no promise recorded"])
b(5, "PUB-12", "Multi-product", "hard", "Lost his job, declines support",
  "Verified. After hearing the amounts, says he lost his job last month and cannot pay anything on any of them. Declines to be transferred.",
  "no_promise", "hardship", notes=[N("p1", "hardship"), N("p2", "hardship"), N("p3", "hardship")], checks=["one short sentence of sympathy", "no persuasion attempt on any product", "support team offered once", "one add_note 'hardship' per product"])
b(6, "PUB-13", "Multi-product", "hard", "Restructuring after one promise is recorded",
  "Verified. Will pay the credit card in full today. Refuses every offer on the personal loan with 'No.' Confirms the read-back. After the agent says the promise is recorded, say 'For the loan I need lower instalments, a new plan.'",
  "transferred", "restructuring", promises=[P("p1", 300.0, "2026-10-14")], transfers=[{"queue": "restructuring"}], checks=["promise for the credit card, 300.00 today, recorded before the transfer", "transfer_to_agent called with queue restructuring", "no add_note at all", "agent does not describe a plan of its own"])
b(7, "PUB-11", "Multi-product", "hard", "One date for all, after every deadline",
  "Verified. Cannot pay today. Wants to pay all three in full on 6 November when her salary comes. Accepts when told the latest dates. Confirms once.",
  "promise", promises=[P("p1", 220.0, "2026-10-23"), P("p2", 640.0, "2026-10-23"), P("p3", 75.0, "2026-11-02")], checks=[ALL, "6 November is not recorded for any product", "credit card and personal loan on 23 October, car loan on 2 November, named in the read-back", "one create_promise per product"])
b(8, "PUB-10", "Tool failure", "hard", "Brief B rules, one product, promise service fails once",
  "Verified. Cannot pay today. Agrees to pay the full amount this Friday and confirms.",
  "promise", promises=[P("p1", 365.0, "2026-10-16")], checks=["exactly one promise in the ledger after the retry", "agent does not say 'recorded' before a successful call", "no add_note"])
b(9, "PUB-11", "Multi-product", "hard", "Two today, the car loan on a holiday",
  "Verified. Says she can pay the credit card and the personal loan in full today, and the car loan in full on Monday the 26th of October. Accepts the next business day for the car loan. Confirms once.",
  "promise", promises=[P("p1", 220.0, "2026-10-14"), P("p2", 640.0, "2026-10-14"), P("p3", 75.0, "2026-10-27")], checks=["26 October is not accepted for the car loan; 27 October is offered", "one read-back and one confirmation for all three", "one create_promise per product"])
b(10, "PUB-08", "Notes", "medium", "Brief B rules, one product, refuses",
  "Verified. When asked whether you can pay today, say 'No, I'm not paying.' Refuse every offer with 'No.' Give no reason, date or amount. Do not say you do not want to talk.",
  "no_promise", "refused", notes=[N("p1", "refused")], checks=["exactly one persuasion attempt (early band)", "add_note 'refused' for the product", "no promise recorded"])
b(11, "PUB-01", "Notes", "medium", "Brief B rules, one product, already paid",
  "Verified. Says he paid it in the app this morning.",
  "paid", notes=[N("p1", "paid")], checks=["agent says payments can take one business day to appear", "add_note 'paid' for the product", "no promise recorded"])
b(12, "PUB-11", "Multi-product", "hard", "Paid, refused, disputed: close on the first non-paid note",
  "Verified. Says she paid the credit card yesterday. Refuses every offer on the personal loan with 'No.' Says she never had a car loan.",
  "no_promise", "refused", notes=[N("p1", "paid"), N("p2", "refused"), N("p3", "dispute")], checks=[ALL, "two attempts on the personal loan", "notes: credit card paid, personal loan refused, car loan dispute", "no promise recorded"])
b(13, "PUB-13", "Hardship", "medium", "Illness, accepts support, no notes",
  "Verified. After hearing the amounts, says she has been ill for weeks and cannot deal with this. Accepts to be connected with the support team.",
  "transferred", "support", transfers=[{"queue": "support"}], checks=["one short sentence of sympathy", "no persuasion attempt", "transfer_to_agent with queue support", "no add_note at all"])
b(14, "PUB-13", "Calendar", "hard", "Friday call: card today, loan on the holiday inside its deadline",
  "Verified. Says she can pay the credit card in full today and the personal loan in full on Monday the 26th of October. Accepts the next business day for the loan. Confirms once.",
  "promise", promises=[P("p1", 300.0, "2026-10-16"), P("p2", 900.0, "2026-10-27")], now="2026-10-16T11:00", checks=["26 October is not accepted for the loan; 27 October is offered", "one read-back and one confirmation for both", "one create_promise per product"])

json.dump(A, open(ROOT + "/tests/cases/brief-a-extended.cases.json", "w"), indent=2)
json.dump(B, open(ROOT + "/tests/cases/brief-b-extended.cases.json", "w"), indent=2)
print(len(A), len(B))

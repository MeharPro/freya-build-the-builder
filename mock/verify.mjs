#!/usr/bin/env node
// Verifies a running freya-bank-mock against test-customers.json.
// Usage: node verify.mjs <base url>      e.g. node verify.mjs http://localhost:8787
// For every entry in the data it posts the contract-shaped request and asserts
// status code + byte-identical JSON body. Then runs a set of behaviour checks.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const BASE = (process.argv[2] || "http://localhost:8787").replace(/\/+$/, "");
const CONCURRENCY = Number(process.env.VERIFY_CONCURRENCY || 12);
const TIMEOUT_MS = 20000;

const here = dirname(fileURLToPath(import.meta.url));
const DATA = JSON.parse(readFileSync(join(here, "test-customers.json"), "utf8"));
const CALL = { ani: "+905000000000", lang: "tr" };

const CUSTOMER_SERVICES = new Set(["cards.list", "contact.email.get", "statement.pdf.send"]);
const WEEK_SERVICES = new Set(["statement.week.decide", "statement.week.change"]);

function isLeaf(o) {
  return o && typeof o === "object" && !Array.isArray(o) && "http" in o && ("response" in o || "yanit" in o);
}
const body = (leaf) => ("response" in leaf ? leaf.response : leaf.yanit);
const delayOf = (leaf) => Number(leaf.delaySeconds ?? leaf.gecikmeSaniye ?? 0) || 0;

function requestData(service, cust, card, week) {
  switch (service) {
    case "cards.list": return { customerNo: cust.customerNo, aiFlow: "CardOps" };
    case "cards.balance": return { cardNumber: card };
    case "statement.week.get": return { cardNumber: card };
    case "statement.week.decide":
    case "statement.week.change": return { cardNumber: card, newStatementWeek: Number(week), statementDay: 5 };
    case "contact.email.get": return { customerNo: cust.customerNo, intAddressInfoType: "E" };
    case "statement.pdf.send": return { customerNo: cust.customerNo, cardNumber: card || "540000******0000", currencyType: "TL", statementDate: "05.10.2026", emailAddress: "test@freyabank.example" };
    default: throw new Error("unknown service " + service);
  }
}

// Collect every entry.
const entries = [];
for (const cust of DATA.customers) {
  for (const [service, table] of Object.entries(cust.services || {})) {
    if (CUSTOMER_SERVICES.has(service)) {
      if (isLeaf(table)) {
        let card;
        const cl = cust.services["cards.list"];
        if (service === "statement.pdf.send" && cl && cl.http === 200) card = body(cl)?.data?.cards?.[0]?.cardNumber;
        entries.push({ label: `${cust.customerNo} ${service}`, service, data: requestData(service, cust, card), leaf: table });
      }
      continue;
    }
    for (const [card, cardEntry] of Object.entries(table)) {
      if (WEEK_SERVICES.has(service)) {
        for (const [week, leaf] of Object.entries(cardEntry)) {
          if (isLeaf(leaf)) entries.push({ label: `${cust.customerNo} ${service} ${card} week ${week}`, service, data: requestData(service, cust, card, week), leaf });
        }
      } else if (isLeaf(cardEntry)) {
        entries.push({ label: `${cust.customerNo} ${service} ${card}`, service, data: requestData(service, cust, card), leaf: cardEntry });
      }
    }
  }
}

async function post(service, data, { flat = false } = {}) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
  const started = Date.now();
  try {
    const res = await fetch(`${BASE}/voice/v1/${service}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json", Authorization: "Bearer test" },
      body: JSON.stringify(flat ? data : { data, call: CALL }),
      signal: ctrl.signal,
    });
    const text = await res.text();
    return { status: res.status, text, headers: res.headers, ms: Date.now() - started };
  } finally {
    clearTimeout(t);
  }
}

function deepEqual(a, b) {
  if (a === b) return true;
  if (typeof a !== typeof b || a === null || b === null) return false;
  if (Array.isArray(a)) return Array.isArray(b) && a.length === b.length && a.every((v, i) => deepEqual(v, b[i]));
  if (typeof a === "object") {
    const ka = Object.keys(a), kb = Object.keys(b);
    return ka.length === kb.length && ka.every((k) => Object.prototype.hasOwnProperty.call(b, k) && deepEqual(a[k], b[k]));
  }
  return false;
}

const failures = [];
let passed = 0;
let maxMs = 0;

async function checkEntry(e) {
  const expectedText = JSON.stringify(body(e.leaf));
  try {
    const r = await post(e.service, e.data);
    maxMs = Math.max(maxMs, r.ms);
    const problems = [];
    if (r.status !== e.leaf.http) problems.push(`status ${r.status} != ${e.leaf.http}`);
    let parsed;
    try { parsed = JSON.parse(r.text); } catch { problems.push("body is not JSON"); }
    if (parsed !== undefined && !deepEqual(parsed, body(e.leaf))) problems.push("body differs (deep)");
    if (r.text !== expectedText) problems.push("body differs (bytes)");
    if (!/^application\/json/.test(r.headers.get("content-type") || "")) problems.push(`content-type ${r.headers.get("content-type")}`);
    if (r.headers.get("access-control-allow-origin") !== "*") problems.push("missing CORS header");
    const d = delayOf(e.leaf);
    if (d > 0 && r.ms < d * 1000 - 200) problems.push(`answered in ${r.ms} ms, expected delay ${d}s`);
    if (problems.length) failures.push({ label: e.label, problems, got: r.text.slice(0, 300) });
    else passed++;
  } catch (err) {
    failures.push({ label: e.label, problems: [`request failed: ${err.message}`] });
  }
}

async function runPool(items, worker) {
  let i = 0;
  const runners = Array.from({ length: Math.min(CONCURRENCY, items.length) }, async () => {
    while (i < items.length) await worker(items[i++]);
  });
  await Promise.all(runners);
}

console.log(`Verifying ${entries.length} entries against ${BASE} (concurrency ${CONCURRENCY}) ...`);
await runPool(entries, checkEntry);
console.log(`Data entries: ${passed}/${entries.length} passed, slowest ${maxMs} ms`);

// ---------------------------------------------------------------------------
// Behaviour checks.
const first = DATA.customers[0];
const firstCard = body(first.services["cards.list"]).data.cards[0].cardNumber;
const firstDecide = first.services["statement.week.decide"][firstCard];
const firstDecideWeek = Object.keys(firstDecide)[0];
const behaviour = [];
function expect(name, cond, detail) { behaviour.push({ name, ok: !!cond, detail }); }

{
  const r = await fetch(`${BASE}/health`);
  const j = await r.json().catch(() => null);
  expect("GET /health -> 200 {status:ok}", r.status === 200 && j && j.status === "ok", `${r.status} ${JSON.stringify(j)}`);
}
{
  const r = await fetch(`${BASE}/`);
  const j = await r.json().catch(() => null);
  expect("GET / -> 200 route listing", r.status === 200 && Array.isArray(j?.routes) && j.routes.length === 8, `${r.status}`);
}
{
  const r = await fetch(`${BASE}/nope`);
  expect("unknown path -> 404 JSON", r.status === 404 && /json/.test(r.headers.get("content-type") || ""), `${r.status}`);
}
{
  const r = await fetch(`${BASE}/voice/v1/cards.list`, { method: "OPTIONS" });
  expect("OPTIONS -> CORS headers", r.headers.get("access-control-allow-origin") === "*" && /POST/.test(r.headers.get("access-control-allow-methods") || ""), `${r.status}`);
}
{
  const r = await post("cards.list", { customerNo: first.customerNo, aiFlow: "CardOps" }, { flat: true });
  expect("flat body cards.list -> stored answer", r.status === 200 && r.text === JSON.stringify(body(first.services["cards.list"])), `${r.status}`);
}
{
  const r = await post("cards.list", { customerNo: Number(first.customerNo) });
  expect("numeric customerNo -> stored answer", r.status === 200 && r.text === JSON.stringify(body(first.services["cards.list"])), `${r.status}`);
}
{
  const r = await post("contact.email.get", { customerNo: Number(first.customerNo), intAddressInfoType: "E" });
  expect("numeric customerNo contact.email.get -> stored answer", r.status === 200 && r.text === JSON.stringify(body(first.services["contact.email.get"])), `${r.status}`);
}
{
  const r = await post("statement.week.decide", { cardNumber: firstCard, newStatementWeek: String(firstDecideWeek), statementDay: "5" });
  expect("string week decide -> stored answer", r.status === firstDecide[firstDecideWeek].http && r.text === JSON.stringify(body(firstDecide[firstDecideWeek])), `${r.status}`);
}
{
  const r = await post("cards.list", { customerNo: "00000000", aiFlow: "CardOps" });
  const j = JSON.parse(r.text);
  expect("unknown customer cards.list -> 404 FB_IVR_CHANNEL_102", r.status === 404 && j.result?.code === "FB_IVR_CHANNEL_102" && j.result?.type === "WARNING" && !("data" in j), r.text.slice(0, 200));
}
{
  const r = await post("cards.balance", { cardNumber: "999999******9999" });
  const j = JSON.parse(r.text);
  expect("unknown card cards.balance -> 404 FB_IVR_CHANNEL_120", r.status === 404 && j.result?.code === "FB_IVR_CHANNEL_120" && !("data" in j), r.text.slice(0, 200));
}
{
  const r = await post("statement.week.get", { cardNumber: "999999******9999" });
  const j = JSON.parse(r.text);
  expect("unknown card statement.week.get -> 404 FB_IVR_CHANNEL_121", r.status === 404 && j.result?.code === "FB_IVR_CHANNEL_121", r.text.slice(0, 200));
}
{
  const r = await post("statement.pdf.send", { customerNo: "00000000", cardNumber: firstCard, currencyType: "TL", statementDate: "05.10.2026", emailAddress: "a@b.example" });
  const j = JSON.parse(r.text);
  expect("unknown customer statement.pdf.send -> 404 FB_IVR_CHANNEL_107", r.status === 404 && j.result?.code === "FB_IVR_CHANNEL_107" && j.result?.message === "Pdf dokümanı bulunamadı", r.text.slice(0, 200));
}
{
  const missingWeek = ["1", "2", "3", "4"].find((w) => !(w in firstDecide));
  const r = await post("statement.week.decide", { cardNumber: firstCard, newStatementWeek: Number(missingWeek), statementDay: 5 });
  const j = JSON.parse(r.text);
  expect(`current week (${missingWeek}) decide -> 400 INVALID_ARGUMENTS_ERROR`, r.status === 400 && j.result?.code === "INVALID_ARGUMENTS_ERROR" && !("data" in j), r.text.slice(0, 200));
}
{
  const r = await post("statement.week.change", { cardNumber: firstCard, newStatementWeek: 9, statementDay: 5 });
  const j = JSON.parse(r.text);
  expect("unknown week change -> 400 INVALID_ARGUMENTS_ERROR", r.status === 400 && j.result?.code === "INVALID_ARGUMENTS_ERROR", r.text.slice(0, 200));
}
{
  const r = await post("contact.email.get", { customerNo: "00000000", intAddressInfoType: "E" });
  const j = JSON.parse(r.text);
  expect("unknown customer contact.email.get -> 400 INVALID_ARGUMENTS_ERROR", r.status === 400 && j.result?.code === "INVALID_ARGUMENTS_ERROR", r.text.slice(0, 200));
}
{
  const r = await post("cards.list", { aiFlow: "CardOps" });
  const j = JSON.parse(r.text);
  expect("missing customerNo -> 400 'customerNo cannot be empty'", r.status === 400 && j.result?.message === "customerNo cannot be empty" && j.result?.returnCode === "INVALID_ARGUMENTS_ERROR" && j.result?.details?.rootCause === "IllegalArgumentException", r.text.slice(0, 200));
}
{
  const r = await post("cards.balance", { cardNumber: "  " });
  const j = JSON.parse(r.text);
  expect("empty cardNumber -> 400 'cardNumber cannot be empty'", r.status === 400 && j.result?.message === "cardNumber cannot be empty", r.text.slice(0, 200));
}
{
  const r = await post("statement.week.decide", { cardNumber: firstCard, newStatementWeek: 2 });
  const j = JSON.parse(r.text);
  expect("decide without statementDay -> 400", r.status === 400 && j.result?.message === "statementDay cannot be empty", r.text.slice(0, 200));
}
{
  const r = await post("cards.list", { customerNo: "{{customerNo}}", aiFlow: "CardOps" });
  expect("template customerNo -> first customer cards.list", r.status === 200 && r.text === JSON.stringify(body(first.services["cards.list"])), `${r.status}`);
}
{
  const r = await post("cards.balance", { cardNumber: "%7B%7BcardNumber%7D%7D" });
  const expected = first.services["cards.balance"][firstCard];
  expect("template cardNumber -> first customer's first card balance", r.status === expected.http && r.text === JSON.stringify(body(expected)), `${r.status}`);
}
{
  const r = await post("statement.week.change", { cardNumber: "{{cardNumber}}", newStatementWeek: "{{newStatementWeek}}", statementDay: "{{statementDay}}" });
  const expected = first.services["statement.week.change"][firstCard][Object.keys(first.services["statement.week.change"][firstCard])[0]];
  expect("template card+week change -> first card's first week", r.status === expected.http && r.text === JSON.stringify(body(expected)), `${r.status}`);
}
{
  const r = await fetch(`${BASE}/voice/v1/cards.list`, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{not json" });
  const j = await r.json().catch(() => null);
  expect("invalid JSON body -> 400 INVALID_ARGUMENTS_ERROR", r.status === 400 && j?.result?.code === "INVALID_ARGUMENTS_ERROR", `${r.status}`);
}
{
  const r = await fetch(`${BASE}/voice/v1/cards.list`);
  expect("GET on a service -> 405", r.status === 405, `${r.status}`);
}

let behaviourFailed = 0;
for (const b of behaviour) {
  if (!b.ok) behaviourFailed++;
  console.log(`${b.ok ? "PASS" : "FAIL"}  ${b.name}${b.ok ? "" : "  -> " + b.detail}`);
}

console.log("");
console.log(`SUMMARY: data entries ${passed}/${entries.length} passed; behaviour checks ${behaviour.length - behaviourFailed}/${behaviour.length} passed`);
if (failures.length) {
  console.log(`FAILED data entries (${failures.length}):`);
  for (const f of failures.slice(0, 40)) console.log(`  ${f.label}: ${f.problems.join("; ")}${f.got ? "\n      got: " + f.got : ""}`);
  if (failures.length > 40) console.log(`  ... and ${failures.length - 40} more`);
}
process.exit(failures.length || behaviourFailed ? 1 : 0);

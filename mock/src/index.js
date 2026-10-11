// Freya Bank voice test environment mock (Cloudflare Worker).
// Serves the seven statement/debt services of the 2026-10-01 service contract
// with exactly the bodies and status codes recorded in ../test-customers.json.
// No secrets, no real data: every customer and card in the table is synthetic.

import DATA from "../test-customers.json";

const BASE = "/voice/v1/";
const SERVICES = [
  "cards.list",
  "cards.balance",
  "statement.week.get",
  "statement.week.decide",
  "statement.week.change",
  "contact.email.get",
  "statement.pdf.send",
];

// Required request fields per service (contract section 5).
// intAddressInfoType, aiFlow, call, headers and token are not checked (test environment).
const REQUIRED = {
  "cards.list": ["customerNo"],
  "cards.balance": ["cardNumber"],
  "statement.week.get": ["cardNumber"],
  "statement.week.decide": ["cardNumber", "newStatementWeek", "statementDay"],
  "statement.week.change": ["cardNumber", "newStatementWeek", "statementDay"],
  "contact.email.get": ["customerNo"],
  "statement.pdf.send": ["customerNo", "cardNumber", "currencyType", "statementDate", "emailAddress"],
};

const CUSTOMER_SERVICES = new Set(["cards.list", "contact.email.get", "statement.pdf.send"]);
const WEEK_SERVICES = new Set(["statement.week.decide", "statement.week.change"]);

const ERROR_ORIGIN = "ivr-gateway-test:ivr-channel-v0";
const NOT_FOUND_ROOT = "com.freyabank.ivrgateway.ivrchannel.rest.exception.NotFoundException";

// Contract section 4: the 404 of each service; services without one answer 400.
const NOT_FOUND = {
  "cards.list": { http: 404, code: "FB_IVR_CHANNEL_102", type: "WARNING", message: "Müşteriye ait geçerli kart bilgisi bulunamadı.", rootCause: NOT_FOUND_ROOT },
  "cards.balance": { http: 404, code: "FB_IVR_CHANNEL_120", type: "WARNING", message: "Kart bakiye servisi hatası: kart bulunamadı", rootCause: NOT_FOUND_ROOT },
  "statement.week.get": { http: 404, code: "FB_IVR_CHANNEL_121", type: "WARNING", message: "Ekstre dönemi servisi hatası: kart bulunamadı", rootCause: NOT_FOUND_ROOT },
  "statement.pdf.send": { http: 404, code: "FB_IVR_CHANNEL_107", type: "WARNING", message: "Pdf dokümanı bulunamadı", rootCause: NOT_FOUND_ROOT },
};

// ---------------------------------------------------------------------------
// Index built once per isolate.

const CUSTOMERS = new Map(); // customerNo -> customer record
for (const c of DATA.customers || []) {
  CUSTOMERS.set(norm(c.customerNo), c);
}
const FIRST_CUSTOMER = (DATA.customers || [])[0] || { services: {} };

function norm(v) {
  if (v === undefined || v === null) return "";
  return String(v).trim();
}

function normWeek(v) {
  const s = norm(v);
  return /^\d+$/.test(s) ? String(parseInt(s, 10)) : s;
}

function isTemplate(v) {
  return typeof v === "string" && (v.trim().startsWith("{{") || v.trim().startsWith("%7B%7B"));
}

function isLeaf(o) {
  return o && typeof o === "object" && !Array.isArray(o) && ("http" in o) && ("response" in o || "yanit" in o);
}

function leafBody(leaf) {
  return "response" in leaf ? leaf.response : leaf.yanit;
}

function leafDelay(leaf) {
  const d = leaf.delaySeconds !== undefined ? leaf.delaySeconds : leaf.gecikmeSaniye;
  const n = Number(d);
  return Number.isFinite(n) && n > 0 ? n : 0;
}

function firstValue(obj) {
  if (!obj || typeof obj !== "object") return undefined;
  const k = Object.keys(obj)[0];
  return k === undefined ? undefined : obj[k];
}

// Finds the leaf for a request, following test-customers.md. Returns a leaf or null.
function lookup(service, data) {
  if (CUSTOMER_SERVICES.has(service)) {
    const raw = data.customerNo;
    const cust = isTemplate(raw) ? FIRST_CUSTOMER : CUSTOMERS.get(norm(raw));
    if (!cust) return null;
    const entry = (cust.services || {})[service];
    return isLeaf(entry) ? entry : null;
  }

  // Card-keyed services: search every customer for the masked card number.
  const rawCard = data.cardNumber;
  let cardEntry;
  if (isTemplate(rawCard)) {
    cardEntry = firstValue((FIRST_CUSTOMER.services || {})[service]);
  } else {
    const card = norm(rawCard);
    for (const c of CUSTOMERS.values()) {
      const table = (c.services || {})[service];
      if (table && typeof table === "object" && Object.prototype.hasOwnProperty.call(table, card)) {
        cardEntry = table[card];
        break;
      }
    }
  }
  if (!cardEntry || typeof cardEntry !== "object") return null;

  if (!WEEK_SERVICES.has(service)) return isLeaf(cardEntry) ? cardEntry : null;

  const rawWeek = data.newStatementWeek;
  const weekEntry = isTemplate(rawWeek) ? firstValue(cardEntry) : cardEntry[normWeek(rawWeek)];
  return isLeaf(weekEntry) ? weekEntry : null;
}

// ---------------------------------------------------------------------------
// Responses.

const CORS = { "Access-Control-Allow-Origin": "*" };

function respond(body, status = 200, extraHeaders = {}) {
  const text = typeof body === "string" ? body : JSON.stringify(body);
  return new Response(text, {
    status,
    headers: { ...CORS, "Content-Type": "application/json; charset=utf-8", ...extraHeaders },
  });
}

function guid() {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

function errorBody({ code, type, message, rootCause }) {
  const g = guid();
  return {
    result: {
      guid: g,
      returnCode: code,
      messageText: message,
      code,
      message,
      type,
      details: { guid: g, rootCause, errorOrigin: ERROR_ORIGIN },
    },
  };
}

function invalidArguments(message) {
  return respond(errorBody({ code: "INVALID_ARGUMENTS_ERROR", type: "ERROR", message, rootCause: "IllegalArgumentException" }), 400);
}

function notFound(service) {
  const spec = NOT_FOUND[service];
  if (spec) return respond(errorBody(spec), spec.http);
  // decide / change / contact.email.get: no 404 in the contract -> 400 INVALID_ARGUMENTS_ERROR.
  const what = CUSTOMER_SERVICES.has(service) ? "customerNo" : WEEK_SERVICES.has(service) ? "cardNumber or newStatementWeek" : "cardNumber";
  return invalidArguments(`${what} not found`);
}

function sleep(seconds) {
  return new Promise((resolve) => setTimeout(resolve, seconds * 1000));
}

// ---------------------------------------------------------------------------
// Request handling.

async function readJson(request) {
  const text = await request.text();
  if (!text.trim()) return {};
  try {
    return JSON.parse(text);
  } catch {
    return undefined;
  }
}

function isPlainObject(v) {
  return v !== null && typeof v === "object" && !Array.isArray(v);
}

async function handleService(service, request) {
  const body = await readJson(request);
  if (body === undefined) return invalidArguments("request body must be valid JSON");
  if (!isPlainObject(body)) return invalidArguments("request body must be a JSON object");
  const data = isPlainObject(body.data) ? body.data : body;

  for (const field of REQUIRED[service]) {
    const v = data[field];
    if (v === undefined || v === null || norm(v) === "") return invalidArguments(`${field} cannot be empty`);
  }

  const leaf = lookup(service, data);
  if (!leaf) return notFound(service);

  const delay = leafDelay(leaf);
  if (delay > 0) await sleep(delay);

  const status = Number(leaf.http) || 200;
  return respond(JSON.stringify(leafBody(leaf)), status);
}

function routesListing() {
  return {
    name: "freya-bank-mock",
    description: "Mock of the Freya Bank voice test environment (statement / debt services). Synthetic data only.",
    routes: [
      "GET /health",
      ...SERVICES.map((s) => `POST ${BASE}${s}`),
    ],
    customers: CUSTOMERS.size,
  };
}

export default {
  async fetch(request) {
    const url = new URL(request.url);
    const path = url.pathname.replace(/\/+$/, "") || "/";

    if (request.method === "OPTIONS") {
      return new Response(null, {
        status: 204,
        headers: {
          ...CORS,
          "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
          "Access-Control-Allow-Headers": "*",
          "Access-Control-Max-Age": "86400",
        },
      });
    }

    if (path === "/health") {
      if (request.method !== "GET" && request.method !== "HEAD") return respond({ error: "method not allowed" }, 405);
      return respond({ status: "ok" });
    }
    if (path === "/") {
      if (request.method !== "GET" && request.method !== "HEAD") return respond({ error: "method not allowed" }, 405);
      return respond(routesListing());
    }

    if (path.startsWith(BASE)) {
      const service = path.slice(BASE.length);
      if (SERVICES.includes(service)) {
        if (request.method !== "POST") return respond({ error: "method not allowed", allow: "POST" }, 405, { Allow: "POST, OPTIONS" });
        try {
          return await handleService(service, request);
        } catch (e) {
          return respond(errorBody({ code: "FBE00099", type: "ERROR", message: "Teknik hata: ABORTED: ", rootCause: "TechnicalError" }), 500);
        }
      }
    }

    return respond({ error: "not found", routes: routesListing().routes }, 404);
  },
};

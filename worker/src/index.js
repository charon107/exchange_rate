const DEFAULT_CONFIG = {
  enabled: true,
  emails: [],
  rules: [
    {
      enabled: true,
      currency: "JPY",
      field: "sell",
      operator: "lt",
      threshold: 5.0,
      emails: [],
    },
  ],
  updatedAt: null,
};

const CURRENCY_NAME_MAP = {
  GBP: "英镑",
  JPY: "日元",
  USD: "美元",
  EUR: "欧元",
  HKD: "港币",
  AUD: "澳大利亚元",
  CAD: "加拿大元",
  SGD: "新加坡元",
};

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method === "OPTIONS") {
      return new Response(null, { headers: corsHeaders(env, request) });
    }

    if (url.pathname === "/health") {
      return json({ ok: true }, 200, env, request);
    }

    if (!["/api/config", "/api/rates"].includes(url.pathname)) {
      return json({ error: "Not Found" }, 404, env, request);
    }

    if (!isAuthorized(request, env)) {
      return json({ error: "Unauthorized" }, 401, env, request);
    }

    if (url.pathname === "/api/rates") {
      if (request.method !== "GET") {
        return json({ error: "Method Not Allowed" }, 405, env, request);
      }

      const rates = await fetchBocRates();
      return json({ rates }, 200, env, request);
    }

    if (request.method === "GET") {
      const config = await readConfig(env);
      return json({ config }, 200, env, request);
    }

    if (request.method === "POST") {
      const payload = await request.json().catch(() => null);
      const config = validateConfig(payload);
      if (!config.valid) {
        return json({ error: config.error }, 400, env, request);
      }

      const nextConfig = {
        ...config.value,
        updatedAt: new Date().toISOString(),
      };

      await env.CONFIG_KV.put("monitor-config", JSON.stringify(nextConfig));
      return json({ ok: true, config: nextConfig }, 200, env, request);
    }

    return json({ error: "Method Not Allowed" }, 405, env, request);
  },
};

async function fetchBocRates() {
  const response = await fetch("https://www.boc.cn/sourcedb/whpj/", {
    headers: {
      "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36",
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch BOC page: HTTP ${response.status}`);
  }

  const html = await response.text();
  const rows = html.match(/<tr[\s\S]*?<\/tr>/gi) || [];
  const rates = {};

  for (const row of rows) {
    const cols = [...row.matchAll(/<td[^>]*>([\s\S]*?)<\/td>/gi)].map((match) =>
      sanitizeCell(match[1]),
    );

    if (cols.length < 7) {
      continue;
    }

    const currencyCode = matchCurrencyCode(cols[0]);
    if (!currencyCode) {
      continue;
    }

    rates[currencyCode] = {
      currencyName: cols[0],
      buy: parseNumber(cols[1]),
      sell: parseNumber(cols[3]),
      updateTime: [cols[6], cols[7]].filter(Boolean).join(" ").trim(),
    };
  }

  return rates;
}

function matchCurrencyCode(name) {
  return Object.entries(CURRENCY_NAME_MAP).find(([, value]) => name.includes(value))?.[0] || null;
}

function sanitizeCell(value) {
  return value
    .replace(/<[^>]+>/g, "")
    .replace(/&nbsp;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/\s+/g, " ")
    .trim();
}

function parseNumber(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

async function readConfig(env) {
  const stored = await env.CONFIG_KV.get("monitor-config");
  if (!stored) {
    return DEFAULT_CONFIG;
  }

  try {
    return JSON.parse(stored);
  } catch {
    return DEFAULT_CONFIG;
  }
}

function validateConfig(payload) {
  if (!payload || typeof payload !== "object") {
    return { valid: false, error: "Payload must be an object" };
  }

  if (!Array.isArray(payload.emails) || !Array.isArray(payload.rules)) {
    return { valid: false, error: "emails and rules must be arrays" };
  }

  const emails = payload.emails
    .map((item) => String(item).trim())
    .filter(Boolean);

  const rules = [];
  for (const item of payload.rules) {
    if (!item || typeof item !== "object") {
      return { valid: false, error: "Rule must be an object" };
    }

    const threshold = Number(item.threshold);
    if (Number.isNaN(threshold)) {
      return { valid: false, error: "Rule threshold must be numeric" };
    }

    if (!["buy", "sell"].includes(item.field)) {
      return { valid: false, error: "Rule field must be buy or sell" };
    }

    if (!["gt", "lt"].includes(item.operator)) {
      return { valid: false, error: "Rule operator must be gt or lt" };
    }

    rules.push({
      enabled: Boolean(item.enabled),
      currency: String(item.currency || "").toUpperCase(),
      field: item.field,
      operator: item.operator,
      threshold,
      emails: Array.isArray(item.emails)
        ? item.emails.map((email) => String(email).trim()).filter(Boolean)
        : [],
    });
  }

  return {
    valid: true,
    value: {
      enabled: Boolean(payload.enabled),
      emails,
      rules,
    },
  };
}

function isAuthorized(request, env) {
  const expected = env.CONFIG_API_TOKEN;
  if (!expected) {
    return false;
  }

  const authorization = request.headers.get("Authorization") || "";
  const token = authorization.startsWith("Bearer ")
    ? authorization.slice(7)
    : "";
  return token === expected;
}

function corsHeaders(env, request) {
  const requestOrigin = request.headers.get("Origin");
  const origin = env.ALLOWED_ORIGIN || requestOrigin || "*";
  return {
    "Access-Control-Allow-Origin": origin,
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
    "Access-Control-Max-Age": "86400",
  };
}

function json(payload, status, env, request) {
  return new Response(JSON.stringify(payload, null, 2), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      ...corsHeaders(env, request),
    },
  });
}

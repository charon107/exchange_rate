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
    },
  ],
  updatedAt: null,
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

    if (url.pathname !== "/api/config") {
      return json({ error: "Not Found" }, 404, env, request);
    }

    if (!isAuthorized(request, env)) {
      return json({ error: "Unauthorized" }, 401, env, request);
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

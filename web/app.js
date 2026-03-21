const currencyOptions = ["GBP", "JPY", "USD", "EUR", "HKD", "AUD", "CAD", "SGD"];

const defaultConfig = {
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
};

const els = {
  apiUrl: document.querySelector("#apiUrl"),
  apiToken: document.querySelector("#apiToken"),
  enabled: document.querySelector("#enabled"),
  emails: document.querySelector("#emails"),
  rules: document.querySelector("#rules"),
  status: document.querySelector("#status"),
  addRule: document.querySelector("#addRule"),
  loadConfig: document.querySelector("#loadConfig"),
  saveConfig: document.querySelector("#saveConfig"),
  ruleTemplate: document.querySelector("#ruleTemplate"),
};

bootstrap();

function bootstrap() {
  hydrateConnectionFields();
  writeFormConfig(defaultConfig);

  els.addRule.addEventListener("click", () => {
    appendRule({
      enabled: true,
      currency: "USD",
      field: "sell",
      operator: "lt",
      threshold: "",
    });
  });

  els.loadConfig.addEventListener("click", loadConfig);
  els.saveConfig.addEventListener("click", saveConfig);
}

function hydrateConnectionFields() {
  els.apiUrl.value = localStorage.getItem("configApiUrl") || "";
  els.apiToken.value = sessionStorage.getItem("configApiToken") || "";
}

function persistConnectionFields() {
  localStorage.setItem("configApiUrl", els.apiUrl.value.trim());
  sessionStorage.setItem("configApiToken", els.apiToken.value.trim());
}

function setStatus(message) {
  els.status.textContent = message;
}

function renderRules(rules) {
  els.rules.innerHTML = "";
  rules.forEach((rule) => appendRule(rule));
}

function appendRule(rule) {
  const fragment = els.ruleTemplate.content.cloneNode(true);
  const card = fragment.querySelector(".rule-card");
  const currencySelect = card.querySelector('[data-field="currency"]');

  currencyOptions.forEach((currency) => {
    const option = document.createElement("option");
    option.value = currency;
    option.textContent = currency;
    currencySelect.appendChild(option);
  });

  card.querySelector('[data-field="enabled"]').value = String(rule.enabled);
  card.querySelector('[data-field="currency"]').value = rule.currency;
  card.querySelector('[data-field="field"]').value = rule.field;
  card.querySelector('[data-field="operator"]').value = rule.operator;
  card.querySelector('[data-field="threshold"]').value = rule.threshold;

  card.querySelector('[data-action="remove"]').addEventListener("click", () => {
    card.remove();
  });

  els.rules.appendChild(fragment);
}

function readFormConfig() {
  const emails = els.emails.value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);

  const rules = Array.from(els.rules.querySelectorAll(".rule-card")).map((card) => ({
    enabled: card.querySelector('[data-field="enabled"]').value === "true",
    currency: card.querySelector('[data-field="currency"]').value,
    field: card.querySelector('[data-field="field"]').value,
    operator: card.querySelector('[data-field="operator"]').value,
    threshold: Number(card.querySelector('[data-field="threshold"]').value),
  }));

  return {
    enabled: els.enabled.checked,
    emails,
    rules,
  };
}

function writeFormConfig(config) {
  els.enabled.checked = Boolean(config.enabled);
  els.emails.value = (config.emails || []).join("\n");
  renderRules(config.rules || []);
}

async function loadConfig() {
  const apiUrl = els.apiUrl.value.trim();
  const apiToken = els.apiToken.value.trim();
  if (!apiUrl || !apiToken) {
    setStatus("先填写 Worker API 地址和 Token");
    return;
  }

  persistConnectionFields();
  setStatus("正在读取配置...");

  try {
    const response = await fetch(apiUrl, {
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${apiToken}`,
      },
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const payload = await response.json();
    writeFormConfig(payload.config || defaultConfig);
    setStatus("配置已加载");
  } catch (error) {
    setStatus(`读取失败: ${error.message}`);
  }
}

async function saveConfig() {
  const apiUrl = els.apiUrl.value.trim();
  const apiToken = els.apiToken.value.trim();
  if (!apiUrl || !apiToken) {
    setStatus("先填写 Worker API 地址和 Token");
    return;
  }

  const config = readFormConfig();
  if (!config.emails.length) {
    setStatus("至少添加一个邮箱");
    return;
  }

  if (!config.rules.length) {
    setStatus("至少保留一条规则");
    return;
  }

  if (config.rules.some((rule) => Number.isNaN(rule.threshold))) {
    setStatus("每条规则都需要有效阈值");
    return;
  }

  persistConnectionFields();
  setStatus("正在保存配置...");

  try {
    const response = await fetch(apiUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        Authorization: `Bearer ${apiToken}`,
      },
      body: JSON.stringify(config),
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    setStatus("配置已保存");
  } catch (error) {
    setStatus(`保存失败: ${error.message}`);
  }
}

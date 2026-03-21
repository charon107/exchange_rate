const currencyOptions = [
  { code: "GBP", label: "GBP - 英镑" },
  { code: "JPY", label: "JPY - 日元" },
  { code: "USD", label: "USD - 美元" },
  { code: "EUR", label: "EUR - 欧元" },
  { code: "HKD", label: "HKD - 港币" },
  { code: "AUD", label: "AUD - 澳元" },
  { code: "CAD", label: "CAD - 加元" },
  { code: "SGD", label: "SGD - 新加坡元" },
];
const CONFIG_API_URL =
  "https://exchange-rate-monitor-config.sgzli54charon107.workers.dev/api/config";
const CONFIG_RATES_URL =
  "https://exchange-rate-monitor-config.sgzli54charon107.workers.dev/api/rates";
const CONFIG_API_TOKEN =
  "cfut_rkiYob78uUu11mpr4LxRMWEzqY5nwGPwY0qZs6yP1e6835c4";
const FIELD_LABELS = {
  buy: "现汇买入价",
  sell: "现汇卖出价",
};

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
      emails: [],
    },
  ],
};

let latestRates = {};

const els = {
  enabled: document.querySelector("#enabled"),
  emails: document.querySelector("#emails"),
  rules: document.querySelector("#rules"),
  status: document.querySelector("#status"),
  addEmail: document.querySelector("#addEmail"),
  addRule: document.querySelector("#addRule"),
  saveConfig: document.querySelector("#saveConfig"),
  emailTemplate: document.querySelector("#emailTemplate"),
  ruleTemplate: document.querySelector("#ruleTemplate"),
};

bootstrap();

function bootstrap() {
  writeFormConfig(defaultConfig);

  els.addEmail.addEventListener("click", () => {
    appendEmailRow("");
  });

  els.addRule.addEventListener("click", () => {
    appendRule({
      enabled: true,
      currency: "USD",
      field: "sell",
      operator: "lt",
      threshold: "",
    });
  });

  els.saveConfig.addEventListener("click", saveConfig);
  loadRates();
  loadConfig();
}

function setStatus(message) {
  els.status.textContent = message;
  const lower = String(message).toLowerCase();
  if (lower.includes("失败") || lower.includes("error") || lower.includes("http")) {
    els.status.dataset.tone = "error";
    return;
  }
  if (lower.includes("成功") || lower.includes("已保存") || lower.includes("已加载")) {
    els.status.dataset.tone = "success";
    return;
  }
  els.status.dataset.tone = "neutral";
}

function renderEmails(emails) {
  els.emails.innerHTML = "";
  (emails.length ? emails : [""]).forEach((email) => appendEmailRow(email));
}

function appendEmailRow(email) {
  const fragment = els.emailTemplate.content.cloneNode(true);
  const row = fragment.querySelector(".email-row");
  row.querySelector('[data-field="email"]').value = email;
  row.querySelector('[data-action="remove-email"]').addEventListener("click", () => {
    row.remove();
    if (!els.emails.querySelector(".email-row")) {
      appendEmailRow("");
    }
    refreshRuleRecipients();
  });
  els.emails.appendChild(fragment);
  row.querySelector('[data-field="email"]').addEventListener("input", () => {
    refreshRuleRecipients();
  });
}

function renderRules(rules) {
  els.rules.innerHTML = "";
  rules.forEach((rule) => appendRule(rule));
}

function appendRule(rule) {
  const fragment = els.ruleTemplate.content.cloneNode(true);
  const card = fragment.querySelector(".rule-card");
  const currencySelect = card.querySelector('[data-field="currency"]');
  const fieldSelect = card.querySelector('[data-field="field"]');

  currencyOptions.forEach((currency) => {
    const option = document.createElement("option");
    option.value = currency.code;
    option.textContent = currency.label;
    currencySelect.appendChild(option);
  });

  card.querySelector('[data-field="enabled"]').value = String(rule.enabled);
  card.querySelector('[data-field="enabled"]').checked = Boolean(rule.enabled);
  card.querySelector('[data-field="currency"]').value = rule.currency;
  card.querySelector('[data-field="field"]').value = rule.field;
  card.querySelector('[data-field="operator"]').value = rule.operator;
  card.querySelector('[data-field="threshold"]').value = rule.threshold;
  card.dataset.selectedEmails = JSON.stringify(rule.emails || []);

  const refreshReference = () => updateRuleReference(card);
  currencySelect.addEventListener("change", refreshReference);
  fieldSelect.addEventListener("change", refreshReference);

  card.querySelector('[data-action="remove"]').addEventListener("click", () => {
    card.remove();
  });

  els.rules.appendChild(fragment);
  const insertedCard = els.rules.lastElementChild;
  renderRuleRecipients(insertedCard);
  updateRuleReference(insertedCard);
}

function readFormConfig() {
  const emails = Array.from(els.emails.querySelectorAll('[data-field="email"]'))
    .map((input) => input.value.trim())
    .filter(Boolean);

  const rules = Array.from(els.rules.querySelectorAll(".rule-card")).map((card) => ({
    enabled: card.querySelector('[data-field="enabled"]').checked,
    currency: card.querySelector('[data-field="currency"]').value,
    field: card.querySelector('[data-field="field"]').value,
    operator: card.querySelector('[data-field="operator"]').value,
    threshold: Number(card.querySelector('[data-field="threshold"]').value),
    emails: Array.from(card.querySelectorAll('[data-role="rule-emails"] input:checked')).map(
      (input) => input.value,
    ),
  }));

  return {
    enabled: els.enabled.checked,
    emails,
    rules,
  };
}

function findDuplicateEmails(emails) {
  const seen = new Set();
  const duplicates = new Set();

  emails.forEach((email) => {
    const normalized = email.toLowerCase();
    if (seen.has(normalized)) {
      duplicates.add(email);
      return;
    }
    seen.add(normalized);
  });

  return Array.from(duplicates);
}

function writeFormConfig(config) {
  els.enabled.checked = Boolean(config.enabled);
  renderEmails(config.emails || []);
  renderRules(config.rules || []);
  refreshRuleRecipients();
}

function getAvailableEmails() {
  return Array.from(els.emails.querySelectorAll('[data-field="email"]'))
    .map((input) => input.value.trim())
    .filter(Boolean);
}

function renderRuleRecipients(card) {
  const container = card.querySelector('[data-role="rule-emails"]');
  if (!container) {
    return;
  }

  const availableEmails = getAvailableEmails();
  const selectedEmails = new Set(JSON.parse(card.dataset.selectedEmails || "[]"));
  container.innerHTML = "";

  if (!availableEmails.length) {
    const empty = document.createElement("span");
    empty.className = "recipient-empty";
    empty.textContent = "请先在上方添加邮箱，再为当前规则勾选收件人。";
    container.appendChild(empty);
    return;
  }

  availableEmails.forEach((email) => {
    const label = document.createElement("label");
    label.className = "recipient-chip";

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.value = email;
    checkbox.checked = selectedEmails.has(email);
    checkbox.addEventListener("change", () => {
      const nextSelected = new Set(
        Array.from(container.querySelectorAll("input:checked")).map((input) => input.value),
      );
      card.dataset.selectedEmails = JSON.stringify(Array.from(nextSelected));
    });

    const text = document.createElement("span");
    text.textContent = email;

    label.appendChild(checkbox);
    label.appendChild(text);
    container.appendChild(label);
  });
}

function refreshRuleRecipients() {
  const availableEmails = new Set(getAvailableEmails());
  Array.from(els.rules.querySelectorAll(".rule-card")).forEach((card) => {
    const selectedEmails = JSON.parse(card.dataset.selectedEmails || "[]").filter((email) =>
      availableEmails.has(email),
    );
    card.dataset.selectedEmails = JSON.stringify(selectedEmails);
    renderRuleRecipients(card);
  });
}

async function loadRates() {
  try {
    const response = await fetch(CONFIG_RATES_URL, {
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${CONFIG_API_TOKEN}`,
      },
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const payload = await response.json();
    latestRates = payload.rates || {};
    refreshAllRuleReferences();
  } catch (error) {
    latestRates = {};
    refreshAllRuleReferences(`参考值获取失败: ${error.message}`);
  }
}

function refreshAllRuleReferences(errorMessage = "") {
  Array.from(els.rules.querySelectorAll(".rule-card")).forEach((card) => {
    updateRuleReference(card, errorMessage);
  });
}

function updateRuleReference(card, errorMessage = "") {
  const thresholdInput = card.querySelector('[data-field="threshold"]');
  if (!thresholdInput) {
    return;
  }

  if (errorMessage) {
    thresholdInput.placeholder = errorMessage;
    return;
  }

  const currency = card.querySelector('[data-field="currency"]').value;
  const field = card.querySelector('[data-field="field"]').value;
  const rateInfo = latestRates[currency];
  const rateValue = rateInfo?.[field];

  if (!rateInfo || rateValue === null || rateValue === undefined) {
    thresholdInput.placeholder = "暂无当前参考值";
    return;
  }

  const updateTime = rateInfo.updateTime ? `，更新时间 ${rateInfo.updateTime}` : "";
  thresholdInput.placeholder = `${currency} ${FIELD_LABELS[field]} ${rateValue}${updateTime}`;
}

async function loadConfig() {
  setStatus("正在读取配置...");

  try {
    const response = await fetch(CONFIG_API_URL, {
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${CONFIG_API_TOKEN}`,
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
  const config = readFormConfig();
  if (!config.emails.length) {
    setStatus("至少添加一个邮箱");
    return;
  }

  const duplicateEmails = findDuplicateEmails(config.emails);
  if (duplicateEmails.length) {
    setStatus(`检测到重复邮箱：${duplicateEmails.join("、")}。请删除重复项后再保存。`);
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

  setStatus("正在保存配置...");

  try {
    const response = await fetch(CONFIG_API_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        Authorization: `Bearer ${CONFIG_API_TOKEN}`,
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

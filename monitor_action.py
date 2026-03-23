#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
GitHub Actions 版本 - 中国银行汇率监控

运行方式:
1. 从 Cloudflare Worker 拉取运行时配置
2. 抓取中国银行外汇牌价
3. 按规则判断是否触发提醒
4. 通过 SMTP 发送邮件
"""

import os
import smtplib
import ssl
import sys
import time
from datetime import datetime
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests
from bs4 import BeautifulSoup


CURRENCY_CONFIG = {
    "GBP": {"name": "英镑", "name_en": "British Pound", "symbol": "GBP"},
    "JPY": {"name": "日元", "name_en": "Japanese Yen", "symbol": "JPY"},
    "USD": {"name": "美元", "name_en": "US Dollar", "symbol": "USD"},
    "EUR": {"name": "欧元", "name_en": "Euro", "symbol": "EUR"},
    "HKD": {"name": "港币", "name_en": "Hong Kong Dollar", "symbol": "HKD"},
    "AUD": {"name": "澳大利亚元", "name_en": "Australian Dollar", "symbol": "AUD"},
    "CAD": {"name": "加拿大元", "name_en": "Canadian Dollar", "symbol": "CAD"},
    "SGD": {"name": "新加坡元", "name_en": "Singapore Dollar", "symbol": "SGD"},
}

FIELD_LABELS = {
    "buy": "现汇买入价",
    "sell": "现汇卖出价",
}

OPERATOR_LABELS = {
    "gt": ">",
    "lt": "<",
}


def fetch_runtime_config():
    """从远端配置 API 拉取配置。"""
    api_url = os.environ.get("CONFIG_API_URL")
    api_token = os.environ.get("CONFIG_API_TOKEN")

    if not api_url:
        print("[ERROR] CONFIG_API_URL is required")
        sys.exit(1)

    headers = {"Accept": "application/json"}
    if api_token:
        headers["Authorization"] = f"Bearer {api_token}"

    try:
        response = requests.get(api_url, headers=headers, timeout=30)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        print(f"[ERROR] Failed to fetch runtime config: {exc}")
        sys.exit(1)

    config = payload.get("config") if isinstance(payload, dict) else None
    if not isinstance(config, dict):
        print("[ERROR] Config API returned invalid payload")
        sys.exit(1)

    return config


def get_boc_exchange_rates():
    """
    从中国银行获取汇率数据。
    返回:
        {
            'GBP': {
                'buy': 923.1,
                'sell': 930.2,
                'currency_name': '英镑',
                'update_time': '2026-03-21 10:00:00'
            }
        }
    """
    url = "https://www.boc.cn/sourcedb/whpj/"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36"
        )
    }

    rates = {}

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        response.encoding = "utf-8"
    except Exception as exc:
        print(f"[ERROR] Failed to request BOC page: {exc}")
        return rates

    try:
        soup = BeautifulSoup(response.text, "lxml")
        main_div = soup.find("div", class_="BOC_main")
        if not main_div:
            print("[ERROR] BOC_main not found")
            return rates

        target_table = None
        for table in main_div.find_all("table"):
            if table.find("th"):
                target_table = table
                break

        if not target_table:
            print("[ERROR] Rate table not found")
            return rates

        rows = target_table.find_all("tr")
        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 7:
                continue

            currency_name = cols[0].get_text(strip=True)
            currency_code = match_currency_code(currency_name)
            if not currency_code:
                continue

            buy_rate = parse_float(cols[1].get_text(strip=True))
            sell_rate = parse_float(cols[3].get_text(strip=True))
            date_part = cols[6].get_text(strip=True)
            time_part = cols[7].get_text(strip=True) if len(cols) > 7 else ""
            update_time = f"{date_part} {time_part}".strip() or "Unknown"

            rates[currency_code] = {
                "buy": buy_rate,
                "sell": sell_rate,
                "currency_name": currency_name,
                "update_time": update_time,
            }
    except Exception as exc:
        print(f"[ERROR] Failed to parse BOC page: {exc}")
        return {}

    return rates


def match_currency_code(currency_name):
    for code, config in CURRENCY_CONFIG.items():
        if config["name"] in currency_name:
            return code
    return None


def parse_float(raw_value):
    if not raw_value:
        return None
    try:
        return float(raw_value)
    except ValueError:
        return None


def normalize_config(config):
    enabled = bool(config.get("enabled", False))
    emails = [email.strip() for email in config.get("emails", []) if str(email).strip()]
    email_set = set(emails)
    rules = []

    for item in config.get("rules", []):
        if not isinstance(item, dict):
            continue

        try:
            threshold = float(item.get("threshold"))
        except (TypeError, ValueError):
            continue

        currency = str(item.get("currency", "")).upper()
        field = item.get("field")
        operator = item.get("operator")

        if currency not in CURRENCY_CONFIG:
            continue
        if field not in FIELD_LABELS:
            continue
        if operator not in OPERATOR_LABELS:
            continue

        rules.append(
            {
                "enabled": bool(item.get("enabled", True)),
                "currency": currency,
                "field": field,
                "operator": operator,
                "threshold": threshold,
                "emails": [
                    email.strip()
                    for email in item.get("emails", [])
                    if str(email).strip() and email.strip() in email_set
                ],
            }
        )

    return {"enabled": enabled, "emails": emails, "rules": rules}


def evaluate_rule(rule, rates):
    currency_code = rule["currency"]
    rate_info = rates.get(currency_code)
    if not rate_info:
        return False, None

    rate_value = rate_info.get(rule["field"])
    if rate_value is None:
        return False, rate_info

    if rule["operator"] == "gt":
        return rate_value > rule["threshold"], rate_info
    return rate_value < rule["threshold"], rate_info


def send_rule_alert(rule, rate_info, sender_email, sender_password, receiver_emails):
    """发送规则命中的提醒邮件。"""
    currency_code = rule["currency"]
    currency_meta = CURRENCY_CONFIG[currency_code]
    rate_value = rate_info.get(rule["field"])
    threshold = rule["threshold"]
    field_label = FIELD_LABELS[rule["field"]]
    operator_label = OPERATOR_LABELS[rule["operator"]]
    update_time = rate_info.get("update_time", "Unknown")
    current_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    subject = (
        f"[Rate Alert] {currency_code} {field_label} "
        f"{rate_value} {operator_label} {threshold}"
    )
    summary = (
        f"{currency_meta['name']} {field_label} {rate_value} "
        f"已满足阈值条件 {operator_label} {threshold}"
    )

    msg = MIMEMultipart("alternative")
    msg["From"] = Header(f"Rate Monitor <{sender_email}>", "utf-8")
    msg["To"] = Header(", ".join(receiver_emails), "utf-8")
    msg["Subject"] = Header(subject, "utf-8")

    text_content = f"""
汇率提醒

货币: {currency_meta['name']} ({currency_code})
监控字段: {field_label}
当前值: {rate_value}
触发条件: {operator_label} {threshold}
中国银行更新时间: {update_time}
检测时间: {current_time}

当前货币信息:
- 现汇买入价: {rate_info.get('buy')}
- 现汇卖出价: {rate_info.get('sell')}

{summary}

数据来源: 中国银行外汇牌价
https://www.boc.cn/sourcedb/whpj/
"""

    html_content = f"""
<html>
  <body style="font-family: Arial, sans-serif; background: #f6f7fb; padding: 24px;">
    <div style="max-width: 640px; margin: 0 auto; background: #ffffff; border-radius: 16px; padding: 24px;">
      <h2 style="margin-top: 0;">汇率提醒</h2>
      <p><strong>货币:</strong> {currency_meta['name']} ({currency_code})</p>
      <p><strong>监控字段:</strong> {field_label}</p>
      <p><strong>当前值:</strong> {rate_value}</p>
      <p><strong>触发条件:</strong> {operator_label} {threshold}</p>
      <p><strong>中国银行更新时间:</strong> {update_time}</p>
      <p><strong>检测时间:</strong> {current_time}</p>
      <hr style="border: 0; border-top: 1px solid #e5e7eb;">
      <p><strong>现汇买入价:</strong> {rate_info.get('buy')}</p>
      <p><strong>现汇卖出价:</strong> {rate_info.get('sell')}</p>
      <p style="color: #0f766e;"><strong>{summary}</strong></p>
      <p>数据来源: <a href="https://www.boc.cn/sourcedb/whpj/">中国银行外汇牌价</a></p>
    </div>
  </body>
</html>
"""

    msg.attach(MIMEText(text_content, "plain", "utf-8"))
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    if "gmail.com" in sender_email:
        smtp_server = "smtp.gmail.com"
        smtp_port = 587
        use_tls = True
    else:
        smtp_server = "smtp.qq.com"
        smtp_port = 465
        use_tls = False

    max_retries = 3
    for attempt in range(max_retries):
        try:
            context = ssl.create_default_context()
            if use_tls:
                server = smtplib.SMTP(smtp_server, smtp_port, timeout=30)
                server.starttls(context=context)
            else:
                server = smtplib.SMTP_SSL(
                    smtp_server, smtp_port, context=context, timeout=30
                )

            server.login(sender_email, sender_password)
            server.sendmail(sender_email, receiver_emails, msg.as_string())
            server.quit()
            print(f"[OK] Alert email sent for {currency_code}")
            return True
        except (smtplib.SMTPServerDisconnected, ConnectionError, TimeoutError, OSError) as exc:
            print(f"[WARN] Attempt {attempt + 1}/{max_retries} failed: {exc}")
            if attempt < max_retries - 1:
                time.sleep(5)
                continue
            print(f"[ERROR] All {max_retries} attempts failed")
            return False
        except smtplib.SMTPAuthenticationError:
            print("[ERROR] SMTP auth failed, check email credentials")
            return False
        except Exception as exc:
            print(f"[ERROR] Send email failed: {exc}")
            return False

    return False


def main():
    sender_email = os.environ.get("SENDER_EMAIL")
    sender_password = os.environ.get("SENDER_PASSWORD")

    if not sender_email or not sender_password:
        print("[ERROR] SENDER_EMAIL and SENDER_PASSWORD are required")
        sys.exit(1)

    raw_config = fetch_runtime_config()
    config = normalize_config(raw_config)

    print("=" * 70)
    print("Exchange Rate Monitor")
    print("=" * 70)
    print(f"Monitor enabled: {config['enabled']}")
    print(f"Receiver count: {len(config['emails'])}")
    print(f"Rule count: {len(config['rules'])}")
    print("-" * 70)

    if not config["enabled"]:
        print("[INFO] Monitoring is disabled in remote config")
        return

    if not config["emails"]:
        print("[INFO] No receiver emails configured")
        return

    active_rules = [rule for rule in config["rules"] if rule["enabled"]]
    if not active_rules:
        print("[INFO] No active rules configured")
        return

    rates = get_boc_exchange_rates()
    if not rates:
        print("[ERROR] Failed to get exchange rates")
        sys.exit(1)

    print("Current Exchange Rates:")
    for code, info in rates.items():
        print(
            f"- {code}: buy={info.get('buy')} sell={info.get('sell')} "
            f"updated={info.get('update_time')}"
        )

    alerts_sent = 0
    for rule in active_rules:
        matched, rate_info = evaluate_rule(rule, rates)
        rule_receivers = rule.get("emails", [])
        print(
            f"[CHECK] {rule['currency']} {FIELD_LABELS[rule['field']]} "
            f"{OPERATOR_LABELS[rule['operator']]} {rule['threshold']} -> {matched} "
            f"(receivers={len(rule_receivers)})"
        )
        if matched and rate_info and rule_receivers:
            if send_rule_alert(
                rule,
                rate_info,
                sender_email=sender_email,
                sender_password=sender_password,
                receiver_emails=rule_receivers,
            ):
                alerts_sent += 1

    print("-" * 70)
    print(f"Done. Total alerts sent: {alerts_sent}")


if __name__ == "__main__":
    main()

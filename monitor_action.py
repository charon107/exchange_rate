#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
GitHub Actions 版本 - 中国银行多货币汇率监控
支持英镑(GBP)和日元(JPY)汇率监控
- 英镑：监控现汇买入价（高于阈值提醒）和现汇卖出价（低于阈值提醒）
- 日元：监控现汇卖出价（低于阈值提醒）
"""

import os
import sys
import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from datetime import datetime
import ssl


# 货币配置
CURRENCY_CONFIG = {
    'GBP': {
        'name': '英镑',
        'name_en': 'GBP (British Pound)',
        'symbol': '💷'
    },
    'JPY': {
        'name': '日元',
        'name_en': 'JPY (Japanese Yen)',
        'symbol': '💴'
    }
}


def get_boc_exchange_rates():
    """
    从中国银行获取所有货币的汇率数据
    返回: dict {货币名称: {'buy': 买入价, 'sell': 卖出价, 'update_time': 更新时间}}
    """
    url = "https://www.boc.cn/sourcedb/whpj/"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    rates = {}
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.encoding = 'utf-8'
        
        if response.status_code != 200:
            print(f"[ERROR] Request failed, status: {response.status_code}")
            return rates
        
        soup = BeautifulSoup(response.text, 'lxml')
        main_div = soup.find("div", class_="BOC_main")
        
        if not main_div:
            print("[ERROR] BOC_main not found")
            return rates
        
        # 找到包含汇率数据的表格
        tables = main_div.find_all("table")
        target_table = None
        for table in tables:
            if table.find("th"):
                target_table = table
                break
        
        if not target_table:
            print("[ERROR] Rate table not found")
            return rates
        
        rows = target_table.find_all("tr")
        
        # 表格结构:
        # 第0列: 货币名称
        # 第1列: 现汇买入价
        # 第2列: 现钞买入价
        # 第3列: 现汇卖出价
        # 第4列: 现钞卖出价
        # 第5列: 中行折算价
        # 第6列: 发布日期时间
        
        for row in rows:
            cols = row.find_all("td")
            if cols and len(cols) >= 7:
                currency_name = cols[0].text.strip()
                buy_rate_str = cols[1].text.strip()
                sell_rate_str = cols[3].text.strip()
                update_time = cols[6].text.strip() if len(cols) > 6 else "Unknown"
                
                buy_rate = None
                sell_rate = None
                
                if buy_rate_str:
                    try:
                        buy_rate = float(buy_rate_str)
                    except ValueError:
                        pass
                
                if sell_rate_str:
                    try:
                        sell_rate = float(sell_rate_str)
                    except ValueError:
                        pass
                
                # 识别货币类型
                currency_code = None
                if "英镑" in currency_name or "Ӣ" in currency_name:
                    currency_code = 'GBP'
                elif "日元" in currency_name:
                    currency_code = 'JPY'
                
                if currency_code:
                    rates[currency_code] = {
                        'buy': buy_rate,
                        'sell': sell_rate,
                        'update_time': update_time
                    }
        
        return rates
        
    except Exception as e:
        print(f"[ERROR] Exception: {e}")
        return rates


def send_currency_alert(currency_code, alert_type, rate, threshold, update_time, 
                        sender_email, sender_password, receiver_emails, all_rates):
    """
    发送货币汇率提醒邮件
    currency_code: 'GBP' 或 'JPY'
    alert_type: 'buy_high' 或 'sell_low'
    """
    try:
        config = CURRENCY_CONFIG.get(currency_code, {})
        currency_name = config.get('name', currency_code)
        currency_name_en = config.get('name_en', currency_code)
        currency_symbol = config.get('symbol', '💱')
        
        msg = MIMEMultipart('alternative')
        msg['From'] = Header(f"Rate Monitor <{sender_email}>", 'utf-8')
        msg['To'] = Header(", ".join(receiver_emails), 'utf-8')
        
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 获取该货币的完整汇率信息
        currency_rates = all_rates.get(currency_code, {})
        buy_rate = currency_rates.get('buy', 'N/A')
        sell_rate = currency_rates.get('sell', 'N/A')
        
        if alert_type == 'buy_high':
            subject = f"[{currency_code} BUY ALERT] {currency_name}现汇买入价 {rate} > {threshold}"
            alert_message = f"{currency_name}现汇买入价 {rate} 已超过阈值 {threshold}"
            alert_color = "#e74c3c"
            rate_label = "现汇买入价"
            condition = f"> {threshold}"
        else:  # sell_low
            subject = f"[{currency_code} SELL ALERT] {currency_name}现汇卖出价 {rate} < {threshold}"
            alert_message = f"{currency_name}现汇卖出价 {rate} 已低于阈值 {threshold}"
            alert_color = "#3498db"
            rate_label = "现汇卖出价"
            condition = f"< {threshold}"
        
        msg['Subject'] = Header(subject, 'utf-8')
        
        text_content = f"""
{currency_symbol} {currency_name} ({currency_code}) 汇率提醒

提醒类型: {alert_type.upper()}
{rate_label}: {rate}
阈值条件: {condition}
中国银行更新时间: {update_time}
检测时间: {current_time}

{currency_name}当前汇率:
- 现汇买入价: {buy_rate}
- 现汇卖出价: {sell_rate}

{alert_message}

数据来源: 中国银行外汇牌价
https://www.boc.cn/sourcedb/whpj/

---
由 GitHub Actions 自动发送
"""
        
        html_content = f"""
<html>
<body style="font-family: Arial, sans-serif; padding: 20px; background-color: #f5f5f5;">
    <div style="max-width: 600px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
        <h2 style="color: {alert_color}; border-bottom: 2px solid {alert_color}; padding-bottom: 10px;">
            {currency_symbol} {currency_name} ({currency_code}) 汇率提醒
        </h2>
        
        <div style="background-color: #fff3cd; padding: 15px; border-radius: 5px; margin: 20px 0;">
            <p style="margin: 0; font-size: 24px; color: #856404; text-align: center;">
                <strong>{rate_label}: <span style="color: {alert_color}; font-size: 32px;">{rate}</span></strong>
            </p>
            <p style="margin: 10px 0 0 0; text-align: center; color: #666;">
                阈值条件: {condition}
            </p>
        </div>
        
        <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #eee; color: #666;">货币:</td>
                <td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>{currency_name_en}</strong></td>
            </tr>
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #eee; color: #666;">现汇买入价:</td>
                <td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>{buy_rate}</strong></td>
            </tr>
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #eee; color: #666;">现汇卖出价:</td>
                <td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>{sell_rate}</strong></td>
            </tr>
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #eee; color: #666;">中国银行更新时间:</td>
                <td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>{update_time}</strong></td>
            </tr>
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #eee; color: #666;">检测时间:</td>
                <td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>{current_time}</strong></td>
            </tr>
        </table>
        
        <p style="color: {alert_color}; font-weight: bold; font-size: 16px;">
            ⚠️ {alert_message}
        </p>
        
        <p style="color: #666; font-size: 12px; margin-top: 30px;">
            数据来源: <a href="https://www.boc.cn/sourcedb/whpj/" style="color: #3498db;">中国银行外汇牌价</a>
        </p>
        
        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
        <p style="color: #999; font-size: 11px; text-align: center;">
            由 GitHub Actions 自动发送
        </p>
    </div>
</body>
</html>
"""
        
        msg.attach(MIMEText(text_content, 'plain', 'utf-8'))
        msg.attach(MIMEText(html_content, 'html', 'utf-8'))
        
        # 根据发件邮箱自动选择 SMTP 服务器
        if "gmail.com" in sender_email:
            smtp_server = "smtp.gmail.com"
            smtp_port = 587
            use_tls = True
        else:
            smtp_server = "smtp.qq.com"
            smtp_port = 465
            use_tls = False
        
        # 发送邮件（带重试机制）
        max_retries = 3
        for attempt in range(max_retries):
            try:
                context = ssl.create_default_context()
                
                if use_tls:
                    server = smtplib.SMTP(smtp_server, smtp_port, timeout=30)
                    server.starttls(context=context)
                else:
                    server = smtplib.SMTP_SSL(smtp_server, smtp_port, context=context, timeout=30)
                
                server.login(sender_email, sender_password)
                server.sendmail(sender_email, receiver_emails, msg.as_string())
                server.quit()
                
                print(f"[OK] {currency_code} alert email sent via {smtp_server}")
                return True
            except (smtplib.SMTPServerDisconnected, ConnectionError, TimeoutError, OSError) as e:
                print(f"[WARN] Attempt {attempt + 1}/{max_retries} failed: {e}")
                if attempt < max_retries - 1:
                    import time
                    time.sleep(5)
                    continue
                else:
                    print(f"[ERROR] All {max_retries} attempts failed")
                    return False
        
        return False
        
    except smtplib.SMTPAuthenticationError:
        print("[ERROR] SMTP auth failed, check email and password")
        return False
    except Exception as e:
        print(f"[ERROR] Send email failed: {e}")
        return False


def main():
    """主函数"""
    # 从环境变量读取配置
    sender_email = os.environ.get('SENDER_EMAIL')
    sender_password = os.environ.get('SENDER_PASSWORD')
    receiver_email_str = os.environ.get('RECEIVER_EMAIL')
    
    # 英镑阈值
    gbp_buy_threshold = float(os.environ.get('GBP_BUY_THRESHOLD', '940'))
    gbp_sell_threshold = float(os.environ.get('GBP_SELL_THRESHOLD', '930'))
    
    # 日元阈值（只监控卖出价，低于此值提醒）
    jpy_sell_threshold = float(os.environ.get('JPY_SELL_THRESHOLD', '5.0'))
    
    # 检查必要的环境变量
    if not sender_email or not sender_password or not receiver_email_str:
        print("[ERROR] Please set SENDER_EMAIL, SENDER_PASSWORD, and RECEIVER_EMAIL in GitHub Secrets")
        sys.exit(1)
    
    # 解析多个收件人
    receiver_emails = [email.strip() for email in receiver_email_str.split(',') if email.strip()]
    if not receiver_emails:
        print("[ERROR] No valid receiver email found")
        sys.exit(1)
    
    print("=" * 60)
    print("Multi-Currency Exchange Rate Monitor (GitHub Actions)")
    print("=" * 60)
    print(f"Receivers: {', '.join(receiver_emails)} ({len(receiver_emails)} total)")
    print("-" * 60)
    print("GBP (英镑) Thresholds:")
    print(f"  - Buy > {gbp_buy_threshold} (alert if higher)")
    print(f"  - Sell < {gbp_sell_threshold} (alert if lower)")
    print("JPY (日元) Thresholds:")
    print(f"  - Sell < {jpy_sell_threshold} (alert if lower)")
    print("=" * 60)
    
    # 获取所有汇率
    rates = get_boc_exchange_rates()
    
    if not rates:
        print("[ERROR] Failed to get exchange rates")
        sys.exit(1)
    
    # 显示获取到的汇率
    print("\nCurrent Exchange Rates (Bank of China):")
    print("-" * 60)
    
    for code in ['GBP', 'JPY']:
        if code in rates:
            r = rates[code]
            config = CURRENCY_CONFIG.get(code, {})
            print(f"{config.get('symbol', '')} {config.get('name', code)} ({code}):")
            print(f"    Buy Rate (Spot):  {r['buy']}")
            print(f"    Sell Rate (Spot): {r['sell']}")
            print(f"    Update Time: {r['update_time']}")
        else:
            print(f"[WARN] {code} rate not found")
    
    print("=" * 60)
    
    alerts_sent = 0
    
    # ========== 英镑监控 ==========
    if 'GBP' in rates:
        gbp = rates['GBP']
        gbp_buy = gbp['buy']
        gbp_sell = gbp['sell']
        gbp_time = gbp['update_time']
        
        # 检查英镑买入价
        if gbp_buy is not None and gbp_buy > gbp_buy_threshold:
            print(f"\n[ALERT] GBP Buy {gbp_buy} > {gbp_buy_threshold}, sending email...")
            if send_currency_alert('GBP', 'buy_high', gbp_buy, gbp_buy_threshold, 
                                   gbp_time, sender_email, sender_password, 
                                   receiver_emails, rates):
                alerts_sent += 1
        else:
            print(f"[OK] GBP Buy {gbp_buy} <= {gbp_buy_threshold}")
        
        # 检查英镑卖出价
        if gbp_sell is not None and gbp_sell < gbp_sell_threshold:
            print(f"[ALERT] GBP Sell {gbp_sell} < {gbp_sell_threshold}, sending email...")
            if send_currency_alert('GBP', 'sell_low', gbp_sell, gbp_sell_threshold,
                                   gbp_time, sender_email, sender_password,
                                   receiver_emails, rates):
                alerts_sent += 1
        else:
            print(f"[OK] GBP Sell {gbp_sell} >= {gbp_sell_threshold}")
    
    # ========== 日元监控 ==========
    if 'JPY' in rates:
        jpy = rates['JPY']
        jpy_sell = jpy['sell']
        jpy_time = jpy['update_time']
        
        # 只检查日元卖出价（低于阈值提醒，适合买入日元的场景）
        if jpy_sell is not None and jpy_sell < jpy_sell_threshold:
            print(f"\n[ALERT] JPY Sell {jpy_sell} < {jpy_sell_threshold}, sending email...")
            if send_currency_alert('JPY', 'sell_low', jpy_sell, jpy_sell_threshold,
                                   jpy_time, sender_email, sender_password,
                                   receiver_emails, rates):
                alerts_sent += 1
        else:
            print(f"[OK] JPY Sell {jpy_sell} >= {jpy_sell_threshold}")
    
    print("\n" + "=" * 60)
    print(f"Done. Total alerts sent: {alerts_sent}")


if __name__ == "__main__":
    main()

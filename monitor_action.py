#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
GitHub Actions 版本 - 中国银行英镑汇率监控
监控现汇买入价（高于阈值提醒）和现汇卖出价（低于阈值提醒）
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


def get_gbp_exchange_rates():
    """
    获取英镑汇率数据
    返回: (现汇买入价, 现汇卖出价, 更新时间) 或 (None, None, None)
    """
    url = "https://www.boc.cn/sourcedb/whpj/"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.encoding = 'utf-8'
        
        if response.status_code != 200:
            print(f"[ERROR] Request failed, status: {response.status_code}")
            return None, None, None
        
        soup = BeautifulSoup(response.text, 'lxml')
        main_div = soup.find("div", class_="BOC_main")
        
        if not main_div:
            print("[ERROR] BOC_main not found")
            return None, None, None
        
        # 找到包含汇率数据的表格
        tables = main_div.find_all("table")
        target_table = None
        for table in tables:
            if table.find("th"):
                target_table = table
                break
        
        if not target_table:
            print("[ERROR] Rate table not found")
            return None, None, None
        
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
                if "英镑" in currency_name or "Ӣ" in currency_name:
                    buy_rate_str = cols[1].text.strip()   # 现汇买入价
                    sell_rate_str = cols[3].text.strip()  # 现汇卖出价
                    update_time = cols[6].text.strip() if len(cols) > 6 else "Unknown"
                    
                    buy_rate = None
                    sell_rate = None
                    
                    if buy_rate_str:
                        try:
                            buy_rate = float(buy_rate_str)
                        except ValueError:
                            print(f"[ERROR] Cannot parse buy rate: {buy_rate_str}")
                    
                    if sell_rate_str:
                        try:
                            sell_rate = float(sell_rate_str)
                        except ValueError:
                            print(f"[ERROR] Cannot parse sell rate: {sell_rate_str}")
                    
                    return buy_rate, sell_rate, update_time
        
        print("[ERROR] GBP rate not found")
        return None, None, None
        
    except Exception as e:
        print(f"[ERROR] Exception: {e}")
        return None, None, None


def send_email_alert(alert_type, rate, update_time, threshold, sender_email, sender_password, receiver_emails, buy_rate=None, sell_rate=None):
    """
    发送邮件提醒
    alert_type: 'buy_high' (买入价过高) 或 'sell_low' (卖出价过低)
    receiver_emails: 收件人列表
    """
    try:
        msg = MIMEMultipart('alternative')
        msg['From'] = Header(f"GBP Monitor <{sender_email}>", 'utf-8')
        msg['To'] = Header(", ".join(receiver_emails), 'utf-8')
        
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if alert_type == 'buy_high':
            subject = f"[BUY ALERT] GBP Buy Rate {rate} > {threshold}"
            alert_message = f"Buy rate {rate} exceeded threshold {threshold}"
            alert_color = "#e74c3c"
            rate_label = "Buy Rate (Spot)"
            condition = f"> {threshold}"
        else:  # sell_low
            subject = f"[SELL ALERT] GBP Sell Rate {rate} < {threshold}"
            alert_message = f"Sell rate {rate} dropped below threshold {threshold}"
            alert_color = "#3498db"
            rate_label = "Sell Rate (Spot)"
            condition = f"< {threshold}"
        
        msg['Subject'] = Header(subject, 'utf-8')
        
        text_content = f"""
GBP Exchange Rate Alert

Alert Type: {alert_type.upper()}
{rate_label}: {rate}
Threshold: {condition}
BOC Update Time: {update_time}
Check Time: {current_time}

Current Rates:
- Buy Rate (Spot): {buy_rate}
- Sell Rate (Spot): {sell_rate}

{alert_message}

Source: Bank of China
https://www.boc.cn/sourcedb/whpj/

---
Sent by GitHub Actions
"""
        
        html_content = f"""
<html>
<body style="font-family: Arial, sans-serif; padding: 20px; background-color: #f5f5f5;">
    <div style="max-width: 600px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
        <h2 style="color: {alert_color}; border-bottom: 2px solid {alert_color}; padding-bottom: 10px;">
            GBP Exchange Rate Alert
        </h2>
        
        <div style="background-color: #fff3cd; padding: 15px; border-radius: 5px; margin: 20px 0;">
            <p style="margin: 0; font-size: 24px; color: #856404; text-align: center;">
                <strong>{rate_label}: <span style="color: {alert_color}; font-size: 32px;">{rate}</span></strong>
            </p>
            <p style="margin: 10px 0 0 0; text-align: center; color: #666;">
                Threshold: {condition}
            </p>
        </div>
        
        <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #eee; color: #666;">Buy Rate (Spot):</td>
                <td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>{buy_rate}</strong></td>
            </tr>
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #eee; color: #666;">Sell Rate (Spot):</td>
                <td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>{sell_rate}</strong></td>
            </tr>
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #eee; color: #666;">BOC Update:</td>
                <td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>{update_time}</strong></td>
            </tr>
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #eee; color: #666;">Check Time:</td>
                <td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>{current_time}</strong></td>
            </tr>
        </table>
        
        <p style="color: {alert_color}; font-weight: bold;">
            {alert_message}
        </p>
        
        <p style="color: #666; font-size: 12px; margin-top: 30px;">
            Source: <a href="https://www.boc.cn/sourcedb/whpj/" style="color: #3498db;">Bank of China Exchange Rates</a>
        </p>
        
        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
        <p style="color: #999; font-size: 11px; text-align: center;">
            Sent by GitHub Actions
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
        else:  # QQ 邮箱或其他
            smtp_server = "smtp.qq.com"
            smtp_port = 465
            use_tls = False
        
        # 发送邮件（带重试机制）
        max_retries = 3
        for attempt in range(max_retries):
            try:
                context = ssl.create_default_context()
                
                if use_tls:
                    # Gmail 使用 STARTTLS
                    server = smtplib.SMTP(smtp_server, smtp_port, timeout=30)
                    server.starttls(context=context)
                else:
                    # QQ 邮箱使用 SSL
                    server = smtplib.SMTP_SSL(smtp_server, smtp_port, context=context, timeout=30)
                
                server.login(sender_email, sender_password)
                server.sendmail(sender_email, receiver_emails, msg.as_string())
                server.quit()
                
                print(f"[OK] Email sent via {smtp_server} to: {', '.join(receiver_emails)}")
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
    
    # 买入价阈值（高于此值提醒）
    buy_threshold = float(os.environ.get('BUY_THRESHOLD', '940'))
    # 卖出价阈值（低于此值提醒）
    sell_threshold = float(os.environ.get('SELL_THRESHOLD', '930'))
    
    # 检查必要的环境变量
    if not sender_email or not sender_password or not receiver_email_str:
        print("[ERROR] Please set SENDER_EMAIL, SENDER_PASSWORD, and RECEIVER_EMAIL in GitHub Secrets")
        sys.exit(1)
    
    # 解析多个收件人（支持逗号分隔）
    receiver_emails = [email.strip() for email in receiver_email_str.split(',') if email.strip()]
    if not receiver_emails:
        print("[ERROR] No valid receiver email found")
        sys.exit(1)
    
    print("=" * 55)
    print("GBP Exchange Rate Monitor (GitHub Actions)")
    print("=" * 55)
    print(f"Receivers: {', '.join(receiver_emails)} ({len(receiver_emails)} total)")
    print(f"Buy Threshold: > {buy_threshold} (alert if higher)")
    print(f"Sell Threshold: < {sell_threshold} (alert if lower)")
    print("=" * 55)
    
    # 获取汇率
    buy_rate, sell_rate, update_time = get_gbp_exchange_rates()
    
    if buy_rate is None and sell_rate is None:
        print("[ERROR] Failed to get exchange rates")
        sys.exit(1)
    
    print(f"GBP Buy Rate (Spot):  {buy_rate}")
    print(f"GBP Sell Rate (Spot): {sell_rate}")
    print(f"BOC Update Time: {update_time}")
    print("=" * 55)
    
    alerts_sent = 0
    
    # 检查买入价是否超过阈值
    if buy_rate is not None and buy_rate > buy_threshold:
        print(f"[ALERT] Buy rate {buy_rate} > {buy_threshold}, sending email...")
        if send_email_alert('buy_high', buy_rate, update_time, buy_threshold, 
                          sender_email, sender_password, receiver_emails,
                          buy_rate, sell_rate):
            alerts_sent += 1
    else:
        print(f"[OK] Buy rate {buy_rate} <= {buy_threshold}, no alert needed")
    
    # 检查卖出价是否低于阈值
    if sell_rate is not None and sell_rate < sell_threshold:
        print(f"[ALERT] Sell rate {sell_rate} < {sell_threshold}, sending email...")
        if send_email_alert('sell_low', sell_rate, update_time, sell_threshold,
                          sender_email, sender_password, receiver_emails,
                          buy_rate, sell_rate):
            alerts_sent += 1
    else:
        print(f"[OK] Sell rate {sell_rate} >= {sell_threshold}, no alert needed")
    
    print("=" * 55)
    print(f"Done. Alerts sent: {alerts_sent}")


if __name__ == "__main__":
    main()

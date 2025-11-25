#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
GitHub Actions 版本 - 中国银行英镑汇率监控
单次运行，检查汇率并在超过阈值时发送邮件
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


def get_gbp_exchange_rate():
    """获取英镑现汇买入价"""
    url = "https://www.boc.cn/sourcedb/whpj/"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.encoding = 'utf-8'
        
        if response.status_code != 200:
            print(f"❌ 请求失败，状态码: {response.status_code}")
            return None, None
        
        soup = BeautifulSoup(response.text, 'lxml')
        main_div = soup.find("div", class_="BOC_main")
        
        if not main_div:
            print("❌ 未找到BOC_main区域")
            return None, None
        
        # 找到包含汇率数据的表格
        tables = main_div.find_all("table")
        target_table = None
        for table in tables:
            if table.find("th"):
                target_table = table
                break
        
        if not target_table:
            print("❌ 未找到汇率表格")
            return None, None
        
        rows = target_table.find_all("tr")
        
        for row in rows:
            cols = row.find_all("td")
            if cols and len(cols) >= 7:
                currency_name = cols[0].text.strip()
                if "英镑" in currency_name or "Ӣ" in currency_name:
                    rate_str = cols[1].text.strip()
                    update_time = cols[6].text.strip() if len(cols) > 6 else "未知"
                    
                    if rate_str:
                        try:
                            rate = float(rate_str)
                            return rate, update_time
                        except ValueError:
                            print(f"❌ 无法解析汇率值: {rate_str}")
                            return None, None
        
        print("❌ 未找到英镑汇率数据")
        return None, None
        
    except Exception as e:
        print(f"❌ 获取汇率时发生错误: {e}")
        return None, None


def send_email_alert(rate, update_time, sender_email, sender_password, receiver_email, threshold):
    """发送邮件提醒"""
    try:
        msg = MIMEMultipart('alternative')
        msg['From'] = Header(f"汇率监控 <{sender_email}>", 'utf-8')
        msg['To'] = Header(receiver_email, 'utf-8')
        msg['Subject'] = Header(f"【汇率提醒】英镑现汇买入价已达 {rate}", 'utf-8')
        
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        text_content = f"""
英镑汇率提醒

当前英镑现汇买入价: {rate}
设定提醒阈值: {threshold}
中国银行更新时间: {update_time}
监控检测时间: {current_time}

英镑现汇买入价已超过您设定的 {threshold} 阈值！

数据来源: 中国银行外汇牌价
https://www.boc.cn/sourcedb/whpj/

---
此邮件由 GitHub Actions 自动发送
"""
        
        html_content = f"""
<html>
<body style="font-family: Arial, sans-serif; padding: 20px; background-color: #f5f5f5;">
    <div style="max-width: 600px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
        <h2 style="color: #e74c3c; border-bottom: 2px solid #e74c3c; padding-bottom: 10px;">
            💷 英镑汇率提醒
        </h2>
        
        <div style="background-color: #fff3cd; padding: 15px; border-radius: 5px; margin: 20px 0;">
            <p style="margin: 0; font-size: 24px; color: #856404; text-align: center;">
                <strong>当前英镑现汇买入价: <span style="color: #e74c3c; font-size: 32px;">{rate}</span></strong>
            </p>
        </div>
        
        <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #eee; color: #666;">设定提醒阈值:</td>
                <td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>{threshold}</strong></td>
            </tr>
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #eee; color: #666;">中国银行更新时间:</td>
                <td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>{update_time}</strong></td>
            </tr>
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #eee; color: #666;">监控检测时间:</td>
                <td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>{current_time}</strong></td>
            </tr>
        </table>
        
        <p style="color: #27ae60; font-weight: bold;">
            ✅ 英镑现汇买入价已超过您设定的 {threshold} 阈值！
        </p>
        
        <p style="color: #666; font-size: 12px; margin-top: 30px;">
            数据来源: <a href="https://www.boc.cn/sourcedb/whpj/" style="color: #3498db;">中国银行外汇牌价</a>
        </p>
        
        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
        <p style="color: #999; font-size: 11px; text-align: center;">
            此邮件由 GitHub Actions 自动发送
        </p>
    </div>
</body>
</html>
"""
        
        msg.attach(MIMEText(text_content, 'plain', 'utf-8'))
        msg.attach(MIMEText(html_content, 'html', 'utf-8'))
        
        # 发送邮件
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.qq.com", 465, context=context) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, receiver_email, msg.as_string())
        
        print(f"✅ 邮件发送成功! 收件人: {receiver_email}")
        return True
        
    except smtplib.SMTPAuthenticationError:
        print("❌ 邮箱认证失败，请检查邮箱地址和授权码")
        return False
    except Exception as e:
        print(f"❌ 发送邮件时发生错误: {e}")
        return False


def main():
    """主函数"""
    # 从环境变量读取配置
    sender_email = os.environ.get('SENDER_EMAIL')
    sender_password = os.environ.get('SENDER_PASSWORD')
    receiver_email = os.environ.get('RECEIVER_EMAIL', '2502571794@qq.com')
    threshold = float(os.environ.get('THRESHOLD', '940'))
    
    # 检查必要的环境变量
    if not sender_email or not sender_password:
        print("❌ 错误: 请在 GitHub Secrets 中设置 SENDER_EMAIL 和 SENDER_PASSWORD")
        sys.exit(1)
    
    print("=" * 50)
    print("🔍 中国银行英镑汇率监控 (GitHub Actions)")
    print(f"📧 收件邮箱: {receiver_email}")
    print(f"🎯 提醒阈值: {threshold}")
    print("=" * 50)
    
    # 获取汇率
    rate, update_time = get_gbp_exchange_rate()
    
    if rate is None:
        print("❌ 未能获取汇率数据")
        sys.exit(1)
    
    print(f"💷 当前英镑现汇买入价: {rate}")
    print(f"🕐 中国银行更新时间: {update_time}")
    
    # 检查是否超过阈值
    if rate > threshold:
        print(f"⚠️ 汇率 {rate} 已超过阈值 {threshold}，发送提醒邮件...")
        if send_email_alert(rate, update_time, sender_email, sender_password, receiver_email, threshold):
            print("✅ 提醒邮件已发送!")
        else:
            sys.exit(1)
    else:
        print(f"✅ 汇率 {rate} 未超过阈值 {threshold}，无需提醒")


if __name__ == "__main__":
    main()


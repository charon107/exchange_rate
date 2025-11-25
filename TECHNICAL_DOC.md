# 技术文档：中国银行英镑汇率监控系统

## 1. 项目概述

### 1.1 功能描述

本项目通过 GitHub Actions 实现 24/7 自动监控中国银行英镑外汇牌价，当汇率满足以下条件时自动发送邮件提醒：

- **现汇买入价** > 设定阈值 → 发送提醒
- **现汇卖出价** < 设定阈值 → 发送提醒

### 1.2 技术栈

| 技术 | 用途 |
|------|------|
| Python 3.11 | 主要编程语言 |
| requests | HTTP 请求库 |
| BeautifulSoup4 | HTML 解析库 |
| lxml | XML/HTML 解析引擎 |
| smtplib | 邮件发送（Python 标准库） |
| GitHub Actions | CI/CD 定时任务调度 |

### 1.3 项目结构

```
exchange_rate/
├── .github/
│   └── workflows/
│       └── monitor.yml      # GitHub Actions 工作流配置
├── .gitignore               # Git 忽略规则
├── monitor_action.py        # 主监控脚本
├── requirements.txt         # Python 依赖
├── README.md               # 使用说明
└── TECHNICAL_DOC.md        # 技术文档（本文件）
```

---

## 2. 系统架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                      GitHub Actions                              │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    Cron Scheduler                        │    │
│  │                  (每5分钟触发一次)                        │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                  Ubuntu Runner                           │    │
│  │  ┌─────────────────────────────────────────────────┐    │    │
│  │  │              monitor_action.py                   │    │    │
│  │  │                                                  │    │    │
│  │  │  1. 获取汇率数据                                 │    │    │
│  │  │  2. 判断是否触发阈值                             │    │    │
│  │  │  3. 发送邮件提醒                                 │    │    │
│  │  └─────────────────────────────────────────────────┘    │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
          │                                    │
          ▼                                    ▼
┌──────────────────┐              ┌──────────────────────┐
│   中国银行网站    │              │    QQ邮箱 SMTP 服务   │
│  (数据来源)       │              │    (邮件发送)         │
└──────────────────┘              └──────────────────────┘
```

### 2.2 数据流图

```
中国银行网站                  GitHub Actions                    用户邮箱
     │                            │                               │
     │  ① HTTP GET 请求           │                               │
     │<───────────────────────────│                               │
     │                            │                               │
     │  ② 返回 HTML 页面          │                               │
     │───────────────────────────>│                               │
     │                            │                               │
     │                   ③ 解析 HTML                              │
     │                   提取汇率数据                              │
     │                            │                               │
     │                   ④ 判断阈值                               │
     │                            │                               │
     │                   ⑤ 触发条件满足                            │
     │                            │───────────────────────────────>│
     │                            │  发送 SMTP 邮件                │
     │                            │                               │
```

---

## 3. 核心模块实现

### 3.1 汇率数据获取模块

#### 3.1.1 数据源

- **URL**: `https://www.boc.cn/sourcedb/whpj/`
- **数据格式**: HTML 表格
- **更新频率**: 银行工作日实时更新

#### 3.1.2 HTML 结构分析

中国银行外汇牌价页面的表格结构：

```html
<div class="BOC_main">
  <table>
    <tr>
      <th>货币名称</th>
      <th>现汇买入价</th>
      <th>现钞买入价</th>
      <th>现汇卖出价</th>
      <th>现钞卖出价</th>
      <th>中行折算价</th>
      <th>发布日期</th>
      <th>发布时间</th>
    </tr>
    <tr>
      <td>英镑</td>
      <td>927.91</td>      <!-- 索引 1: 现汇买入价 -->
      <td>927.91</td>      <!-- 索引 2: 现钞买入价 -->
      <td>934.80</td>      <!-- 索引 3: 现汇卖出价 -->
      <td>934.80</td>      <!-- 索引 4: 现钞卖出价 -->
      <td>931.35</td>      <!-- 索引 5: 中行折算价 -->
      <td>2025/11/25</td>  <!-- 索引 6: 发布日期 -->
      <td>16:00:50</td>    <!-- 索引 7: 发布时间 -->
    </tr>
    ...
  </table>
</div>
```

#### 3.1.3 解析逻辑

```python
def get_gbp_exchange_rates():
    """
    获取英镑汇率数据
    返回: (现汇买入价, 现汇卖出价, 更新时间)
    """
    # 1. 发送 HTTP 请求
    response = requests.get(url, headers=headers, timeout=30)
    
    # 2. 解析 HTML
    soup = BeautifulSoup(response.text, 'lxml')
    
    # 3. 定位数据表格
    main_div = soup.find("div", class_="BOC_main")
    target_table = main_div.find("table")  # 包含 <th> 的表格
    
    # 4. 遍历行，查找英镑数据
    for row in target_table.find_all("tr"):
        cols = row.find_all("td")
        if "英镑" in cols[0].text:
            buy_rate = float(cols[1].text)   # 现汇买入价
            sell_rate = float(cols[3].text)  # 现汇卖出价
            update_time = cols[6].text       # 发布时间
            return buy_rate, sell_rate, update_time
```

### 3.2 邮件发送模块

#### 3.2.1 SMTP 配置

| 参数 | 值 |
|------|-----|
| 服务器 | smtp.qq.com |
| 端口 | 465 (SSL) |
| 加密 | SSL/TLS |
| 认证 | 邮箱 + 授权码 |

#### 3.2.2 邮件格式

支持两种格式，邮件客户端会自动选择最佳显示方式：

- **纯文本格式** (text/plain): 用于简单邮件客户端
- **HTML 格式** (text/html): 用于现代邮件客户端，支持样式

#### 3.2.3 多收件人支持

```python
# 解析多个收件人（逗号分隔）
receiver_emails = [email.strip() for email in receiver_email_str.split(',')]

# 发送给多个收件人
server.sendmail(sender_email, receiver_emails, msg.as_string())
```

### 3.3 阈值判断逻辑

```python
# 买入价监控：高于阈值发提醒（适合卖出英镑的场景）
if buy_rate > buy_threshold:
    send_alert('buy_high', buy_rate, ...)

# 卖出价监控：低于阈值发提醒（适合买入英镑的场景）
if sell_rate < sell_threshold:
    send_alert('sell_low', sell_rate, ...)
```

**应用场景说明**：

| 场景 | 关注指标 | 条件 | 含义 |
|------|----------|------|------|
| 想卖英镑换人民币 | 现汇买入价 | 越高越好 | 银行买入你的英镑，价格高你赚得多 |
| 想买英镑 | 现汇卖出价 | 越低越好 | 银行卖给你英镑，价格低你花得少 |

---

## 4. GitHub Actions 配置

### 4.1 工作流配置文件

```yaml
# .github/workflows/monitor.yml

name: GBP Rate Monitor

on:
  # 定时触发：每5分钟运行一次
  schedule:
    - cron: '*/5 * * * *'
  
  # 手动触发：用于测试
  workflow_dispatch:

jobs:
  check-rate:
    runs-on: ubuntu-latest
    
    steps:
      # 步骤1: 检出代码
      - uses: actions/checkout@v4
      
      # 步骤2: 设置 Python 环境
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      # 步骤3: 安装依赖
      - run: pip install -r requirements.txt
      
      # 步骤4: 运行监控脚本
      - run: python monitor_action.py
        env:
          SENDER_EMAIL: ${{ secrets.SENDER_EMAIL }}
          SENDER_PASSWORD: ${{ secrets.SENDER_PASSWORD }}
          RECEIVER_EMAIL: ${{ secrets.RECEIVER_EMAIL }}
          BUY_THRESHOLD: ${{ vars.BUY_THRESHOLD || '940' }}
          SELL_THRESHOLD: ${{ vars.SELL_THRESHOLD || '930' }}
```

### 4.2 Cron 表达式说明

```
*/5 * * * *
 │  │ │ │ │
 │  │ │ │ └── 星期几 (0-7, 0和7都是周日)
 │  │ │ └──── 月份 (1-12)
 │  │ └────── 日期 (1-31)
 │  └──────── 小时 (0-23)
 └────────── 分钟 (0-59)

*/5 = 每5分钟
*   = 每个（小时/日/月/星期）
```

### 4.3 Secrets vs Variables

| 类型 | 用途 | 安全性 | 示例 |
|------|------|--------|------|
| Secrets | 敏感信息 | 加密存储，日志中显示为 `***` | 邮箱、密码 |
| Variables | 非敏感配置 | 明文存储，可公开 | 阈值数字 |

---

## 5. 安全设计

### 5.1 敏感信息保护

1. **GitHub Secrets 加密存储**
   - 所有敏感信息存储在 Secrets 中
   - 即使仓库公开，他人也无法查看
   - Actions 日志自动遮盖敏感内容

2. **代码中无硬编码敏感信息**
   - 所有配置通过环境变量传入
   - 代码可安全公开

### 5.2 QQ 邮箱授权码

使用授权码而非 QQ 密码的好处：
- 授权码可随时撤销
- 不影响 QQ 账号安全
- 符合邮箱服务商安全规范

---

## 6. 错误处理

### 6.1 网络请求错误

```python
try:
    response = requests.get(url, timeout=30)
except requests.exceptions.RequestException as e:
    print(f"[ERROR] Network error: {e}")
    return None, None, None
```

### 6.2 数据解析错误

```python
try:
    rate = float(rate_str)
except ValueError:
    print(f"[ERROR] Cannot parse rate: {rate_str}")
    return None, None, None
```

### 6.3 邮件发送错误

```python
try:
    server.sendmail(sender, receivers, msg)
except smtplib.SMTPAuthenticationError:
    print("[ERROR] SMTP auth failed")
except Exception as e:
    print(f"[ERROR] Send failed: {e}")
```

---

## 7. 运行时序图

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  GitHub  │     │  Python  │     │   BOC    │     │   SMTP   │
│  Actions │     │  Script  │     │  Website │     │  Server  │
└────┬─────┘     └────┬─────┘     └────┬─────┘     └────┬─────┘
     │                │                │                │
     │ 1. 触发运行    │                │                │
     │───────────────>│                │                │
     │                │                │                │
     │                │ 2. GET 请求    │                │
     │                │───────────────>│                │
     │                │                │                │
     │                │ 3. HTML 响应   │                │
     │                │<───────────────│                │
     │                │                │                │
     │                │ 4. 解析数据    │                │
     │                │ 5. 判断阈值    │                │
     │                │                │                │
     │                │ 6. [如触发] 发送邮件            │
     │                │───────────────────────────────>│
     │                │                │                │
     │                │ 7. 发送成功    │                │
     │                │<───────────────────────────────│
     │                │                │                │
     │ 8. 运行完成    │                │                │
     │<───────────────│                │                │
     │                │                │                │
```

---

## 8. 性能与资源

### 8.1 运行时间

- 单次运行：约 **15-20 秒**
- 主要耗时：网络请求 + Python 环境初始化

### 8.2 GitHub Actions 配额

| 账户类型 | 每月免费额度 |
|----------|-------------|
| Free | 2,000 分钟 |
| Pro | 3,000 分钟 |

**本项目用量估算**：
- 每次运行：~0.3 分钟
- 每天运行：288 次 × 0.3 = ~86 分钟
- 每月运行：~2,600 分钟

> ⚠️ 免费账户可能超出配额，可考虑调整为每 10-15 分钟运行一次

### 8.3 优化建议

如需减少配额消耗，可修改 cron 表达式：

```yaml
# 每10分钟运行一次
- cron: '*/10 * * * *'

# 每15分钟运行一次
- cron: '*/15 * * * *'

# 仅工作日运行（周一到周五）
- cron: '*/5 * * * 1-5'
```

---

## 9. 扩展开发

### 9.1 添加更多货币

修改 `get_gbp_exchange_rates()` 函数，支持参数化货币名称：

```python
def get_exchange_rates(currency_name="英镑"):
    for row in rows:
        if currency_name in cols[0].text:
            ...
```

### 9.2 添加更多通知渠道

可扩展支持：
- 企业微信机器人
- 钉钉机器人
- Telegram Bot
- Slack Webhook

### 9.3 添加历史数据记录

可结合 GitHub Actions 的 artifacts 或外部数据库存储历史汇率数据。

---

## 10. 常见问题

### Q1: 为什么没收到邮件？

1. 检查 Secrets 配置是否正确
2. 查看 Actions 运行日志是否有错误
3. 确认汇率是否达到触发阈值
4. 检查邮箱垃圾箱

### Q2: 授权码在哪里获取？

QQ邮箱 → 设置 → 账户 → POP3/SMTP服务 → 开启 → 生成授权码

### Q3: 可以监控其他货币吗？

可以，修改代码中的货币名称匹配条件即可。

### Q4: 运行日志中邮箱显示为 `***` 是什么？

这是 GitHub 的安全机制，Secrets 的值会被自动遮盖，说明配置正确。

---

## 11. 版本历史

| 版本 | 日期 | 更新内容 |
|------|------|----------|
| 1.0.0 | 2025-11-25 | 初始版本，支持买入价监控 |
| 1.1.0 | 2025-11-25 | 添加卖出价监控 |
| 1.2.0 | 2025-11-25 | 支持多收件人 |

---

## 12. 许可证

MIT License


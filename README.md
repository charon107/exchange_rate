# 中国银行多货币汇率监控

通过 GitHub Actions 自动监测中国银行外汇牌价，支持多货币监控：

## 监控规则

| 货币 | 监控条件 | 触发邮件 |
|------|----------|----------|
| 💷 英镑 (GBP) | 现汇买入价 > 阈值 | 发送英镑提醒 |
| 💷 英镑 (GBP) | 现汇卖出价 < 阈值 | 发送英镑提醒 |
| 💴 日元 (JPY) | 现汇卖出价 < 阈值 | 发送日元提醒 |

**注意**：每种货币的提醒邮件独立发送，只包含该货币的信息。

## 快速开始

### 1. Fork 或克隆此仓库

### 2. 设置 Secrets

**Settings** → **Secrets and variables** → **Actions** → **Secrets**

| Name | Value |
|------|-------|
| `SENDER_EMAIL` | 你的 Gmail 邮箱 |
| `SENDER_PASSWORD` | Gmail 应用专用密码（16位） |
| `RECEIVER_EMAIL` | 收件邮箱（多个用逗号分隔） |

### 3. 设置阈值

**Settings** → **Secrets and variables** → **Actions** → **Variables**

| Name | 说明 | 默认值 |
|------|------|--------|
| `GBP_BUY_THRESHOLD` | 英镑买入价阈值，**高于**此值发提醒 | `940` |
| `GBP_SELL_THRESHOLD` | 英镑卖出价阈值，**低于**此值发提醒 | `930` |
| `JPY_SELL_THRESHOLD` | 日元卖出价阈值，**低于**此值发提醒 | `5.0` |

### 4. 获取 Gmail 应用专用密码

1. 开启两步验证：[Google 账户安全](https://myaccount.google.com/security)
2. 生成应用专用密码：[App Passwords](https://myaccount.google.com/apppasswords)
3. 选择 "邮件" + "其他"，生成 16 位密码

### 5. 启用 Actions

- 点击 **Actions** 标签 → 启用
- 工作流每 5 分钟自动运行

### 6. 手动测试

**Actions** → **Multi-Currency Rate Monitor** → **Run workflow**

## 应用场景

| 场景 | 关注货币 | 关注指标 | 阈值设置 |
|------|----------|----------|----------|
| 想卖英镑换人民币 | 英镑 | 现汇买入价 | 越高越好 |
| 想买英镑 | 英镑 | 现汇卖出价 | 越低越好 |
| 想买日元 | 日元 | 现汇卖出价 | 越低越好 |

## 数据来源

[中国银行外汇牌价](https://www.boc.cn/sourcedb/whpj/)

## 分支说明

- `main`: 原始英镑监控版本
- `feature/multi-currency`: 多货币监控版本（英镑 + 日元）

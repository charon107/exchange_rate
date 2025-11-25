# 中国银行英镑汇率监控

通过 GitHub Actions 自动监测中国银行英镑汇率：
- **现汇买入价** > 阈值 → 发邮件提醒
- **现汇卖出价** < 阈值 → 发邮件提醒

## 快速开始

### 1. Fork 或克隆此仓库

### 2. 设置 Secrets

**Settings** → **Secrets and variables** → **Actions** → **New repository secret**

| Name | Value |
|------|-------|
| `SENDER_EMAIL` | 你的 Gmail 邮箱 |
| `SENDER_PASSWORD` | Gmail 应用专用密码（16位） |
| `RECEIVER_EMAIL` | 收件邮箱（多个用逗号分隔） |

**多收件人示例：** `aaa@gmail.com,bbb@qq.com,ccc@163.com`

### 3. 设置阈值（可选）

**Settings** → **Secrets and variables** → **Actions** → **Variables** → **New repository variable**

| Name | 说明 | 默认值 |
|------|------|--------|
| `BUY_THRESHOLD` | 买入价阈值，**高于**此值发提醒 | `940` |
| `SELL_THRESHOLD` | 卖出价阈值，**低于**此值发提醒 | `930` |

### 4. 获取 Gmail 应用专用密码

1. 开启两步验证：[Google 账户安全](https://myaccount.google.com/security)
2. 生成应用专用密码：[App Passwords](https://myaccount.google.com/apppasswords)
3. 选择 "邮件" + "其他"，生成 16 位密码

### 5. 启用 Actions

- 点击 **Actions** 标签 → 启用
- 工作流每 5 分钟自动运行

### 6. 手动测试

**Actions** → **GBP Rate Monitor** → **Run workflow**

## 监控逻辑

| 条件 | 动作 |
|------|------|
| 现汇买入价 > `BUY_THRESHOLD` | 发送买入价过高提醒 |
| 现汇卖出价 < `SELL_THRESHOLD` | 发送卖出价过低提醒 |

## 数据来源

[中国银行外汇牌价](https://www.boc.cn/sourcedb/whpj/)

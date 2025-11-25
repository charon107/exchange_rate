# 中国银行英镑汇率监控

通过 GitHub Actions 自动监测中国银行英镑现汇买入价，当价格超过设定阈值时发送邮件提醒。

## 功能特点

- 🔍 每5分钟自动检查中国银行外汇牌价
- 💷 监测英镑现汇买入价
- 📧 价格超阈值自动发送邮件提醒
- ☁️ 云端运行，无需本地服务器

## 快速开始

### 1. Fork 或克隆此仓库

### 2. 设置 Secrets

在仓库页面：**Settings** → **Secrets and variables** → **Actions** → **New repository secret**

添加以下 Secrets：

| Name | Value |
|------|-------|
| `SENDER_EMAIL` | 你的QQ邮箱，如 `123456@qq.com` |
| `SENDER_PASSWORD` | QQ邮箱授权码（16位） |
| `RECEIVER_EMAIL` | 收件邮箱，如 `2502571794@qq.com` |

### 3. 获取QQ邮箱授权码

1. 登录 [QQ邮箱](https://mail.qq.com)
2. **设置** → **账户**
3. 找到 **POP3/SMTP服务** → 开启
4. 点击 **生成授权码**

### 4. 设置阈值（可选）

**Settings** → **Secrets and variables** → **Actions** → **Variables** → **New repository variable**

| Name | Value |
|------|-------|
| `THRESHOLD` | `940`（默认值，可自定义）|

### 5. 启用 Actions

- 仓库页面点击 **Actions** 标签
- 点击 **I understand my workflows, go ahead and enable them**
- 工作流会每 5 分钟自动运行一次

### 6. 手动测试

**Actions** → **监控英镑汇率** → **Run workflow**

## 数据来源

- [中国银行外汇牌价](https://www.boc.cn/sourcedb/whpj/)

## 注意事项

1. QQ邮箱授权码不是QQ密码，需要单独生成
2. GitHub Actions 免费账户每月有 2000 分钟额度，完全够用
3. 当前英镑现汇买入价约为 927（2025年11月）

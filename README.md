# 中国银行汇率监控控制台

这个仓库现在包含一套完整的 `GitHub Pages + Cloudflare Worker + GitHub Actions` 方案：

- `web/`：托管到 GitHub Pages 的管理界面
- `worker/`：托管到 Cloudflare Worker 的配置 API
- `monitor_action.py`：GitHub Actions 定时执行的监控脚本

## 功能

- Web 页面开启或关闭监控
- Web 页面添加多个提醒邮箱
- Web 页面配置多个货币监控规则
- GitHub Actions 定时抓取中国银行外汇牌价
- 满足阈值后通过 SMTP 发邮件

## 配置模型

Web 界面保存的是运行时配置，结构如下：

```json
{
  "enabled": true,
  "emails": ["example@gmail.com"],
  "rules": [
    {
      "enabled": true,
      "currency": "JPY",
      "field": "sell",
      "operator": "lt",
      "threshold": 5.0
    }
  ]
}
```

字段说明：

- `enabled`：全局开关
- `emails`：提醒收件人列表
- `currency`：货币代码，如 `JPY`、`GBP`、`USD`
- `field`：监控字段，`buy` 为现汇买入价，`sell` 为现汇卖出价
- `operator`：比较方式，`gt` 为大于，`lt` 为小于
- `threshold`：阈值

## 部署步骤

### 1. 部署 Cloudflare Worker

进入 `worker/`：

```bash
npm install
```

创建 Cloudflare KV，并把 `worker/wrangler.jsonc` 里的以下值替换掉：

- `kv_namespaces[0].id`
- `vars.ALLOWED_ORIGIN`

然后部署：

```bash
npx wrangler secret put CONFIG_API_TOKEN
npx wrangler deploy
```

部署完成后，得到一个类似下面的地址：

```text
https://exchange-rate-monitor-config.<subdomain>.workers.dev/api/config
```

### 2. 配置 GitHub Actions Secrets

在 GitHub 仓库的 `Settings -> Secrets and variables -> Actions -> Secrets` 中添加：

- `SENDER_EMAIL`
- `SENDER_PASSWORD`
- `CONFIG_API_URL`
- `CONFIG_API_TOKEN`

说明：

- `SENDER_EMAIL`：发件邮箱
- `SENDER_PASSWORD`：邮箱授权码或应用专用密码
- `CONFIG_API_URL`：Worker 的 `/api/config` 地址
- `CONFIG_API_TOKEN`：与 `wrangler secret put CONFIG_API_TOKEN` 写入的值一致

### 3. 启用 GitHub Pages

仓库已经包含自动部署工作流 [deploy-pages.yml](/D:/Project/exchange_rate/.github/workflows/deploy-pages.yml)。

在 GitHub 仓库里：

1. 进入 `Settings -> Pages`
2. Source 选择 `GitHub Actions`
3. 推送到 `main` 后会自动部署 `web/`

### 4. 使用 Web 控制台

打开 GitHub Pages 页面后：

1. 填 Worker API 地址
2. 填管理 Token
3. 点“读取配置”
4. 修改开关、邮箱、规则
5. 点“保存配置”

## 监控脚本行为

[monitor_action.py](/D:/Project/exchange_rate/monitor_action.py#L46) 每次执行时会先从 Worker 拉配置，再访问中国银行外汇牌价，并按规则判断是否发信。

支持的货币代码当前包括：

- `GBP`
- `JPY`
- `USD`
- `EUR`
- `HKD`
- `AUD`
- `CAD`
- `SGD`

## 目录结构

```text
.
├─ .github/workflows/
│  ├─ deploy-pages.yml
│  └─ monitor.yml
├─ web/
│  ├─ app.js
│  ├─ index.html
│  └─ styles.css
├─ worker/
│  ├─ package.json
│  ├─ wrangler.jsonc
│  └─ src/index.js
├─ monitor_action.py
└─ requirements.txt
```

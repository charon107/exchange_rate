# 技术文档：中国银行汇率监控系统

## 1. 项目概览

这个项目由三部分组成：

- `web/`：前端控制台，用户通过网页维护监控配置
- `worker/`：Cloudflare Worker，负责存取配置并给前端提供辅助接口
- `monitor_action.py`：GitHub Actions 定时执行的 Python 监控脚本

核心目标是：

1. 用户在网页中配置规则
2. 配置保存到 Cloudflare KV
3. GitHub Actions 按 cron 定时运行 Python 脚本
4. 脚本抓取中国银行汇率页面
5. 命中规则后按规则绑定邮箱发提醒邮件

## 2. 系统架构

### 2.1 组件职责

**前端 `web/`**

- 展示控制台页面
- 自动读取当前配置
- 修改监控规则和邮箱绑定关系
- 请求 Worker 保存配置
- 请求 Worker 获取最近一次汇率参考值

**Cloudflare Worker `worker/src/index.js`**

- `GET /api/config`：读取配置
- `POST /api/config`：保存配置
- `GET /api/rates`：抓取中国银行最新汇率，返回前端用于阈值参考
- 配置存储在 Cloudflare KV 中

**GitHub Actions + Python**

- GitHub Actions 按定时规则运行
- 运行 `monitor_action.py`
- Python 脚本从 Worker 读取配置
- Python 脚本直接抓中国银行外汇牌价
- 命中规则后通过 SMTP 发邮件

## 3. 数据流

### 3.1 用户配置流程

1. 用户打开网页
2. 前端调用 Worker 的 `/api/config`
3. Worker 从 KV 返回当前配置
4. 用户修改规则与邮箱绑定
5. 前端调用 Worker 的 `POST /api/config`
6. Worker 将新配置写入 KV

### 3.2 自动监控流程

1. GitHub Actions 根据 cron 触发
2. 运行 `python monitor_action.py`
3. 脚本请求 Worker `/api/config`
4. 获取当前监控配置
5. 抓取中国银行页面 `https://www.boc.cn/sourcedb/whpj/`
6. 解析对应币种的买入价、卖出价、更新时间
7. 遍历所有启用规则
8. 若命中规则，则只向该规则绑定的邮箱发送邮件

## 4. 当前配置模型

当前配置结构如下：

```json
{
  "enabled": true,
  "emails": [
    "a@example.com",
    "b@example.com"
  ],
  "rules": [
    {
      "enabled": true,
      "currency": "JPY",
      "field": "sell",
      "operator": "lt",
      "threshold": 5.0,
      "emails": [
        "a@example.com"
      ]
    },
    {
      "enabled": true,
      "currency": "USD",
      "field": "buy",
      "operator": "gt",
      "threshold": 720.0,
      "emails": [
        "a@example.com",
        "b@example.com"
      ]
    }
  ]
}
```

说明：

- `enabled`：全局监控开关
- `emails`：邮箱池，前端统一维护
- `rules[].enabled`：单条规则开关
- `rules[].currency`：币种代码
- `rules[].field`：`buy` 或 `sell`
- `rules[].operator`：`gt` 或 `lt`
- `rules[].threshold`：阈值
- `rules[].emails`：该规则绑定的邮箱列表

这实现了“规则和邮箱是 n 对 n 关系”：

- 一个规则可以绑定多个邮箱
- 一个邮箱可以被多条规则复用

## 5. 前端逻辑

关键文件：

- [web/index.html](/D:/Project/exchange_rate/web/index.html)
- [web/app.js](/D:/Project/exchange_rate/web/app.js)
- [web/styles.css](/D:/Project/exchange_rate/web/styles.css)

当前前端行为：

- 页面加载后自动调用 `loadConfig()`
- 页面加载后自动调用 `loadRates()`
- 阈值输入框会显示最新参考汇率作为 placeholder
- 规则中的“启用”与页面底部“启用监控”都使用滑块样式
- 页面内置了 Worker API 地址和访问 token

## 6. Worker 接口

关键文件：

- [worker/src/index.js](/D:/Project/exchange_rate/worker/src/index.js)

### 6.1 `GET /health`

健康检查接口。

返回：

```json
{
  "ok": true
}
```

### 6.2 `GET /api/config`

读取当前监控配置。

要求：

- 需要 `Authorization: Bearer <CONFIG_API_TOKEN>`

### 6.3 `POST /api/config`

保存监控配置。

要求：

- 需要 `Authorization: Bearer <CONFIG_API_TOKEN>`

### 6.4 `GET /api/rates`

抓取中国银行最新汇率，供前端显示参考值。

要求：

- 需要 `Authorization: Bearer <CONFIG_API_TOKEN>`

## 7. Python 监控脚本逻辑

关键文件：

- [monitor_action.py](/D:/Project/exchange_rate/monitor_action.py)

### 7.1 主要流程

`main()` 做的事：

1. 读取 GitHub Secrets 中的邮箱配置和 Worker 配置
2. 请求 Worker 获取当前运行时配置
3. 如果全局监控关闭，直接结束
4. 抓取中国银行汇率页面
5. 遍历所有启用规则
6. 若命中规则，只向该规则的绑定邮箱发送邮件

### 7.2 汇率抓取

函数：

- `get_boc_exchange_rates()`

从中国银行页面解析：

- `buy`：现汇买入价
- `sell`：现汇卖出价
- `update_time`：更新时间

### 7.3 规则判断

函数：

- `evaluate_rule()`

规则判断方式：

- `gt`：当前值大于阈值
- `lt`：当前值小于阈值

### 7.4 邮件发送

函数：

- `send_rule_alert()`

行为：

- 命中后生成纯文本和 HTML 两种邮件内容
- Gmail 使用 `smtp.gmail.com:587`
- 其他默认走 `smtp.qq.com:465`
- 带 3 次重试

## 8. GitHub Actions 调度

关键文件：

- [.github/workflows/monitor.yml](/D:/Project/exchange_rate/.github/workflows/monitor.yml)

当前 cron：

```yaml
schedule:
  - cron: "*/10 1-9 * * 1-5"
```

含义：

- 每 10 分钟运行一次
- UTC 1:00 到 9:59
- 周一到周五

换算为北京时间，大致是：

- 工作日 9:00 到 17:59
- 每 10 分钟执行一次

## 9. 邮件发送范围

现在不是“所有规则命中都发给所有邮箱”，而是：

- 只有命中的规则才会发信
- 只有被该规则绑定的邮箱才会收到这封信

这使得不同用户可以只接收自己关心的币种和条件。

## 10. 当前已知限制

### 10.1 前端内置管理 token

当前前端把 Worker 的访问 token 直接写在页面代码里。  
这意味着任何能访问页面的人都能修改配置。

这适合轻量内部使用，不适合公开管理后台。

### 10.2 Worker 参考值依赖实时抓取

前端显示的参考值是通过 Worker 实时抓中国银行页面得到的。  
如果中国银行页面结构变化，参考值显示可能失效。

### 10.3 邮件是规则触发即发，不做去重

如果某条规则在多次定时检查中持续命中，就可能在多次执行中重复发邮件。  
当前没有“冷却时间”或“去重窗口”。

## 11. 可继续扩展的方向

- 为规则增加冷却时间，避免重复发信
- 增加“测试邮件”按钮
- 支持更多通知渠道，如 Telegram、Slack、企业微信
- 引入真正的登录权限，而不是把 token 写在前端
- 增加历史汇率记录和趋势图

## 12. 目录结构

```text
.
├─ .github/workflows/
│  └─ monitor.yml
├─ web/
│  ├─ app.js
│  ├─ index.html
│  └─ styles.css
├─ worker/
│  ├─ package.json
│  ├─ package-lock.json
│  ├─ wrangler.jsonc
│  └─ src/index.js
├─ monitor_action.py
├─ requirements.txt
├─ README.md
└─ technical doc.md
```

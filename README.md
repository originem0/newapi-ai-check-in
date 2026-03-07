# newapi.ai 多账号自动化奖励脚本

用于多账号执行 `newapi.ai` / 类 `newapi` 站点的自动化流程。  
当前仓库已从单纯“签到脚本”演进为**自动化奖励脚本**，支持：

- 常规签到
- 查询用户信息时自动触发奖励
- 通过转盘 / 抽奖获得奖励
- 通过 CDK 自动充值
- cookies / GitHub / Linux.do 多种认证方式
- Linux.do 读帖自动化任务

> 注意：不同 provider 的奖励方式不同，并不都是“签到”。  
> 例如：`x666 / 薄荷 API` 走的是 **up.x666.me 抽奖自动到账**，不是 `/api/user/checkin`。

---

## 功能特性

- ✅ 单账号 / 多账号运行
- ✅ cookies、GitHub、Linux.do 多认证方式
- ✅ 仅尝试已配置的通知渠道
- ✅ Cloudflare / WAF 场景支持
- ✅ 敏感信息日志脱敏（cookie / token / CDK / OAuth code）
- ✅ 账号级统计与正确退出码
- ✅ `x666` 等特殊 provider 的显式行为建模

---

## 当前支持的内置 provider

- AnyRouter
- AgentRouter
- WONG
- 薄荷 API (`x666`)
- Huan API
- KFC API
- B4U
- Elysiver
- HotaruApi
- Neb
- runawaytime
- 以及仓库内置的其它 provider

你也可以通过 `PROVIDERS` 自定义 provider。

---

## 行为模型说明

### 1) 常规签到

典型路径：

- 查询今日签到状态
- 若未签到则调用 `/api/user/checkin`
- 然后查询用户信息

### 2) 自动奖励（查询用户信息即触发）

部分站点没有独立签到接口，查询用户信息时会自动完成奖励流程。

### 3) 抽奖 / 转盘奖励

部分 provider 不是签到，而是抽奖或轮盘：

- `x666`：调用 `up.x666.me` 抽奖，奖励直接累计到账户
- `b4u` / `runawaytime`：通过抽奖获取 CDK，再自动充值

### 4) CDK 自动充值

若 provider 配置了 `get_cdk + topup_path`，脚本会：

- 获取 CDK
- 按顺序执行充值
- 失败则停止后续充值

### 5) Linux.do 读帖自动化

仓库还包含独立的 Linux.do 自动读帖任务：

- 尝试恢复 Linux.do 登录态
- 自动浏览一批 topic
- 输出页面行为结果
- 严格区分：
  - 页面行为成功
  - 业务验证成功
  - 无法验证（`uncertain`）
  - 基础设施失败（`infra_failed`）

> 重要：  
> 当前版本**不能稳定从服务端证明“读帖任务已完成”**，所以读帖任务即使访问了一批有效帖子，也默认只会记为 `uncertain`，而不是完全成功。

---

## 使用方法

### 1. Fork 本仓库

点击右上角 **Fork**，将仓库 fork 到你自己的 GitHub 账户。

### 2. 启用 GitHub Actions

1. 打开你 fork 后仓库的 **Actions**
2. 启用 workflow
3. 设置 `production` Environment（推荐）

### 3. 配置环境变量 / Secrets

建议在：

- `Settings -> Environments -> production -> Environment secrets`

中配置以下变量。

---

## 账号配置

### `ACCOUNTS`

主账号配置，必须是 JSON 数组。

示例：

```json
[
  {
    "name": "主账号",
    "provider": "anyrouter",
    "cookies": {
      "session": "你的 session"
    },
    "api_user": "你的 api_user"
  },
  {
    "name": "使用全局 OAuth",
    "provider": "agentrouter",
    "github": true,
    "linux.do": true
  },
  {
    "name": "薄荷",
    "provider": "x666",
    "cookies": {
      "session": "你的 session"
    },
    "api_user": "你的 api_user",
    "access_token": "来自 qd.x666.me 的 token"
  }
]
```

### 字段说明

- `name`：可选，日志和通知中的显示名称
- `provider`：可选，默认 `anyrouter`
- `cookies`：可选，用于 cookies 登录
- `api_user`：使用 cookies 时必填
- `proxy`：可选，单账号代理
- `github`：可选，支持 `true / object / array`
- `linux.do`：可选，支持 `true / object / array`
- `access_token`：`x666` 必填
- `get_cdk_cookies`：部分需要外部站点抽奖的 provider 必填

### OAuth 配置格式

`github` 和 `linux.do` 支持三种格式：

#### 1. `true`：使用全局账号

```json
{"provider": "agentrouter", "github": true}
```

#### 2. 单个账号对象

```json
{"provider": "agentrouter", "github": {"username": "user", "password": "pass"}}
```

#### 3. 多账号数组

```json
{"provider": "agentrouter", "github": [
  {"username": "user1", "password": "pass1"},
  {"username": "user2", "password": "pass2"}
]}
```

---

## 全局 OAuth 账号

### `ACCOUNTS_GITHUB`

```json
[
  {"username": "用户名1", "password": "密码1"},
  {"username": "用户名2", "password": "密码2"}
]
```

### `ACCOUNTS_LINUX_DO`

```json
[
  {"username": "用户名1", "password": "密码1"},
  {"username": "用户名2", "password": "密码2"}
]
```

---

## 特殊 provider 说明

### `x666 / 薄荷 API`

这是当前最容易误解的 provider。

#### 它不是“普通签到”

当前实现中：

- 不调用常规 `/api/user/checkin`
- 会访问 `up.x666.me`
- 执行每日抽奖
- 奖励**自动累积到账户**

#### 必填字段

```json
{
  "provider": "x666",
  "cookies": {"session": "..."},
  "api_user": "...",
  "access_token": "..."
}
```

如果缺少 `access_token`，账号会在加载阶段被跳过。

#### `access_token` 能否自动获取？

**当前版本不能自动获取。**

仓库现在只会消费你提供的 `access_token`，不会自动登录 `qd.x666.me` 去抓取 token。

---

## 自定义 provider

### `PROVIDERS`

用于补充自定义 provider，必须是 JSON 对象。

说明：

- 自定义 provider 适用于规则较简单的站点
- 复杂的 `get_cdk` / 特殊 OAuth / 特殊奖励逻辑仍需要代码支持

---

## 代理配置

### 全局代理：`PROXY`

```json
{
  "server": "http://proxy.example.com:8080"
}
```

或者：

```json
{
  "server": "http://proxy.example.com:8080",
  "username": "username",
  "password": "password"
}
```

### 单账号代理

直接在 `ACCOUNTS` 某个账号内写：

```json
{
  "provider": "anyrouter",
  "proxy": {
    "server": "http://proxy.example.com:8080"
  }
}
```

---

## 无人值守 / 交互式行为

### `ALLOW_INTERACTIVE_AUTH`

默认情况下，脚本按**无人值守优先**策略运行。

这意味着：

- 如果某个流程需要人工 OTP
- 或 Cloudflare 验证必须人工介入

脚本会**明确失败**，而不是无限等待或伪装成自动化成功。

若你希望允许手动介入，可设置：

```bash
ALLOW_INTERACTIVE_AUTH=true
```

适合：

- 手动触发 workflow
- 本地调试

不建议用于真正的定时无人值守任务。

---

## 调试产物

### `DEBUG_ARTIFACTS`

默认情况下，脚本**不会**把异常 HTML / 原始响应体落盘。

如果需要排查特殊问题，可开启：

```bash
DEBUG_ARTIFACTS=true
```

开启后：

- 解析失败的响应可能会写入 `logs/`
- 仅用于临时调试

建议调试完成后关闭。

---

## 如何获取 `cookies` 与 `api_user`

### 获取 `session` cookie

浏览器 F12 -> Application -> Cookies -> `session`

> session 可能会失效，失效后通常会出现 401 / 认证失败。

![获取 cookies](./assets/request-cookie-session.png)

### 获取 `api_user`

浏览器 F12 -> Application -> Local Storage -> `user` 对象中的 `id`

![获取 api_user](./assets/request-api-user.png)

---

## GitHub / Linux.do 自动化说明

### GitHub

- 支持缓存的登录态恢复
- 支持通过 StepSecurity wait-for-secrets 注入 OTP
- 若无人值守模式下必须人工输入 OTP，会显式失败

### Linux.do

- 支持缓存登录态恢复
- 支持 Cloudflare 挑战自动求解
- 若自动求解失败且不允许交互式认证，会显式失败

### Linux.do 读帖任务

独立 workflow：

- `.github/workflows/linuxdo-read.yml`

当前实现要点：

- 读取 `ACCOUNTS_LINUX_DO`
- 维护独立的 topic 状态缓存
- 优先从 Linux.do 列表页发现当前账号可见的 topic 候选
- 列表页发现会优先使用更精确的 topic 列表选择器，而不是直接抓全页面所有 `/t/` 链接
- 默认**不启用**旧的 topic ID 扫描 fallback
- 只有显式设置 `LINUXDO_ENABLE_ID_FALLBACK=true` 时，才会启用旧的 ID 扫描策略
- 使用更严格的结果模型：
  - `uncertain`
  - `failed`
  - `infra_failed`

#### 相关环境变量

- `ACCOUNTS_LINUX_DO`
- `LINUXDO_BASE_TOPIC_ID`
- `LINUXDO_MAX_POSTS`
- `LINUXDO_MAX_TOPIC_ATTEMPTS`
- `LINUXDO_MAX_RUNTIME_SECONDS`
- `LINUXDO_ENABLE_ID_FALLBACK`
- `ALLOW_INTERACTIVE_AUTH`

这些变量即使在 GitHub Actions 中被注入为空字符串，也会自动回退到默认值，不会再因为 `int('')` 之类的问题直接崩溃。

其中：

- `LINUXDO_ENABLE_ID_FALLBACK`
  - 默认关闭
  - 仅当列表页候选发现不足、且你明确允许时，才会启用旧版 topic ID 扫描

#### 读帖状态缓存

读帖任务现在使用 `linuxdo_reads/*.json` 存储结构化状态，包含：

- `last_topic_id`
- `last_success_topic_id`
- `invalid_streak`
- `attempted_count`
- `last_run_at`

同时兼容旧版缓存：

- `linuxdo_reads/*_topic_id.txt`

如果发现旧版 txt 缓存，脚本会自动迁移到新的 JSON 状态文件。

另外，当前版本增加了**坏区间自恢复**逻辑：

- 如果缓存游标相对 `LINUXDO_BASE_TOPIC_ID` 漂移过大
- 且本轮一个有效 topic 都没有读到

脚本会自动回退到 base 区间并重试一次，避免长期卡死在无效 topic 区间。

#### 读帖任务的结果解释

- `uncertain`
  - 页面访问和滚动行为完成
  - 但无法严格证明服务端已记录“读帖任务完成”
- `failed`
  - 没有读到有效帖子，或登录失败
- `infra_failed`
  - 网络、站点可达性、基础设施层失败

这比旧版“自认为成功”更保守，也更诚实。

---

## 通知

脚本只会尝试**已配置的通知方式**。

支持：

- Email
- DingTalk
- Feishu
- WeChat Work
- PushPlus
- Server 酱
- Telegram

相关变量：

- `EMAIL_USER`
- `EMAIL_PASS`
- `EMAIL_TO`
- `CUSTOM_SMTP_SERVER`
- `DINGDING_WEBHOOK`
- `FEISHU_WEBHOOK`
- `WEIXIN_WEBHOOK`
- `PUSHPLUS_TOKEN`
- `SERVERPUSHKEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

当前通知标题已从旧的 `Check-in Alert` 改为更准确的：

- `Automation Run Alert`

---

## Action 保活（可选）

GitHub 对长期无活动的 fork 仓库可能会自动禁用 Actions。  
如果你想尽量保持自动运行，可配置：

- `ACTIONS_TRIGGER_PAT`

---

## 执行结果与退出码

当前版本已修复旧版统计问题：

- 以**账号级**成功/失败为准
- 不再把“认证方式数量”误当作“账号数量”
- 退出码含义：
  - `0`：至少一个账号成功
  - `1`：全部账号失败，或系统初始化失败

---

## 本地开发

```bash
uv sync --dev
python -m camoufox fetch
uv run pytest
uv run main.py
```

### 本地运行 Linux.do 读帖任务

```bash
uv sync --dev
python -m camoufox fetch
uv run python -u linuxdo_read_posts.py
```

如果你要本地手动处理 challenge / 登录交互，可以临时打开：

```bash
ALLOW_INTERACTIVE_AUTH=true
```

---

## 故障排查

如果运行失败，请优先检查：

1. `ACCOUNTS` 是否为合法 JSON 数组
2. cookies + `api_user` 是否对应同一账号
3. `x666` 是否配置了有效 `access_token`
4. 是否触发了需要人工介入的 OTP / Cloudflare 验证
5. provider 接口是否已变更
6. 是否开启了代理且代理可用

---

## 安全说明

当前版本已对以下信息做脱敏处理：

- cookies
- token
- OAuth code
- CDK
- StepSecurity secrets

但你仍应当把仓库当作**敏感自动化仓库**处理：

- 不要把真实密钥提交到 git
- 优先使用 GitHub Environment secrets
- 调试时谨慎开启 `DEBUG_ARTIFACTS`

---

## 免责声明

本项目仅用于学习、研究与自动化实践，请在使用前确认遵守目标网站的使用条款与相关规则。

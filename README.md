# AI Daily Skill

为企业部门生成个性化日报。通过飞书知识库和群聊自动构建部门画像，从互联网采集当天最新资讯，输出 HTML 日报页面。

## 前提条件

- Claude Code / OpenClaw 环境
- Python 3
- 飞书 MCP 插件（任意版本均可，skill 会自动适配工具名）

### 飞书权限

飞书 MCP 插件需要以下权限。不同插件封装方式不同，有些已内置，有些需要在[飞书开放平台](https://open.feishu.cn)手动开启：

| 权限 | 权限标识 | 用途 | 缺失影响 |
|---|---|---|---|
| 知识库节点列表 | `wiki:wiki:readonly` | 初始化画像 | 无法自动生成画像 |
| 读取文档内容 | `docx:document:readonly` | 初始化画像 | 同上 |
| 读取群聊消息 | `im:message:readonly` | 每日信号采集 | 画像不会自动更新 |
| 读取群聊信息 | `im:chat:readonly` | 验证群聊 ID | 无法验证群是否存在 |
| 用户信息（可选） | `contact:user.base:readonly` | 识别发言人 | 不影响核心功能 |

> **权限不全也能用**：缺少知识库权限 → 手动创建画像文件即可。缺少群聊权限 → 以 degraded 模式运行（不读群聊，仅靠搜索）。skill 会告诉你具体是哪个权限缺失。

## 第一次使用

### 1. 安装 skill

将本目录放入 Claude Code 的 skills 目录下。

### 2. 运行初始化

```bash
/ai-daily
```

AI 会自动完成以下操作（无需手动配置）：

1. 扫描你安装的飞书 MCP 工具，自动匹配可用能力
2. 读取飞书知识库，推断你所在部门的领域、关注话题和跟踪实体
3. 搜索并验证适合该部门的信息来源（官方博客、行业媒体、社区等）
4. 生成部门画像文件 `config/dept-profile.yaml`
5. 展示推荐的信息来源，等你确认

### 3. 绑定飞书群聊

初始化完成后，AI 会提示你设置一个飞书群聊 ID。这个群的讨论内容会被用来**更新画像权重**（不会出现在日报正文中）：

```bash
/ai-daily set-group <chat_id>
```

设置后状态变为 `active`，可以开始生成日报。

> **没有飞书群聊？** 可以跳过这一步，skill 会以 `degraded` 模式运行——只用画像静态配置和搜索结果生成日报，不读取群聊信号。

### 4. 生成第一份日报

```bash
/ai-daily
```

AI 会搜索当天资讯、筛选加工、生成 HTML，然后启动本地服务并在浏览器中打开。

## 日常使用

```bash
/ai-daily                    # 生成今日日报
/ai-daily 竞品动态            # 本次重点关注某方向
/ai-daily 2026-03-20         # 指定日期
```

每次运行时，AI 会：
1. 读取飞书群聊当天消息，更新画像权重（哪些话题讨论多→搜索权重提高）
2. 基于画像搜索当天资讯（≥10 条查询，一手来源优先）
3. 按"最新 > 最真 > 最热"筛选，生成 HTML 日报
4. 启动本地 HTTP 服务，浏览器打开

## 调整配置

### 控制命令

| 命令 | 什么时候用 |
|---|---|
| `/ai-daily set-group <chat_id>` | 换一个飞书群作为信号源 |
| `/ai-daily set-domain <domain>` | 手动修正部门领域（如 `product`、`engineering`、`finance`） |
| `/ai-daily set-context <text>` | 补充自由文本描述（如"专注日本市场的 B2B SaaS"） |
| `/ai-daily refresh-profile` | 重新读取飞书 KB 刷新画像（保留群聊信号历史） |

### 手动编辑画像

直接编辑 `config/dept-profile.yaml` 可以：

- 添加/删除跟踪实体（`tracking.competitors` 等）
- 调整话题权重（`topic_weights`）
- 修改信息来源（`sources.direct`、`sources.search_queries`）
- 调整信号处理参数（`signal_rules`）

完整字段说明见 `reference/dept-profile-template.yaml`。

### 支持的领域

`set-domain` 可选值：`ai`、`product`、`engineering`、`marketing`、`finance`、`legal`、`operations`、`sales`、`research`、`hr`、`data`、`design`、`growth`、`security`、`strategy`、`customer_success`、`bd`、`general`

## 日报页面功能

生成的 HTML 日报包含：

- **左栏**：今日速览（3 条）、行动建议（可一键发送给 AI 工具）、趋势雷达
- **右栏**：资讯卡片（标题 + 摘要 + 与你相关 + 标签 + 原文链接）
- **交互**：投票、收藏、标签关注、AI 深入（支持 Claude/ChatGPT/DeepSeek）
- **反馈采集**：阅读行为自动记录，离开页面时提交，用于下次画像更新

## 局域网共享

反馈服务默认监听 `0.0.0.0:17890`，同一局域网的其他设备可以直接访问：

```
http://<你的局域网 IP>:17890/daily/2026-03-23.html
```

启动时会打印局域网地址。

## 常见问题

### 初始化时提示"找不到飞书工具"

飞书插件未安装。安装任意飞书 MCP 插件即可，或手动创建 `config/dept-profile.yaml`。

### 初始化时提示权限不足 / 403

知识库或文档读取权限未开启。去[飞书开放平台](https://open.feishu.cn) → 应用权限 → 开启 `wiki:wiki:readonly` 和 `docx:document:readonly`。

### 群聊消息读取失败

- `im:message:readonly` 权限未开启 → 在飞书开放平台开启
- 群聊 ID 错误 → 在飞书群设置中查看群链接，重新 `/ai-daily set-group <正确ID>`

### 日报跑完了但提示有步骤被跳过

这是正常的降级模式。AI 会在输出中标注 `⚠️ [步骤名] 未完成 — [原因] — [建议操作]`。常见原因：
- 群聊权限缺失 → 画像未更新但日报仍可生成
- 搜索结果不足 → 日报条数可能少于预期
- 渲染脚本报错 → 检查 JSON 格式

### 日报内容太旧，不是今天的新闻

Skill 要求 ≥80% 内容来自今天/昨天。如果仍然偏旧，可以 `/ai-daily refresh-profile` 刷新画像后重试。

### 服务启动失败

端口 17890-17899 被占用 → 关闭占用程序或等待旧服务超时退出（默认 2 小时）。

### 群聊信号没有生效

确认 `config/dept-profile.yaml` 中 `status` 为 `active`，且 `department.feishu_group_id` 已设置。

## 目录结构

```text
.
├── SKILL.md                          # 技能定义（AI 执行指令）
├── config/
│   └── dept-profile.yaml             # 部门画像（自动生成 + 每日更新）
├── reference/                        # 模板和示例文件
├── scripts/
│   ├── render_daily.py               # JSON → HTML 渲染
│   ├── open_daily.py                 # 打开日报页面
│   └── feedback_server.py            # HTTP 服务 + 反馈接收
├── output/daily/                     # 生成的日报文件
└── data/feedback/                    # 反馈数据
```

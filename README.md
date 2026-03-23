# AI Daily Skill

企业部门日报生成技能。通过飞书知识库和群聊信号自动构建部门画像，从互联网多渠道采集与部门相关的资讯，经 AI 加工后生成 HTML 日报页面。

## 核心特性

- **部门画像驱动** — 首次使用时读取飞书知识库自动推断部门领域、关注话题和信息来源
- **群聊信号更新** — 每日从飞书群聊提取讨论热点，增量更新画像权重
- **领域无关** — 支持任意部门（产品/工程/市场/金融/法务等），搜索策略和标签由画像决定
- **质量框架** — 事实密度要求、来源分层（一手/二手/社区）、出稿前自检
- **结构化 JSON → 模板渲染** — AI 生成结构化数据，脚本稳定输出 HTML
- **反馈闭环** — 本地 HTTP 服务采集阅读行为，支持局域网访问

## 目录结构

```text
.
├── SKILL.md                          # 技能定义（AI 执行指令）
├── config/
│   └── dept-profile.yaml             # 部门画像（自动生成 + 每日更新）
├── reference/
│   ├── daily_example.html            # HTML 成品样板
│   ├── daily_payload_example.json    # JSON payload 示例
│   ├── daily_evaluation_template.md  # 日报质量评估模板
│   ├── dept-profile-template.yaml    # 部门画像 schema 模板
│   ├── feedback_schema.json          # 反馈数据 JSON Schema
│   └── profile_template.yaml         # 旧版配置模板（仅迁移用）
├── scripts/
│   ├── render_daily.py               # JSON → HTML 渲染
│   ├── open_daily.py                 # 打开日报页面
│   └── feedback_server.py            # HTTP 服务 + 反馈接收
├── output/
│   └── daily/                        # 生成的 JSON 和 HTML
└── data/
    └── feedback/                     # 反馈数据
```

## 快速开始

### 首次使用

运行 `/ai-daily`，skill 会自动：

1. 读取飞书知识库，推断部门画像
2. 搜索并验证适合该部门的信息来源
3. 生成 `config/dept-profile.yaml`
4. 提示设置飞书群聊 ID：`/ai-daily set-group <chat_id>`

### 日常使用

```bash
/ai-daily                    # 生成今日日报
/ai-daily 竞品动态            # 重点关注某方向
/ai-daily 2026-03-20         # 指定日期
```

### 控制命令

```bash
/ai-daily set-group <chat_id>         # 设置飞书群聊 ID
/ai-daily set-domain <domain>         # 设置主领域
/ai-daily set-context <text>          # 设置自由文本上下文
/ai-daily refresh-profile             # 重新读取飞书 KB 重建画像
```

## 画像状态机

`dept-profile.yaml` 有 4 个状态：

```
uninitialized → awaiting_group_id → active ⇄ degraded
```

| 状态 | 含义 |
|---|---|
| `uninitialized` | 首次使用，需读取飞书 KB |
| `awaiting_group_id` | 画像已生成，等待设置群聊 ID |
| `active` | 正常运行 |
| `degraded` | 飞书 MCP 不可用，跳过群聊信号，使用当前画像继续生成 |

## 执行流程

```
第零步：画像检查 → 状态路由
第一步：读取飞书群聊信号 → 增量更新画像
第二步：画像驱动搜索（≥10 条查询，一手来源优先）
第三步：筛选加工（最新 > 最真 > 最热，事实密度检查）
第四步：生成 JSON → render_daily.py 渲染 HTML
第五步：更新导航首页
第五点五步：更新画像历史
第六步：启动反馈服务
第七步：输出结果
```

## 质量框架

### 事实密度

每条资讯必须包含 `key_facts`（实体名、日期、硬数字、约束条件）和 `source_tier`（primary/secondary/community）。

### 来源分层

1. **一手来源（primary）** — 官方博客/changelog/release/论文直链
2. **二手来源（secondary）** — 媒体报道、公众号（只作线索层）
3. **社区来源（community）** — Twitter/Reddit/HN 讨论

### 出稿前自检

- 每条有硬数据？
- ≥60% 标记为一手来源？
- ≥80% 来自今天/昨天？
- "与你相关"具体到行动？
- 覆盖 ≥3 个不同话题方向？

## 脚本说明

### render_daily.py

```bash
python3 scripts/render_daily.py output/daily/2026-03-23.json
```

### open_daily.py

```bash
python3 scripts/open_daily.py 2026-03-23              # 自动选择
python3 scripts/open_daily.py 2026-03-23 --mode http   # 仅 HTTP
python3 scripts/open_daily.py 2026-03-23 --mode file   # 仅本地文件
```

### feedback_server.py

```bash
python3 scripts/feedback_server.py
```

- 默认监听 `0.0.0.0:17890`，支持局域网访问
- 端口冲突自动 +1
- 超时 2 小时自动退出
- 启动时自动清理残留的 `.server_port` 文件

## 配置

服务相关配置在 `config/dept-profile.yaml` 外独立管理，使用 SKILL.md 默认值（端口 17890，超时 2 小时）。

画像中的 `signal_rules` 可调整信号处理参数：

```yaml
signal_rules:
  topic_boost_threshold: 2      # 话题增强最低消息数
  daily_decay: 0.9              # 每日权重衰减系数
  max_messages_per_run: 1000    # 群聊消息分页上限
  high_weight_query_threshold: 0.6  # 高权重话题分配 2 条查询
```

完整参数见 `reference/dept-profile-template.yaml`。

## 飞书 MCP 依赖

| 能力 | 工具名 | 用途 |
|---|---|---|
| 列出 KB 节点 | `feishu_wiki_space_node` | 初始化画像 |
| 读取文档 | `feishu_fetch_doc` | 初始化画像 |
| 读取群聊消息 | `feishu_im_user_get_messages` | 每日信号采集 |

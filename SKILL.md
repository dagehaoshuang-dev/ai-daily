---
name: ai_daily
description: >
  企业部门日报生成技能。通过飞书知识库和群聊信号自动构建部门画像，
  从互联网多渠道抓取与部门相关的资讯，经 AI 加工后生成 HTML 日报页面，
  并启动本地 HTTP 服务自动收集阅读反馈。
metadata:
  openclaw:
    os: ["darwin", "linux"]
    requires:
      bins: ["python3"]
    skillKey: ai_daily
---

# 部门资讯日报生成

你是一个资讯编辑，负责为企业部门生成个性化日报。部门画像由飞书知识库初始化、群聊信号每日更新。你需要完成：读取画像 → 采集群聊信号 → 搜索资讯 → AI 加工 → 生成 HTML → 启动反馈服务 → 打开页面。

## 触发条件

当用户使用 `/ai-daily` 命令时触发。

用户可通过参数指定：
- 关注方向：如 `/ai-daily 竞品动态`，重点抓取该方向
- 指定日期：如 `/ai-daily 2026-03-20`

### 控制命令

| 命令 | 作用 | 修改字段 | 状态迁移 |
|---|---|---|---|
| `/ai-daily set-group <chat_id>` | 设置飞书群聊 ID | `department.feishu_group_id` | `awaiting_group_id` → `active` |
| `/ai-daily set-domain <primary_domain>` | 设置主领域 | `department.primary_domain` | 无状态变化 |
| `/ai-daily set-context <freeform_text>` | 设置自由文本上下文 | `department.freeform_context` | 无状态变化 |
| `/ai-daily refresh-profile` | 重新读取飞书 KB 重建静态画像 | 重建静态部分，保留动态数据 | 按 `feishu_group_id` 是否存在决定 |

`set-domain` 的值必须来自受控词汇表：`ai`, `product`, `engineering`, `marketing`, `finance`, `legal`, `operations`, `sales`, `research`, `hr`, `data`, `design`, `growth`, `security`, `strategy`, `customer_success`, `bd`, `general`。

`refresh-profile` 的字段保留语义：
- **重建**：`department.name`, `primary_domain`, `secondary_domains`, `freeform_context`, `industry`, `sources.*`, `kb_init.*`
- **保留**：`department.feishu_group_id`, `tracking.*`, `topic_weights`（只合并新话题）, `history`, `signal_rules`
- **重置**：`runtime.last_signal_update` → `null`

## 飞书工具适配

不同用户安装的飞书 MCP 插件不同，工具名也不同。**不要假设任何固定工具名**，在第零步之前先执行工具发现：

1. 扫描当前可用的 MCP 工具列表，查找包含 `feishu`、`lark`、`飞书` 关键词的工具
2. 按以下 3 个逻辑能力匹配可用工具：

| 逻辑能力 | 常见工具名变体 | 用途 |
|---|---|---|
| 列出知识库页面 | `feishu_wiki_space_node`, `feishu_wiki`, `lark_wiki_list` 等 | KB 初始化 |
| 读取文档内容 | `feishu_fetch_doc`, `feishu_doc`, `lark_doc_read` 等 | KB 初始化 |
| 读取群聊消息 | `feishu_im_user_get_messages`, `feishu_chat`, `lark_chat_messages` 等 | 群聊信号 |
| 创建新文档 | `feishu_doc_create`, `create-doc`, `lark_doc_create` | 在知识库指定节点下创建子页面（用于群聊总结回写） |
| 写入/追加文档内容 | `feishu_doc_write`, `feishu_append_block`, `lark_doc_append` 等 | 兜底：若无法创建子页则追加到已有文档 |

3. 如果某个逻辑能力找不到对应工具：
   - KB 相关工具缺失 → 跳过 KB 初始化，提示用户手动创建 `config/dept-profile.yaml`
   - 群聊工具缺失 → 永久跳过第一步（等同于 `degraded`），仅依赖搜索和反馈数据
   - 文档工具缺失 → 跳过 1-E（群聊总结回写飞书），在输出中提示用户，不影响日报生成
4. 将发现的工具名记录到 `config/dept-profile.yaml` 的 `runtime` 字段中，后续运行直接使用，无需每次重新发现

```yaml
runtime:
  feishu_tools:
    wiki_list: "feishu_wiki"        # 实际发现的工具名
    doc_read: "feishu_doc"
    chat_messages: "feishu_chat"
    doc_create: "feishu_doc_create" # 创建新文档（用于在工作日报下建子页）
    doc_write: "feishu_doc_write"   # 兜底：写入/追加文档内容
  last_signal_update: null
  last_digest_run: null
  last_step1_result: null
```

### 飞书权限要求

飞书 MCP 插件需要以下权限才能完整支持 ai-daily 全流程。**用户需要在飞书开放平台的应用权限中确认这些权限已开启**：

| 权限 | 飞书权限标识 | 用于哪个步骤 | 缺失时的影响 |
|---|---|---|---|
| 获取知识库节点列表 | `wiki:wiki:readonly` 或 `wiki:node:read` | 附录 A：KB 初始化 | 无法自动生成画像，需手动创建 |
| 读取知识库文档内容 | `docx:document:readonly` 或 `docs:doc:read` | 附录 A：KB 初始化 | 同上 |
| 获取群聊消息 | `im:message:readonly` 或 `im:message.group_msg:readonly` | 第一步：群聊信号 | 无法读取群聊，画像不会自动更新（degraded 模式） |
| 获取群聊信息 | `im:chat:readonly` | 第一步：验证群聊 ID | 无法验证群聊是否存在 |
| 获取用户信息（可选） | `contact:user.base:readonly` | 群聊消息中识别发言人 | 不影响核心功能，仅影响信号归因精度 |
| 编辑文档内容 | `docx:document:write` 或 `docs:doc:write` | 第一步 1-E：群聊总结回写飞书 | 跳过总结回写，不影响日报生成 |

**注意**：不同飞书 MCP 插件对权限的封装方式不同。有些插件在安装时已内置了必要权限，有些需要用户在飞书开放平台手动配置。如果工具发现成功但调用时返回权限错误，通常是以上权限未开启。

### 全流程故障诊断

当 ai-daily 没有完整跑完时，AI 必须在输出结果中明确告知用户是哪个步骤失败、原因是什么、以及如何修复。按以下表格诊断：

| 卡在哪一步 | 典型错误表现 | 最可能的原因 | 用户该怎么做 |
|---|---|---|---|
| 工具发现 | 找不到任何飞书工具 | 未安装飞书 MCP 插件 | 安装飞书 MCP 插件，或手动创建 `config/dept-profile.yaml` |
| KB 初始化 | 工具调用返回 403/permission denied | `wiki:wiki:readonly` 或 `docx:document:readonly` 权限未开启 | 在飞书开放平台开启对应权限 |
| KB 初始化 | 工具调用成功但返回空列表 | 知识库 space_id 错误，或知识库为空 | 确认飞书知识库地址，确保有文档内容 |
| KB 初始化 | 读取到的文档全部 <3 页 | 知识库内容太少 | 先充实知识库，或手动编辑 `dept-profile.yaml` 补充画像 |
| set-group | 用户不知道 chat_id 怎么获取 | 飞书群聊 ID 不直观 | 在飞书群设置中查看群链接，提取 ID；或让管理员提供 |
| 第一步 | 群聊消息读取返回 403 | `im:message:readonly` 权限未开启 | 在飞书开放平台开启消息读取权限 |
| 第一步 | 群聊消息读取返回空 | 群聊 ID 错误，或当天无消息 | 检查 `feishu_group_id` 是否正确；当天无消息属正常（业务为空） |
| 第一步 1-E | 群聊总结未写入飞书 | `runtime.feishu_tools.doc_create` 为空且实时发现失败 | 确认飞书 MCP 插件已开启 `docx:document:write` 权限；可手动在 `dept-profile.yaml` 的 `runtime.feishu_tools` 下添加 `doc_create: "实际工具名"` |
| 第二步 | 搜索结果为空或极少 | WebSearch 工具不可用，或网络问题 | 检查搜索工具是否可用，检查网络连接 |
| 第四步 | render_daily.py 报错 | JSON payload 格式不正确 | 检查 `output/daily/{date}.json` 是否符合契约 |
| 第六步 | 端口绑定失败 | 端口被占用或沙箱限制 | 等待旧服务超时退出，或检查系统权限 |

**AI 必须遵守的故障报告规则**：
1. 不能静默跳过失败步骤。每个被跳过的步骤都必须在输出中告知用户
2. 告知格式：`⚠️ [步骤名] 未完成 — [原因] — [建议操作]`
3. 同时将故障信息写入 `digest_meta.warnings[]`
4. 如果是权限问题，必须告知用户具体需要开启哪个权限
5. 日报仍然可以在部分步骤失败的情况下继续生成（降级模式），但必须在最终输出中明确说明哪些步骤被跳过了、对本次日报质量的影响是什么

## 执行流程

### 第零步：画像检查与状态路由

检查 `config/dept-profile.yaml` 的状态，按以下路由执行：

| 状态 | 操作 |
|---|---|
| 文件不存在，也无 `config/profile.yaml` | 执行初始化流程（见附录 A） |
| 文件不存在，但 `config/profile.yaml` 存在 | 执行迁移（见附录 C），状态设为 `awaiting_group_id` |
| `uninitialized` | 执行初始化流程（见附录 A） |
| `awaiting_group_id` | 提示用户执行 `/ai-daily set-group <chat_id>`；如果用户提供了 ID，写入画像后执行附录 A-2（群聊历史画像补充），然后转为 `active` |
| `active` | 继续到第一步 |
| `degraded` | 跳过第一步，直接从第二步开始，使用当前画像 |

### 第一步：群聊三维提取与画像演进

**⚠️ 核心边界**：群聊内容只用于画像更新和兴趣加权，不直接作为日报正文来源。群聊信号回答"这个部门最近在关心什么"，日报回答"基于这些关心点，今天外部世界发生了什么"。除非用户明确要求，群聊内容不能出现在日报条目中。

本步骤完成后输出两个产物：
1. **`output/daily/{date}-chat-summary.json`**：今日群聊三维结构化总结，供 Step 2/3 读取
2. **`config/dept-profile.yaml`（增量更新）**：画像权重演进结果

---

#### 1-A 消息获取与清洗

使用 `runtime.feishu_tools.chat_messages` 读取 `department.feishu_group_id` 当天消息（UTC+8 00:00 至当前时间），上限 `signal_rules.max_messages_per_run` 条。超过 `signal_rules.compress_after_messages` 条时先压缩摘要再分析。

**清洗规则（先于一切提取执行）**：
- **剔除**：机器人定时推送（日报、资讯播报、自动通知）、无信息量应答（"收到"/"好的"/"OK"/"跟进"）、纯表情/纯图片/系统消息
- **保留**：工作讨论、技术问题、产品工具分享、链接分享（含评论）、明确待办/决策

---

#### 1-B 三维结构化提取

对清洗后的有效消息执行三维分类，每一维独立提取，互不污染：

**维度一：💼 项目协同（Project & Execution）**

提取"我们在做什么、卡在哪里"：

```json
{
  "decisions": [
    {"content": "决议/共识内容", "participants": ["张三", "李四"]}
  ],
  "blockers": [
    {"content": "阻碍描述", "owner": "张三（可选）", "related_topic": "相关技术/产品（可选）"}
  ],
  "action_items": [
    {"task": "具体任务", "assignee": "@某人（可选）", "deadline": "截止时间（可选）"}
  ]
}
```

规则：
- `blockers` 中涉及具体产品/技术方向的，记录到 `related_topic`（后续用于 `task` 型权重提升）
- 仅提取群内有明确表述的内容，不推测或脑补

**维度二：🔗 信息资源（Information & Resources）**

提取"我们发现了什么好东西"：

```json
{
  "resources": [
    {
      "name": "资源名称（工具名/项目名/论文名）",
      "url": "链接（若有）",
      "type": "tool|paper|repo|article|other",
      "evaluation": "good|warning|neutral|untested",
      "comment": "群友评价原文摘录（如'好评推荐'/'有坑'/'待测试'）",
      "mentioned_by": "提及人数（数字）"
    }
  ]
}
```

规则：
- `evaluation: good` 的资源且为一手来源（GitHub/官方博客/论文页），可追加到 `sources.direct`
- `mentioned_by >= 2` 的资源优先级更高

**维度三：🎯 兴趣画像（Insights & Interests）**

提取"我们在关注什么、态度是什么"：

```json
{
  "hot_topics": [
    {
      "topic": "话题名称",
      "summary": "一句话摘要",
      "keywords": ["关键词1", "关键词2"],
      "signal_type_hint": "burst|sustained|task",
      "mention_count": 8,
      "stance": "positive|negative|neutral|mixed",
      "stance_note": "核心立场描述，如'对 Devin 实际编码能力的质疑'（可选）",
      "preferred_angles": ["工程落地", "与现有工具对比"],
      "avoid_angles": ["纯理论原理"]
    }
  ],
  "emerging_signals": [
    {
      "keyword": "首次出现的关键词/话题",
      "context": "出现语境描述",
      "mention_count": 3
    }
  ]
}
```

规则：
- `signal_type_hint` 判断依据：
  - `burst`：当日 `mention_count >= signal_rules.burst_threshold` 且无历史记录
  - `sustained`：与 `topic_weights` 中已有话题连续匹配
  - `task`：出现在维度一的 `blockers.related_topic` 或 `action_items` 中
- `preferred_angles` 和 `avoid_angles` 从群友讨论的侧重点中归纳（"群里只讨论落地效果，没人关心原理" → `avoid_angles: ["纯理论原理"]`）
- 仅被单人单次提及且无后续讨论的话题归入 `emerging_signals`，不进入 `hot_topics`

---

#### 1-C 输出今日文件（两个产物）

**产物一：群聊三维总结** → `output/daily/{date}-chat-summary.json`

```json
{
  "date": "2026-03-25",
  "generated_at": "2026-03-25T09:30:00+08:00",
  "message_stats": {
    "total_fetched": 150,
    "after_cleaning": 87,
    "coverage": "full"
  },
  "project_execution": { /* 维度一结果 */ },
  "information_resources": { /* 维度二结果 */ },
  "insights_interests": { /* 维度三结果 */ }
}
```

**产物二：今日用户画像快照** → `output/daily/{date}-user-profile.json`

从维度三（兴趣画像）中提炼，格式更紧凑，专为日报搜索和串场逻辑设计：

```json
{
  "date": "2026-03-25",
  "hot_topics": [
    {
      "topic": "LLM Agent",
      "weight_today": 0.9,
      "signal_type": "sustained",
      "keywords": ["定时任务", "插件生态", "MCP"],
      "preferred_angles": ["工程落地", "与现有工具对比"],
      "avoid_angles": ["纯理论原理"],
      "stance": "positive",
      "stance_note": "对 Agent 落地能力持积极态度，重点关注实际工程化效果"
    }
  ],
  "blockers": ["多文件串流卡顿", "MCP 权限配置复杂"],
  "new_signals": ["Cursor 插件生态", "小程序入口"],
  "summary": "今日群聊聚焦于 Agent 落地能力，重点讨论定时任务和插件生态，有同学反馈多文件串流存在卡顿问题。"
}
```

**两个文件的用途**：
- `chat-summary.json`：完整三维原始记录，供审计和回溯
- `user-profile.json`：今日画像快照，Step 2/3 **直接读这个**，格式简洁

---

#### 1-D 画像演进（更新 dept-profile.yaml）

**升级时机**：每次生成今日 `user-profile.json` 后，扫描 `output/daily/` 中最近 `staging_confirm_days` 天的 `*-user-profile.json`，执行以下演进逻辑。

**① 跨天确认 → 写入长期画像**

| 情况 | 操作 |
|------|------|
| 话题在最近 `staging_confirm_days` 天连续出现 | 写入 / 更新 `topic_weights`；合并 `preferred_angles` / `avoid_angles` |
| 话题命中现有 topic 且今日有信号 | `weight += daily_boost`（上限 1.0）；更新 `last_signal`、`signal_count += 1` |
| 话题来自 `task` 型（blocker/action_item 相关）| `weight += daily_boost * task_boost_multiplier` |
| 话题为 `burst` 型（单日高频，次日消失）| 不升入长期画像；仅存在于当日 `user-profile.json` |
| 当日无信号的长期话题 | `burst` 型：`weight *= burst_decay`；其他：`weight *= daily_decay`；下限 `weight_floor` |

新话题**不再需要 `staging_topics` 缓冲区**，staging 过程隐含在每日 `user-profile.json` 文件中——扫描近 N 天文件即可判断是否确认。

**② tracking 实体更新**

维度三 `hot_topics.keywords` 中出现公司/产品/市场名 → 新增或更新 `tracking` 对应条目

**③ sources 更新**

维度二 `resources` 中 `evaluation: good` 且 URL 为一手来源 → 追加到 `sources.direct`（去重）

**④ 剪枝**

`last_signal` > `prune_days` 天前 且 `weight < prune_score_threshold` 且（`prune_require_zero_7d` 为 true 时需 7 天无信号）→ 从 `topic_weights` 移除

**⑤ history 更新**

在 `history` 数组头部插入今日记录，保留最近 7 条：

```yaml
- date: "2026-03-25"
  top_topics: ["Claude", "Cursor", "Agent"]
  blockers: ["多文件串流卡顿", "MCP 权限配置复杂"]
  group_signals: "群聊聚焦于 Agent 落地能力，重点讨论了定时任务和插件生态。"
```

---

#### 1-E 群聊总结回写飞书（必选，若工具可用）

完成 1-D 画像演进后，将今日群聊总结作为**独立新子页面**创建在飞书知识库的指定节点下，供团队成员人工查阅。

**目标父节点**：`department.chat_summary_wiki_node`（Wiki Node Token，从 `config/dept-profile.yaml` 读取）。

**前置检查**：
1. 读取 `runtime.feishu_tools.doc_create`
2. 若字段为空或缺失 → 立即扫描当前可用 MCP 工具列表，查找包含飞书/lark 关键词且含 `create_doc` 或 `create-doc` 的工具
3. 发现工具 → 写入 `runtime.feishu_tools.doc_create`，继续执行
4. 扫描后仍找不到 → 跳过，输出 `⚠️ [1-E] 未完成 — 未找到文档创建工具 — 建议确认飞书 MCP 插件已开启 docx:document:write 权限`

**文档标题**：`【AI Lab 每日洞察】{YYYY-MM-DD}`

**文档内容格式**（严格按以下 Markdown 结构生成，不要随意增减节）：

```markdown
# 📅 AI Lab 每日洞察 ({当天日期})

## 🎯 核心焦点 (1分钟速读)
{一句话总结今天群内讨论最热烈的 1-2 个方向，直接写结论，不写废话}

## 💼 项目协同与讨论
{今日决议、阻碍、待办。无内容则写”今日无明确协同事项”，不省略此节}
- **决议**：{decisions，无则省略此行}
- **阻碍**：{blockers，无则省略此行}
- **待办**：{action_items，无则省略此行}

## 🔗 优质信息源
{群内分享的链接、工具、论文。格式如下，无资源则写”今日无资源分享”}
- **[资源名称](URL)** — 群友评价：{评价原文，无评价则留空}

## 💡 深度观点碰撞
{对新模型、新产品、行业趋势的深度分析与观点。无则写”今日无深度讨论”}
- {观点描述，保留立场和态度，去掉口水话}
```

**写入规则**：
- 每次运行创建一个独立新页面，不修改已有页面
- 内容不出现具体人名，用”有同学提到”代替
- 完成后输出生成的 Wiki 文档 URL，方便用户直接跳转查看

---

#### 故障分类

| 故障类型 | 条件 | 状态迁移 |
|---|---|---|
| 传输/认证失败 | MCP 调用返回错误、超时或权限拒绝 | → `degraded` |
| 业务为空 | 调用成功但返回 0 条消息（安静日） | 保持 `active`；仅施加衰减；输出空的 chat-summary.json 和 user-profile.json |
| 部分获取 | 至少一页成功但分页不完整 | 保持 `active`；处理可用消息；添加 `GROUP_CHAT_PARTIAL_FETCH` warning |
| 完整成功 | 所有页获取无错误，≥1 条消息被处理 | 保持/恢复 `active` |

传输/认证失败时：设置 `status: degraded`，添加 `GROUP_CHAT_TRANSPORT_FAILURE` 到 `digest_meta.warnings[]`，继续到第二步（Step 2 读不到 user-profile.json 时跳过群聊语境相关逻辑）。

**从 `degraded` 恢复**：后续运行第一步以完整成功或部分获取完成时，自动恢复为 `active`。

### 第二步：采集 — 画像驱动的智能搜索

AI 根据 `config/dept-profile.yaml` 和今日群聊总结构建搜索策略，使用搜索工具并行抓取。

**注意**：如果当前状态为 `degraded`（第一步被跳过），在 `digest_meta.warnings[]` 中添加 `PROFILE_DEGRADED` warning（每次 degraded 状态下运行都要添加，不仅是首次转换时）。

**读取今日用户画像快照**：优先读取 `output/daily/{date}-user-profile.json`（Step 1 的输出）。如果文件不存在（degraded 状态），跳过群聊语境相关逻辑，不要报错。

**⚠️ 时效性硬约束**：搜索查询必须携带时间限定词（如"today"、当天日期、"最新"、"2026-03"），确保结果偏向近 24 小时内容。

**搜索策略构建**（由画像 + 群聊总结共同驱动）：
- `primary_domain` + `secondary_domains` + `freeform_context` → 决定直抓页面来源和基础查询词
- `tracking.competitors/products` → 针对性搜索（每个 `score` ≥ `signal_rules.query_entity_score_threshold` 的实体生成一条查询）
- `topic_weights` → 权重 ≥ `signal_rules.high_weight_query_threshold` 的话题分配 2 条查询；介于 `low_weight_query_threshold` 和 `high_weight_query_threshold` 之间的分配 1 条；低于 `low_weight_query_threshold` 的跳过
- `sources.direct` → 每次运行直接抓取
- `sources.search_queries` → 作为种子查询词使用；AI 可根据时事补充
- **今日用户画像增强**（如果 `{date}-user-profile.json` 存在）：
  - `hot_topics[].preferred_angles` → 融入对应话题的搜索修饰词（如 `preferred_angles: ["工程落地"]` → 查询词加 "实际应用 最佳实践"）
  - `hot_topics[].avoid_angles` → 在搜索 prompt 中排除对应方向（如 `avoid_angles: ["纯理论原理"]` → 搜索时不用 "原理 论文 综述" 等词）
  - `blockers[]` → 为每个 blocker 额外追加 1 条搜索（团队卡住的问题最可能需要外部解法）

**AI 自主决定搜索什么、搜多少、从哪里搜。** 以下是指导原则：
- 并行发起至少 10 条搜索，覆盖中英文
- 搜索词结合画像中的实体和话题动态构造
- 群聊信号中权重高的话题加大搜索力度
- 抓取 1-2 个新闻聚合页补充细节（WebFetch）
- 如果某个方向搜索结果不够丰富，主动调整关键词重新搜索

**搜索深度要求**：
- 初筛后如果有效候选不足 20 条，必须追加搜索（调整关键词、换搜索引擎、换语言、加领域通用查询如"[行业] news today"）
- 至少 2 条搜索应直接抓取领域相关的一手来源页面（如官方博客、changelog、release 页面）
- 搜索不能只停在第一轮结果，发现线索后应围绕公司名/项目名/产品名继续追踪

**读取历史反馈**：同时扫描 `data/feedback/` 目录下最近 7 天的 JSON 文件作为次要信号（结构参见 `reference/feedback_schema.json`）。如果不存在或无数据，视为"暂无历史反馈"，不要报错。

信号优先级：
1. 飞书群聊信号（主要 — 反映团队行为，来自 chat-summary.json）
2. HTML 页面反馈（次要 — 个人阅读行为）
3. `dept-profile.yaml` 静态配置（基线）

**来源分层规则**：
AI 在采集时必须区分来源层级：
1. **一手来源（primary）**：官方博客/公告/产品页、文档/changelog/release、论文直链/项目页、创始人/官方账号原始发言、财报/监管文件
2. **二手来源（secondary）**：媒体报道、公众号文章、新闻聚合页、行业分析文章
3. **社区来源（community）**：Twitter/X、Reddit、HN、V2EX 讨论帖

规则：
- 媒体/公众号/聚合页只作为**线索发现层**，不作为最终事实来源
- 发现线索后，必须尝试追溯到一手来源
- 如果追不到一手来源，在 `source_tier` 标记为 `secondary` 并在摘要中注明"当前主要依据媒体报道，尚未找到一手发布材料"
- 社区讨论类内容不能写成已确认事实，必须注明是社区信号

### 第三步：筛选与加工 — AI 编辑判断（全景呈现模式）

**这一步完全由 AI 的编辑判断力完成**，不使用任何评分公式或代码过滤。

AI 作为"总编辑"，从采集到的全部资讯中做以下决策，**核心要求是“全景呈现”，即回复必须尽可能全面完整，方便查阅全貌，严禁过于简略。**

**⚠️ 筛选层级（不可颠倒）**：
- **第一层：时效性门槛** — 不是今天/近 24 小时的内容，默认不入选。
- **第二层：全景相关性** — 通过时效性门槛后，按部门画像权重、跟踪实体以及**今日群聊热点**排序。必须确保覆盖所有核心方向，不能只选容易搜到的。

**⚠️ 全景密度要求**：
- **正文条目**：默认目标补齐至 **10-12 条**，确保各个维度（大厂、中国、开源、安全、研究）都有代表性条目入选。
- **背景上下文**：每条资讯不仅要写发生了什么，还要包含**前因后果**和**技术背景**的简述。
- **多维度解读**：💡 与你相关部分必须包含对工作流、决策、技术路径或学习重点的深度分析。

1. **筛选**（由 `daily.max_items` 控制总量，基准为 10 条）：
   - 判断每条资讯对本部门的价值，而非通用重要性
   - 同一事件的多个报道只保留最有价值的一条
   - 考虑话题多样性，避免某个方向占比过高
   - 结合反馈数据：部门成员过去投票/收藏的同类资讯应优先入选
   - **筛选优先级（最新 > 最真 > 最热 > 画像相关）**：
     - 最新：优先保留今天/近 24 小时新增的明确事实
     - 最真：优先保留能追到一手来源的条目
     - 最热：优先保留有真实扩散讨论或开发者跟进的条目
     - 画像相关：在以上三项满足后，按部门画像权重排序
   - 旧闻、纯媒体转述、只有营销热度但无实质信息的内容默认降级
   - 硬塞弱条目不如诚实地少放，但**最终日报至少应有 8 条资讯**（含拓展阅读）。如果筛选后不足 8 条，必须回到第二步追加搜索（拓宽关键词、换语言、加领域通用查询），而不是直接以 3-5 条交差

2. **排序**：
   - 不使用固定公式，AI 根据"如果我是本部门成员，最想先看到什么"来排序
   - 重大行业事件可以打破兴趣偏好排在前面

3. **分级**：
   - 🔥 重大：足以改变行业格局或直接影响部门工作的事件
   - 📌 值得关注：有价值但不紧急
   - 普通：信息补充
   - 拓展阅读（1-2 条）：部门兴趣范围外，但 AI 认为值得拓展视野的内容

4. **生成内容**（每条资讯）：
   - 标题：可以根据部门领域微调侧重点
   - 结构化摘要：发生了什么 / 为什么重要（用部门成员能理解的语言）
   - 💡 与你相关：基于部门领域和兴趣，解读这件事和本部门有什么关系。**必须具体到行动**，至少回答以下 4 个维度中的 2 个：
     1. 谁应该关注？（工程师/产品/运营/管理层）
     2. 什么时间做？（本周/本月/持续观察/可忽略）
     3. 具体怎么做？（测什么/看什么/比什么/是否上手试）
     4. 成本或门槛是什么？（免费/付费/需申请/接入成本）
     - ❌ 不要写"值得关注""建议持续跟踪"这类空话
     - ✅ 要写"产品经理本周可以直接用同类任务对比 A 和 B，重点看完成率和 token 成本"
   - **串场推荐语（`context_hook`）**：如果 `{date}-user-profile.json` 存在，检查此条资讯是否与以下内容有自然关联：
     - `blockers`：资讯提供了 blocker 的解法/替代方案
     - `hot_topics`：资讯与今日讨论的话题直接相关
     - 有关联时生成 1 句串场语（≤30 字），格式：`"结合今天群里聊到的 [具体问题/话题]，这篇[描述]…"`
     - **无自然关联时留空**，不强行关联；串场语不出现具体人名，用"群里有同学提到"
   - 标签（1-4 个，基于 `dept-profile` 动态推断，体现部门领域特点）
   - 原文链接

5. **生成全局内容**：
   - **今日速览**（3 条）：对本部门最重要的 3 件事，必须包含与部门的关联点
   - **行动建议**（3-4 条）：📖建议学习 / 🔧建议尝试 / 👁️持续关注 / ⚠️需要警惕，每条生成一个精心构造的 `data-action-prompt`（深度 prompt，后续发送给 AI 工具用）
   - **趋势雷达**：上升 / 消退 / 持续热点 + AI 洞察段落

6. **兴趣漂移检测**：
   - 如果群聊信号（第一步）中某个话题持续高频但不在 `config/dept-profile.yaml` 的 `topic_weights` 中，在日报底部提示："检测到部门近期对 #XX 关注度上升，是否要加入跟踪？"
   - 如果 `dept-profile.yaml` 中某个话题近 7 天群聊信号和反馈中均无互动，考虑降低该话题的采集量

#### 日报中间数据契约

在方案二中，AI **先生成结构化 JSON，再调用脚本渲染 HTML**。不要边写 HTML 边临时决定字段。每条资讯至少应包含：

```json
{
  "id": "article-1",
  "title": "资讯标题",
  "priority": "major",
  "time_label": "3小时前",
  "source": "来源名",
  "url": "https://example.com",
  "summary": {
    "what_happened": "发生了什么",
    "why_it_matters": "为什么重要"
  },
  "relevance": "与部门相关的解读",
  "context_hook": "结合今天群里聊到的多 Agent 串流卡顿问题，这篇报告刚好给出了一种轻量解法…",
  "tags": ["#竞品动态", "#行业趋势"],
  "is_exploration": false,
  "key_facts": {
    "entity": "实体名称",
    "date": "2026-03-23",
    "numbers": ["具体数字、版本号、定价等"],
    "constraints": "适用范围或限制条件"
  },
  "source_tier": "primary"
}
```

（`tags` 为部门领域特定标签，由 AI 基于 `dept-profile` 每次动态推断，不硬编码。）

#### 事实密度要求

每条资讯的 `key_facts` 必须包含可核查的硬信息。不同类型内容的必填信息不同：

**产品/功能更新**：产品名、发布时间、核心新增能力、定价/配额（如有）、支持平台/适用范围
**定价/政策变更**：生效日期、计费方式变化、限额/上限、影响的用户范围
**论文/研究**：论文标题、方法名、解决的问题、关键实验结果/benchmark、代码仓库链接（如有）
**开源项目/工具**：项目名、仓库链接、当天信号（新 release/trending/star 激增）、核心能力
**行业事件（收购/融资/政策）**：事件主体、日期、金额（如公开）、原始材料来源
**社区讨论**：讨论平台、主题、核心争议点、是否有一手来源对应（社区信号不能写成硬事实）

**不合格示例**：
- ❌ "某公司推出了新功能" — 没有时间、没有功能名、没有硬数据
- ❌ "社区都在讨论这个框架" — 没有平台、没有讨论点、没有对比对象

**合格示例**：
- ✅ "Cursor 于 2026-03-11 在 Marketplace 新增 30+ 插件，包括 Atlassian、Datadog、GitLab 等，cloud agents 可通过 MCP 直接调用"

约束：
- `id` 必须是稳定的 `article-N`
- `priority` 仅允许 `major | notable | normal`
- `time_label` **必须反映来源的真实发布时间**，不能编造。如果来源页面有明确发布日期，用相对时间（如"2 天前"、"昨天"）或绝对日期（如"3月21日"）。如果无法确定发布时间，写"日期不详"，**禁止写"3小时前"之类的虚假相对时间**
- `tags` 为 1-4 个 `#标签`
- `url` 必须是可直接打开的原文链接
- `summary.what_happened` 和 `summary.why_it_matters` 必须都存在
- 拓展阅读需额外标记 `is_exploration: true`
- `key_facts` 必须至少包含 `entity` 和 `date`，以及至少一项 `numbers` 或 `constraints`
- `source_tier` 仅允许 `primary | secondary | community`，优先使用一手来源

完整 payload 需包含：
- `meta`：日期、角色、生成时间等顶层信息
- `left_sidebar.overview`
- `left_sidebar.actions`
- `left_sidebar.trends`
- `articles`
- `data_sources`
- `digest_meta`：运行时警告（`{code, message, severity}` 结构）

可直接参考：`reference/daily_payload_example.json`

#### 生成质量约束

为保证日报长期稳定达到较高质量，生成内容时必须额外满足以下约束：

1. **头部排序约束**
   - 前 3 条优先放真正重要的产品 / 模型 / 平台级变化
   - 前 3 条尽量保持"一条资讯对应一个明确事件"，不要把多个公司或多个发布揉成一条抽象判断
   - 如果存在足以影响行业格局、工作流入口或用户日常工作的重大事件，应优先进入前 3

2. **来源精度约束**
   - 核心资讯必须优先链接到精确原始来源，而不是官网首页、频道首页或泛聚合页
   - `articles` 前 5 条默认应使用官方发布页、原始博客、论文页、项目页或一手公告
   - 只有在没有更精确原文时，才退而使用高质量二手来源，并在摘要里避免把推断说成事实

3. **信号多样性约束**
   - 整体内容不能只由头部英文厂商新闻构成，需主动覆盖不同类型信号
   - 默认应尽量覆盖以下类别中的至少 3 类：
     - 国际头部产品 / 模型 / 平台动态
     - 中国 AI 动态
     - 开源 / GitHub / 社区项目
     - 论文 / 研究 / Benchmark / 安全信号
     - 企业工作流 / 办公 / 开发工具入口变化
   - 如果 `daily.max_items >= 8`，应优先做到：
     - 至少 1 条中国信号
     - 至少 1 条开源 / GitHub / 社区信号
     - 至少 1 条研究、评测、论文或安全信号

4. **拓展阅读约束**
   - 拓展阅读优先承载 Early Signal：传播尚不广、但可能影响后续产品形态、Agent 工作流、模型部署或治理方式的具体项目 / 方向
   - 不要把空泛的行业评论、趋势口号或没有明确事件支撑的宏观判断放进拓展阅读
   - 拓展阅读仍应有具体来源、具体项目或具体发布，而不是只有概念总结

5. **去泛化约束**
   - 后半部分条目也应尽量使用具体事件、具体项目、具体发布来表达，不要大量使用"行业正在..."、"开始..."、"持续演进..."这类抽象概括
   - 如果一条内容无法回答"发生了什么"和"为什么现在值得看"，就不应入选

6. **左栏内容约束**
   - 今日速览的 3 条必须与正文前部重点条目一致，不能写成比正文更抽象的趋势判断
   - 行动建议应尽量对应正文里的具体事件或工具，而不是脱离当天内容单独发挥
   - 趋势雷达可以概括，但必须建立在正文已覆盖的具体信号之上

7. **输出风格约束**
   - 以高信息密度、强可验证性、低空话率为优先
   - 摘要应明确区分事实、判断和推断；没有直接证据的内容不要写成确定结论
   - 对用户真正相关的价值要落到工作流、决策、技术路线、工具选择或学习重点上，而不是泛泛而谈

如果多个约束冲突，优先顺序为：
1. 重大事件优先
2. 来源精确优先
3. 排序清晰优先
4. 信号多样性优先
5. 表达完整优先

### 第四步：AI 生成 HTML

**优先使用模板化渲染，不再默认由 AI 手写整页 HTML。**

标准流程：
1. AI 先生成结构化 payload，写入 `output/daily/{date}.json`
2. 调用 `scripts/render_daily.py output/daily/{date}.json`
3. 由脚本输出 `output/daily/{date}.html`
4. 生成后调用 `scripts/open_daily.py {date}` 打开页面；若反馈服务已启动则优先打开本机 HTTP 地址，否则回退到本地文件

只有在渲染脚本缺失或损坏时，才退回到直接生成完整 HTML。

重要约束：
- **不要重新设计页面结构，不要重写交互逻辑，不要删改反馈 JS 的行为。**
- 通过渲染脚本稳定复用样板页结构、样式和脚本，只替换日期、角色、统计数字、左栏文案、资讯卡片内容和数据来源。
- 渲染结果必须保留 `data-article-id`、`data-title`、`data-tags`、`data-action-prompt` 等属性，确保反馈采集和 AI 工具菜单正常工作。
- HTTP 模式下只在离开页面时提交一次完整 feedback summary；不要新增定时事件批量落盘逻辑。
- 如果无法 100% 确认某段 JS 的作用，宁可原样保留，也不要自行改写。

成品样板文件：`reference/daily_example.html`
- 该文件是一份已经生产验证过的完整日报页面
- 包含完整的布局、样式、反馈 JS、AI 工具集成
- 渲染器应保持与样板一致的结构和交互体验，只替换实际的资讯内容

#### 技术依赖

```html
<script src="https://cdn.tailwindcss.com"></script>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
```

Tailwind 扩展色值：`primary: '#1A1A2E'`、`accent: '#6C5CE7'`。

自定义 CSS 仅两段：
```css
.ai-gradient-line { border-left: 3px solid; border-image: linear-gradient(to bottom, #6C5CE7, #3B82F6) 1; }
.ai-bg { background: linear-gradient(135deg, #F8F7FF, #F0F7FF); }
```

#### 页面布局（PC 左右双栏）

- `body`：`h-screen overflow-hidden flex flex-col`
- 顶部栏：Logo + 日期 + 资讯数 + 用户角色
- 左栏（420px，白色，独立滚动）：今日速览 → 行动建议 → 趋势雷达
- 右栏（自适应，独立滚动）：资讯卡片列表

#### Font Awesome 图标映射（不用 emoji）

| 场景 | FA Class |
|------|----------|
| 日报标题 | `fa-solid fa-robot` |
| 日期 | `fa-regular fa-calendar` |
| 速览 | `fa-solid fa-bolt` |
| 资讯 | `fa-solid fa-newspaper` |
| 行动建议 | `fa-solid fa-bullseye` |
| 趋势 | `fa-solid fa-chart-line` |
| 重大 | `fa-solid fa-fire` (text-red-500) |
| 关注 | `fa-solid fa-thumbtack` (text-amber-500) |
| 与你相关 | `fa-solid fa-lightbulb` (text-accent) |
| 学习 | `fa-solid fa-book-open` (text-blue-500) |
| 尝试 | `fa-solid fa-wrench` (text-emerald-500) |
| 关注 | `fa-solid fa-eye` (text-amber-500) |
| 警惕 | `fa-solid fa-triangle-exclamation` (text-red-500) |
| 上升 | `fa-solid fa-arrow-trend-up` (text-emerald-500) |
| 下降 | `fa-solid fa-arrow-trend-down` (text-gray-400) |
| 热点 | `fa-solid fa-fire` (text-red-500) |
| 洞察 | `fa-solid fa-wand-magic-sparkles` (text-accent) |
| 原文 | `fa-solid fa-arrow-up-right-from-square` |
| AI 深入 | `fa-solid fa-wand-magic-sparkles` |
| 发送 AI | `fa-solid fa-paper-plane` |

#### 资讯卡片 HTML 结构

```html
<article class="bg-white rounded-xl shadow-sm p-4 card-hover"
         data-article-id="article-N" data-title="标题" data-tags='["#标签"]'>
  <div class="flex items-start justify-between">
    <h3 class="text-[15px] font-semibold text-primary leading-snug">
      <i class="fa-solid fa-fire text-red-500 mr-1.5 text-xs"></i>标题
    </h3>
    <span class="text-xs text-gray-400 whitespace-nowrap ml-3">时间</span>
  </div>
  <p class="text-xs text-gray-400 mt-1"><i class="fa-solid fa-link mr-1"></i>来源</p>
  <div class="ai-gradient-line pl-3 my-2.5 text-[13px] text-gray-600 leading-relaxed">
    结构化摘要
  </div>
  <div class="bg-[#F8F7FF] rounded-lg px-3 py-2 text-[13px] text-gray-700 my-2">
    <i class="fa-solid fa-lightbulb text-accent mr-1"></i>
    <strong>与你相关：</strong>解读
  </div>
  <div class="flex items-center justify-between mt-2">
    <div class="flex gap-1.5 flex-wrap">标签</div>
    <!-- JS 自动注入：投票、收藏、AI 深入按钮 -->
    <a href="URL" target="_blank" class="text-accent text-xs hover:underline">
      <i class="fa-solid fa-arrow-up-right-from-square mr-1"></i>原文
    </a>
  </div>
</article>
```

拓展阅读卡片加 `border border-dashed border-gray-200`，标签用 `bg-gray-100 text-gray-500`。

#### 行动建议 HTML 结构

每条 `<li>` 必须包含 `data-action-prompt` 属性（精心构造的深度 prompt）：

```html
<li class="action-item flex items-start gap-2.5 ai-bg rounded-lg px-3 py-2.5"
    data-action-type="learn"
    data-action-prompt="请帮我深入了解...（具体分析角度）">
  <i class="fa-solid fa-book-open text-blue-500 mt-0.5 text-sm"></i>
  <div class="flex-1">
    <strong class="text-blue-600">建议学习</strong>
    <p class="text-gray-600 mt-0.5 leading-relaxed">建议内容</p>
  </div>
</li>
```

#### 必须包含的 JavaScript

在 `</body>` 前注入完整的反馈采集 + AI 原生交互 JS，包括：

**AI 工具配置：**

```javascript
const AI_TOOLS = [
  { id: 'claude', name: 'Claude', icon: 'fa-solid fa-message', url: 'https://claude.ai/new?q={prompt}' },
  { id: 'chatgpt', name: 'ChatGPT', icon: 'fa-brands fa-openai', url: 'https://chatgpt.com/?q={prompt}' },
  { id: 'deepseek', name: 'DeepSeek', icon: 'fa-solid fa-magnifying-glass', url: 'https://chat.deepseek.com/?q={prompt}' },
  { id: 'copy', name: '复制 Prompt', icon: 'fa-regular fa-copy', url: null }
];
```

**反馈采集（JS 动态注入到每张卡片）：**

隐式：
- IntersectionObserver 追踪卡片停留时长（>5s 记录），root 为右栏滚动容器
- 原文链接点击追踪
- 文本复制追踪

显式：
- 投票按钮（▲ caret-up）：`vote-btn`
- 收藏按钮（bookmark）：`bookmark-btn`
- 标签可点击关注/取消：`tag-clickable` + `tag-clicked`

**AI 原生交互：**

行动建议：
- 每条右上角常驻 ✈️ 图标（`.ai-trigger-icon`）
- 鼠标 hover 图标时左侧弹出浮层菜单（`.ai-menu`）
- 结构：外层 `.ai-trigger-wrap`（`pointer-events:none`），菜单 + 图标（`pointer-events:auto`）
- 用 JS mouseenter/mouseleave 控制显隐（150ms 延迟关闭），避免 hover 间隙

资讯卡片：
- 操作栏「AI 深入」按钮（`.card-ai-btn`）常驻显示
- hover 时上方弹出浮层菜单
- 结构：`.card-ai-wrap`（`position:relative; flex-shrink:0`），菜单绝对定位 `bottom:calc(100%+6px); right:0`
- 同样用 JS mouseenter/mouseleave 控制

**反馈上报：**

```javascript
const IS_HTTP = location.protocol.startsWith('http');

// 只在离开页面时提交完整 summary
function onLeave() {
  const summary = buildSummary();
  if (IS_HTTP) navigator.sendBeacon('/api/feedback', JSON.stringify(summary));
  // 无论什么模式都写 localStorage + 控制台
  localStorage 写入 ai_daily_feedback（最多保留最近 30 条）;
  console.log(JSON.stringify(summary, null, 2));
}
```

**汇总数据结构：**

```json
{
  "date": "2026-03-21",
  "session": { "total_time_seconds": 180, "total_events": 12 },
  "explicit_feedback": { "voted": [], "bookmarked": [], "tags_followed": [], "tags_unfollowed": [] },
  "implicit_feedback": { "dwell_ranking": [], "articles_clicked": [], "articles_copied": [] },
  "ai_interaction": { "tools_used": {}, "detail": [] },
  "interest_profile": { "tag_scores": [], "top_interests": [] },
  "all_events": []
}
```

说明：
- `date`、`session`、`explicit_feedback`、`implicit_feedback`、`ai_interaction`、`interest_profile` 是正式反馈必备字段
- `all_events` 是可选调试字段，可保留原始事件日志，但不能替代结构化 summary

### 第五步：更新导航首页

更新或创建 `output/index.html`，列出所有已生成的日报。

### 第五点五步：更新画像历史

每次日报生成完成后，更新 `config/dept-profile.yaml`：

1. 从本次日报中提取 top 3 话题
2. 将群聊信号摘要为 1-3 条短字符串
3. 追加/覆盖 `history` 中当日条目（同日多次运行 last-write-wins）
4. 裁剪 `history` 仅保留最近 7 个日历日
5. 更新 `runtime.last_digest_run` 为当前时间

### 第六步：启动反馈服务

1. 使用现有的 `scripts/feedback_server.py` 启动 HTTP 服务（serve `output/` 目录 + `POST /api/feedback` 写入 `data/feedback/{date}.json`，默认 `server.host: 0.0.0.0` 允许局域网访问，端口默认 17890，冲突自动 +1，超时 2 小时自动退出）
2. 启动服务：`python3 scripts/feedback_server.py`
3. 等待 `data/.server_port` 写入，读取端口号
4. 当前机器使用 `python3 scripts/open_daily.py {date} --mode http` 打开页面；局域网其他用户使用启动日志中打印出的 `http://<局域网IP>:<port>/daily/{date}.html`

### 第七步：输出结果

告知用户：
1. 文件路径和资讯条数
2. 数据来源渠道
3. 反馈服务状态（端口 + 超时时间）
4. 如有历史反馈：已参考多少天的反馈调整推荐

## 日报质量评估流程

当用户请求“评估日报质量”时，不进入生成流程，改为执行以下步骤：

### 第一步：确定评估对象

优先顺序：

1. 用户明确指定的日报文件或内容
2. 当前目录下最新的 `output/daily/{date}.json` 或 `output/daily/{date}.html`
3. 如果同时存在 JSON 和 HTML，优先使用 JSON 作为结构化输入，HTML 作为排版和展示补充

### 第二步：读取当前用户兴趣上下文

评估日报时，不能只按通用媒体标准打分，还要判断它**是否适合当前这位用户**。

因此应优先读取：

- `config/profile.yaml`
- `data/feedback/` 下最近 7 天的反馈 JSON（如存在）

评估时沿用生成流程中的原则：

- `profile.yaml` 代表用户的显式偏好
- 历史反馈代表用户的真实行为偏好
- 两者冲突时，**以行为反馈为准，profile 为辅**

需要明确梳理以下问题：

- 这位用户的主角色与工作语境是什么
- 用户显式关注哪些主题，优先级如何
- 用户最近真实更在意哪些标签、话题、工具或内容形态
- 这份日报的前几条内容，是否真正命中了这些重点

如果没有 `profile.yaml` 或历史反馈为空，则继续做通用质量评估，但必须明确说明：**本次未纳入用户兴趣个性化维度，只能给出通用质量判断。**

### 第三步：读取评估方法

必须参考：

- `reference/daily_evaluation_template.md`

如果用户额外提供评估方法论文档，也要一并参考，并优先遵循用户提供的评估规则。

### 第四步：构建 Ground Truth

围绕评估日期构建当日最重要的 AI 事件 Ground Truth：

- 优先使用官方 / 一手来源
- 覆盖产品 / 模型 / 平台
- 覆盖中国信号、开源 / GitHub、社区 / 论文
- 明确哪些事件是真正“应该被写进日报”的

同时还要构建一份**用户相关 Ground Truth**：

- 哪些事件虽然不是全行业最热，但对当前用户最有价值
- 哪些事件与用户角色、关注主题、最近反馈高度相关，应被优先呈现
- 哪些内容即便行业上重要，但对该用户可以后置

### 第五步：做覆盖、结构与用户匹配评估

至少输出：

- 一句话总评
- 五维评分：Coverage / Product Priority / Readability / Signal Diversity / Early Signal
- 用户匹配判断：这份日报是否真正贴近当前用户的角色、兴趣与近期行为
- 覆盖对比
- 用户相关性对比
- 漏项
- 结构问题
- 改进建议

评估时要同时回答两类问题：

1. **通用质量是否过关**
   - 是否覆盖了当日最重要事件
   - 排序是否合理
   - 来源是否精确
   - 是否有足够的信号多样性和早期信号

2. **对当前用户是否合适**
   - 前 3 条是否足够贴近用户角色与兴趣
   - 行动建议是否真的可用于该用户的工作或决策
   - 是否出现了用户高度关心的话题被后置、遗漏或表达过浅
   - 是否塞入了太多对该用户价值不高的泛行业内容

### 第六步：输出结构化评估

输出格式应尽量贴近 `reference/daily_evaluation_template.md`，并明确：

- 总分
- 主要优点
- 明显问题
- 是否达到“可作为高质量行业判断输入”的标准
- 是否达到“对当前用户足够有用、足够相关”的标准

## 参考文件

| 文件 | 用途 |
|------|------|
| `reference/daily_example.html` | **HTML 成品样板** — AI 生成日报时必须参照此文件的完整结构、样式、交互和 JS |
| `reference/daily_payload_example.json` | **日报 payload 示例** — 方案二中 AI 生成 JSON 时应参考此结构 |
| `reference/dept-profile-template.yaml` | **部门画像模板** — 飞书 KB 初始化时参照生成 `config/dept-profile.yaml` |
| `reference/profile_template.yaml` | 旧版用户配置模板 — 仅用于迁移参考 |
| `reference/daily_evaluation_template.md` | **日报评估模板** — 评估日报质量时应按此结构输出结果 |
| `reference/feedback_schema.json` | 反馈数据 JSON Schema — 定义 `data/feedback/{date}.json` 的完整结构 |

## 脚本文件

| 文件 | 用途 | 调用方式 |
|------|------|---------|
| `scripts/render_daily.py` | 将 `output/daily/{date}.json` 稳定渲染为 HTML | `python3 scripts/render_daily.py output/daily/{date}.json` |
| `scripts/open_daily.py` | 打开已生成的日报页面，优先使用本地 HTTP 服务地址 | `python3 scripts/open_daily.py {date}` |
| `scripts/feedback_server.py` | HTTP 静态服务 + 反馈接收，超时自动退出 | 后台运行 |

注意：生成任务中，**采集、加工、筛选、摘要、行动建议由 AI 完成；HTML 结构输出优先由渲染脚本完成。** 评估任务中，AI 负责读取日报、构建 Ground Truth、完成打分和输出评估结果。

## AI 与脚本的职责分工

| 职责 | 由谁完成 | 原因 |
|------|---------|------|
| 首次使用引导（画像初始化） | AI（调用飞书 MCP 工具） | 需要读取飞书 KB 并推断部门画像 |
| 构建编辑策略 | AI | 需要综合理解用户画像 + 行为反馈 |
| 搜索关键词设计 | AI | 需要根据用户兴趣动态构造，不能硬编码 |
| 资讯抓取 | AI（调用搜索工具）| 需要根据搜索结果质量动态调整策略 |
| 筛选、排序、分级 | AI | 需要编辑判断力，不能用评分公式替代 |
| 摘要、解读、行动建议 | AI | 需要基于用户角色的语境理解 |
| 飞书 KB 读取与画像生成 | AI（调用飞书 MCP 工具） | 需要理解文档内容推断领域 |
| 群聊信号提取 | AI（调用飞书 MCP 工具） | 需要自然语言理解提取话题 |
| 画像增量更新与衰减 | AI | 需要按 signal_rules 参数执行权重计算 |
| 结构化 payload 生成 | AI | 内容是动态的，需要 AI 生成当天的结构化数据 |
| HTML 渲染 | 脚本（`render_daily.py`） | 页面结构、样式和反馈 JS 需要稳定复用，避免模型每次重写整页 |
| 日报质量评估 | AI | 需要构建 Ground Truth、做覆盖匹配并输出定性定量判断 |
| 兴趣漂移检测 | AI | 需要对比 profile 和行为数据的差异 |
| 反馈数据收集 | 脚本（HTTP 服务）| 纯网络 IO，无需 AI 介入 |

#### 内容质量自检（出稿前强制）

在生成结构化 JSON 之前，AI 必须自检以下 6 项。**前 2 项为阻断项**，不达标则必须回到第二步补搜后重新筛选：

1. **🚫 时效性门槛（阻断项）**：是否至少 80% 的资讯来自今天或昨天？如果旧闻过多，**不能继续输出**，必须回到第二步追加带时间限定的搜索
2. **🚫 当天热点覆盖（阻断项）**：是否遗漏了今天明显的重大事件？用 1-2 条宽泛搜索（如"AI news today"、"科技新闻 今天"）快速核查，如果发现重大遗漏，必须补入
3. **硬数据检查**：每条资讯的 `key_facts` 是否包含具体数字、日期、版本号或定价？如果某条只有抽象描述没有硬数据，要么补充要么降级
4. **一手来源检查**：是否至少 60% 的资讯标记为 `source_tier: primary`？如果一手来源不足，尝试追加搜索原始页面
5. **行动建议检查**：每条的"与你相关"是否具体到了动作和时间？如果只写了"值得关注"，必须重写
6. **覆盖广度检查**：是否覆盖了画像中权重 > 0.3 的至少 3 个不同话题方向？如果过于集中在单一方向，补充其他方向的搜索

#### HTML 生成前自检

在写出最终 HTML 前，至少自检以下几点：

- 顶部栏日期、资讯数、用户角色已替换
- 左栏包含：今日速览、行动建议、趋势雷达
- 每个资讯卡片都带 `data-article-id`、`data-title`、`data-tags`
- 每个行动建议 `<li>` 都带 `data-action-prompt`
- 原文链接都存在且可点击
- 页面保留 `/api/feedback` 上报逻辑，且只提交完整 session summary
- 拓展阅读卡片使用虚线边框和灰色标签样式

---

## 附录：初始化流程（仅首次使用时执行）

以下内容仅在 `dept-profile.yaml` 不存在或状态为 `uninitialized` 时需要阅读。日常运行（状态为 `active` 或 `degraded`）请直接从第一步开始。

### 附录 A：飞书 KB 初始化

使用飞书工具适配阶段发现的工具（`runtime.feishu_tools.wiki_list` 和 `runtime.feishu_tools.doc_read`）读取知识库。

读取范围由 `kb_init` 配置控制（默认：2 层深度，最多 20 页，跳过 >50KB 的页面）。

AI 分析读取到的文档内容，推断：
- 部门名称、主领域（`primary_domain`）、次要领域（`secondary_domains`）
- 行业描述（`industry`）、自由文本上下文（`freeform_context`）

生成 `config/dept-profile.yaml`（参考 `reference/dept-profile-template.yaml`），状态设为 `awaiting_group_id`。

**KB 的定位**：KB 提供的是部门的"官方自我描述"——组织架构、项目定义、OKR 等。这些信息用于推断部门领域和行业背景，但**不能替代群聊历史中的真实行为数据**。如果 KB 和群聊历史矛盾（比如 KB 写的是"大模型研发"但群里天天在讨论产品竞品），以群聊历史为准。

**异常处理**：
- 个别页面读取失败 → 跳过并记录到 `kb_init.init_coverage_note`，添加 `KB_INIT_PAGES_SKIPPED` warning
- 所有页面失败 → 不阻断初始化，标记 KB 为不可用，继续到附录 A-2 用群聊历史建画像
- 可读页面 <3 → 生成最小画像（`primary_domain: general`），继续到附录 A-2 补充
- AI 无法推断 `primary_domain` → 设为 `general`，提示用户通过 `/ai-daily set-domain <domain>` 确认

### 附录 A-2：群聊历史画像补充

当用户设置了 `feishu_group_id` 后（从 `awaiting_group_id` 转出时），**读取该群最近 7 天的历史消息**，用于补充和修正从 KB 推断出的初始画像。

**⚠️ 上下文管理**：7 天原始消息可能有数千条，不能一次性全部读入。必须**逐天处理、滚动摘要**：

**执行方式**：
1. 倒序遍历最近 7 天（从昨天开始，往前推 7 天），每次只读取 1 天的消息
2. 对每天的消息执行第一步的同一套流程：**数据清洗 → 结构化中间提取**
3. 提取完当天的结构化摘要后，**丢弃原始消息**，只保留摘要结果：
   ```
   {日期, 热点话题[], 高频关键词[], 提到的实体[], 分享的链接[], 工作信号{}}
   ```
4. 7 天全部处理完后，从 7 份每日摘要中合并出画像基线

**从 7 天摘要中合并画像**：
- **高频话题** → 写入 `topic_weights`（被多天讨论的话题权重更高：出现 ≥3 天 → 权重 0.7，2 天 → 0.6，1 天 → 0.4）
- **反复提到的产品/公司/项目名** → 写入 `tracking` 各分类（出现天数越多，`score` 越高）
- **群友频繁分享的链接域名** → 补充到 `sources.direct`
- **工作讨论中反复出现的技术方向/工具** → 用于修正 `primary_domain` 和 `secondary_domains`（如果与 KB 推断的不一致，以群聊行为为准）

**与 KB 画像的合并规则**：
- `primary_domain`：如果群聊历史明确指向不同领域，以群聊为准，降级 KB 推断结果到 `secondary_domains`
- `tracking`：合并 KB 和群聊历史中的所有实体，群聊历史中出现的实体 `score` 更高
- `topic_weights`：合并两个来源的话题，群聊来源的权重按上述天数规则计算
- `sources`：合并两个来源推荐的数据源，去重

**如果群聊工具不可用**：
跳过此步骤，仅依赖 KB 画像，状态直接设为 `active`。在 `digest_meta.warnings[]` 中记录 `CHAT_HISTORY_UNAVAILABLE`。

**如果某一天的消息读取失败**：
跳过该天，继续处理其他天。最终摘要中标注实际覆盖了几天。

### 附录 B：来源探索

在附录 A 推断出部门领域后，AI **必须主动搜索并验证**适合该部门的信息来源，写入 `sources.direct` 和 `sources.search_queries`。不能凭空猜测或只给泛用来源。

**执行方式**：
1. 根据部门的 `primary_domain` + `industry` + `freeform_context`，搜索该领域的权威信息来源（如 "fintech industry news sources"、"B2B SaaS competitive intelligence sources"）
2. 识别以下三类来源并分别处理：

| 来源类型 | 写入字段 | 示例 |
|---|---|---|
| **一手来源页面**（官方博客/changelog/release 页面、监管机构公告页、行业协会发布页） | `sources.direct` | 竞品官方博客 URL、行业监管公告页 URL |
| **结构化搜索词**（用于 WebSearch，覆盖行业动态/竞品/政策/技术趋势） | `sources.search_queries` | `"fintech regulation 2026"`、`"[竞品名] 最新发布"` |
| **聚合/社区页面**（行业论坛、Reddit 子版、HN、专业社区） | `sources.direct`（标注为社区源） | `reddit.com/r/fintech`、`news.ycombinator.com` |

3. 对 `sources.direct` 中的每个 URL，尝试一次 WebFetch 验证可访问性。不可访问的来源标注在 `kb_init.init_coverage_note` 中但仍保留（可能是临时网络问题）
4. `sources.search_queries` 至少包含 5 条种子查询词，覆盖：部门核心业务方向、主要竞品/跟踪实体、行业政策/法规、技术趋势
5. 将来源探索结果展示给用户确认，告知"以下是为贵部门推荐的信息来源，后续每日日报将从这些渠道采集。如需调整可手动编辑 `config/dept-profile.yaml` 的 `sources` 字段"

### 附录 C：旧版 profile.yaml 迁移

如果 `config/profile.yaml` 存在但 `config/dept-profile.yaml` 不存在：
1. 读取旧文件
2. 映射可用字段到新 schema（写入 `schema_version: 1`）
3. 以下字段不迁移：`server.port`, `server.timeout_hours`, `role`, `role_context`, `topics`, `exclude_topics`, `daily.*`
4. 将旧文件重命名为 `config/profile.yaml.bak`
5. 状态设为 `awaiting_group_id`

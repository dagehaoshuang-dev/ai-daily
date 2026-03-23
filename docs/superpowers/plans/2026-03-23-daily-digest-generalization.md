# Daily Digest Generalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Modify the `ai-daily` skill to serve any enterprise department by reading Feishu KB and group chat to build and maintain a department profile that drives search strategy, replacing the hardcoded AI-domain focus.

**Architecture:** The skill's SKILL.md is a prompt/instruction file — there is no traditional code to test. Implementation is structured edits to SKILL.md sections plus a new reference template. `render_daily.py` and `feedback_server.py` are NOT modified.

**Tech Stack:** YAML (profile schema), Markdown (SKILL.md), JSON (payload contract)

**Spec:** `docs/superpowers/specs/2026-03-23-daily-digest-generalization-design.md`

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `SKILL.md` | Modify | Main skill definition — frontmatter, all execution steps, reference tables |
| `reference/dept-profile-template.yaml` | Create | Full dept-profile.yaml schema template with comments |
| `reference/profile_template.yaml` | Keep | Preserved for migration reference; not used by new flow |
| `reference/daily_payload_example.json` | Modify | Add `digest_meta.warnings[]` field to the example |
| `scripts/render_daily.py` | No change | — |
| `scripts/feedback_server.py` | No change | — |

---

### Task 1: Create dept-profile-template.yaml

**Files:**
- Create: `reference/dept-profile-template.yaml`

- [ ] **Step 1: Write the template file**

Write the complete `dept-profile-template.yaml` with all fields from the spec schema, including comments explaining each section. Use the spec's YAML block (lines 129–210) as the source of truth. Include `schema_version: 1`, `status`, `department`, `kb_init`, `tracking`, `topic_weights`, `sources`, `signal_rules`, `history`, and `runtime` sections.

The template should use placeholder values (`""`, `[]`, `null`) rather than the example values from the spec, so it serves as a blank starting point.

- [ ] **Step 2: Commit**

```bash
git add reference/dept-profile-template.yaml
git commit -m "feat: add dept-profile.yaml template for department-driven digest"
```

---

### Task 2: Update SKILL.md frontmatter and introduction

**Files:**
- Modify: `SKILL.md:1-17`

- [ ] **Step 1: Update frontmatter**

Change:
- `name`: `ai_daily` → `ai_daily` (keep for backwards compat)
- `description`: Remove "AI 资讯" specificity. New description:

```yaml
description: >
  企业部门日报生成技能。通过飞书知识库和群聊信号自动构建部门画像，
  从互联网多渠道抓取与部门相关的资讯，经 AI 加工后生成 HTML 日报页面，
  并启动本地 HTTP 服务自动收集阅读反馈。
```

- [ ] **Step 2: Update intro paragraph (line 15-17)**

Replace the opening paragraph:

```markdown
# 部门资讯日报生成

你是一个资讯编辑，负责为企业部门生成个性化日报。部门画像由飞书知识库初始化、群聊信号每日更新。你需要完成：读取画像 → 采集群聊信号 → 搜索资讯 → AI 加工 → 生成 HTML → 启动反馈服务 → 打开页面。
```

- [ ] **Step 3: Update trigger section (lines 19-25)**

Replace trigger conditions to include new commands:

```markdown
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
```

- [ ] **Step 4: Commit**

```bash
git add SKILL.md
git commit -m "feat: update SKILL.md frontmatter, intro, and trigger section for domain-agnostic digest"
```

---

### Task 3: Rewrite Step 0 — Profile state machine + migration

**Files:**
- Modify: `SKILL.md:29-62` (current "第零步：首次使用引导")

- [ ] **Step 1: Replace Step 0 with state machine routing**

Replace the entire "第零步" section with:

```markdown
### 第零步：画像检查与状态路由

检查 `config/dept-profile.yaml` 的状态，按以下路由执行：

| 状态 | 操作 |
|---|---|
| 文件不存在，也无 `config/profile.yaml` | 触发飞书 KB 初始化（路径 A） |
| 文件不存在，但 `config/profile.yaml` 存在 | 执行迁移（见下方），状态设为 `awaiting_group_id` |
| `uninitialized` | 触发飞书 KB 初始化（路径 A） |
| `awaiting_group_id` | 提示用户执行 `/ai-daily set-group <chat_id>`，然后退出 |
| `active` | 继续到第一步 |
| `degraded` | 跳过第一步，直接从第二步开始，使用当前画像 |

#### 路径 A：飞书 KB 初始化

使用飞书 MCP 工具读取知识库：

| 逻辑能力 | 已知工具名 | 用途 |
|---|---|---|
| 列出 KB 知识节点 | `feishu_wiki_space_node` | 枚举知识库页面 |
| 读取文档内容 | `feishu_fetch_doc` | 读取页面内容 |

读取范围由 `kb_init` 配置控制（默认：2 层深度，最多 20 页，跳过 >50KB 的页面）。

AI 分析读取到的文档内容，推断：
- 部门名称、主领域（`primary_domain`）、次要领域（`secondary_domains`）
- 行业描述（`industry`）、自由文本上下文（`freeform_context`）
- 推荐数据源（`sources.direct`、`sources.search_queries`）
- 初始话题权重（`topic_weights`）和跟踪实体（`tracking`）

生成 `config/dept-profile.yaml`（参考 `reference/dept-profile-template.yaml`），状态设为 `awaiting_group_id`。

如果个别页面读取失败，跳过并记录到 `kb_init.init_coverage_note`，同时添加 `KB_INIT_PAGES_SKIPPED` warning 到 `digest_meta.warnings[]`。如果所有页面失败，退出并提示检查飞书 MCP 连接。如果可读页面 <3，生成最小画像（`primary_domain: general`），提示用户确认领域。如果 AI 无法从文档中推断出 `primary_domain`，设为 `general` 并提示用户通过 `/ai-daily set-domain <domain>` 确认。

#### 旧版 profile.yaml 迁移

如果 `config/profile.yaml` 存在但 `config/dept-profile.yaml` 不存在：
1. 读取旧文件
2. 映射可用字段到新 schema（写入 `schema_version: 1`）
3. 以下字段不迁移：`server.port`, `server.timeout_hours`, `role`, `role_context`, `topics`, `exclude_topics`, `daily.*`
4. 将旧文件重命名为 `config/profile.yaml.bak`
5. 状态设为 `awaiting_group_id`
```

- [ ] **Step 2: Commit**

```bash
git add SKILL.md
git commit -m "feat: rewrite Step 0 with profile state machine, KB init, and migration"
```

---

### Task 4: Add new Step 1 — Group chat signal extraction

**Files:**
- Modify: `SKILL.md:64-81` (current "第一步：理解用户")

- [ ] **Step 1: Replace Step 1 with group chat signal reading**

Replace the entire "第一步" with:

```markdown
### 第一步：读取群聊信号

使用飞书 MCP 工具（`feishu_im_user_get_messages`）读取指定群聊（`department.feishu_group_id`）当天的消息。

**消息获取**：从今天 UTC+8 00:00 分页读取到当前时间。持续分页直到到达当天起始时间或达到 `signal_rules.max_messages_per_run` 条上限。如果获取的消息超过 `signal_rules.compress_after_messages` 条，先摘要/压缩再分析。

**信号提取规则**（所有阈值来自 `signal_rules.*`）：
- **话题增强**：某话题被 ≥ `topic_boost_threshold` 条消息提及 → `weight += daily_boost`（上限 1.0）
- **实体信号**：公司/产品/市场名在 ≥ `entity_threshold` 条消息中出现 → 新增或更新 `tracking` 条目
- **新话题**：不在画像中的话题，被 ≥ `new_topic_threshold` 次提及 → 以 `new_topic_initial_weight` 权重新增
- **噪声过滤**：单次提及忽略

**提取后处理**：
- 对当日未收到信号的所有话题施加衰减：`weight *= daily_decay`（下限 `weight_floor`）
- 剪枝 tracking 条目：`last_signal` > `prune_days` 天前 且 `score` < `prune_score_threshold` 且 `signal_count_7d == 0`（如果 `prune_require_zero_7d` 为 true）
- 将增量变更写回 `config/dept-profile.yaml`
- 更新 `runtime.last_signal_update` 和 `runtime.last_step1_result`

**故障分类**：

| 故障类型 | 条件 | 状态迁移 |
|---|---|---|
| 传输/认证失败 | MCP 调用返回错误、超时或权限拒绝 | → `degraded` |
| 业务为空 | 调用成功但返回 0 条消息（安静日） | 保持 `active`；仅施加衰减 |
| 部分获取 | 至少一页成功但分页不完整 | 保持 `active`；处理可用消息；添加 warning |
| 完整成功 | 所有页获取无错误，≥1 条消息被处理 | 保持/恢复 `active` |

传输/认证失败时：设置 `status: degraded`，添加 `GROUP_CHAT_TRANSPORT_FAILURE` 到 `digest_meta.warnings[]`，继续到第二步。

**从 `degraded` 恢复**：当后续运行中第一步以完整成功或部分获取完成时，自动恢复为 `active`。
```

- [ ] **Step 2: Commit**

```bash
git add SKILL.md
git commit -m "feat: add Step 1 — Feishu group chat signal extraction with failure classification"
```

---

### Task 5: Update Step 2 — Domain-driven search strategy

**Files:**
- Modify: `SKILL.md:83-94` (current "第二步：采集")

- [ ] **Step 1: Replace Step 2 with profile-driven search**

Replace the "第二步" content. Keep the section header, replace the body:

```markdown
### 第二步：采集 — 画像驱动的智能搜索

AI 根据 `config/dept-profile.yaml` 构建搜索策略，使用搜索工具并行抓取。

**注意**：如果当前状态为 `degraded`（第一步被跳过），在 `digest_meta.warnings[]` 中添加 `PROFILE_DEGRADED` warning（每次 degraded 状态下运行都要添加，不仅是首次转换时）。

**搜索策略构建**（由画像驱动）：
- `primary_domain` + `secondary_domains` + `freeform_context` → 决定直抓页面来源和基础查询词
- `tracking.competitors/products` → 针对性搜索（每个 `score` ≥ `signal_rules.query_entity_score_threshold` 的实体生成一条查询）
- `topic_weights` → 权重 ≥ `signal_rules.high_weight_query_threshold` 的话题分配 2 条查询；介于 `low_weight_query_threshold` 和 `high_weight_query_threshold` 之间的分配 1 条；低于 `low_weight_query_threshold` 的跳过
- `sources.direct` → 每次运行直接抓取
- `sources.search_queries` → 作为种子查询词使用；AI 可根据时事补充

**AI 自主决定搜索什么、搜多少、从哪里搜。** 以下是指导原则：
- 并行发起至少 4 条搜索，覆盖中英文
- 搜索词结合画像中的实体和话题动态构造
- 群聊信号中权重高的话题加大搜索力度
- 抓取 1-2 个新闻聚合页补充细节（WebFetch）
- 如果某个方向搜索结果不够丰富，主动调整关键词重新搜索

**读取历史反馈**：同时扫描 `data/feedback/` 目录下最近 7 天的 JSON 文件作为次要信号（结构参见 `reference/feedback_schema.json`）。如果不存在或无数据，视为"暂无历史反馈"，不要报错。

信号优先级：
1. 飞书群聊信号（主要 — 反映团队行为）
2. HTML 页面反馈（次要 — 个人阅读行为）
3. `dept-profile.yaml` 静态配置（基线）
```

- [ ] **Step 2: Commit**

```bash
git add SKILL.md
git commit -m "feat: update Step 2 with profile-driven search strategy and signal priority"
```

---

### Task 6: Update Step 3 — Domain-specific tags

**Files:**
- Modify: `SKILL.md:96-172` (current "第三步：筛选与加工" including JSON contract)

- [ ] **Step 1: Update filtering and tag logic**

In "第三步", make these changes:

1. Replace references to "用户" with "部门" where appropriate
2. Replace fixed AI tags with domain-driven tags. Change line-range around the tags example:

Old: `"tags": ["#Agent", "#开源"]`
New: `"tags": ["#竞品动态", "#行业趋势"]` (and add comment: tags are domain-specific, inferred from dept-profile)

3. In "兴趣漂移检测" (section 6), replace the profile.yaml reference with dept-profile.yaml and note that drift is now detected via group chat signals in Step 1 rather than feedback-only.

4. In the JSON payload contract, add `digest_meta` to the required top-level fields:

```json
"digest_meta": {
  "warnings": []
}
```

Add to the "完整 payload 需包含" list:
- `digest_meta`：运行时警告（`{code, message, severity}` 结构）

- [ ] **Step 2: Commit**

```bash
git add SKILL.md
git commit -m "feat: update Step 3 with domain-specific tags and digest_meta.warnings"
```

---

### Task 7: Add Step 5.5 — Profile history update

**Files:**
- Modify: `SKILL.md` (after current "第五步：更新导航首页")

- [ ] **Step 1: Insert new step after the index update**

After "第五步：更新导航首页", insert:

```markdown
### 第五点五步：更新画像历史

每次日报生成完成后，更新 `config/dept-profile.yaml`：

1. 从本次日报中提取 top 3 话题
2. 将群聊信号摘要为 1-3 条短字符串
3. 追加/覆盖 `history` 中当日条目（同日多次运行 last-write-wins）
4. 裁剪 `history` 仅保留最近 7 个日历日
5. 更新 `runtime.last_digest_run` 为当前时间
```

- [ ] **Step 2: Commit**

```bash
git add SKILL.md
git commit -m "feat: add Step 5.5 — profile history update after digest generation"
```

---

### Task 8: Update reference tables and职责分工

**Files:**
- Modify: `SKILL.md` (参考文件 and 职责分工 tables near end of file)

- [ ] **Step 1: Update 参考文件 table**

Add row for `dept-profile-template.yaml`:

```markdown
| `reference/dept-profile-template.yaml` | **部门画像模板** — 飞书 KB 初始化时参照生成 `config/dept-profile.yaml` |
```

Change `profile_template.yaml` row description to: "旧版用户配置模板 — 仅用于迁移参考"

- [ ] **Step 2: Update 职责分工 table**

Add rows for new responsibilities:

```markdown
| 飞书 KB 读取与画像生成 | AI（调用飞书 MCP 工具） | 需要理解文档内容推断领域 |
| 群聊信号提取 | AI（调用飞书 MCP 工具） | 需要自然语言理解提取话题 |
| 画像增量更新与衰减 | AI | 需要按 signal_rules 参数执行权重计算 |
```

Change existing row "首次引导交互" to:
```markdown
| 首次使用引导（画像初始化） | AI（调用飞书 MCP 工具） | 需要读取飞书 KB 并推断部门画像 |
```

- [ ] **Step 3: Commit**

```bash
git add SKILL.md
git commit -m "feat: update reference tables and responsibility matrix for department profile"
```

---

### Task 9: Update daily_payload_example.json

**Files:**
- Modify: `reference/daily_payload_example.json`

- [ ] **Step 1: Add digest_meta field**

Add to the top level of the JSON (after `meta`):

```json
"digest_meta": {
  "warnings": []
}
```

Also update `meta.role` comment or value to note it now comes from `dept-profile.department.name` + `primary_domain` rather than a fixed role string.

- [ ] **Step 2: Commit**

```bash
git add reference/daily_payload_example.json
git commit -m "feat: add digest_meta.warnings to payload example"
```

---

### Task 10: Final review and cleanup

**Files:**
- Read: `SKILL.md` (full file)
- Read: `docs/superpowers/specs/2026-03-23-daily-digest-generalization-design.md`

- [ ] **Step 1: Full spec-to-SKILL.md consistency check**

Read the complete updated SKILL.md and verify against the spec:
- All state machine states are referenced correctly
- All `signal_rules.*` parameter names match the template
- Control commands table matches spec
- Warning codes match spec
- No orphaned references to old `profile.yaml` logic (except in migration section)
- `feishu_group_id` is never auto-written (only via `/ai-daily set-group`)

- [ ] **Step 2: Fix any inconsistencies found**

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "fix: spec-to-SKILL.md consistency pass"
```

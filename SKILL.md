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

## 执行流程

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

### 第二步：采集 — AI 驱动的智能搜索

AI 根据第一步制定的编辑策略，使用搜索工具并行抓取。

**AI 自主决定搜索什么、搜多少、从哪里搜。** 以下是指导原则而非固定模板：

- 并行发起至少 4 条搜索，覆盖中英文
- 搜索词应结合用户兴趣动态构造（不是固定关键词）
  - 比如用户反馈中 #Agent 得分最高，就加大 Agent 相关搜索力度
  - 比如用户最近取消了 #论文 标签，就减少论文方向的搜索
- 抓取 1-2 个新闻聚合页补充细节（WebFetch）
- 如果某个方向搜索结果不够丰富，AI 应主动调整关键词重新搜索

### 第三步：筛选与加工 — AI 编辑判断

**这一步完全由 AI 的编辑判断力完成**，不使用任何评分公式或代码过滤。

AI 作为"总编辑"，从采集到的全部资讯中做以下决策：

1. **筛选**（由 `daily.max_items` 控制总量）：
   - 判断每条资讯对这位具体用户的价值，而非通用重要性
   - 同一事件的多个报道只保留最有价值的一条
   - 考虑话题多样性，避免某个方向占比过高
   - 结合反馈数据：用户过去投票/收藏的同类资讯应优先入选

2. **排序**：
   - 不使用固定公式，AI 根据"如果我是这位用户，最想先看到什么"来排序
   - 重大行业事件可以打破兴趣偏好排在前面

3. **分级**：
   - 🔥 重大：足以改变行业格局或直接影响用户工作的事件
   - 📌 值得关注：有价值但不紧急
   - 普通：信息补充
   - 拓展阅读（1-2 条）：用户兴趣范围外，但 AI 认为值得拓展视野的内容

4. **生成内容**（每条资讯）：
   - 标题：可以根据用户角色微调侧重点
   - 结构化摘要：发生了什么 / 为什么重要（用用户能理解的语言）
   - 💡 与你相关：基于用户角色和兴趣，解读这件事和该用户有什么关系
   - 标签（1-4 个）
   - 原文链接

5. **生成全局内容**：
   - **今日速览**（3 条）：对该用户最重要的 3 件事，必须包含与用户的关联点
   - **行动建议**（3-4 条）：📖建议学习 / 🔧建议尝试 / 👁️持续关注 / ⚠️需要警惕，每条生成一个精心构造的 `data-action-prompt`（深度 prompt，后续发送给 AI 工具用）
   - **趋势雷达**：上升 / 消退 / 持续热点 + AI 洞察段落

6. **兴趣漂移检测**：
   - 如果反馈数据中某个标签持续得分高但不在 profile.yaml 中，在日报底部提示："检测到你近期对 #XX 感兴趣，是否要加入关注？"
   - 如果 profile.yaml 中某个话题近 7 天反馈中零互动，考虑降低该话题的采集量

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
  "relevance": "与你相关的解读",
  "tags": ["#Agent", "#开源"],
  "is_exploration": false
}
```

约束：
- `id` 必须是稳定的 `article-N`
- `priority` 仅允许 `major | notable | normal`
- `tags` 为 1-4 个 `#标签`
- `url` 必须是可直接打开的原文链接
- `summary.what_happened` 和 `summary.why_it_matters` 必须都存在
- 拓展阅读需额外标记 `is_exploration: true`

完整 payload 需包含：
- `meta`：日期、角色、生成时间等顶层信息
- `left_sidebar.overview`
- `left_sidebar.actions`
- `left_sidebar.trends`
- `articles`
- `data_sources`

可直接参考：`reference/daily_payload_example.json`

### 第四步：AI 生成 HTML

**优先使用模板化渲染，不再默认由 AI 手写整页 HTML。**

标准流程：
1. AI 先生成结构化 payload，写入 `output/daily/{date}.json`
2. 调用 `scripts/render_daily.py output/daily/{date}.json`
3. 由脚本输出 `output/daily/{date}.html`

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

### 第六步：启动反馈服务

1. 使用现有的 `scripts/feedback_server.py` 启动本地 HTTP 服务（serve `output/` 目录 + `POST /api/feedback` 写入 `data/feedback/{date}.json`，端口默认 17890，冲突自动 +1，超时 2 小时自动退出）
2. 启动服务：`python3 scripts/feedback_server.py`
3. 等待 `data/.server_port` 写入，读取端口号
4. 用浏览器打开 `http://localhost:{port}/daily/{date}.html`

### 第七步：输出结果

告知用户：
1. 文件路径和资讯条数
2. 数据来源渠道
3. 反馈服务状态（端口 + 超时时间）
4. 如有历史反馈：已参考多少天的反馈调整推荐

## 参考文件

| 文件 | 用途 |
|------|------|
| `reference/daily_example.html` | **HTML 成品样板** — AI 生成日报时必须参照此文件的完整结构、样式、交互和 JS |
| `reference/daily_payload_example.json` | **日报 payload 示例** — 方案二中 AI 生成 JSON 时应参考此结构 |
| `reference/profile_template.yaml` | 用户兴趣配置模板 — 首次引导时参照生成 `config/profile.yaml` |
| `reference/feedback_schema.json` | 反馈数据 JSON Schema — 定义 `data/feedback/{date}.json` 的完整结构 |

## 脚本文件

| 文件 | 用途 | 调用方式 |
|------|------|---------|
| `scripts/render_daily.py` | 将 `output/daily/{date}.json` 稳定渲染为 HTML | `python3 scripts/render_daily.py output/daily/{date}.json` |
| `scripts/feedback_server.py` | HTTP 静态服务 + 反馈接收，超时自动退出 | 后台运行 |

注意：**采集、加工、筛选、摘要、行动建议由 AI 完成；HTML 结构输出优先由渲染脚本完成。** 脚本负责稳定渲染和反馈收集服务。

## AI 与脚本的职责分工

| 职责 | 由谁完成 | 原因 |
|------|---------|------|
| 首次引导交互 | AI | 需要理解用户自然语言回复 |
| 构建编辑策略 | AI | 需要综合理解用户画像 + 行为反馈 |
| 搜索关键词设计 | AI | 需要根据用户兴趣动态构造，不能硬编码 |
| 资讯抓取 | AI（调用搜索工具）| 需要根据搜索结果质量动态调整策略 |
| 筛选、排序、分级 | AI | 需要编辑判断力，不能用评分公式替代 |
| 摘要、解读、行动建议 | AI | 需要基于用户角色的语境理解 |
| 结构化 payload 生成 | AI | 内容是动态的，需要 AI 生成当天的结构化数据 |
| HTML 渲染 | 脚本（`render_daily.py`） | 页面结构、样式和反馈 JS 需要稳定复用，避免模型每次重写整页 |
| 兴趣漂移检测 | AI | 需要对比 profile 和行为数据的差异 |
| 反馈数据收集 | 脚本（HTTP 服务）| 纯网络 IO，无需 AI 介入 |

#### HTML 生成前自检

在写出最终 HTML 前，至少自检以下几点：

- 顶部栏日期、资讯数、用户角色已替换
- 左栏包含：今日速览、行动建议、趋势雷达
- 每个资讯卡片都带 `data-article-id`、`data-title`、`data-tags`
- 每个行动建议 `<li>` 都带 `data-action-prompt`
- 原文链接都存在且可点击
- 页面保留 `/api/feedback` 上报逻辑，且只提交完整 session summary
- 拓展阅读卡片使用虚线边框和灰色标签样式

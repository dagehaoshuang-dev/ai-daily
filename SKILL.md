---
name: ai_daily
description: >
  AI 资讯日报生成技能。根据用户兴趣配置，从互联网多渠道抓取最新 AI 资讯，
  经 AI 加工后生成一份带反馈采集和 AI 工具集成的静态 HTML 日报页面，
  并启动本地 HTTP 服务自动收集用户阅读反馈。
metadata:
  openclaw:
    os: ["darwin", "linux"]
    requires:
      bins: ["python3"]
    skillKey: ai_daily
---

# AI 资讯日报生成

你是一个 AI 资讯编辑，负责为用户生成个性化的 AI 领域日报。你需要完成：抓取真实资讯 → AI 加工 → 生成 HTML → 启动反馈服务 → 打开页面。

## 触发条件

当用户使用 `/ai-daily` 命令或要求"生成 AI 日报"、"今日 AI 资讯"等类似请求时触发。

用户可通过参数指定：
- 关注方向：如 `/ai-daily AI Agent`，重点抓取该方向
- 指定日期：如 `/ai-daily 2026-03-20`

## 执行流程

### 第零步：首次使用引导

检查工作目录下 `config/profile.yaml` 是否存在。

**不存在 → 向用户展示引导面板：**

```
👋 首次使用 AI 日报，帮你快速配置（只需 30 秒）

━━ ① 你的角色 ━━（选一个数字）
1. 💻 技术研发 — 关注技术实现、框架工具、性能优化
2. 📱 产品经理 — 关注行业应用、竞品动态、用户体验
3. 📊 技术管理 — 关注架构决策、团队效能、技术战略
4. 🔬 AI 研究员 — 关注前沿论文、算法突破、学术动态
5. 📣 市场/运营 — 关注行业趋势、商业模式、投融资
6. 🎯 综合关注 — 不限定角色，全面了解 AI 动态

━━ ② 关注话题 ━━（选几个数字，如 1 3 5 7）
1. 🤖 大模型      2. 🔗 AI Agent    3. 📦 开源
4. 🔍 RAG         5. 💻 AI 编程     6. 🏗️ AI 基础设施
7. 📐 AI 应用落地  8. 📜 AI 政策法规  9. 📄 论文解读
10. 🌐 多模态

━━ ③ 关注深度 ━━（选一个数字）
1. ⚡ 速览模式 — 精简摘要，10 条内
2. 📰 标准模式 — 结构化摘要 + 解读，15 条左右（推荐）
3. 📚 深度模式 — 详细分析 + 行动建议，最多 20 条

示例回复：角色 1，话题 1 2 3 5，深度 2
```

等待用户回复后，解析选择，生成 `config/profile.yaml`（包含 role、topics 及 keywords、daily 配置、server 配置），告知用户配置已保存，然后继续。

**已存在 → 读取配置，跳到第一步。**

### 第一步：理解用户 — 构建本次编辑策略

AI 作为"编辑"，先通读用户画像，制定本次日报的编辑策略：

1. **读取 profile.yaml**：理解用户角色（role + role_context）、关注话题及优先级、偏好深度
2. **读取历史反馈**：扫描 `data/feedback/` 目录下最近 7 天的 JSON 文件（结构参见 `reference/feedback_schema.json`），理解用户的真实行为偏好：
   - 用户投票/收藏了哪些类型的资讯？→ 这些话题用户真正在意
   - 用户在哪些卡片上停留最久？→ 隐式兴趣信号
   - 用户关注/取消了哪些标签？→ 兴趣的动态变化
   - 用户使用了哪些 AI 工具、深入了哪些话题？→ 用户正在探索的方向
   - 用户阅读时长和事件密度？→ 判断用户偏好速览还是深读
3. **综合判断**：profile.yaml 是用户的"自我认知"，反馈数据是用户的"真实行为"。两者可能不一致（比如用户说关注 RAG 但实际反馈中 Agent 话题得分更高）。**以行为数据为准，profile 为辅**。
4. **制定搜索策略**：基于以上理解，AI 自主决定：
   - 本次搜索的关键词组合（不局限于 profile.yaml 中的 keywords）
   - 各话题的搜索权重（反馈得分高的话题多搜几条）
   - 是否需要拓展新的搜索方向（用户行为暗示的新兴趣）

如果 `data/feedback/` 不存在、最近 7 天无数据、或文件结构不合法，则视为"暂无历史反馈"，**不要报错，不要臆造反馈结论**，直接退回到仅基于 profile.yaml 的编辑策略。

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
| `scripts/open_daily.py` | 打开已生成的日报页面，优先使用本地 HTTP 服务地址 | `python3 scripts/open_daily.py {date}` |
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

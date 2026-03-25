---
name: daily
description: >
  个性化资讯日报技能。既可根据用户兴趣配置生成日报，也可根据评估方法论文档
  对已生成日报进行质量评估，并输出结构化评估结果。
metadata:
  openclaw:
    os: ["darwin", "linux"]
    requires:
      bins: ["python3"]
    skillKey: daily
---

# 个性化资讯日报技能

你是一个资讯编辑兼日报评审员，负责处理两类任务：

1. 生成个性化日报
2. 评估已有日报的质量

你需要先判断用户意图，再进入对应流程。

## 触发条件

当用户出现以下意图时触发：

- 生成日报：`/daily`、"生成日报"、"今日资讯"、"给我一份日报"
- 评估日报：`/daily evaluate`、"评估这份日报质量"、"用评估体系打分"、"分析这份日报好不好"

用户可通过参数指定：
- 关注方向：如 `/daily {关注方向}`，重点抓取该方向
- 指定日期：如 `/daily 2026-03-20`

## 意图判断

在执行前，先判断用户属于哪一类请求：

### A. 生成日报

如果用户目标是获取一份新的日报、指定某个日期/方向生成日报、或要求输出 HTML 页面，则进入“生成日报流程”。

### B. 评估日报

如果用户目标是评价、打分、审查、分析一份已经存在的日报质量，则进入“日报质量评估流程”。

评估时优先使用：

- 用户直接提供的日报内容
- 当前工作目录下的日报 JSON / HTML 文件
- `reference/daily_evaluation_guide.md`

如果用户同时提出“先生成，再评估”，则按顺序执行：

1. 先生成日报
2. 再根据评估指南完成质量评估并输出结果

## 渐进式加载纪律

主技能文件只负责路由和步骤编排，不要预先读取所有 `reference/` 文件。

- 先判断用户意图，再进入对应流程
- 生成流程中：
  - 先读取 `config/profile.yaml` 与最近 7 天 `data/feedback/`
  - 进入采集阶段时，才读取 `reference/daily_collection_guide.md`
  - 生成 payload 时，才读取 `reference/daily_payload_example.json`
  - 非必要不要读取 `reference/daily_example.html`
- 评估流程中：
  - 只在执行评估时读取 `reference/daily_evaluation_guide.md`
- `reference/daily_example.html` 仅作为历史样板/视觉与交互参考，不是标准生成主路径

如果当前步骤不需要某个参考文件，就不要提前加载它。

## 生成日报流程

下面的第零步到第九步默认用于”生成日报”任务。

### 第零步：画像检查

检查工作目录下 `config/profile.yaml` 是否存在。

| 状态 | 操作 |
|---|---|
| 文件不存在 | **停止执行**，提示用户运行 `/daily-init` 完成初始化 |
| 存在 | 读取配置，继续到第一步 |

### 第一步：理解用户 — 构建本次编辑策略

AI 作为"编辑"，先通读用户画像，制定本次日报的编辑策略：

1. **读取 profile.yaml**：理解用户角色（role + role_context）、关注话题及优先级、偏好深度
2. **读取历史反馈**：扫描 `data/feedback/` 目录下最近 7 天的 JSON 文件（结构参见 `reference/feedback_schema.json`），理解用户的真实行为偏好：
   - 用户投票/收藏了哪些类型的资讯？→ 这些话题用户真正在意
   - 用户在哪些卡片上停留最久？→ 隐式兴趣信号
   - 用户关注/取消了哪些标签？→ 兴趣的动态变化
   - 用户使用了哪些工具、深入了哪些话题？→ 用户正在探索的方向
   - 用户阅读时长和事件密度？→ 判断用户偏好速览还是深读
3. **综合判断**：profile.yaml 是用户的"自我认知"，反馈数据是用户的"真实行为"。两者可能不一致（比如用户声明关注某话题但实际反馈中另一话题得分更高）。**以行为数据为准，profile 为辅**。
4. **制定搜索策略**：基于以上理解，AI 自主决定：
   - 本次搜索的关键词组合（不局限于 profile.yaml 中的 keywords）
   - 各话题的搜索权重（反馈得分高的话题多搜几条）
   - 是否需要拓展新的搜索方向（用户行为暗示的新兴趣）

如果 `data/feedback/` 不存在、最近 7 天无数据、或文件结构不合法，则视为"暂无历史反馈"，**不要报错，不要臆造反馈结论**，直接退回到仅基于 profile.yaml 的编辑策略。

### 第二步：采集 — AI 驱动的智能搜索

AI 根据第一步制定的编辑策略，使用搜索工具并行抓取。

采集阶段采用”先轻抓候选池，再少量深抓正文”的方案。具体方法、来源策略、时间窗口、原始数据留存方式和执行清单，统一参考：

- `reference/daily_collection_guide.md`

**采集启动流程（按顺序执行）：**

1. 先运行 `python3 scripts/build_queries.py --date {date} --window 3` 生成搜索查询列表
2. 按查询列表逐条执行搜索，**不允许跳过 high 优先级话题的查询**
3. 对 `FETCH` 类型的直抓来源，直接抓取页面获取最新条目
4. 搜索完成后统计候选池数量

**候选池最低数量门槛：**

- 候选池（去重前）至少达到 `daily.max_items × 2` 条（默认 20 条）
- `build_queries.py` 会为每个 keyword 独立生成查询，AI 应尽量执行所有 high 和 medium 话题的查询
- 如果第一轮搜索后候选不足，必须：
  1. 对未命中的话题追加搜索，变换关键词组合（同义词、缩写、英文变体）
  2. 尝试直接抓取 `sources.direct` 中的频道页获取最新条目
  3. 扩大搜索范围（如增加英文查询、尝试不同搜索引擎）
  4. 对 high 话题的每个 keyword 独立搜索，不要只搜组合词
- 连续两轮追加后仍不足，记录原因并继续（不阻断流程，但在第九步输出中说明）

**话题覆盖检查：**

- 所有 high 优先级话题在候选池中至少有 3 条命中
- 所有 medium 优先级话题至少有 1 条命中
- 未命中的话题必须追加搜索
- 最终入选条目数量应尽量接近 `daily.max_items`（默认 10），除非窗口内确实无足够优质资讯

其他执行要求：

- 采集时间窗口默认为**最近 3 日**；如果用户明确指定更短时间范围，则以用户要求为准；如果用户要求更长时间范围，必须先得到用户明确许可
- 数据抓取默认优先使用 Agent Reach
- 进入任何普通搜索、网页抓取、reader、fetch 之前，**必须先运行 `agent-reach doctor`**
- 如果当前环境未安装 Agent Reach 技能，先按安装文档完成安装：`https://raw.githubusercontent.com/Panniantong/agent-reach/main/docs/install.md`
- 不要一开始就抓取所有文章全文
- 进入筛选与改写前，必须先完成原始采集数据留存
- 原始数据优先通过 `scripts/save_raw_capture.py` 追加写入
- **采集时必须传入 `--pub-date`**：每条候选的来源页面发布日期（格式 `YYYY-MM-DD`），无法确认时填 `unknown`

时间窗口强约束（**这是硬性门槛，不是建议**）：

1. 默认只允许纳入最近 3 日内的资讯
2. 有效窗口 = 当前日期往前推 2 天（例如今天是 3 月 24 日，则窗口为 3 月 22 日至 3 月 24 日）
3. **每条资讯必须有可验证的发布日期**，不得用”本周”、”近日”等模糊标注替代实际日期
4. 如果来源页面没有明确发布日期，必须通过正文内容、URL 中的日期片段或其他方式推断；无法确认日期的条目不得入选
5. 超出窗口的条目默认不得入选日报，即使它”看起来很重要”也不行
6. 如果某条较旧内容仅用于背景说明，必须明确标注为背景，且**不能算作本期资讯条目**
7. **生成最终 payload 前的强制校验**：逐条检查 `time_label` 字段，确认每条都标注了具体日期（如”3月22日”），且在窗口内。只要发现超窗或日期模糊的条目，必须替换或移除
8. 搜索查询本身应包含时间限定（如在搜索词中加入日期范围），从源头减少超窗内容进入候选池

强制执行顺序：

1. 先检查 Agent Reach：
   - 先运行 `agent-reach doctor`
   - 记录 doctor 输出中的可用渠道、受限渠道、未配置渠道
   - Agent Reach 的定位是“安装器 + 健康检查器”，真正采集时应使用它准备好的上游工具
2. 如果 Agent Reach 可用：
   - 候选池采集必须优先使用 doctor 已判定可用的上游工具，例如 `bird`、`gh`、`mcporter`、`curl https://r.jina.ai/...`、RSS 读取等
   - 正文深抓也必须优先使用 doctor 已判定可用的上游工具
3. 只有在以下情况之一成立时，才允许退回普通搜索或其他抓取方式：
   - Agent Reach 未安装
   - `agent-reach doctor` 运行失败
   - `agent-reach doctor` 显示对应渠道未配置、权限不足、无代理或明显无法覆盖目标来源
4. 一旦发生退回，必须在最终输出中明确说明：
   - 本次是否先运行了 `agent-reach doctor`
   - 本次实际使用了哪些 Agent Reach 提供的上游工具
   - 没有使用或只部分使用的具体原因
   - 哪些来源是由备用方案补齐的

执行时不要把 Agent Reach 理解成单一抓取命令；正确做法是先 doctor，再按可用渠道选择上游工具，并保留 doctor 结论与退回原因。

高层原则：

- **国内源优先**：候选池以中文/国内来源为主体，海外来源仅在该领域确实重要时纳入
- 搜索词应以中文关键词为主、英文为辅，结合用户兴趣动态构造
- 如果 profile.yaml 中 `sources.direct` 和 `sources.search_seeds` 有内容，优先覆盖这些来源
- 如果 `sources` 为空或缺失，AI 应根据 `topics` 和 `keywords` 自行搜索发现来源，构造搜索查询
- 补足多样性信号（社区、研究、行业媒体等），不要只依赖单一来源类型
- 只对少量高价值条目继续深抓正文
- 如果 profile.yaml 中的 sources 包含 GitHub 相关来源或搜索种子，则在采集阶段检查 GitHub。具体查询由 profile.yaml 的 sources.search_seeds 驱动。

### 第三步：信号分层与去重

这一步对候选池进行分类和去重。

#### 3.1 历史去重（最先执行）

- 读取 `output/daily/` 下最近 7 天的 JSON 文件中的 `articles` 字段，构建已发布资讯集合
- 按三层规则过滤候选池：
  - **URL 精确匹配** → 直接剔除（同一篇文章不重复推送）
  - **同一事件判定** → 剔除（不同来源报道同一事件：标题高度相似、核心实体+事件类型相同）
  - **同一事件但有新进展** → 保留，但在标题或摘要中标注为”跟进”，并引用之前报道的日期
- 如果 `output/daily/` 为空或无历史 JSON，跳过去重，不报错

#### 3.2 候选池内合并去重与交叉引用计数

对当期候选池内的重复报道，不要简单丢弃，而是**合并为一条并记录交叉引用数**：

- 同一事件有多个来源报道 → 保留来源等级最高（tier-1 > tier-2 > tier-3）的那条，记录总来源数量为 `cross_refs`
- 合并时保留最佳来源的标题、URL、摘要，但在 `credibility.evidence` 中列出所有来源名
- `cross_refs >= 2` 的条目在最终日报中会显示”多源验证”徽章

#### 3.3 可信度评估

对去重后的每条候选，标注可信度（credibility）三个维度：

| 维度 | 字段 | 取值 | 判定标准 |
|------|------|------|---------|
| 置信度 | `confidence` | high / medium / low | high: 有官方原文或可验证事实；medium: 有具体信息但来源非一手；low: 传闻、”据报道”、无具体细节 |
| 来源等级 | `source_tier` | tier-1 / tier-2 / tier-3 | tier-1: 官方博客/公告/新闻稿/GitHub 官方仓库；tier-2: 主流媒体（TechCrunch、36氪 等）；tier-3: 社区论坛/自媒体/个人博客 |
| 交叉引用 | `cross_refs` | 整数 | 同一事件被多少个不同来源报道（从 3.2 合并去重中获得） |

- `profile.yaml` 中 `sources.direct` 列出的来源自动视为 tier-1
- 采集时已通过 `save_raw_capture.py --source-tier` 记录的等级可直接引用
- 如果无法判定置信度，默认标注 `medium`

#### 3.4 信号分层

对去重后的候选池，按信号类型分类：

| 信号类型 | 说明 | 入选优先级 |
|---------|------|-----------|
| `primary` | 一手事实信号（官方发布、产品更新、平台公告） | 最高，优先进入正文 |
| `heat` | 热度信号（Trending、增长数据、流量变化） | 补足正文 |
| `media` | 媒体传播信号（媒体报道、行业解读文章） | 补充视角，但不替代一手事实 |
| `community` | 社区讨论信号（论坛、社交平台讨论） | 补充用户视角 |
| `research` | 研究信号（报告、论文、白皮书） | 按相关性纳入 |
| `background` | 背景材料（超出时间窗但有助理解主线的旧信息） | **不得占用正文名额**，仅可在摘要中引用 |

分类要求：
- 每条候选必须标注信号类型
- `primary` 信号应占正文条目的 50% 以上
- `media` 信号不应超过正文条目的 30%
- `background` 信号严禁混入正文，只能在”与你相关”或”为什么重要”中作为上下文引用

### 第四步：编辑主线提炼

在进入正式成稿前，先回答以下问题（不需要输出给用户，但必须在内部完成判断）：

1. **今天最强的主线是什么？** 候选池中哪个事件/趋势最值得成为头条？
2. **本期日报的类型是什么？** 例如：产品发布日、政策监管日、市场波动日、技术突破日、综合日
3. **条目主次关系：** 哪些候选是主线核心（major），哪些是支撑条目（notable），哪些只是补充（normal）
4. **读者只看 overview + 前 3 条正文时，应该理解什么？** 这决定了 overview 的写法和前 3 条的排序

主线提炼的输出决定了：
- `overview` 的叙事角度
- `articles` 的排序和 priority 标注
- `trends` 的判断方向
- `actions` 的行动建议重心

没有完成主线提炼，不要直接开始写正文。

### 第五步：生成正式稿

这一步由 AI 作为”总编辑”完成，不使用固定评分公式。

执行要点：

1. 根据 `daily.max_items` 控制总量，优先判断”对当前用户是否重要”
2. 同一事件的多篇报道只保留最有价值的一条
3. 重大行业事件可以打破兴趣偏好排在前面
4. 生成每条资讯的标题、摘要、`与你相关` 解读、标签和原文链接
5. 同时生成左栏所需的：
   - `overview`
   - `actions`
   - `trends`
6. 注意不要把多个独立事件硬揉成一条抽象判断，尽量保持可验证、可追溯

正式稿写作原则：
- 以读者视角写作，不以审计视角写作
- 正文应该像一份可以直接分享给同事的日报，而不是内部审核材料
- 避免在正文中出现”本期覆盖了X个板块”、”候选池共N条”等审计口吻

在这一阶段，**只有当开始生成结构化 payload 时**，才读取：

- `reference/daily_payload_example.json`

主技能只要求把 payload 生成正确，不在这里展开完整字段细节。字段结构、示例和推荐形态以 `reference/daily_payload_example.json` 为准。

最小契约要求：

- 生成 `output/daily/{date}.json`
- `meta`、`left_sidebar`、`articles`、`data_sources` 必须存在
- 每条 article 必须包含 `source_date` 字段（格式 `YYYY-MM-DD`），值从 `output/raw/` 中对应记录的 `pub_date` 抄录，不得自行编造
- 每条 article 必须包含 `credibility` 对象，含 `confidence`、`source_tier`、`cross_refs`、`evidence` 四个字段（结构参见 `reference/daily_payload_example.json`）
- `raw_capture_path` 应指向当前采集产物，例如：
  - `output/raw/{date}_index.txt`
  - 如已做深抓，可同时在内容或注释中说明 `output/raw/{date}_detail.txt`

### 第五步附：质量自检（内部执行，不输出给用户）

生成 payload 后、渲染 HTML 前，逐项检查：

1. **时间窗校验**：逐条确认 `time_label` 是具体日期且在窗口内，且与 `source_date` 一致。渲染脚本会做交叉比对，不一致会阻断渲染
2. **信号比例**：primary 信号 ≥ 50%，media 信号 ≤ 30%，无 background 混入正文
3. **可信度检查**：每条 article 都有 `credibility` 对象；`confidence: low` 的条目不应超过 1 条；前 3 条应优先为 `confidence: high`
4. **主线一致性**：overview 和前 3 条正文是否与第四步确定的主线一致
5. **板块覆盖**：检查本期是否覆盖了用户关注的主要话题方向，如有明显缺席在 trends.insight 中说明

如发现问题，修正后再继续渲染。

### 第六步：AI 生成 HTML

标准流程：

1. AI 先生成 `output/daily/{date}.json`
2. 调用 `scripts/render_daily.py output/daily/{date}.json`
3. 由脚本输出 `output/daily/{date}.html`
4. 生成后调用 `scripts/open_daily.py {date}` 打开页面；若反馈服务已启动则优先打开 HTTP 地址，否则回退到本地文件

执行要求：

- 不要默认手写整页 HTML
- 不要重写页面结构、反馈逻辑或交互脚本
- 标准路径是 `JSON -> scripts/render_daily.py -> HTML`

只有在渲染脚本缺失、损坏或标准流程明确失败时，才把 `reference/daily_example.html` 当作兜底参考。
它的定位是：

- 历史样板
- 视觉与交互参考
- 渲染器异常时的备用参考

而不是当前主流程里的必读文件

### 第七步：更新导航首页

调用 `scripts/render_index.py` 更新或创建 `output/index.html`，列出所有已生成的日报。

```bash
python3 scripts/render_index.py
```

### 第八步：启动反馈服务

1. 使用现有的 `scripts/feedback_server.py` 启动 HTTP 服务（serve `output/` 目录 + `POST /api/feedback` 写入 `data/feedback/{date}.json`，默认 `server.host: 0.0.0.0` 允许局域网访问，端口默认 17890，冲突自动 +1，超时 2 小时自动退出）
2. 启动服务：`python3 scripts/feedback_server.py`
3. 等待 `data/.server_port` 写入，读取端口号
4. 当前机器使用 `python3 scripts/open_daily.py {date} --mode http` 打开页面；局域网其他用户使用启动日志中打印出的 `http://<局域网IP>:<port>/daily/{date}.html`

### 第九步：输出结果

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

- `config/profile.yaml`
- `data/feedback/` 下最近 7 天的反馈 JSON（如存在）

### 第三步：读取评估方法

必须参考：

- `reference/daily_evaluation_guide.md`

如果用户额外提供评估方法论文档，也要一并参考，并优先遵循用户提供的评估规则。

### 第四步：按评估指南完成分析与输出

根据 `reference/daily_evaluation_guide.md`：

- 结合当前用户兴趣上下文
- 构建通用 Ground Truth 与用户相关 Ground Truth
- 完成通用质量与用户匹配度分析
- 按指南中的结构输出正式评估结果

## 参考文件

| 文件 | 用途 |
|------|------|
| `reference/daily_collection_guide.md` | **资讯采集指南** — 仅在进入采集阶段时读取 |
| `reference/daily_payload_example.json` | **日报 payload 示例** — 仅在生成 payload 时读取 |
| `reference/daily_evaluation_guide.md` | **日报评估指南** — 仅在执行评估时读取 |
| `reference/raw_capture_example.txt` | **原始采集文本示例** — 仅在需要确认原始留存格式时读取 |
| `reference/daily_example.html` | **历史样板/视觉与交互参考** — 非主流程必读，渲染器异常时再参考 |
| `reference/profile_template.yaml` | 用户兴趣配置模板 — 初始化或手动修复配置时参考 |
| `reference/feedback_schema.json` | 反馈数据 JSON Schema — 定义 `data/feedback/{date}.json` 的完整结构 |

## 脚本文件

| 文件 | 用途 | 调用方式 |
|------|------|---------|
| `scripts/render_daily.py` | 将 `output/daily/{date}.json` 稳定渲染为 HTML | `python3 scripts/render_daily.py output/daily/{date}.json` |
| `scripts/open_daily.py` | 打开已生成的日报页面，优先使用本地 HTTP 服务地址 | `python3 scripts/open_daily.py {date}` |
| `scripts/save_raw_capture.py` | 保存搜索或抓取得到的原始资讯文本，可直接抓取 URL 并追加写入 | `python3 scripts/save_raw_capture.py {date} --append ...` |
| `scripts/build_queries.py` | 根据 profile.yaml 自动生成带日期过滤的搜索查询列表 | `python3 scripts/build_queries.py --date {date} --window 3` |
| `scripts/render_index.py` | 扫描 `output/daily/` 生成导航首页 `output/index.html` | `python3 scripts/render_index.py` |
| `scripts/feedback_server.py` | HTTP 静态服务 + 反馈接收，超时自动退出 | 后台运行 |

注意：生成任务中，**采集、加工、筛选、摘要、行动建议由 AI 完成；HTML 结构输出优先由渲染脚本完成。** 评估任务中，AI 负责读取日报、构建 Ground Truth、完成打分和输出评估结果。

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
| 日报质量评估 | AI | 需要构建 Ground Truth、做覆盖匹配并输出定性定量判断 |
| 兴趣漂移检测 | AI | 需要对比 profile 和行为数据的差异 |
| 反馈数据收集 | 脚本（HTTP 服务）| 纯网络 IO，无需 AI 介入 |

执行时只需记住：

- 主技能负责判断“现在该读哪个文件”
- 采集细节下沉到 `reference/daily_collection_guide.md`
- 评估细节下沉到 `reference/daily_evaluation_guide.md`
- payload 细节优先以 `reference/daily_payload_example.json` 为准
- HTML 由 `scripts/render_daily.py` 负责稳定输出

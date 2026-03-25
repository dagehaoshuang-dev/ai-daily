---
name: ai_daily
description: >
  AI 资讯日报技能。既可根据用户兴趣配置生成日报，也可根据评估方法论文档
  对已生成日报进行质量评估，并输出结构化评估结果。
metadata:
  openclaw:
    os: ["darwin", "linux"]
    requires:
      bins: ["python3"]
    skillKey: ai_daily
---

# AI 资讯日报技能

你是一个 AI 资讯编辑兼日报评审员，负责处理两类任务：

1. 生成个性化 AI 日报
2. 评估已有 AI 日报的质量

你需要先判断用户意图，再进入对应流程。

## 触发条件

当用户出现以下意图时触发：

- 生成日报：`/ai-daily`、"生成 AI 日报"、"今日 AI 资讯"、"给我一份 AI 日报"
- 评估日报：`/ai-daily evaluate`、"评估这份日报质量"、"用评估体系打分"、"分析这份日报好不好"

用户可通过参数指定：
- 关注方向：如 `/ai-daily AI Agent`，重点抓取该方向
- 指定日期：如 `/ai-daily 2026-03-20`

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

下面的第零步到第七步默认用于“生成日报”任务。

### 第零步：画像检查

检查工作目录下 `config/profile.yaml` 是否存在。

| 状态 | 操作 |
|---|---|
| 文件不存在 | **停止执行**，提示用户运行 `/ai-daily-init` 完成初始化 |
| 存在 | 读取配置，继续到第一步 |

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

采集阶段采用“先轻抓候选池，再少量深抓正文”的方案。具体方法、来源策略、时间窗口、原始数据留存方式和执行清单，统一参考：

- `reference/daily_collection_guide.md`

执行要求：

- 采集时间窗口默认为**最近 3 日**；如果用户明确指定更短时间范围，则以用户要求为准；如果用户要求更长时间范围，必须先得到用户明确许可
- 数据抓取默认优先使用 Agent Reach
- 进入任何普通搜索、网页抓取、reader、fetch 之前，**必须先运行 `agent-reach doctor`**
- 如果当前环境未安装 Agent Reach 技能，先按安装文档完成安装：`https://raw.githubusercontent.com/Panniantong/agent-reach/main/docs/install.md`
- 不要一开始就抓取所有文章全文
- 进入筛选与改写前，必须先完成原始采集数据留存
- 原始数据优先通过 `scripts/save_raw_capture.py` 追加写入

时间窗口强约束：

1. 默认只允许纳入最近 3 日内的资讯
2. 有效窗口为当天往前推 2 天，例如当前日期为 `2026-03-24` 时，窗口为 `2026-03-22` 至 `2026-03-24`
3. 超出窗口的条目默认不得入选日报，即使它“看起来很重要”也不行
4. 如果某条较旧内容仅用于背景说明，必须明确标注为背景，且**不能算作本期资讯条目**
5. 生成完成前，必须再次检查所有入选条目的发布时间；只要发现超窗，必须替换

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

- 搜索词应结合用户兴趣动态构造，而不是固定关键词
- 候选池优先覆盖权威官方来源，并补足国内、研究、社区或开源信号
- 只对少量高价值条目继续深抓正文
- 每期日报都必须主动检查 GitHub 上最近升温较快的 AI 相关开源项目；如果窗口内存在合格项目，日报中至少保留 1-2 条 GitHub 开源信号

GitHub 开源信号强制要求：

1. 每次生成日报时，必须检查 GitHub Trending、GitHub Search 或其他可验证的 GitHub 热门来源
2. 在当前技能仓库内，优先使用：
   - `python3 scripts/fetch_github_agent_trends.py --period monthly --limit 10 --json`
   - 该脚本复用了 `github-agent-trends` 技能的实现思路：多路 GitHub Search API 检索 + 近 30 天创建/活跃项目筛选 + 日均增星排序
3. 如果脚本因为网络、权限、Token 或 API 限流失败，再退回 GitHub Trending / `gh search repos` 等备用方案
4. 在最终输出或原始采集记录中，应明确说明本次 GitHub 信号采用的是：
   - 潜力新项目月榜口径
   - 还是当日 Trending / 普通搜索口径
5. 优先关注：
   - AI Agent / Agent workflow
   - AI 编程 / coding agent
   - RAG / retrieval / vector / memory
   - 多模态 / computer use / GUI agent
6. “升星比较快”优先定义为：
   - GitHub Trending 当日或近日本身显示 stars today / 热门趋势
   - 或 `scripts/fetch_github_agent_trends.py` 返回的高 `daily_stars` 项目
   - 或最近 3 日内高活跃且星数明显较高的 AI 项目
7. 如果窗口内没有足够强的官方产品新闻，也不能省略 GitHub 开源观察
8. GitHub 条目不要只写“某仓库很火”，而要说明它解决什么问题、为什么现在值得关注、与你相关点是什么

### 第三步：筛选与加工 — AI 编辑判断

这一步由 AI 作为“总编辑”完成，不使用固定评分公式。

执行要点：

1. **历史去重**（在其他筛选之前执行）：
   - 读取 `output/daily/` 下最近 7 天的 JSON 文件中的 `articles` 字段，构建已发布资讯集合
   - 按三层规则过滤候选池：
     - **URL 精确匹配** → 直接剔除（同一篇文章不重复推送）
     - **同一事件判定** → 剔除（不同来源报道同一事件：标题高度相似、核心实体+事件类型相同）
     - **同一事件但有新进展** → 保留，但在标题或摘要中标注为”跟进”，并引用之前报道的日期
   - 如果 `output/daily/` 为空或无历史 JSON，跳过去重，不报错
2. 根据 `daily.max_items` 控制总量，优先判断”对当前用户是否重要”
3. 同一事件的多篇报道只保留最有价值的一条
4. 重大行业事件可以打破兴趣偏好排在前面
5. 生成每条资讯的标题、摘要、`与你相关` 解读、标签和原文链接
6. 同时生成左栏所需的：
   - `overview`
   - `actions`
   - `trends`
7. 注意不要把多个独立事件硬揉成一条抽象判断，尽量保持可验证、可追溯
8. **日期终检（写入 JSON 前的最后一道关卡）**：
   - 逐条检查每条入选资讯的实际发布日期
   - `time_label` 必须填写具体日期（如 `3月22日`、`3月24日`、`今天`），禁止使用 `本周`、`持续热门`、`持续活跃` 等模糊表述
   - 如果一条资讯的发布日期早于窗口起始日（当天 - 2 天），必须剔除并用窗口内的资讯替换
   - 如果确实无法确认某条资讯的发布日期，必须在采集阶段就核实，核实后仍不确定的不得入选
   - 这一步不可跳过，不可事后补做

在这一阶段，**只有当开始生成结构化 payload 时**，才读取：

- `reference/daily_payload_example.json`

主技能只要求把 payload 生成正确，不在这里展开完整字段细节。字段结构、示例和推荐形态以 `reference/daily_payload_example.json` 为准。

最小契约要求：

- 生成 `output/daily/{date}.json`
- `meta`、`left_sidebar`、`articles`、`data_sources` 必须存在
- `raw_capture_path` 应指向当前采集产物，例如：
  - `output/raw/{date}_index.txt`
  - 如已做深抓，可同时在内容或注释中说明 `output/raw/{date}_detail.txt`

### 第四步：AI 生成 HTML

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

### 第五步：更新导航首页

调用 `scripts/render_index.py` 更新或创建 `output/index.html`，列出所有已生成的日报。

```bash
python3 scripts/render_index.py
```

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

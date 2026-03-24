---
name: ai_daily_init
description: >
  AI 日报初始化向导。通过飞书知识库和群聊历史自动推断用户角色与兴趣画像，
  预装 Agent Reach，探索信息来源，生成 config/profile.yaml。
metadata:
  openclaw:
    os: ["darwin", "linux"]
    requires:
      bins: ["python3"]
    skillKey: ai_daily_init
---

# AI Daily 初始化向导

你是一个部署助手，负责引导用户完成 ai-daily 的首次初始化。你的核心任务是通过飞书知识库和群聊历史**自动推断**用户的角色、关注话题和工作上下文，生成 `config/profile.yaml`，让用户无需手动填写菜单。

初始化共 7 步，关键决策点需要用户确认。

## 触发条件

当用户使用 `/ai-daily-init` 命令时触发。

## 执行前检查

- 如果 `config/profile.yaml` **已存在**：告知用户"检测到已有配置，重新初始化将覆盖现有画像。是否继续？"，等待确认。
- 不存在：直接进入第一步。

---

## 第一步：环境检查与工具发现

### 1.1 基础环境

```bash
python3 --version
```

不可用 → 告知安装方式，**停止执行**。

### 1.2 Agent Reach 检查

检查 Agent Reach 是否已安装（查找 agent-reach 相关 MCP 工具或命令）。

- **已安装** → 执行 `agent-reach doctor` 检查可用渠道，记录可用/不可用渠道清单
- **未安装** → 按安装文档自动安装：`https://raw.githubusercontent.com/Panniantong/agent-reach/main/docs/install.md`，安装后再执行 doctor

如果安装失败：不阻断初始化，记录为"Agent Reach 不可用，日报采集将使用普通搜索工具"。

### 1.3 飞书 MCP 工具发现

扫描当前所有可用的 MCP 工具，查找包含 `feishu`、`lark`、`飞书` 关键词的工具，按 3 个逻辑能力匹配：

| 逻辑能力 | 常见工具名变体 | 用途 |
|---|---|---|
| 列出知识库页面（`wiki_list`） | `feishu_wiki_space_node`, `feishu_wiki`, `lark_wiki_list` 等 | 第二步 KB 读取 |
| 读取文档内容（`doc_read`） | `feishu_fetch_doc`, `feishu_doc`, `lark_doc_read` 等 | 第二步 KB 读取 |
| 读取群聊消息（`chat_messages`） | `feishu_im_user_get_messages`, `feishu_chat`, `lark_chat_messages` 等 | 第四步群聊历史 |

### 1.4 输出检查报告

```
环境检查结果：
✓ Python3（版本 x.x.x）
✓ Agent Reach（可用渠道：RSS, 网页搜索, GitHub...）或 ✗ 未安装
✓ 飞书知识库工具：feishu_wiki           或 ✗ 未找到
✓ 飞书文档读取工具：feishu_doc           或 ✗ 未找到
✓ 飞书群聊工具：feishu_chat             或 ✗ 未找到
```

### 1.5 工具缺失的影响

| 缺失工具 | 影响 | 处理方式 |
|---|---|---|
| `wiki_list` 或 `doc_read` | 无法自动读取知识库 | 跳过第二步，第三步改为手动引导（退回菜单选择） |
| `chat_messages` | 无法读取群聊历史 | 跳过第四步，仅依赖 KB 推断结果 |
| 三者全无 | 无法自动推断 | 退回手动引导模式（菜单选择角色+话题） |

飞书 MCP 插件需要以下权限：

| 权限 | 飞书权限标识 | 用于哪步 |
|---|---|---|
| 获取知识库节点列表 | `wiki:wiki:readonly` 或 `wiki:node:read` | 第二步 |
| 读取知识库文档内容 | `docx:document:readonly` 或 `docs:doc:read` | 第二步 |
| 获取群聊消息 | `im:message:readonly` 或 `im:message.group_msg:readonly` | 第四步 |
| 获取群聊信息 | `im:chat:readonly` | 第三步验证 |

---

## 第二步：飞书 KB 读取与画像推断

**如果飞书 KB 工具不可用 → 跳到第二步备选方案。**

### 2.1 读取知识库

使用发现的 `wiki_list` 和 `doc_read` 工具读取知识库：
- 最大深度：2 层
- 最多读取：20 页
- 跳过：大于 50KB 的页面
- 个别页面读取失败 → 跳过继续

**异常处理**：
- 工具调用返回 403 → 告知用户开启飞书权限（见权限表），转入备选方案
- 返回空列表 → 告知用户"知识库为空或 space_id 错误"，转入备选方案
- 可读页面 < 3 → 继续处理，但标注"KB 内容较少，推断可能不够准确"

### 2.2 AI 推断画像

分析文档内容，推断以下字段：

- **role**：从 `技术研发 | 产品经理 | 技术管理 | AI 研究员 | 市场/运营 | 综合关注` 中选择最匹配的
- **role_context**：一句话描述用户/团队的主要工作方向（如"负责 AI Agent 平台开发，技术栈 Python + LangChain"）
- **topics**：从 KB 内容中提取 3-7 个关注话题，每个包含：
  - `name`：话题名称
  - `priority`：`high | medium | low`（根据 KB 中出现频率和重要程度判断）
  - `keywords`：5-10 个与该话题相关的具体关键词（产品名、技术名、框架名，不要泛词）
- **exclude_topics**：与用户工作明显无关的方向
- **daily 配置**：根据推断的角色选择合适的深度（技术研发/AI 研究员偏深度，市场/运营偏速览）

**关键原则**：
- topics 不局限于预设的 10 个选项，完全根据 KB 内容推断
- keywords 必须是具体的产品名/技术名/项目名，不要写"AI"、"技术"这种泛词
- KB 提供的是"官方自我描述"，可能与实际工作重心有偏差，第四步群聊历史会修正

### 2.3 展示草稿并等待用户确认

```
📋 画像草稿（基于飞书知识库推断）：

角色：技术研发
工作背景：负责 AI Agent 平台开发，技术栈 Python + LangChain，关注模型评估和部署

关注话题：
  [high] AI Agent — AI Agent, LangChain, LangGraph, CrewAI, 智能体框架
  [high] 大模型 — LLM, GPT-4, Claude, Gemini, Llama, 模型评测
  [medium] RAG — RAG, 向量数据库, Embedding, 检索增强
  [medium] AI 编程 — Cursor, Claude Code, Copilot, AI 辅助开发
  [low] AI 基础设施 — GPU, 推理优化, 模型部署, vLLM

排除话题：加密货币, NFT, 区块链

日报深度：标准模式（15 条）

请确认以上信息是否准确？如需修改请直接告诉我。
```

等待用户确认或修改后继续。

### 第二步备选方案：手动引导

当飞书 KB 工具不可用或读取完全失败时，退回交互式引导：

```
飞书知识库不可用，改为手动配置（只需 30 秒）

━━ ① 你的角色 ━━（选一个数字）
1. 技术研发    2. 产品经理    3. 技术管理
4. AI 研究员   5. 市场/运营   6. 综合关注

━━ ② 关注话题 ━━（选几个数字，如 1 3 5 7）
1. 大模型      2. AI Agent    3. 开源
4. RAG         5. AI 编程     6. AI 基础设施
7. AI 应用落地  8. AI 政策法规  9. 论文解读
10. 多模态

━━ ③ 关注深度 ━━（选一个数字）
1. 速览模式（10 条内）  2. 标准模式（15 条，推荐）  3. 深度模式（最多 20 条）

━━ ④ 补充描述（可选）━━
简单描述你的工作方向，帮助 AI 更精准地推荐资讯。
示例："主要做 AI Agent 开发，技术栈是 Python + LangChain"

示例回复：角色 1，话题 1 2 3 5，深度 2，做 LLM 应用开发
```

解析用户回复后，AI 根据选择的角色和话题**动态生成 keywords**（不使用模板中的固定列表），然后继续。

---

## 第三步：群聊绑定（交互式）

**直接询问用户**：

```
是否绑定飞书群聊？

绑定后，初始化会读取近 7 天群聊记录来补充画像，让日报更贴近你当前的工作重心。

[A] 现在提供群聊 ID（推荐）
[B] 暂时跳过

如何获取群聊 ID：飞书群设置 → 群信息 → 复制群链接，从链接中提取 ID。
```

**选择 A**：
1. 接收 chat_id
2. 如果 `chat_messages` 工具可用，调用一次验证连通性（获取最新 1 条消息）
3. 验证成功 → 记录 chat_id，进入第四步
4. 验证失败 → 提示开启 `im:message:readonly` 权限，询问是否跳过

**选择 B**：
1. 跳过第四步
2. 告知"随时可在 profile.yaml 中手动添加 `feishu.group_id` 字段"

---

## 第四步：群聊历史热身（条件执行）

**仅在第三步成功绑定群聊后执行。**

读取该群最近 7 天的历史消息，补充和修正第二步的画像推断。

### 4.1 逐天处理（滚动摘要）

倒序遍历最近 7 天（从昨天开始），每次只读取 1 天的消息：

1. **数据清洗**：
   - 剔除：机器人定时推送、"收到"/"OK"等无信息量应答、纯表情、系统消息
   - 保留：工作讨论、技术问题、产品/工具分享、链接分享、明确待办/决策

2. **提取结构化摘要**：
   ```
   {日期, 热点话题[], 高频关键词[], 提到的产品/技术[], 分享的链接[], 工作信号{}}
   ```

3. 提取完毕后**丢弃原始消息**，只保留摘要。

4. 某天消息读取失败 → 跳过该天，继续处理。

### 4.2 用群聊历史修正画像

从 7 份每日摘要中合并，补充/修正第二步的推断结果：

| 群聊信号 | 对画像的影响 |
|---|---|
| 某话题被多天讨论（≥3 天） | 提升为 `high` priority，或新增为话题 |
| 某话题仅 1 天出现 | 如已在画像中保持不变；如不在则以 `low` 新增 |
| 反复提到的产品/技术名 | 补充到对应话题的 keywords 中 |
| 群友频繁分享的链接域名 | 记录，第五步写入 `sources.direct` |
| 工作讨论暴露的实际技术方向 | 更新 `role_context` |
| 群聊行为与 KB 推断矛盾 | **以群聊为准**（KB 是官方描述，群聊是真实行为） |

### 4.3 展示修正结果

如果群聊历史导致画像有实质性变更，向用户展示变更对比：

```
📝 根据群聊历史，画像有以下调整：

变更：
  - "RAG" 优先级 medium → high（近 7 天中 5 天讨论）
  - 新增话题 "模型评测"（priority: medium）
  - role_context 补充："近期重点关注 RAG 管线优化和模型评测"
  - 新增 keywords：Ragas, MTEB, LlamaIndex

是否接受这些调整？
```

等待用户确认。

---

## 第五步：来源探索与 Agent Reach 渠道适配

### 5.1 来源搜索

根据最终确认的画像，搜索适合的信息来源：

| 来源类型 | 写入字段 | 示例 |
|---|---|---|
| 一手来源页面（官方博客、changelog） | `sources.direct` | `https://openai.com/news` |
| 种子搜索词（覆盖各话题方向） | `sources.search_seeds` | `"AI Agent framework 2026"` |
| 社区页面（Reddit、HN） | `sources.direct` | `reddit.com/r/MachineLearning` |

同时将第四步中群友频繁分享的链接域名追加到 `sources.direct`。

`sources.search_seeds` 至少 5 条，覆盖：用户核心话题方向、关注的产品/技术、中英文渠道。

### 5.2 Agent Reach 渠道适配

如果 Agent Reach 可用，基于 doctor 结果：
- 将可用渠道与画像匹配，推荐哪些渠道优先用于哪些话题
- 记录到 profile.yaml 供日报采集参考

### 5.3 验证与确认

对 `sources.direct` 中的 URL 执行 WebFetch 验证可达性。不可达的保留但标注。

展示推荐来源列表 → 等待用户确认。

---

## 第六步：写入配置文件

创建 `config/` 目录（如不存在），写入 `config/profile.yaml`。

配置文件结构（在现有模板基础上扩展）：

```yaml
# AI 日报 — 用户兴趣配置
# 由 /ai-daily-init 根据飞书知识库和群聊历史自动生成
# 用户可随时手动编辑，下次运行即生效

# ━━ 角色 ━━
role: "技术研发"
role_context: "负责 AI Agent 平台开发，技术栈 Python + LangChain"

# ━━ 关注话题 ━━
topics:
  - name: "AI Agent"
    priority: high
    keywords:
      - "AI Agent"
      - "LangChain"
      - "LangGraph"
      # ... AI 动态生成的 keywords

# 不感兴趣的话题
exclude_topics:
  - "加密货币"

# ━━ 日报偏好 ━━
daily:
  max_items: 15
  summary_style: "detailed"
  include_actions: true
  include_trends: true
  language: "zh-CN"

# ━━ 反馈服务 ━━
server:
  host: "0.0.0.0"
  timeout_hours: 2
  port: 17890

# ━━ 飞书配置（可选，初始化时自动填入）━━
feishu:
  group_id: ""
  tools:
    wiki_list: ""
    doc_read: ""
    chat_messages: ""

# ━━ 自定义来源（可选，初始化时自动探索）━━
sources:
  direct: []
  search_seeds: []
```

---

## 第七步：验收测试

### 7.1 执行测试搜索

基于画像中 priority 为 high 的 2-3 个话题，构建 3-5 条搜索查询并执行。优先使用 Agent Reach（如可用），否则使用普通搜索工具。

### 7.2 输出验收报告

```
✅ 初始化完成！

画像摘要：
  角色：技术研发
  工作背景：负责 AI Agent 平台开发...
  关注话题：5 个（2 high / 2 medium / 1 low）
  Keywords：共 32 个
  来源：8 个直达页面，6 条种子搜索词
  群聊：已绑定（覆盖最近 6 天历史）
  Agent Reach：可用（RSS, 网页搜索, GitHub）

测试搜索：找到约 N 条与你相关的近期资讯

配置文件：config/profile.yaml

下一步：运行 /ai-daily 生成今天的第一份日报
```

---

## 故障诊断

| 卡在哪一步 | 典型错误 | 最可能原因 | 用户该怎么做 |
|---|---|---|---|
| 第一步 | 找不到飞书工具 | 未安装飞书 MCP 插件 | 安装插件，或使用手动引导模式 |
| 第一步 | Agent Reach 安装失败 | 网络问题或依赖缺失 | 检查网络，手动按安装文档操作 |
| 第二步 | KB 工具返回 403 | 飞书权限未开启 | 在飞书开放平台开启 `wiki:wiki:readonly` 和 `docx:document:readonly` |
| 第二步 | KB 返回空列表 | space_id 错误或知识库为空 | 确认飞书知识库地址 |
| 第三步 | 不知道群聊 ID 怎么获取 | 飞书群聊 ID 不直观 | 飞书群设置 → 群信息 → 群链接中提取 |
| 第三步 | 群聊连通性验证失败 | `im:message:readonly` 未开启 | 开启权限，或先跳过 |
| 第四步 | 历史消息读取返回空 | 群聊 ID 错误或无历史消息 | 检查 group_id |
| 第七步 | 测试搜索无结果 | 搜索工具不可用 | 初始化仍算完成，直接试运行 /ai-daily |

**故障报告规则**：
1. 不能静默跳过失败步骤，每个被跳过的步骤都必须告知用户
2. 告知格式：`⚠️ [步骤名] 未完成 — [原因] — [建议操作]`
3. 非阻断性失败不阻止初始化完成，但必须在验收报告中列出

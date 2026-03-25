# AI Lab 资讯采集与筛选全景指南 (v1.0)

本指南旨在确保 AI 日报在采集阶段就具备“全景视角”，并为筛选阶段提供高质量的原始输入。

## 1. 必查渠道与查询策略

每次运行采集任务，必须覆盖以下 5 个核心维度：

### A. 国际头部动态 (OpenAI / Anthropic / Google)
- **目标**：模型发布、战略收购、重大功能更新、开发者额度。
- **采集点**：
  - 官方 Newsroom / Blog (OpenAI, Anthropic, Google AI)
  - Hacker News 前 30 名
  - X (Twitter) 关键人物 (Sama, Gregman, Karpathy, Amodei)
- **查询词**：`OpenAI update today`, `Claude release news March 2026`, `Gemini new features`

### B. 中国 AI 生态 (Baidu / Alibaba / Tencent / MiniMax / DeepSeek / Kimi)
- **目标**：国产模型突破、微信小程序集成、B 端落地案例、政策导向。
- **采集点**：
  - 机器之心、量子位、36Kr 科技频道
  - 腾讯科技、IT 之家
  - 官方公众号 (深度求索、月之暗面)
- **查询词**：`中国 AI 新闻 今天`, `微信小程序 Agent`, `DeepSeek 进展`

### C. 开源与工具链 (GitHub / Hugging Face)
- **目标**：Trending 项目、Agent 框架 (Deer-Flow, Open SWE)、底层工具 (uv, Ruff)。
- **采集点**：
  - GitHub Trending (Daily/Weekly)
  - Hugging Face Daily Papers
- **查询词**：`GitHub trending AI agents`, `uv Python manager news`

### D. 安全与合规 (Security / Governance)
- **目标**：包投毒事件、监管诉讼、AI 伦理争议。
- **采集点**：
  - GitHub Issues (针对主流 AI 包如 LiteLLM)
  - The Verge AI Channel
- **查询词**：`LiteLLM compromised`, `AI supply chain attack`, `Anthropic lawsuit`

### E. 垂直领域研究 (Benchmarking / Reasoning)
- **目标**：形式化证明 (Lean4)、数学竞赛表现、复杂任务执行基准。
- **采集点**：
  - Arxiv AI Section
  - Epoch AI
- **查询词**：`Lean4 AI reasoning`, `frontier math open problem solved AI`

## 2. 筛选与全景呈现规则

- **补位逻辑**：若初始搜索结果不足 10 条高质量资讯，必须按上述 A -> E 的优先级进行二次精准搜索，补齐至 **10-12 条**。
- **来源分层**：
  - **一手官方 (Primary)**：官方博客、Changelog、Release 页面。
  - **一手项目 (Project)**：GitHub Repo、论文原文。
  - **媒体线索 (Secondary)**：36Kr、The Verge 等，需在摘要中注明。
- **背景还原**：摘要部分必须包含“前因后果”和“技术背景”的简述。
- **关联反馈**：优先保留命中 `dept-profile.yaml` 中高权重话题或今日群聊热点的条目。

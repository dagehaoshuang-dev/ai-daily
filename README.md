# AI Daily Skill

一个用于生成 AI 资讯日报的 Skill 包。

它的核心目标是：

- 根据用户画像生成个性化 AI 日报
- 使用结构化 JSON 作为中间层
- 通过模板化渲染稳定输出 HTML 页面
- 启动本地反馈服务，采集阅读行为
- 支持本机访问和局域网访问

## 目录结构

```text
.
├── SKILL.md
├── README.md
├── reference/
│   ├── daily_example.html
│   ├── daily_payload_example.json
│   ├── feedback_schema.json
│   └── profile_template.yaml
└── scripts/
    ├── feedback_server.py
    ├── open_daily.py
    └── render_daily.py
```

## 工作流

当前采用方案二：

1. AI 先生成结构化日报数据：`output/daily/{date}.json`
2. 调用渲染脚本输出 HTML：`output/daily/{date}.html`
3. 启动反馈服务提供页面和 `/api/feedback`
4. 打开页面进行查看

## 快速开始

### 1. 准备配置

首次使用时，需要准备：

- `config/profile.yaml`

可以参考：

- [reference/profile_template.yaml](/Users/user/Documents/project/ai-daily/reference/profile_template.yaml)

### 2. 准备日报 JSON

可以让 AI 生成：

- `output/daily/{date}.json`

结构参考：

- [reference/daily_payload_example.json](/Users/user/Documents/project/ai-daily/reference/daily_payload_example.json)

### 3. 渲染 HTML

```bash
python3 scripts/render_daily.py output/daily/2026-03-23.json
```

默认会输出：

- `output/daily/2026-03-23.html`

### 4. 打开页面

优先自动选择：

```bash
python3 scripts/open_daily.py 2026-03-23
```

只打开本地文件：

```bash
python3 scripts/open_daily.py 2026-03-23 --mode file
```

只打开 HTTP 地址：

```bash
python3 scripts/open_daily.py 2026-03-23 --mode http
```

### 5. 启动反馈服务

```bash
python3 scripts/feedback_server.py
```

服务启动后会打印：

- 本机访问地址
- 局域网访问地址
- 反馈写入目录

## 脚本说明

### `scripts/render_daily.py`

把日报 JSON 渲染成 HTML。

示例：

```bash
python3 scripts/render_daily.py output/daily/2026-03-23.json
```

### `scripts/open_daily.py`

打开已生成的日报页面。

行为：

- `auto`：优先 HTTP，否则回退到本地文件
- `http`：只输出或打开 HTTP 地址
- `file`：只输出或打开本地文件

示例：

```bash
python3 scripts/open_daily.py 2026-03-23 --print-only --mode auto
```

### `scripts/feedback_server.py`

启动静态服务并接收反馈。

特性：

- 服务 `output/` 目录
- 接收 `POST /api/feedback`
- 写入 `data/feedback/{date}.json`
- 支持端口冲突自动顺延
- 支持局域网访问
- 超时自动退出

## 配置说明

`config/profile.yaml` 中与服务相关的配置：

```yaml
server:
  host: "0.0.0.0"
  timeout_hours: 2
  port: 17890
```

说明：

- `127.0.0.1`：仅本机访问
- `0.0.0.0`：允许局域网内其他设备访问

## 反馈数据

反馈写入目录：

- `data/feedback/`

结构参考：

- [reference/feedback_schema.json](/Users/user/Documents/project/ai-daily/reference/feedback_schema.json)

页面离开时会提交一份完整的 session summary，而不是中途持续落盘事件批次。

## 局域网访问

当服务监听在 `0.0.0.0` 时，局域网其他设备可通过下面的形式访问：

```text
http://<你的局域网IP>:17890/daily/2026-03-23.html
```

如果本机可以访问、其他设备不行，优先检查：

- 访问设备是否启用了代理
- 是否连接在同一个局域网
- 路由器是否开启了客户端隔离
- 访问设备是否走了 VPN

## 常见问题

### 1. 页面没有自动打开

先检查：

```bash
python3 scripts/open_daily.py 2026-03-23 --print-only --mode auto
```

如果返回的是 `file://`，说明反馈服务还没成功启动。

### 2. 服务启动失败，提示端口不可用

如果错误信息提到：

- 当前环境不允许监听本地端口

那么通常不是端口被占用，而是运行环境、沙箱或系统权限限制。

### 3. 局域网地址打不开

如果浏览器里出现代理软件的错误页，比如 Privoxy、Clash、Surge 之类，说明请求没有直接到达当前服务，而是被访问端设备的代理接管了。

## 参考文件

- [SKILL.md](/Users/user/Documents/project/ai-daily/SKILL.md)
- [reference/daily_example.html](/Users/user/Documents/project/ai-daily/reference/daily_example.html)
- [reference/daily_payload_example.json](/Users/user/Documents/project/ai-daily/reference/daily_payload_example.json)
- [reference/profile_template.yaml](/Users/user/Documents/project/ai-daily/reference/profile_template.yaml)
- [reference/feedback_schema.json](/Users/user/Documents/project/ai-daily/reference/feedback_schema.json)

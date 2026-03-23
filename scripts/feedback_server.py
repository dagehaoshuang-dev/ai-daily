#!/usr/bin/env python3
"""
AI 日报反馈收集服务
- 静态文件服务：serve output/ 目录
- 反馈接收：POST /api/feedback → 写入 data/feedback/{date}.json
- 自动超时退出（默认 2 小时）
- 端口冲突自动 +1（默认 17890 起）
"""
import http.server
import json
import os
import sys
import socket
import time
import threading
from pathlib import Path
from functools import partial

DEFAULT_PORT = 17890
DEFAULT_TIMEOUT_HOURS = 2
DEFAULT_HOST = "0.0.0.0"


def resolve_root_dir():
    """优先从环境变量/工作目录推断 Skill 根目录，避免依赖固定层级。"""
    env_root = os.environ.get("AI_DAILY_ROOT")
    candidates = []
    if env_root:
        candidates.append(Path(env_root).expanduser())

    cwd = Path.cwd().resolve()
    candidates.extend([cwd, *cwd.parents])

    script_dir = Path(__file__).resolve().parent
    candidates.extend([script_dir, *script_dir.parents])

    seen = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if (
            (candidate / "SKILL.md").exists()
            and (candidate / "reference" / "daily_example.html").exists()
            and (candidate / "scripts" / "feedback_server.py").exists()
        ):
            return candidate

    return script_dir.parent


ROOT_DIR = resolve_root_dir()
OUTPUT_DIR = ROOT_DIR / "output"
FEEDBACK_DIR = ROOT_DIR / "data" / "feedback"
PORT_FILE = ROOT_DIR / "data" / ".server_port"


def normalize_feedback_payload(body):
    """仅落盘完整 session 结构；兼容旧版事件批量上报但不写入正式反馈文件。"""
    if not isinstance(body, dict):
        return None, "invalid"

    if "session" in body and "explicit_feedback" in body and "implicit_feedback" in body:
        normalized = dict(body)
        normalized.setdefault("date", time.strftime("%Y-%m-%d"))
        return normalized, "summary"

    if "events" in body:
        return None, "event_batch"

    return None, "invalid"


def get_local_ip_addresses():
    """返回可用于局域网访问的本机 IPv4 地址。"""
    ips = set()
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, family=socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127."):
                ips.add(ip)
    except socket.gaierror:
        pass

    # 通过 UDP 套接字获取默认出口地址，通常更接近实际可访问网卡
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            if ip and not ip.startswith("127."):
                ips.add(ip)
    except OSError:
        pass

    return sorted(ips)


class FeedbackHandler(http.server.SimpleHTTPRequestHandler):
    """处理静态文件 + 反馈 API"""

    def __init__(self, *args, directory=None, **kwargs):
        super().__init__(*args, directory=directory, **kwargs)

    def do_POST(self):
        if self.path == "/api/feedback":
            self._handle_feedback()
        else:
            self.send_error(404)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    def _handle_feedback(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length else {}
        normalized, payload_type = normalize_feedback_payload(body)

        if payload_type == "event_batch":
            self.send_response(202)
            self.send_header("Content-Type", "application/json")
            self._cors_headers()
            self.end_headers()
            self.wfile.write(b'{"ok":true,"accepted":false,"reason":"event_batch_ignored"}')
            return

        if payload_type != "summary":
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self._cors_headers()
            self.end_headers()
            self.wfile.write(b'{"ok":false,"error":"invalid_feedback_payload"}')
            return

        date = normalized.get("date", time.strftime("%Y-%m-%d"))
        filepath = FEEDBACK_DIR / f"{date}.json"

        FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)

        # 追加合并
        existing = {"sessions": []}
        if filepath.exists():
            try:
                existing = json.loads(filepath.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, IOError):
                pass

        existing["sessions"].append(normalized)
        filepath.write_text(
            json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self._cors_headers()
        self.end_headers()
        self.wfile.write(b'{"ok":true}')

    def _cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def log_message(self, format, *args):
        pass  # 静默


def find_port(base, host, max_try=10):
    """从 base 开始找一个可绑定到 host 的可用端口。"""
    last_error = None
    for i in range(max_try):
        port = base + i
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind((host, port))
                return port, None
            except OSError as exc:
                last_error = exc
    return None, last_error


def load_server_config():
    """从 profile.yaml 读取 server 配置"""
    config_path = ROOT_DIR / "config" / "profile.yaml"
    if config_path.exists():
        try:
            import yaml

            with open(config_path, encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
            return cfg.get("server", {})
        except ImportError:
            # 没有 pyyaml，用简单解析
            text = config_path.read_text(encoding="utf-8")
            cfg = {}
            for line in text.splitlines():
                line = line.strip()
                if line.startswith("timeout_hours:"):
                    try:
                        cfg["timeout_hours"] = float(line.split(":")[1].strip())
                    except ValueError:
                        pass
                elif line.startswith("host:"):
                    cfg["host"] = line.split(":", 1)[1].strip().strip("'\"")
                elif line.startswith("port:"):
                    try:
                        cfg["port"] = int(line.split(":")[1].strip())
                    except ValueError:
                        pass
            return cfg
    return {}


def main():
    cfg = load_server_config()
    bind_host = cfg.get("host", DEFAULT_HOST)
    port_base = cfg.get("port", DEFAULT_PORT)
    timeout_hours = cfg.get("timeout_hours", DEFAULT_TIMEOUT_HOURS)

    port, port_error = find_port(port_base, bind_host)
    if not port:
        if isinstance(port_error, PermissionError):
            print(
                "ERROR: 当前环境不允许监听本地端口，反馈服务未启动。",
                file=sys.stderr,
            )
            print(
                f"       尝试绑定地址 {bind_host}，端口范围 {port_base}-{port_base + 9} 时被权限策略阻止。",
                file=sys.stderr,
            )
            print(
                "       这通常不是端口占用，而是沙箱、系统策略或权限限制导致。",
                file=sys.stderr,
            )
        else:
            print(
                f"ERROR: 地址 {bind_host} 的端口 {port_base}-{port_base + 9} 全部不可用。",
                file=sys.stderr,
            )
            if port_error is not None:
                print(f"       最后一次错误: {port_error}", file=sys.stderr)
        sys.exit(1)

    # 写入端口文件
    PORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    PORT_FILE.write_text(str(port))

    # 超时自动退出
    def auto_exit():
        print(f"\n⏰ 已运行 {timeout_hours} 小时，自动停止。")
        PORT_FILE.unlink(missing_ok=True)
        os._exit(0)

    threading.Timer(timeout_hours * 3600, auto_exit).start()

    # 启动服务
    handler = partial(FeedbackHandler, directory=str(OUTPUT_DIR))
    server = http.server.HTTPServer((bind_host, port), handler)

    print("✅ AI 日报服务已启动")
    print(f"   监听地址: {bind_host}:{port}")
    print(f"   本机访问: http://localhost:{port}")
    if bind_host in {"0.0.0.0", ""}:
        lan_ips = get_local_ip_addresses()
        if lan_ips:
            print("   局域网访问:")
            for ip in lan_ips:
                print(f"   - http://{ip}:{port}")
    print(f"   静态目录: {OUTPUT_DIR}")
    print(f"   反馈写入: {FEEDBACK_DIR}")
    print(f"   {timeout_hours} 小时后自动停止")
    print(f"   按 Ctrl+C 手动停止")
    sys.stdout.flush()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 手动停止服务")
        PORT_FILE.unlink(missing_ok=True)


if __name__ == "__main__":
    main()

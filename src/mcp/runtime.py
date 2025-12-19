from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import time
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import IO

from ..app_context import AppContext
from ..config import BASE_DIR, LOG_DIR
from .helpers import safe_int


@dataclass
class ProcInfo:
    pid: int | None
    running: bool
    url: str | None = None
    log_path: str | None = None


class McpRuntime:
    def __init__(self, ctx: AppContext) -> None:
        self._ctx = ctx
        self._mcp_proc: subprocess.Popen | None = None
        self._web_proc: subprocess.Popen | None = None
        self._mcp_listen_pid: int | None = None
        self._web_listen_pid: int | None = None
        self._mcp_log_fp: IO[bytes] | None = None
        self._web_log_fp: IO[bytes] | None = None
        self._mcp_log: Path = LOG_DIR / "mcp_sse.log"
        self._web_log: Path = LOG_DIR / "mcp_web.log"

        self._last_mcp_host: str = self._ctx.settings.get("mcp_host", "127.0.0.1")
        try:
            self._last_mcp_port = int(self._ctx.settings.get("mcp_port", "8000"))
        except Exception:
            self._last_mcp_port = 8000
        self._last_web_host: str = self._ctx.settings.get("mcp_web_host", "127.0.0.1")
        try:
            self._last_web_port = int(self._ctx.settings.get("mcp_web_port", "7860"))
        except Exception:
            self._last_web_port = 7860

    def _find_local_venv_python(self) -> str | None:
        candidates = [
            BASE_DIR / ".venv" / "Scripts" / "python.exe",
            BASE_DIR / ".venv" / "bin" / "python",
        ]
        for path in candidates:
            if path.exists():
                return str(path)
        return None

    def _python_can_import(self, python_exe: str, expr: str) -> bool:
        check = subprocess.run(
            [python_exe, "-c", expr],
            cwd=str(BASE_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return check.returncode == 0

    def _assert_port_free(self, host: str, port: int) -> None:
        last_exc: OSError | None = None
        for family, socktype, proto, _canon, sockaddr in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM):
            try:
                with socket.socket(family, socktype, proto) as sock:
                    sock.bind(sockaddr)
                    return
            except OSError as exc:
                last_exc = exc
        if last_exc is not None:
            raise RuntimeError(f"端口占用或无法绑定：{host}:{port}（{last_exc}）") from last_exc
        raise RuntimeError(f"端口占用或无法绑定：{host}:{port}")

    def _find_listening_pid(self, port: int) -> int | None:
        if os.name != "nt":
            return None
        try:
            proc = subprocess.run(
                ["netstat", "-ano"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
        except Exception:
            return None
        needle = f":{port}"
        for line in (proc.stdout or "").splitlines():
            parts = line.strip().split()
            if len(parts) < 5:
                continue
            if parts[0].upper() != "TCP":
                continue
            local = parts[1]
            state = parts[3].upper()
            if state != "LISTENING":
                continue
            if not local.endswith(needle):
                continue
            with suppress(Exception):
                return int(parts[4])
        return None

    def _wait_listening_pid(self, port: int, *, timeout_s: float = 2.0) -> int | None:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            pid = self._find_listening_pid(port)
            if pid is not None:
                return pid
            time.sleep(0.05)
        return self._find_listening_pid(port)

    def mcp_info(self) -> ProcInfo:
        running = self._mcp_proc is not None and self._mcp_proc.poll() is None
        pid = self._mcp_proc.pid if running and self._mcp_proc else None
        host = self._last_mcp_host
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        return ProcInfo(
            pid=pid,
            running=running,
            url=f"http://{host}:{self._last_mcp_port}/sse" if running else None,
            log_path=str(self._mcp_log),
        )

    def web_info(self) -> ProcInfo:
        running = self._web_proc is not None and self._web_proc.poll() is None
        pid = self._web_proc.pid if running and self._web_proc else None
        host = self._last_web_host
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        return ProcInfo(
            pid=pid,
            running=running,
            url=f"http://{host}:{self._last_web_port}" if running else None,
            log_path=str(self._web_log),
        )

    def start_mcp_sse(self, *, host: str, port: int, allow_write: bool, max_bytes: int) -> None:
        if self._mcp_proc and self._mcp_proc.poll() is None:
            return
        host = (host or "").strip() or "127.0.0.1"
        if host.startswith("[") and host.endswith("]"):
            host = host[1:-1].strip() or "127.0.0.1"
        if host == "localhost":
            host = "127.0.0.1"
        if host not in {"127.0.0.1", "::1"}:
            raise ValueError("MCP is local-only; host must be 127.0.0.1/localhost/::1")
        self._last_mcp_host = host
        self._last_mcp_port = port
        self._assert_port_free(host, port)

        LOG_DIR.mkdir(parents=True, exist_ok=True)
        self._close_log(self._mcp_log_fp)
        self._mcp_log_fp = self._mcp_log.open("ab")
        env = os.environ.copy()
        env["CERT_MCP_TRANSPORT"] = "sse"
        env["CERT_MCP_HOST"] = host
        env["CERT_MCP_PORT"] = str(port)
        env["CERT_MCP_ALLOW_WRITE"] = "1" if allow_write else "0"
        env["CERT_MCP_MAX_BYTES"] = str(max_bytes)
        cmd: list[str]
        python_exe = sys.executable
        if self._python_can_import(python_exe, "import mcp"):
            cmd = [python_exe, "-m", "src.mcp.server"]
        else:
            venv_python = self._find_local_venv_python()
            if venv_python and self._python_can_import(venv_python, "import mcp"):
                cmd = [venv_python, "-m", "src.mcp.server"]
            else:
                if shutil.which("uv") is None:
                    raise RuntimeError("mcp is not installed; run: uv sync")
                cmd = ["uv", "run", "python", "-m", "src.mcp.server"]
        self._mcp_proc = subprocess.Popen(
            cmd,
            cwd=str(BASE_DIR),
            env=env,
            stdout=self._mcp_log_fp,
            stderr=self._mcp_log_fp,
        )
        self._mcp_listen_pid = self._wait_listening_pid(self._last_mcp_port)

    def stop_mcp(self) -> None:
        self._terminate(self._mcp_proc)
        if self._mcp_listen_pid is not None:
            current = self._find_listening_pid(self._last_mcp_port)
            if current == self._mcp_listen_pid:
                with suppress(Exception):
                    subprocess.run(
                        ["taskkill", "/PID", str(current), "/T", "/F"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=False,
                    )
        self._mcp_listen_pid = None
        self._mcp_proc = None
        self._close_log(self._mcp_log_fp)
        self._mcp_log_fp = None

    def start_web(self, *, host: str, port: int) -> None:
        if self._web_proc and self._web_proc.poll() is None:
            return
        host = (host or "").strip() or "127.0.0.1"
        if host.startswith("[") and host.endswith("]"):
            host = host[1:-1].strip() or "127.0.0.1"
        if host == "localhost":
            host = "127.0.0.1"
        if host not in {"127.0.0.1", "::1"}:
            raise ValueError("MCP Web is local-only; host must be 127.0.0.1/localhost/::1")
        self._last_web_host = host
        self._last_web_port = safe_int(str(port), 7860, min_value=1, max_value=65535)
        self._assert_port_free(host, self._last_web_port)

        LOG_DIR.mkdir(parents=True, exist_ok=True)
        self._close_log(self._web_log_fp)
        self._web_log_fp = self._web_log.open("ab")
        cmd: list[str]
        python_exe = sys.executable
        check_expr = "import gradio; assert hasattr(gradio, 'Blocks')"
        if self._python_can_import(python_exe, check_expr):
            cmd = [python_exe, "-m", "src.mcp.web"]
        else:
            venv_python = self._find_local_venv_python()
            if venv_python and self._python_can_import(venv_python, check_expr):
                cmd = [venv_python, "-m", "src.mcp.web"]
            else:
                if shutil.which("uv") is None:
                    raise RuntimeError("gradio is not installed; run: uv sync --group mcp-web")
                cmd = ["uv", "run", "python", "-m", "src.mcp.web"]
        env = os.environ.copy()
        env["CERT_MCP_WEB_HOST"] = host
        env["CERT_MCP_WEB_PORT"] = str(self._last_web_port)
        env["CERT_MCP_WEB_INBROWSER"] = "0"
        self._web_proc = subprocess.Popen(
            cmd,
            cwd=str(BASE_DIR),
            env=env,
            stdout=self._web_log_fp,
            stderr=self._web_log_fp,
        )
        self._web_listen_pid = self._wait_listening_pid(self._last_web_port)

    def stop_web(self) -> None:
        self._terminate(self._web_proc)
        if self._web_listen_pid is not None:
            current = self._find_listening_pid(self._last_web_port)
            if current == self._web_listen_pid:
                with suppress(Exception):
                    subprocess.run(
                        ["taskkill", "/PID", str(current), "/T", "/F"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=False,
                    )
        self._web_listen_pid = None
        self._web_proc = None
        self._close_log(self._web_log_fp)
        self._web_log_fp = None

    def shutdown(self) -> None:
        self.stop_web()
        self.stop_mcp()

    def _terminate(self, proc: subprocess.Popen | None) -> None:
        if not proc or proc.poll() is not None:
            return
        with suppress(Exception):
            proc.terminate()
        with suppress(Exception):
            proc.wait(timeout=2)
        if proc.poll() is None:
            with suppress(Exception):
                proc.kill()
        if proc.poll() is None and os.name == "nt":
            with suppress(Exception):
                subprocess.run(
                    ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )

    def _close_log(self, fp: IO[bytes] | None) -> None:
        if fp is None:
            return
        with suppress(Exception):
            fp.close()


_RUNTIME: McpRuntime | None = None


def get_mcp_runtime(ctx: AppContext | None = None) -> McpRuntime:
    global _RUNTIME
    if _RUNTIME is None:
        if ctx is None:
            raise RuntimeError("McpRuntime is not initialized")
        _RUNTIME = McpRuntime(ctx)
    return _RUNTIME

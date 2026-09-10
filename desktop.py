"""Windows desktop entry point for the SendePro PyInstaller build."""
from __future__ import annotations

import os
import socket
import sys
import threading
import time
import traceback
from pathlib import Path

import uvicorn
import webview


def application_directory() -> Path:
    return Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent


APP_DIR = application_directory()
os.chdir(APP_DIR)
os.environ["SENDEPRO_DESKTOP"] = "1"
os.environ.setdefault("CORS_ORIGINS", "http://localhost:3001,http://127.0.0.1:3001")

from backend.main import app  # noqa: E402


def port_is_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex(("127.0.0.1", port)) == 0


def run_server(server: uvicorn.Server) -> None:
    server.run()


def main() -> None:
    if port_is_open(3001):
        raise RuntimeError("Port 3001 is already in use. Close the existing SendePro/Vite window and try again.")
    config = uvicorn.Config(app, host="127.0.0.1", port=3001, log_level="info", access_log=False)
    server = uvicorn.Server(config)
    thread = threading.Thread(target=run_server, args=(server,), daemon=True)
    thread.start()
    deadline = time.time() + 20
    while time.time() < deadline and not port_is_open(3001):
        time.sleep(0.1)
    if not port_is_open(3001):
        raise RuntimeError("SendePro could not start its local server.")
    webview.create_window("SendePro", "http://127.0.0.1:3001", width=1440, height=900, min_size=(1050, 700))
    try:
        webview.start()
    finally:
        server.should_exit = True


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        error_file = APP_DIR / "sendepro-desktop-error.log"
        error_file.write_text(traceback.format_exc(), encoding="utf-8")
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, f"{exc}\n\nDetails: {error_file}", "SendePro could not start", 0x10)
        except Exception:
            raise

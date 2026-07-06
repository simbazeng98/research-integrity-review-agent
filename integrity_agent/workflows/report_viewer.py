from __future__ import annotations

import functools
import http.server
from dataclasses import dataclass
from pathlib import Path
import socketserver
import threading
import webbrowser

from integrity_agent.core.i18n import I18nManager


class QuietHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return


class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


@dataclass
class ReportViewer:
    server: socketserver.TCPServer
    thread: threading.Thread
    url: str
    port: int

    def shutdown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


def _choose_report_name(directory_path: Path, report_name: str | None) -> str:
    if report_name:
        return report_name
    for candidate in (
        "review_report.html",
        "review_package_dashboard.html",
        "raw_pv_dashboard.html",
        "pv_domain_dashboard.html",
    ):
        if (directory_path / candidate).exists():
            return candidate
    html_files = sorted(directory_path.glob("*.html"))
    return html_files[0].name if html_files else "review_report.html"


def start_server_and_open_browser(
    directory_path: Path | str,
    port: int = 8080,
    report_name: str | None = None,
    locale: str = "en",
) -> ReportViewer:
    directory = Path(directory_path).expanduser().resolve()
    if not directory.exists():
        raise FileNotFoundError(f"Report directory does not exist: {directory}")

    selected_report = _choose_report_name(directory, report_name)
    handler = functools.partial(QuietHTTPRequestHandler, directory=str(directory))

    selected_port = port
    while True:
        try:
            server = ReusableTCPServer(("127.0.0.1", selected_port), handler)
            break
        except OSError:
            if selected_port == 0:
                raise
            selected_port += 1

    actual_port = int(server.server_address[1])
    url = f"http://localhost:{actual_port}/{selected_report}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    manager = I18nManager()
    manager.set_locale(locale if locale in {"en", "zh"} else "en")
    print(f"{manager.translate('viewer.serving')}: {url}")
    webbrowser.open(url)
    return ReportViewer(server=server, thread=thread, url=url, port=actual_port)

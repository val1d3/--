"""Вспомогательные средства тестов: фальшивый реестр npm."""

import json
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HTTP_OK = 200
HTTP_NOT_FOUND = 404
LOCALHOST = "127.0.0.1"
POLL_INTERVAL = 0.01
HANDLER_METHOD = "do_GET"


def ok(data):
    """Готовый ответ 200 с JSON-телом."""
    return HTTP_OK, json.dumps(data).encode("utf-8")


class TempDirTestCase(unittest.TestCase):
    """Тест с временной папкой, создаваемой при первом обращении."""

    _tmp = None

    @property
    def tmp(self):
        """Путь к временной папке; удаляется после завершения теста."""
        if self._tmp is None:
            holder = tempfile.TemporaryDirectory()
            self.addCleanup(holder.cleanup)
            self._tmp = Path(holder.name)
        return self._tmp


class QuietServer(ThreadingHTTPServer):
    """HTTP-сервер, не печатающий ошибки оборванных соединений."""

    daemon_threads = True

    def handle_error(self, request, client_address):
        """Игнорирует ошибки (клиент мог оборвать соединение по таймауту)."""


class Handler(BaseHTTPRequestHandler):
    """Отвечает заранее заданными ответами по пути запроса."""

    def handle_get(self):
        """Обрабатывает GET: ищет путь в таблице ответов."""
        registry = self.server.registry
        registry.requests.append(self.path)
        time.sleep(registry.delay)
        status, body = registry.responses.get(
            self.path, (HTTP_NOT_FOUND, b"{}")
        )
        self.send_response(status)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        """Отключает журнал запросов в консоли."""


setattr(Handler, HANDLER_METHOD, Handler.handle_get)


class FakeRegistry:
    """Локальный HTTP-сервер, имитирующий реестр npm (контекст-менеджер)."""

    def __init__(self, responses, delay=0.0):
        """responses: путь -> (код ответа, тело в байтах)."""
        self.responses = responses
        self.delay = delay
        self.requests = []
        self.server = None
        self.thread = None

    def __enter__(self):
        """Запускает сервер на свободном порту."""
        self.server = QuietServer((LOCALHOST, 0), Handler)
        self.server.registry = self
        self.thread = threading.Thread(
            target=self.server.serve_forever,
            kwargs={"poll_interval": POLL_INTERVAL},
            daemon=True,
        )
        self.thread.start()
        return self

    def __exit__(self, *exc_info):
        """Останавливает сервер."""
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    @property
    def url(self):
        """Адрес сервера, например http://127.0.0.1:50321."""
        host, port = self.server.server_address
        return f"http://{host}:{port}"

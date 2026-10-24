"""Тесты получения прямых зависимостей из реестра npm."""

import unittest
import urllib.error
from unittest import mock

from npm_repo import RepositoryError, build_url, get_direct_dependencies
from support import FakeRegistry, ok

SHORT_TIMEOUT = 0.2
SLOW_DELAY = 1.0
URLOPEN = "npm_repo.urllib.request.urlopen"


class BuildUrlTests(unittest.TestCase):
    """Построение URL запроса."""

    def test_plain_name(self):
        """Обычное имя пакета."""
        url = build_url("https://registry.npmjs.org", "express", "4.18.2")
        self.assertEqual(url, "https://registry.npmjs.org/express/4.18.2")

    def test_trailing_slash(self):
        """Завершающий слэш в адресе репозитория не удваивается."""
        url = build_url("https://registry.npmjs.org/", "express", "4.18.2")
        self.assertEqual(url, "https://registry.npmjs.org/express/4.18.2")

    def test_scoped_name(self):
        """В имени вида @scope/name слэш кодируется."""
        url = build_url("https://r.org", "@babel/core", "7.0.0")
        self.assertEqual(url, "https://r.org/@babel%2Fcore/7.0.0")


class DependenciesTests(unittest.TestCase):
    """Разбор прямых зависимостей из ответа реестра."""

    def fetch(self, responses, name="pkg", version="1.0.0", **kwargs):
        """Запрашивает зависимости у фальшивого реестра."""
        with FakeRegistry(responses, **kwargs.pop("server", {})) as reg:
            return get_direct_dependencies(reg.url, name, version, **kwargs)

    def assert_error(self, pattern, responses, **kwargs):
        """Проверяет, что запрос завершается RepositoryError."""
        with self.assertRaisesRegex(RepositoryError, pattern):
            self.fetch(responses, **kwargs)

    def test_returns_sorted_dependencies(self):
        """Возвращаются прямые зависимости, отсортированные по имени."""
        body = ok({"dependencies": {"qs": "6.11.0", "etag": "~1.8.1"}})
        result = self.fetch({"/pkg/1.0.0": body})
        self.assertEqual(result, {"etag": "~1.8.1", "qs": "6.11.0"})
        self.assertEqual(list(result), ["etag", "qs"])

    def test_no_dependencies_key(self):
        """Нет поля dependencies - пустой результат."""
        self.assertEqual(self.fetch({"/pkg/1.0.0": ok({})}), {})

    def test_dev_dependencies_ignored(self):
        """devDependencies не считаются прямыми зависимостями."""
        body = ok({"devDependencies": {"mocha": "1.0.0"}})
        self.assertEqual(self.fetch({"/pkg/1.0.0": body}), {})

    def test_scoped_package_request(self):
        """Для @scope/name запрашивается закодированный путь."""
        responses = {"/@a%2Fb/2.0.0": ok({"dependencies": {"x": "1"}})}
        result = self.fetch(responses, name="@a/b", version="2.0.0")
        self.assertEqual(result, {"x": "1"})

    def test_not_found(self):
        """Пакета или версии нет в репозитории."""
        self.assert_error("не найдены", {})

    def test_server_error(self):
        """Ошибка сервера (HTTP 500)."""
        self.assert_error("HTTP 500", {"/pkg/1.0.0": (500, b"oops")})

    def test_invalid_json(self):
        """Тело ответа - не JSON."""
        self.assert_error("JSON", {"/pkg/1.0.0": (200, b"<html>")})

    def test_json_not_object(self):
        """JSON - не объект."""
        self.assert_error("объект", {"/pkg/1.0.0": ok([1, 2])})

    def test_dependencies_not_object(self):
        """Поле dependencies - не объект."""
        self.assert_error("dependencies", {"/pkg/1.0.0": ok(
            {"dependencies": ["a", "b"]}
        )})

    def test_dependency_spec_not_string(self):
        """Диапазон версии - не строка."""
        self.assert_error("dependencies", {"/pkg/1.0.0": ok(
            {"dependencies": {"a": 1}}
        )})

    def test_timeout(self):
        """Репозиторий отвечает слишком медленно."""
        self.assert_error(
            "время ожидания",
            {"/pkg/1.0.0": ok({})},
            server={"delay": SLOW_DELAY},
            timeout=SHORT_TIMEOUT,
        )

    def test_invalid_dependency_entries(self):
        """Null, пустой диапазон и недопустимое имя не теряются молча."""
        for deps in (None, {"x": ""}, {"bad name": "1.0.0"}):
            with self.subTest(deps=deps):
                self.assert_error("dependencies", {"/pkg/1.0.0": ok(
                    {"dependencies": deps}
                )})


class NetworkErrorTests(unittest.TestCase):
    """Сетевые сбои имитируются подменой urlopen (не зависят от ОС)."""

    def assert_network_error(self, pattern, error):
        """Проверяет сообщение об ошибке при сбое urlopen."""
        with mock.patch(URLOPEN, side_effect=error):
            with self.assertRaisesRegex(RepositoryError, pattern):
                get_direct_dependencies("https://r.org", "pkg", "1.0.0")

    def test_connection_refused(self):
        """Репозиторий отказал в соединении."""
        reason = ConnectionRefusedError("refused")
        self.assert_network_error(
            "подключиться", urllib.error.URLError(reason)
        )

    def test_dns_failure(self):
        """Имя сервера не удалось определить."""
        reason = OSError("Name or service not known")
        self.assert_network_error(
            "подключиться", urllib.error.URLError(reason)
        )

    def test_connect_timeout(self):
        """Тайм-аут при установке соединения."""
        reason = TimeoutError("timed out")
        self.assert_network_error(
            "время ожидания", urllib.error.URLError(reason)
        )

    def test_connection_reset(self):
        """Соединение оборвалось во время чтения ответа."""
        self.assert_network_error(
            "подключиться", ConnectionResetError("reset")
        )


if __name__ == "__main__":
    unittest.main()

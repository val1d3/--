"""Тесты командной строки для этапов 1, 2 и 3."""

import contextlib
import io
import unittest

from main import EXIT_ERROR, EXIT_OK, main
from support import FakeRegistry, TempDirTestCase, ok

DEPS = {"dependencies": {"qs": "6.11.0", "etag": "~1.8.1"}}


class MainTests(TempDirTestCase):
    """Поведение CLI при разных конфигурациях и ответах реестра."""

    def write_config(self, repository, test_mode="false", package="pkg"):
        """Создаёт YAML-конфигурацию и возвращает путь к ней."""
        lines = [
            f"package: {package}",
            f"repository: {repository}",
            f"test_mode: {test_mode}",
            "version: 1.0.0",
            f"output: {self.tmp / 'g.png'}",
        ]
        path = self.tmp / "config.yaml"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return str(path)

    def run_main(self, path, stage="2"):
        """Запускает main, возвращает код, stdout и stderr."""
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out):
            with contextlib.redirect_stderr(err):
                code = main(["--config", path, "--stage", stage])
        return code, out.getvalue(), err.getvalue()

    def test_prints_direct_dependencies(self):
        """Выводятся прямые зависимости в алфавитном порядке."""
        with FakeRegistry({"/pkg/1.0.0": ok(DEPS)}) as reg:
            code, out, _ = self.run_main(self.write_config(reg.url))
        self.assertEqual(code, EXIT_OK)
        self.assertIn("Прямые зависимости pkg@1.0.0 (2):", out)
        self.assertLess(out.index("etag: ~1.8.1"), out.index("qs: 6.11.0"))

    def test_no_dependencies(self):
        """У пакета нет зависимостей."""
        with FakeRegistry({"/pkg/1.0.0": ok({})}) as reg:
            code, out, _ = self.run_main(self.write_config(reg.url))
        self.assertEqual(code, EXIT_OK)
        self.assertIn("прямых зависимостей нет", out)

    def test_package_not_found(self):
        """Пакета нет в репозитории: сообщение и код 1."""
        with FakeRegistry({}) as reg:
            code, out, err = self.run_main(self.write_config(reg.url))
        self.assertEqual(code, EXIT_ERROR)
        self.assertEqual(out, "")
        self.assertIn("Ошибка репозитория", err)

    def test_config_error(self):
        """Ошибка конфигурации: сообщение и код 1."""
        code, _, err = self.run_main(str(self.tmp / "nope.yaml"))
        self.assertEqual(code, EXIT_ERROR)
        self.assertIn("Ошибка конфигурации", err)

    def test_test_graph(self):
        """Третий этап строит граф из файла и сохраняет ребро цикла."""
        repo = self.tmp / "repo.txt"
        repo.write_text("A: B\nB: A\n", encoding="utf-8")
        path = self.write_config(repo, test_mode="true", package="A")
        code, out, err = self.run_main(path, stage="3")
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(err, "")
        self.assertIn("A -> B", out)
        self.assertIn("Цикл: B -> A", out)

    def test_stage_one(self):
        """Первый этап выводит все параметры без доступа к сети."""
        path = self.write_config("https://registry.invalid")
        code, out, err = self.run_main(path, stage="1")
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(err, "")
        for key in (
            "package", "repository", "test_mode",
            "version", "output", "filter",
        ):
            self.assertIn(key + ":", out)


if __name__ == "__main__":
    unittest.main()

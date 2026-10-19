"""Тесты загрузки и проверки конфигурации."""

import unittest

from config import ConfigError, load_config
from support import TempDirTestCase

VALID = {
    "package": "express",
    "repository": "https://registry.npmjs.org",
    "test_mode": "false",
    "version": "4.18.2",
    "output": "graph.png",
    "filter": "types",
}


class ConfigTestCase(TempDirTestCase):
    """Базовый класс: создание YAML-файлов во временной папке."""

    def write(self, **overrides):
        """Создаёт YAML-файл; значение None удаляет ключ."""
        params = {**VALID, **overrides}
        lines = [f"{k}: {v}" for k, v in params.items() if v is not None]
        path = self.tmp / "config.yaml"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return str(path)

    def make_repo(self, text="A: B\nB:\n"):
        """Создаёт файл тестового репозитория."""
        repo = self.tmp / "repo.txt"
        repo.write_text(text, encoding="utf-8")
        return str(repo)

    def assert_error(self, pattern, path):
        """Проверяет, что загрузка падает с ConfigError."""
        with self.assertRaisesRegex(ConfigError, pattern):
            load_config(path)


class ValidConfigTests(ConfigTestCase):
    """Корректные конфигурации."""

    def test_valid_config(self):
        """Корректный конфиг загружается без ошибок."""
        cfg = load_config(self.write(output=str(self.tmp / "g.png")))
        self.assertEqual(cfg.package, "express")
        self.assertEqual(cfg.version, "4.18.2")
        self.assertFalse(cfg.test_mode)
        self.assertEqual(cfg.filter, "types")

    def test_filter_is_optional(self):
        """Фильтр можно не задавать - он пустой."""
        self.assertEqual(load_config(self.write(filter=None)).filter, "")

    def test_empty_filter_value(self):
        """Пустое значение 'filter:' в YAML равно значению по умолчанию."""
        self.assertEqual(load_config(self.write(filter="")).filter, "")

    def test_scoped_package(self):
        """Имена вида @scope/name допустимы."""
        cfg = load_config(self.write(package="'@babel/core'"))
        self.assertEqual(cfg.package, "@babel/core")

    def test_legacy_uppercase_name(self):
        """Старые пакеты с заглавными буквами (JSONStream) допустимы."""
        cfg = load_config(self.write(package="JSONStream"))
        self.assertEqual(cfg.package, "JSONStream")

    def test_test_mode_valid(self):
        """Тестовый режим: имя - заглавные буквы, репозиторий - файл."""
        path = self.write(
            package="A", repository=self.make_repo(), test_mode="true"
        )
        self.assertTrue(load_config(path).test_mode)


class FileErrorTests(ConfigTestCase):
    """Ошибки чтения файла конфигурации."""

    def test_missing_file(self):
        """Отсутствующий файл конфигурации."""
        self.assert_error("не найден", str(self.tmp / "nope.yaml"))

    def test_invalid_yaml(self):
        """Синтаксическая ошибка YAML."""
        path = self.tmp / "bad.yaml"
        path.write_text("package: [unclosed\n", encoding="utf-8")
        self.assert_error("YAML", str(path))

    def test_not_a_mapping(self):
        """Корень YAML - не словарь."""
        path = self.tmp / "list.yaml"
        path.write_text("- a\n- b\n", encoding="utf-8")
        self.assert_error("ключ", str(path))

    def test_unknown_key(self):
        """Опечатка в имени параметра."""
        self.assert_error("pakage", self.write(pakage="x"))


class ParameterErrorTests(ConfigTestCase):
    """Ошибки значений отдельных параметров."""

    def test_missing_required(self):
        """Обязательный параметр не задан."""
        for key in ("package", "repository", "version", "output"):
            with self.subTest(key=key):
                self.assert_error(key, self.write(**{key: None}))

    def test_empty_package(self):
        """Пустое имя пакета."""
        self.assert_error("package", self.write(package="''"))

    def test_bad_package_name(self):
        """Недопустимые имена npm-пакетов."""
        for name in ("my pkg", "-x/y", ".hidden", "a/b"):
            with self.subTest(name=name):
                self.assert_error("имя", self.write(package=f"'{name}'"))

    def test_bad_url(self):
        """Некорректный URL репозитория."""
        for url in ("ftp://x.org", "registry.npmjs.org", "http://"):
            with self.subTest(url=url):
                self.assert_error("URL", self.write(repository=url))

    def test_bad_version(self):
        """Версия не в формате semver."""
        for ver in ("1.0", "latest", "^1.2.3", "v1.2.3", "01.2.3"):
            with self.subTest(ver=ver):
                self.assert_error("Версия", self.write(version=f"'{ver}'"))

    def test_numeric_version_must_be_string(self):
        """Версия 1.5 без кавычек читается YAML как число."""
        self.assert_error("строкой", self.write(version="1.5"))

    def test_bad_output_name(self):
        """Недопустимое имя файла изображения."""
        for out in ("graph.svg", "graph", ".png"):
            with self.subTest(out=out):
                self.assert_error("изображения", self.write(output=out))

    def test_output_dir_missing(self):
        """Папка для изображения не существует."""
        out = self.tmp / "no_dir" / "g.png"
        self.assert_error("Папка", self.write(output=str(out)))

    def test_bad_test_mode(self):
        """test_mode должен быть логическим."""
        self.assert_error("test_mode", self.write(test_mode="maybe"))


class TestModeErrorTests(ConfigTestCase):
    """Ошибки в тестовом режиме."""

    def test_bad_name(self):
        """Имя строчными буквами недопустимо."""
        path = self.write(
            package="express", repository=self.make_repo(), test_mode="true"
        )
        self.assert_error("заглавные", path)

    def test_missing_file(self):
        """Файл тестового репозитория не существует."""
        path = self.write(
            package="A", repository="nope.txt", test_mode="true"
        )
        self.assert_error("не найден", path)


if __name__ == "__main__":
    unittest.main()

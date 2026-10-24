"""Проверки диапазонов npm и приоритета версий SemVer."""

import unittest

from npm_repo import RepositoryError
from semver import select_version, version_key


class SemverTests(unittest.TestCase):
    """Границы диапазонов, нулевые версии и prerelease."""

    def test_range_selection(self):
        """Выбирается максимальная версия внутри каждого диапазона."""
        versions = [
            "0.0.3", "0.0.4", "0.2.3", "0.2.9", "0.3.0",
            "1.0.0", "1.2.3", "1.2.9", "1.3.0", "2.0.0",
        ]
        cases = {
            "^0.0.3": "0.0.3",
            "^0.2.3": "0.2.9",
            "^0.0": "0.0.4",
            "^0": "0.3.0",
            "^1.2.3": "1.3.0",
            "~1.2.3": "1.2.9",
            "~1": "1.3.0",
            "1.2.x": "1.2.9",
            "1": "1.3.0",
            "*": "2.0.0",
            "1.2.3": "1.2.3",
            ">=1 <2": "1.3.0",
            "1.0.0 - 1.2": "1.2.9",
            "1 - 1.2.3": "1.2.3",
            "<1 || >=2.0.0": "2.0.0",
            "<=1.2": "1.2.9",
            ">1": "2.0.0",
            ">= 1.2.3 < 1.3.0": "1.2.9",
            "v1.2.3": "1.2.3",
            "=1.2.3": "1.2.3",
        }
        for spec, expected in cases.items():
            with self.subTest(spec=spec):
                self.assertEqual(select_version(versions, spec), expected)

    def test_prereleases(self):
        """Prerelease разрешается только для явно указанного ядра."""
        versions = ["1.2.3-beta.2", "1.2.3-beta.10", "1.2.4-beta.1"]
        self.assertEqual(
            select_version(versions, "^1.2.3-beta.2"),
            "1.2.3-beta.10",
        )
        with self.assertRaises(RepositoryError):
            select_version(versions, "*")

    def test_semver_order(self):
        """Числовые идентификаторы сравниваются численно; build не влияет."""
        self.assertLess(version_key("1.0.0-9"), version_key("1.0.0-10"))
        self.assertLess(version_key("1.0.0-10"), version_key("1.0.0-a"))
        self.assertLess(version_key("1.0.0-a"), version_key("1.0.0"))
        self.assertEqual(version_key("1.0.0+a"), version_key("1.0.0+b"))

    def test_unsupported_or_unsatisfied(self):
        """Неизвестный синтаксис не подменяется последней версией."""
        specs = (
            "git+https://host/x",
            "file:../x",
            "^9",
            "<*",
            "npm:other@1",
            "1.x.2",
            "~01.0.0",
        )
        for spec in specs:
            with self.subTest(spec=spec):
                with self.assertRaises(RepositoryError):
                    select_version(["1.2.3"], spec)

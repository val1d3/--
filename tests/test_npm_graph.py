"""Интеграционные проверки транзитивного npm-графа через HTTP."""

import unittest

from graph import build_graph
from npm_repo import RepositoryError
from npm_source import NpmRepository
from support import FakeRegistry, ok


class NpmGraphTests(unittest.TestCase):
    """Проверяет диапазоны, версии узлов, кэш, фильтр и сетевые ошибки."""

    def test_transitive_range_cycle_and_cache(self):
        """Диапазон выбирает версию; цикл не вызывает повторный запрос."""
        responses = {
            "/root/1.0.0": ok({"dependencies": {"child": "^1.0.0"}}),
            "/child": ok({
                "versions": {
                    "1.0.0": {},
                    "1.1.0": {"dependencies": {"root": "1.0.0"}},
                    "2.0.0": {},
                },
            }),
        }
        with FakeRegistry(responses) as reg:
            graph = build_graph(NpmRepository(reg.url), "root", "1.0.0")
            self.assertEqual(reg.requests, ["/root/1.0.0", "/child"])
        self.assertEqual(
            graph.edges[("root", "1.0.0")],
            [("child", "1.1.0")],
        )
        self.assertEqual(
            graph.cycle_edges,
            [(("child", "1.1.0"), ("root", "1.0.0"))],
        )

    def test_same_package_different_versions(self):
        """Две версии одного пакета остаются разными вершинами графа."""
        responses = {
            "/a/1.0.0": ok({
                "dependencies": {"b": "1.0.0", "x": "1.0.0"},
            }),
            "/b/1.0.0": ok({"dependencies": {"x": "2.0.0"}}),
            "/x/1.0.0": ok({}),
            "/x/2.0.0": ok({}),
        }
        with FakeRegistry(responses) as reg:
            graph = build_graph(NpmRepository(reg.url), "a", "1.0.0")
        self.assertIn(("x", "1.0.0"), graph.edges)
        self.assertIn(("x", "2.0.0"), graph.edges)
        self.assertEqual(graph.cycle_edges, [])

    def test_filter_before_request(self):
        """Исключённый пакет не загружается для разрешения диапазона."""
        body = {"dependencies": {"skip": "^1.0.0"}}
        with FakeRegistry({"/a/1.0.0": ok(body)}) as reg:
            graph = build_graph(NpmRepository(reg.url), "a", "1.0.0", "skip")
            self.assertEqual(reg.requests, ["/a/1.0.0"])
        self.assertEqual(graph.edges, {("a", "1.0.0"): []})

    def test_dist_tag(self):
        """Опубликованный dist-tag разрешается в конкретную версию."""
        body = {
            "versions": {"2.0.0": {}},
            "dist-tags": {"next": "2.0.0"},
        }
        with FakeRegistry({"/a": ok(body)}) as reg:
            graph = build_graph(NpmRepository(reg.url), "a", "next")
        self.assertEqual(graph.edges, {("a", "2.0.0"): []})

    def test_invalid_registry_documents(self):
        """Повреждённые versions и dist-tags вызывают ошибку."""
        documents = [
            {},
            {"versions": []},
            {"versions": {"1.0.0": None}},
            {"versions": {}, "dist-tags": []},
            {"versions": {}, "dist-tags": {"latest": []}},
        ]
        for document in documents:
            with self.subTest(document=document):
                with FakeRegistry({"/a": ok(document)}) as reg:
                    with self.assertRaises(RepositoryError):
                        build_graph(NpmRepository(reg.url), "a", "latest")

    def test_transitive_missing_version(self):
        """Ошибка транзитивного узла не даёт вывести неполный граф."""
        body = {"dependencies": {"missing": "1.0.0"}}
        with FakeRegistry({"/a/1.0.0": ok(body)}) as reg:
            with self.assertRaisesRegex(RepositoryError, "не найдены"):
                build_graph(NpmRepository(reg.url), "a", "1.0.0")

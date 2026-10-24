"""Проверки DFS: транзитивность, циклы, фильтрация и глубокий граф."""

import unittest

from graph import build_graph
from npm_repo import RepositoryError
from support import TempDirTestCase
from test_repo import TestRepository

DEEP_SIZE = 1500


class MemorySource:
    """Граф в памяти с журналом обращений к вершинам."""

    def __init__(self, data):
        """Сохраняет таблицу зависимостей."""
        self.data = data
        self.calls = []

    def resolve(self, name, spec):
        """Версии не используются в учебном графе."""
        return name, ""

    def dependencies(self, node):
        """Регистрирует порядок раскрытия вершин."""
        self.calls.append(node[0])
        return dict.fromkeys(self.data[node[0]], "")


class GraphTests(unittest.TestCase):
    """Обход не путает повторную вершину и обратное ребро цикла."""

    def test_diamond_is_depth_first(self):
        """Общая зависимость посещается один раз, порядок именно DFS."""
        source = MemorySource({"A": "BC", "B": "D", "C": "D", "D": ""})
        graph = build_graph(source, "A", "")
        self.assertEqual(source.calls, ["A", "B", "D", "C"])
        self.assertEqual(graph.edges[("C", "")], [("D", "")])
        self.assertEqual(graph.cycle_edges, [])

    def test_cycle_and_self_loop(self):
        """Оба вида циклов сохраняют рёбра и завершают обход."""
        source = MemorySource({"A": "AB", "B": "A"})
        graph = build_graph(source, "A", "")
        self.assertEqual(source.calls, ["A", "B"])
        self.assertEqual(
            graph.cycle_edges,
            [
                (("A", ""), ("A", "")),
                (("B", ""), ("A", "")),
            ],
        )

    def test_filter_prunes_branch(self):
        """Исключённая ветвь не запрашивается и не попадает в граф."""
        source = MemorySource({"A": "BC", "B": "D", "C": "", "D": ""})
        graph = build_graph(source, "A", "", "B")
        self.assertEqual(source.calls, ["A", "C"])
        self.assertEqual(graph.edges[("A", "")], [("C", "")])

    def test_filtered_root(self):
        """Исключённый корень даёт пустой граф без запросов."""
        source = MemorySource({"A": "B"})
        self.assertEqual(build_graph(source, "A", "", "A").edges, {})
        self.assertEqual(source.calls, [])

    def test_filter_is_substring(self):
        """Фильтр совпадает с частью имени."""
        source = MemorySource({"A": ["BETA", "C"], "C": []})
        build_graph(source, "A", "", "ET")
        self.assertEqual(source.calls, ["A", "C"])

    def test_deep_graph(self):
        """Цепочка длиннее лимита рекурсии обходится явным стеком."""
        data = {str(i): [str(i + 1)] for i in range(DEEP_SIZE)}
        data[str(DEEP_SIZE)] = []
        source = MemorySource(data)
        graph = build_graph(source, "0", "")
        self.assertEqual(len(graph.edges), DEEP_SIZE + 1)


class TestRepositoryTests(TempDirTestCase):
    """Формат файла и сообщения об ошибках тестового репозитория."""

    def source(self, text):
        """Создаёт репозиторий из временного UTF-8 файла."""
        path = self.tmp / "repo.txt"
        path.write_text(text, encoding="utf-8")
        return TestRepository(path)

    def test_valid_file_and_isolated_node(self):
        """Лист остаётся в графе, недостижимая вершина не включается."""
        graph = build_graph(self.source("A: B\nB:\nZ:\n"), "A", "")
        self.assertEqual(list(graph.edges), [("A", ""), ("B", "")])
        self.assertEqual(graph.edges[("B", "")], [])

    def test_invalid_files(self):
        """Пустой файл, синтаксис, повторы и отсутствующие ссылки ошибочны."""
        values = ("", "a: B", "A B", "A:\nA:", "A: B", "A: B1")
        for text in values:
            with self.subTest(text=text):
                with self.assertRaises(RepositoryError):
                    self.source(text)

    def test_missing_root(self):
        """Корень должен присутствовать в файле."""
        with self.assertRaisesRegex(RepositoryError, "не найден"):
            build_graph(self.source("A:"), "B", "")

    def test_missing_file(self):
        """Ошибка чтения оформляется как ошибка репозитория."""
        with self.assertRaisesRegex(RepositoryError, "прочитать"):
            TestRepository(self.tmp / "missing.txt")

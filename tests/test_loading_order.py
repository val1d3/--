"""Проверки порядка загрузки и четвёртого режима CLI."""

import contextlib
import io
import sys
import unittest
from pathlib import Path

from graph import DependencyGraph, build_graph
from loading_order import DependencyCycleError, loading_order
from main import EXIT_ERROR, EXIT_OK, main
from test_graph import MemorySource
import test_main

DEEP_SIZE = sys.getrecursionlimit() + 100
ROOT = Path(__file__).resolve().parents[1]


class LoadingOrderTests(unittest.TestCase):
    """Зависимости предшествуют потребителям, циклы не дают порядка."""

    def order(self, data, excluded=""):
        """Строит граф из памяти и возвращает имена в порядке загрузки."""
        graph = build_graph(MemorySource(data), "A", "", excluded)
        return [name for name, _ in loading_order(graph)]

    def test_diamond(self):
        """Общая зависимость появляется один раз и раньше обоих родителей."""
        data = {"A": "BC", "B": "D", "C": "D", "D": ""}
        self.assertEqual(self.order(data), ["D", "B", "C", "A"])

    def test_filter_and_leaf(self):
        """Фильтр исключает B, а лист и исключённый корень обработаны."""
        data = {"A": "BC", "B": "D", "C": "D", "D": ""}
        self.assertEqual(self.order(data, "B"), ["D", "C", "A"])
        self.assertEqual(self.order({"A": ""}), ["A"])
        self.assertEqual(self.order(data, "A"), [])

    def test_cycles(self):
        """Цикл и самоссылка вызывают явную ошибку."""
        for data in ({"A": "A"}, {"A": "B", "B": "A"}):
            with self.subTest(data=data):
                with self.assertRaises(DependencyCycleError):
                    self.order(data)

    def test_deep_chain(self):
        """Глубина больше лимита рекурсии не мешает итеративному DFS."""
        nodes = [(str(i), "") for i in range(DEEP_SIZE)]
        edges = {node: [target] for node, target in zip(nodes, nodes[1:])}
        edges[nodes[-1]] = []
        self.assertEqual(loading_order(DependencyGraph(edges)), nodes[::-1])

    def test_versions_are_distinct(self):
        """Разные версии одного имени остаются разными узлами."""
        root, first, second = ("A", "1"), ("B", "1"), ("B", "2")
        graph = DependencyGraph({root: [first, second], first: [], second: []})
        self.assertEqual(loading_order(graph), [first, second, root])


class LoadingOrderCliTests(unittest.TestCase):
    """Проверка пользовательского вывода на готовых примерах."""

    def run_example(self, name):
        """Запускает четвёртый этап с абсолютными путями во временном файле."""
        fixture = test_main.MainTests()
        self.addCleanup(fixture.doCleanups)
        path = fixture.write_config(ROOT / "examples" / name, "true", "A")
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(["--stage", "4", "--config", path])
        return code, out.getvalue(), err.getvalue()

    def test_success(self):
        """CLI печатает порядок ромба и возвращает успешный код."""
        code, out, err = self.run_example("test_repo.txt")
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(err, "")
        self.assertIn("1. D\n2. B\n3. C\n4. A\n", out)

    def test_cycle_has_no_partial_output(self):
        """При цикле stdout пуст, ошибка направляется в stderr."""
        code, out, err = self.run_example("cycle.txt")
        self.assertEqual(code, EXIT_ERROR)
        self.assertEqual(out, "")
        self.assertIn("цикл", err)

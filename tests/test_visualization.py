"""Проверки DOT, запуска Graphviz и пятого этапа CLI."""

import shutil
import subprocess
import unittest
from unittest.mock import patch

import test_main
from graph import DependencyGraph
from main import EXIT_ERROR, EXIT_OK
from support import TempDirTestCase
from visualization import (
    PNG_SIGNATURE,
    VisualizationError,
    quote_label,
    save_visualization,
    to_dot,
)

A = ("A", "")
B = ("B", "")
C = ("C", "")
D = ("D", "")
FAKE_PNG = PNG_SIGNATURE + b"mock image"


class VisualizationTests(TempDirTestCase):
    """Проверки структуры и ошибок; внешний dot заменяется в unit-тестах."""

    def test_shared_dependency(self):
        """Общая вершина одна, но оба входящих ребра сохраняются."""
        graph = DependencyGraph({A: [B, C], B: [D], C: [D], D: []})
        dot = to_dot(graph)
        self.assertEqual(dot.count('[label="D"]'), 1)
        self.assertIn("n1 -> n3;", dot)
        self.assertIn("n2 -> n3;", dot)
        self.assertEqual(dot.count(" -> "), 4)

    def test_cycles(self):
        """Цикл и самоссылка экспортируются без повторного обхода."""
        dot = to_dot(DependencyGraph({A: [A, B], B: [A]}))
        for edge in ("n0 -> n0;", "n0 -> n1;", "n1 -> n0;"):
            self.assertIn(edge, dot)

    def test_versions_and_empty_graph(self):
        """Разные версии имеют разные ID; пустой граф допустим."""
        graph = DependencyGraph({("pkg", "1.0.0"): [],
                                 ("pkg", "2.0.0"): []})
        dot = to_dot(graph)
        self.assertIn('n0 [label="pkg@1.0.0"]', dot)
        self.assertIn('n1 [label="pkg@2.0.0"]', dot)
        empty = to_dot(DependencyGraph())
        self.assertTrue(empty.startswith("digraph dependencies {"))
        self.assertNotIn("[label=", empty)

    def test_escaping_and_invalid_edge(self):
        """Метки экранируются; отсутствующая вершина вызывает ошибку."""
        self.assertEqual(quote_label('a"b\\c\nd'), '"a\\"b\\\\c\\nd"')
        with self.assertRaises(VisualizationError):
            to_dot(DependencyGraph({A: [B]}))

    @patch("visualization.subprocess.run")
    def test_save_files(self, run):
        """Пути с пробелами поддерживаются; dot получает UTF-8 через stdin."""
        run.return_value.stdout = FAKE_PNG
        output = self.tmp / "мой граф.png"
        graph = DependencyGraph({A: []})
        dot_path, png_path = save_visualization(graph, output)
        self.assertEqual(dot_path.read_text("utf-8"), to_dot(graph))
        self.assertEqual(png_path.read_bytes(), FAKE_PNG)
        self.assertEqual(run.call_args.args[0], ["dot", "-Tpng"])
        self.assertEqual(run.call_args.kwargs["input"],
                         to_dot(graph).encode("utf-8"))

    @patch("visualization.subprocess.run")
    def test_renderer_errors_preserve_old_image(self, run):
        """Сбой dot не затирает прежнее изображение; DOT сохраняется."""
        errors = (
            FileNotFoundError(),
            subprocess.TimeoutExpired("dot", 60),
            subprocess.CalledProcessError(1, "dot", stderr=b"bad DOT"),
            PermissionError("denied"),
        )
        output = self.tmp / "graph.png"
        output.write_bytes(b"old image")
        for error in errors:
            with self.subTest(error=type(error).__name__):
                run.side_effect = error
                with self.assertRaises(VisualizationError):
                    save_visualization(DependencyGraph(), output)
                self.assertEqual(output.read_bytes(), b"old image")
                self.assertTrue(output.with_suffix(".dot").is_file())

    @patch("visualization.subprocess.run")
    def test_invalid_png_and_write_error(self, run):
        """Не-PNG и ошибки файловой системы не приводят к traceback."""
        run.return_value.stdout = b"not an image"
        with self.assertRaises(VisualizationError):
            save_visualization(DependencyGraph(), self.tmp / "g.png")
        with self.assertRaises(VisualizationError):
            save_visualization(DependencyGraph(), self.tmp / "no" / "g.png")

    @unittest.skipUnless(shutil.which("dot"), "Graphviz не установлен")
    def test_real_graphviz(self):
        """Установленный Graphviz создаёт настоящий PNG циклического графа."""
        _, png = save_visualization(
            DependencyGraph({A: [B], B: [A]}), self.tmp / "cycle.png"
        )
        self.assertTrue(png.read_bytes().startswith(PNG_SIGNATURE))


class VisualizationCliTests(unittest.TestCase):
    """Интеграция выбора этапа, фильтра и обработки ошибок."""

    def fixture(self):
        """Готовит CLI и циклический репозиторий в отдельной папке."""
        fixture = test_main.MainTests()
        self.addCleanup(fixture.doCleanups)
        repo = fixture.tmp / "repo.txt"
        repo.write_text("A: B\nB: A\n", encoding="utf-8")
        path = fixture.write_config(repo, test_mode="true", package="A")
        return fixture, path

    @patch("visualization.subprocess.run")
    def test_cli_success_and_filter(self, run):
        """CLI сохраняет цикл; фильтр применяется перед экспортом."""
        run.return_value.stdout = FAKE_PNG
        fixture, path = self.fixture()
        code, out, err = fixture.run_main(path, stage="5")
        self.assertEqual((code, err), (EXIT_OK, ""))
        self.assertIn("PNG сохранён:", out)
        with open(path, "a", encoding="utf-8") as config:
            config.write("filter: B\n")
        code, _, err = fixture.run_main(path, stage="5")
        self.assertEqual((code, err), (EXIT_OK, ""))
        dot = (fixture.tmp / "g.dot").read_text("utf-8")
        self.assertIn('[label="A"]', dot)
        self.assertNotIn('[label="B"]', dot)

    @patch("visualization.subprocess.run", side_effect=FileNotFoundError)
    def test_cli_error(self, run):
        """Отсутствие Graphviz даёт понятное сообщение и код 1."""
        fixture, path = self.fixture()
        code, out, err = fixture.run_main(path, stage="5")
        self.assertEqual((code, out), (EXIT_ERROR, ""))
        self.assertIn("Graphviz не найден", err)


if __name__ == "__main__":
    unittest.main()

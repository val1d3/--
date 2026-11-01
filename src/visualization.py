"""Экспорт графа в DOT и создание PNG внешней программой Graphviz."""

import subprocess
from pathlib import Path

from graph import node_label

RENDER_TIMEOUT = 60
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class VisualizationError(Exception):
    """Ошибка запуска Graphviz или сохранения результата."""


def quote_label(value):
    """Экранирует специальные символы строковой метки DOT."""
    value = value.replace("\\", "\\\\").replace('"', '\\"')
    value = value.replace("\r", "\\r").replace("\n", "\\n")
    return '"' + value + '"'


def to_dot(graph):
    """Сохраняет все вершины, версии, общие связи и циклы в DOT."""
    identifiers = {node: f"n{i}" for i, node in enumerate(graph.edges)}
    lines = [
        "digraph dependencies {",
        "  rankdir=LR;",
        '  node [shape=box, fontname="Arial"];',
    ]
    for node, identifier in identifiers.items():
        label = quote_label(node_label(node))
        lines.append(f"  {identifier} [label={label}];")
    for node, targets in graph.edges.items():
        for target in targets:
            if target not in identifiers:
                raise VisualizationError("Граф содержит неизвестную вершину")
            lines.append(f"  {identifiers[node]} -> {identifiers[target]};")
    lines.append("}")
    return "\n".join(lines) + "\n"


def render_png(dot_text):
    """Запускает dot без оболочки и возвращает PNG в виде байтов."""
    try:
        result = subprocess.run(
            ["dot", "-Tpng"],
            input=dot_text.encode("utf-8"),
            capture_output=True,
            check=True,
            timeout=RENDER_TIMEOUT,
        )
    except FileNotFoundError as exc:
        raise VisualizationError(
            "Graphviz не найден: установите его и добавьте dot в PATH"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise VisualizationError("Превышено время работы Graphviz") from exc
    except subprocess.CalledProcessError as exc:
        details = (exc.stderr or b"").decode("utf-8", errors="replace")
        message = f"Ошибка Graphviz: {details.strip()}"
        raise VisualizationError(message) from exc
    except OSError as exc:
        message = f"Не удалось запустить Graphviz: {exc}"
        raise VisualizationError(message) from exc
    if not result.stdout.startswith(PNG_SIGNATURE):
        raise VisualizationError("Graphviz не вернул изображение PNG")
    return result.stdout


def save_visualization(graph, output):
    """Сохраняет DOT рядом с PNG; при сбое Graphviz DOT остаётся доступен."""
    png_path = Path(output)
    dot_path = png_path.with_suffix(".dot")
    dot_text = to_dot(graph)
    try:
        dot_path.write_text(dot_text, encoding="utf-8")
        png_data = render_png(dot_text)
        png_path.write_bytes(png_data)
    except OSError as exc:
        raise VisualizationError(f"Не удалось записать файл: {exc}") from exc
    return dot_path, png_path

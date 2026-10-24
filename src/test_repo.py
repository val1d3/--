"""Чтение учебного графа из строк вида A: B C."""

import re
from pathlib import Path

from npm_repo import RepositoryError

LINE_RE = re.compile(r"\s*([A-Z]+)\s*:\s*([A-Z]+(?:\s+[A-Z]+)*)?\s*")


def read_test_repository(path):
    """Читает граф и проверяет объявления вершин."""
    try:
        text = Path(path).read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        raise RepositoryError(f"Не удалось прочитать '{path}': {exc}") from exc
    graph = {}
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        match = LINE_RE.fullmatch(line)
        if not match:
            raise RepositoryError(f"Строка {number}: ожидается A: B C")
        name, targets = match.groups()
        if name in graph:
            raise RepositoryError(f"Повторное описание пакета: {name}")
        graph[name] = dict.fromkeys((targets or "").split(), "")
    validate_references(graph)
    return graph


def validate_references(graph):
    """Каждый упомянутый пакет должен иметь строку, в том числе лист."""
    if not graph:
        raise RepositoryError("Тестовый репозиторий пуст")
    for name, dependencies in graph.items():
        for target in dependencies:
            if target not in graph:
                raise RepositoryError(f"Пакет {target} из {name} не описан")


class TestRepository:
    """Источник зависимостей из файла с именами из заглавных букв."""

    def __init__(self, path):
        """Загружает и проверяет весь тестовый репозиторий."""
        self.graph = read_test_repository(path)

    def resolve(self, name, spec):
        """Возвращает идентификатор тестового узла без версии."""
        if name not in self.graph:
            raise RepositoryError(f"Пакет {name} не найден в тестовом файле")
        return name, ""

    def dependencies(self, node):
        """Возвращает непосредственных соседей тестового узла."""
        return self.graph[node[0]]

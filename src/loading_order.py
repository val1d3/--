"""Порядок загрузки: зависимости раньше зависящих от них пакетов."""

from graph import node_label
from npm_repo import RepositoryError


class DependencyCycleError(RepositoryError):
    """Строгий порядок загрузки невозможен из-за цикла."""


def visit_component(root, edges, visited, result):
    """Добавляет компоненту в порядке завершения итеративного DFS."""
    active = {root}
    stack = [(root, iter(edges[root]))]
    while stack:
        node, children = stack[-1]
        target = next(children, None)
        if target is None:
            stack.pop()
            active.remove(node)
            visited.add(node)
            result.append(node)
            continue
        if target in active:
            raise DependencyCycleError(
                "Порядок загрузки невозможен: цикл "
                f"{node_label(node)} -> {node_label(target)}"
            )
        if target not in edges:
            raise RepositoryError(f"В графе нет {node_label(target)}")
        if target not in visited:
            active.add(target)
            stack.append((target, iter(edges[target])))


def loading_order(graph):
    """Возвращает порядок всех вершин; при цикле выдаёт ошибку."""
    visited, result = set(), []
    for root in graph.edges:
        if root not in visited:
            visit_component(root, graph.edges, visited, result)
    return result


def print_loading_order(graph):
    """Печатает полный порядок, включая корень, после проверки циклов."""
    order = loading_order(graph)
    if not order:
        print("Порядок загрузки пуст: все пакеты исключены фильтром.")
        return
    print("Порядок загрузки (зависимости перед пакетами):")
    for number, node in enumerate(order, start=1):
        print(f"{number}. {node_label(node)}")

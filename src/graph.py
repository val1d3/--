"""Итеративный DFS с сохранением рёбер и обнаружением циклов."""

from dataclasses import dataclass, field


@dataclass
class DependencyGraph:
    """Список смежности в порядке DFS и обратные рёбра циклов."""

    edges: dict = field(default_factory=dict)
    cycle_edges: list = field(default_factory=list)


def enter_node(node, source, graph, active, stack):
    """Открывает вершину, сохраняя итератор соседей в явном стеке."""
    graph.edges[node] = []
    active.add(node)
    stack.append((node, iter(source.dependencies(node).items())))


def build_graph(source, package, version, excluded=""):
    """Обходит достижимые вершины DFS без рекурсии, исключая подстроку."""
    graph = DependencyGraph()
    if excluded and excluded in package:
        return graph
    root = source.resolve(package, version)
    stack, active = [], set()
    enter_node(root, source, graph, active, stack)
    while stack:
        node, children = stack[-1]
        child = next(children, None)
        if child is None:
            active.remove(node)
            stack.pop()
            continue
        name, spec = child
        if excluded and excluded in name:
            continue
        target = source.resolve(name, spec)
        graph.edges[node].append(target)
        if target in active:
            graph.cycle_edges.append((node, target))
        if target not in graph.edges:
            enter_node(target, source, graph, active, stack)
    return graph


def node_label(node):
    """Форматирует npm-узел с версией или тестовый узел без версии."""
    name, version = node
    return f"{name}@{version}" if version else name


def print_graph(graph):
    """Печатает список смежности и обратные рёбра найденных циклов."""
    print(f"Граф зависимостей: {len(graph.edges)} вершин")
    for node, targets in graph.edges.items():
        names = ", ".join(node_label(target) for target in targets)
        print(f"{node_label(node)} -> {names or '(нет зависимостей)'}")
    for source, target in graph.cycle_edges:
        print(f"Цикл: {node_label(source)} -> {node_label(target)}")

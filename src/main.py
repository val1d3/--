"""CLI: демонстрация конфигурации, прямых зависимостей и полного графа."""

import argparse
import sys

from config import ConfigError, load_config
from graph import build_graph, print_graph
from npm_repo import RepositoryError
from npm_source import NpmRepository
from test_repo import TestRepository

EXIT_OK = 0
EXIT_ERROR = 1
STAGE_CONFIG = 1
STAGE_DIRECT = 2
STAGE_GRAPH = 3


def parse_args(argv):
    """Разбирает путь к YAML и номер демонстрируемого этапа."""
    parser = argparse.ArgumentParser(
        prog="depgraph",
        description="Анализ графа зависимостей npm-пакетов.",
    )
    parser.add_argument(
        "-c",
        "--config",
        default="config.yaml",
        help="путь к YAML-файлу конфигурации (по умолчанию config.yaml)",
    )
    parser.add_argument(
        "--stage",
        type=int,
        default=STAGE_GRAPH,
        choices=(STAGE_CONFIG, STAGE_DIRECT, STAGE_GRAPH),
        help="1: параметры; 2: прямые зависимости; 3: полный граф",
    )
    return parser.parse_args(argv)


def print_params(config):
    """Выводит все шесть параметров для демонстрации первого этапа."""
    for key, value in vars(config).items():
        print(f"{key}: {value}")


def print_dependencies(config, dependencies):
    """Выводит прямые зависимости заданного пакета для второго этапа."""
    title = f"{config.package}@{config.version}"
    if not dependencies:
        print(f"{title}: прямых зависимостей нет")
        return
    print(f"Прямые зависимости {title} ({len(dependencies)}):")
    for name, spec in dependencies.items():
        print(f"  {name}: {spec}")


def run_stage(config, stage):
    """Выполняет выбранный этап с параметрами из YAML."""
    if stage == STAGE_CONFIG:
        print_params(config)
        return
    source = (
        TestRepository(config.repository)
        if config.test_mode
        else NpmRepository(config.repository)
    )
    if stage == STAGE_DIRECT:
        node = source.resolve(config.package, config.version)
        print_dependencies(config, source.dependencies(node))
        return
    graph = build_graph(source, config.package, config.version, config.filter)
    print_graph(graph)


def main(argv=None):
    """Запускает приложение; ошибки конфигурации и репозитория дают код 1."""
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        config = load_config(args.config)
        run_stage(config, args.stage)
    except ConfigError as exc:
        print(f"Ошибка конфигурации: {exc}", file=sys.stderr)
        return EXIT_ERROR
    except RepositoryError as exc:
        print(f"Ошибка репозитория: {exc}", file=sys.stderr)
        return EXIT_ERROR
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())

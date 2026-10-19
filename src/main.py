"""Точка входа: прямые зависимости npm-пакета (этап 2)."""

import argparse
import sys

from config import ConfigError, load_config
from npm_repo import RepositoryError, get_direct_dependencies

EXIT_OK = 0
EXIT_ERROR = 1
TEST_MODE_MESSAGE = (
    "Режим тестового репозитория будет доступен на этапе 3 "
    "(поставьте test_mode: false)"
)


def parse_args(argv):
    """Разбирает аргументы командной строки."""
    parser = argparse.ArgumentParser(
        prog="depgraph",
        description="Визуализация графа зависимостей npm-пакетов.",
    )
    parser.add_argument(
        "-c",
        "--config",
        default="config.yaml",
        help="путь к YAML-файлу конфигурации (по умолчанию config.yaml)",
    )
    return parser.parse_args(argv)


def print_dependencies(config, dependencies):
    """Выводит прямые зависимости заданного пакета."""
    title = f"{config.package}@{config.version}"
    if not dependencies:
        print(f"{title}: прямых зависимостей нет")
        return
    print(f"Прямые зависимости {title} ({len(dependencies)}):")
    for name, spec in dependencies.items():
        print(f"  {name}: {spec}")


def run(config):
    """Получает и выводит зависимости, возвращает код завершения."""
    if config.test_mode:
        print(f"Ошибка: {TEST_MODE_MESSAGE}", file=sys.stderr)
        return EXIT_ERROR
    try:
        dependencies = get_direct_dependencies(
            config.repository, config.package, config.version
        )
    except RepositoryError as exc:
        print(f"Ошибка репозитория: {exc}", file=sys.stderr)
        return EXIT_ERROR
    print_dependencies(config, dependencies)
    return EXIT_OK


def main(argv=None):
    """Запускает приложение и возвращает код завершения."""
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        config = load_config(args.config)
    except ConfigError as exc:
        print(f"Ошибка конфигурации: {exc}", file=sys.stderr)
        return EXIT_ERROR
    return run(config)


if __name__ == "__main__":
    sys.exit(main())

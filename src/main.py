"""Точка входа: загрузка конфигурации и вывод параметров (этап 1)."""

import argparse
import sys

from config import ConfigError, load_config

EXIT_OK = 0
EXIT_ERROR = 1


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


def print_params(config):
    """Выводит все параметры в формате ключ-значение."""
    for key, value in vars(config).items():
        print(f"{key}: {value}")


def main(argv=None):
    """Запускает приложение и возвращает код завершения."""
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        config = load_config(args.config)
    except ConfigError as exc:
        print(f"Ошибка конфигурации: {exc}", file=sys.stderr)
        return EXIT_ERROR
    print_params(config)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
"""Загрузка и проверка конфигурации в формате YAML."""

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import yaml

MAX_NAME_LENGTH = 214
URL_SCHEMES = ("http", "https")
IMAGE_SUFFIX = ".png"
KNOWN_KEYS = (
    "package",
    "repository",
    "test_mode",
    "version",
    "output",
    "filter",
)

NPM_NAME_RE = re.compile(
    r"^(@[a-z0-9~-][a-z0-9._~-]*/)?[A-Za-z0-9~-][A-Za-z0-9._~-]*$"
)
TEST_NAME_RE = re.compile(r"^[A-Z]+$")
NUM = r"(0|[1-9]\d*)"
SEMVER_RE = re.compile(
    rf"^{NUM}\.{NUM}\.{NUM}(-[0-9A-Za-z.-]+)?(\+[0-9A-Za-z.-]+)?$"
)


class ConfigError(Exception):
    """Ошибка в конфигурационном файле."""


@dataclass(frozen=True)
class Config:
    """Параметры, настраиваемые пользователем."""

    package: str
    repository: str
    test_mode: bool
    version: str
    output: str
    filter: str


def read_yaml(path):
    """Читает YAML-файл и возвращает словарь параметров."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ConfigError(f"Файл конфигурации не найден: {path}") from None
    except (OSError, UnicodeDecodeError) as exc:
        raise ConfigError(f"Не удалось прочитать '{path}': {exc}") from exc
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ConfigError(f"Некорректный YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError("Конфигурация должна быть набором 'ключ: значение'")
    return data


def check_unknown_keys(data):
    """Запрещает неизвестные ключи (защита от опечаток)."""
    unknown = sorted(str(key) for key in data if key not in KNOWN_KEYS)
    if unknown:
        raise ConfigError(f"Неизвестные параметры: {', '.join(unknown)}")


def get_str(data, key, default=None):
    """Возвращает строковый параметр; без default он обязателен."""
    value = data.get(key)
    if value is None:
        value = default
    if value is None:
        raise ConfigError(f"Не задан обязательный параметр '{key}'")
    if not isinstance(value, str):
        raise ConfigError(
            f"Параметр '{key}' должен быть строкой "
            f"(заключите значение в кавычки)"
        )
    value = value.strip()
    if default is None and not value:
        raise ConfigError(f"Параметр '{key}' не может быть пустым")
    return value


def get_bool(data, key, default):
    """Возвращает логический параметр (true/false в YAML)."""
    value = data.get(key, default)
    if not isinstance(value, bool):
        raise ConfigError(f"Параметр '{key}' должен быть true или false")
    return value


def validate_package(name, test_mode):
    """Проверяет имя пакета: npm-имя или заглавные латинские буквы."""
    if test_mode:
        if not TEST_NAME_RE.fullmatch(name):
            raise ConfigError(
                "В тестовом режиме имя пакета - заглавные латинские "
                f"буквы (A, B, AB...), получено '{name}'"
            )
        return
    if len(name) > MAX_NAME_LENGTH:
        raise ConfigError(f"Имя пакета длиннее {MAX_NAME_LENGTH} символов")
    if not NPM_NAME_RE.fullmatch(name):
        raise ConfigError(f"Недопустимое имя npm-пакета: '{name}'")


def validate_repository(repository, test_mode):
    """Проверяет URL репозитория или путь к файлу тестового репозитория."""
    if test_mode:
        if not Path(repository).is_file():
            raise ConfigError(
                f"Файл тестового репозитория не найден: {repository}"
            )
        return
    parsed = urlparse(repository)
    if parsed.scheme not in URL_SCHEMES or not parsed.netloc:
        raise ConfigError(
            f"Некорректный URL репозитория (нужен http/https): {repository}"
        )


def validate_version(version):
    """Проверяет, что версия записана по правилам semver."""
    if not SEMVER_RE.fullmatch(version):
        raise ConfigError(
            f"Версия '{version}' не соответствует формату X.Y.Z"
        )


def validate_output(output):
    """Проверяет имя файла изображения и существование его папки."""
    path = Path(output)
    if path.suffix.lower() != IMAGE_SUFFIX or not path.stem:
        raise ConfigError(
            f"Имя файла изображения должно иметь вид name{IMAGE_SUFFIX}"
        )
    if not path.parent.is_dir():
        raise ConfigError(f"Папка не существует: {path.parent}")


def load_config(path):
    """Загружает YAML-файл, проверяет параметры и возвращает Config."""
    data = read_yaml(path)
    check_unknown_keys(data)
    test_mode = get_bool(data, "test_mode", False)
    config = Config(
        package=get_str(data, "package"),
        repository=get_str(data, "repository"),
        test_mode=test_mode,
        version=get_str(data, "version"),
        output=get_str(data, "output"),
        filter=get_str(data, "filter", ""),
    )
    validate_package(config.package, test_mode)
    validate_repository(config.repository, test_mode)
    validate_version(config.version)
    validate_output(config.output)
    return config

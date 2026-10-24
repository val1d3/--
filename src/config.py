"""Загрузка и проверка конфигурации в формате YAML."""

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import yaml

MAX_NAME_LENGTH = 214
MIN_PORT = 1
MAX_PORT = 65535
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
MODE_RE = re.compile(r"(?:true|false)", re.IGNORECASE)
HOST = r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?"
URL_RE = re.compile(
    rf"https?://(?:{HOST}(?:\.{HOST})*|\[[0-9A-Fa-f:]+\])"
    r"(?::[0-9]{1,5})?(?:/[^\s?#\\]*)?"
)
PATH_RE = re.compile(r'(?:[A-Za-z]:)?[^<>:"|?*\x00-\x1f]+')
NUM = r"(?:0|[1-9][0-9]*)"
PRE = rf"(?:{NUM}|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*)"
SEMVER_RE = re.compile(
    rf"{NUM}\.{NUM}\.{NUM}(?:-{PRE}(?:\.{PRE})*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
)


class ConfigLoader(yaml.SafeLoader):
    """Безопасный YAML с явной проверкой логических значений."""


ConfigLoader.yaml_implicit_resolvers = {
    key: [(tag, regex) for tag, regex in rules
          if tag != "tag:yaml.org,2002:bool"]
    for key, rules in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
ConfigLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool", MODE_RE, list("tTfF")
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
        data = yaml.load(text, Loader=ConfigLoader)
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
    """Проверяет true/false регулярным выражением, возвращает bool."""
    value = data.get(key, default)
    text = str(value)
    if not MODE_RE.fullmatch(text):
        raise ConfigError(f"Параметр '{key}' должен быть true или false")
    return text.lower() == "true"


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
        if not PATH_RE.fullmatch(repository):
            raise ConfigError(f"Некорректный путь репозитория: {repository}")
        if not Path(repository).is_file():
            raise ConfigError(
                f"Файл тестового репозитория не найден: {repository}"
            )
        return
    if not URL_RE.fullmatch(repository):
        raise ConfigError(
            f"Некорректный URL репозитория (нужен http/https): {repository}"
        )

    try:
        port = urlsplit(repository).port
        if port is not None and not MIN_PORT <= port <= MAX_PORT:
            raise ValueError("порт вне диапазона")
    except ValueError as exc:
        raise ConfigError(f"Некорректный URL репозитория: {exc}") from exc


def validate_version(version):
    """Проверяет, что версия записана по правилам semver."""
    if not SEMVER_RE.fullmatch(version):
        raise ConfigError(
            f"Версия '{version}' не соответствует формату X.Y.Z"
        )


def validate_output(output):
    """Проверяет имя файла изображения и существование его папки."""
    if not PATH_RE.fullmatch(output):
        raise ConfigError("Некорректный путь файла изображения")
    path = Path(output)
    if path.is_dir():
        raise ConfigError("Путь изображения указывает на папку")
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

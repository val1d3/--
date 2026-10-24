"""Получение информации о пакетах из реестра npm по HTTP."""

import http.client
import json
import socket
import urllib.error
import urllib.request
from urllib.parse import quote

from config import MAX_NAME_LENGTH, NPM_NAME_RE

HTTP_NOT_FOUND = 404
TIMEOUT_SECONDS = 15
TIMEOUT_ERRORS = (TimeoutError, socket.timeout)
HEADERS = {
    "User-Agent": "depgraph/0.2 (educational project)",
    "Accept": "application/json",
}


class RepositoryError(Exception):
    """Ошибка получения данных из репозитория."""


def build_url(repository, name, version):
    """Строит URL метаданных версии: <репозиторий>/<имя>/<версия>."""
    base = repository.rstrip("/")
    return f"{base}/{quote(name, safe='@')}/{quote(version, safe='')}"


def http_error(code, url):
    """Создаёт ошибку по коду HTTP-ответа."""
    if code == HTTP_NOT_FOUND:
        return RepositoryError(
            f"Пакет или версия не найдены в репозитории: {url}"
        )
    return RepositoryError(f"Репозиторий вернул ошибку HTTP {code}: {url}")


def network_error(reason, url, timeout):
    """Создаёт ошибку по причине сетевого сбоя."""
    if isinstance(reason, TIMEOUT_ERRORS):
        return RepositoryError(
            f"Превышено время ожидания ответа ({timeout} с): {url}"
        )
    return RepositoryError(
        f"Не удалось подключиться к репозиторию ({reason}): {url}"
    )


def parse_json_object(body):
    """Разбирает тело ответа и проверяет, что это JSON-объект."""
    try:
        data = json.loads(body.decode("utf-8"))
    except ValueError:
        raise RepositoryError(
            "Ответ репозитория не является корректным JSON"
        ) from None
    if not isinstance(data, dict):
        raise RepositoryError("Ответ репозитория не является JSON-объектом")
    return data


def fetch_json(url, timeout=TIMEOUT_SECONDS):
    """Загружает JSON-объект по URL, ошибки превращает в RepositoryError."""
    request = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
    except urllib.error.HTTPError as exc:
        raise http_error(exc.code, url) from None
    except urllib.error.URLError as exc:
        raise network_error(exc.reason, url, timeout) from exc
    except (OSError, http.client.HTTPException) as exc:
        raise network_error(exc, url, timeout) from exc
    return parse_json_object(body)


def get_direct_dependencies(repository, name, version,
                            timeout=TIMEOUT_SECONDS):
    """Возвращает прямые зависимости пакета: {имя: диапазон версий}."""
    url = build_url(repository, name, version)
    return extract_dependencies(fetch_json(url, timeout))


def extract_dependencies(metadata):
    """Проверяет имена и диапазоны зависимостей в метаданных версии."""
    dependencies = metadata.get("dependencies", {})
    is_valid = isinstance(dependencies, dict) and all(
        valid_dependency(name, spec) for name, spec in dependencies.items()
    )
    if not is_valid:
        raise RepositoryError(
            "Поле 'dependencies' должно быть объектом 'имя: диапазон'"
        )
    return dict(sorted(dependencies.items()))


def valid_dependency(name, spec):
    """Проверяет запись dependencies до построения URL запроса."""
    return (
        isinstance(name, str) and len(name) <= MAX_NAME_LENGTH
        and NPM_NAME_RE.fullmatch(name) is not None
        and isinstance(spec, str) and bool(spec.strip())
    )

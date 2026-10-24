"""Кэшируемый источник метаданных npm для транзитивного обхода."""

from urllib.parse import quote

from config import SEMVER_RE
from npm_repo import (
    RepositoryError,
    extract_dependencies,
    fetch_json,
    get_direct_dependencies,
)
from semver import select_version


class NpmRepository:
    """Разрешает диапазоны версий и читает зависимости напрямую по HTTP."""

    def __init__(self, url):
        """Создаёт кэши метаданных пакетов и зависимостей версий."""
        self.url = url
        self.documents = {}
        self.cache = {}

    def document(self, name):
        """Загружает список версий пакета один раз за запуск."""
        if name not in self.documents:
            url = self.url.rstrip("/") + "/" + quote(name, safe="@")
            data = fetch_json(url)
            if not isinstance(data.get("versions"), dict):
                raise RepositoryError(f"У {name} нет объекта versions")
            self.documents[name] = data
        return self.documents[name]

    def resolve(self, name, spec):
        """Разрешает точную версию, dist-tag или диапазон в имя/версию."""
        if SEMVER_RE.fullmatch(spec):
            return name, spec
        data = self.document(name)
        versions = data["versions"]
        tags = data.get("dist-tags", {})
        if not isinstance(tags, dict):
            raise RepositoryError(f"У {name} некорректный объект dist-tags")
        if spec in tags:
            version = tags[spec]
            if not isinstance(version, str) or version not in versions:
                raise RepositoryError(f"У {name} некорректный тег {spec}")
            if not SEMVER_RE.fullmatch(version):
                raise RepositoryError(f"У {name} некорректная версия тега")
        else:
            version = select_version(versions, spec)
        return name, version

    def dependencies(self, node):
        """Читает зависимости конкретной версии, используя кэш документа."""
        if node not in self.cache:
            name, version = node
            if name in self.documents:
                metadata = self.documents[name]["versions"].get(version)
                if not isinstance(metadata, dict):
                    raise RepositoryError(f"Нет метаданных {name}@{version}")
                self.cache[node] = extract_dependencies(metadata)
            else:
                self.cache[node] = get_direct_dependencies(
                    self.url, name, version
                )
        return self.cache[node]

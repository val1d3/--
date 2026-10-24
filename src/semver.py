"""Сравнение SemVer и раскрытие диапазонов npm без сторонних библиотек."""

import operator
import re

from config import NUM, SEMVER_RE
from npm_repo import RepositoryError

CORE_SIZE = 3
MINOR = 1

PART_RE = re.compile(rf"(?:{NUM}|[xX*])(?:\.(?:{NUM}|[xX*])){{0,2}}")
TOKEN_RE = re.compile(r"(>=|<=|>|<|=|\^|~)?(.*)")
OPERATORS = {
    "=": operator.eq,
    ">": operator.gt,
    ">=": operator.ge,
    "<": operator.lt,
    "<=": operator.le,
}


def version_key(text):
    """Возвращает ключ порядка SemVer, игнорируя build metadata."""
    if not SEMVER_RE.fullmatch(text):
        raise RepositoryError(f"Некорректная версия в реестре: {text}")
    core, _, pre = text.split("+", 1)[0].partition("-")
    numbers = tuple(int(part) for part in core.split("."))
    identifiers = tuple(
        (0, int(part)) if part.isdigit() else (1, part)
        for part in pre.split(".")
    ) if pre else ()
    return numbers + (not bool(pre), identifiers)


def partial(text):
    """Дополняет частичную версию нулями и сообщает точность."""
    text = text.removeprefix("v")
    if SEMVER_RE.fullmatch(text):
        return text, CORE_SIZE
    if not PART_RE.fullmatch(text):
        raise RepositoryError(f"Неподдерживаемый диапазон npm: {text}")
    parts = text.split(".")
    numbers = []
    wildcard = False
    for part in parts:
        if part in ("x", "X", "*"):
            wildcard = True
        elif wildcard:
            raise RepositoryError(f"Некорректный диапазон npm: {text}")
        else:
            numbers.append(int(part))
    count = len(numbers)
    numbers.extend([0] * (CORE_SIZE - count))
    return ".".join(map(str, numbers)), count


def upper_bound(version, index):
    """Строит исключительную верхнюю границу с prerelease -0."""
    core = list(version_key(version)[:CORE_SIZE])
    core[index] += 1
    core[index + 1:] = [0] * (CORE_SIZE - index - 1)
    return ".".join(map(str, core)) + "-0"


def compatible_bounds(op, version, count):
    """Раскрывает тильду и каретку в пару сравнений."""
    if not count:
        return []
    core = version_key(version)[:CORE_SIZE]
    if op == "~":
        index = min(MINOR, count - 1)
    else:
        index = next((i for i, n in enumerate(core) if n), count - 1)
        index = min(index, count - 1)
    return [(">=", version), ("<", upper_bound(version, index))]


def wildcard_bounds(op, version, count):
    """Раскрывает сравнение с частичной версией или wildcard."""
    if not count:
        return [("<", "0.0.0-0")] if op in ("<", ">") else []
    upper = upper_bound(version, count - 1)
    choices = {
        "=": [(">=", version), ("<", upper)],
        ">=": [(">=", version)],
        ">": [(">=", upper.removesuffix("-0"))],
        "<": [("<", version + "-0")],
        "<=": [("<", upper)],
    }
    return choices[op]


def expand_token(token):
    """Превращает один элемент диапазона в простые сравнения."""
    match = TOKEN_RE.fullmatch(token)
    op, value = match.groups()
    version, count = partial(value)
    op = op or "="
    if op in ("~", "^"):
        return compatible_bounds(op, version, count)
    if count < CORE_SIZE:
        return wildcard_bounds(op, version, count)
    return [(op, version)]


def hyphen_bounds(left, right):
    """Разбирает диапазон с дефисом, включая неполные границы."""
    low, low_count = partial(left)
    high, high_count = partial(right)
    result = [(">=", low)] if low_count else []
    if high_count == CORE_SIZE:
        result.append(("<=", high))
    elif high_count:
        result.append(("<", upper_bound(high, high_count - 1)))
    return result


def parse_range(spec):
    """Возвращает альтернативы, каждая из которых есть набор условий."""
    alternatives = []
    for clause in spec.split("||"):
        clause = clause.strip()
        hyphen = re.fullmatch(r"(\S+)\s+-\s+(\S+)", clause)
        if hyphen:
            bounds = hyphen_bounds(*hyphen.groups())
        else:
            clause = re.sub(r"(>=|<=|[<>=~^])\s+", r"\1", clause)
            bounds = [
                bound
                for token in clause.split()
                for bound in expand_token(token)
            ]
        alternatives.append([(op, version_key(v)) for op, v in bounds])
    return alternatives


def matches_clause(key, clause):
    """Проверяет условия и явное разрешение prerelease этого ядра версии."""
    if not key[CORE_SIZE]:
        allowed = any(
            not bound[CORE_SIZE] and key[:CORE_SIZE] == bound[:CORE_SIZE]
            for _, bound in clause
        )
        if not allowed:
            return False
    return all(OPERATORS[op](key, bound) for op, bound in clause)


def select_version(versions, spec):
    """Выбирает максимальную подходящую опубликованную версию."""
    alternatives = parse_range(spec)
    candidates = []
    for version in versions:
        if not SEMVER_RE.fullmatch(version):
            continue
        key = version_key(version)
        if any(matches_clause(key, clause) for clause in alternatives):
            candidates.append((key, version))
    if not candidates:
        raise RepositoryError(f"Нет версии, подходящей под '{spec}'")
    return max(candidates)[1]

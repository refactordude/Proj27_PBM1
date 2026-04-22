"""LLM이 생성한 SQL을 실행 전 검증한다.

정책:
- SELECT / SHOW / DESCRIBE / EXPLAIN 만 허용
- 단일 statement만 허용 (세미콜론으로 여러 개 불가)
- DDL/DML 키워드 어디든 포함되면 차단
- LIMIT 절이 없으면 자동 주입
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import sqlparse

_ALLOWED_STATEMENT_TYPES = {"SELECT"}
_ALLOWED_LEADING_KEYWORDS = {"SELECT", "WITH", "SHOW", "DESCRIBE", "DESC", "EXPLAIN"}
_FORBIDDEN = re.compile(
    r"\b("
    r"INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|CREATE|RENAME|REPLACE|GRANT|REVOKE|"
    r"MERGE|CALL|LOAD|HANDLER|LOCK|UNLOCK|SET|USE"
    r")\b",
    re.IGNORECASE,
)
_LIMIT_RE = re.compile(r"\blimit\b", re.IGNORECASE)


@dataclass
class SafetyResult:
    ok: bool
    reason: str = ""
    sanitized_sql: str = ""


def validate_and_sanitize(sql: str, *, default_limit: int = 1000) -> SafetyResult:
    sql = (sql or "").strip().rstrip(";").strip()
    if not sql:
        return SafetyResult(False, "빈 SQL입니다.")

    statements = [s for s in sqlparse.split(sql) if s.strip()]
    if len(statements) > 1:
        return SafetyResult(False, "여러 개의 statement는 허용되지 않습니다.")

    parsed = sqlparse.parse(sql)
    if not parsed:
        return SafetyResult(False, "SQL을 파싱할 수 없습니다.")

    first_token = None
    for tok in parsed[0].tokens:
        if not tok.is_whitespace and not _is_comment(tok):
            first_token = tok
            break
    if first_token is None:
        return SafetyResult(False, "SQL이 비어 있습니다.")

    leading = first_token.normalized.upper()
    if leading not in _ALLOWED_LEADING_KEYWORDS:
        return SafetyResult(False, f"허용되지 않은 SQL 시작 키워드입니다: {leading}")

    if _FORBIDDEN.search(sql):
        return SafetyResult(False, "쓰기/DDL 키워드가 포함되어 있습니다.")

    stmt_type = parsed[0].get_type().upper()
    if leading in {"SELECT", "WITH"} and stmt_type not in _ALLOWED_STATEMENT_TYPES:
        return SafetyResult(False, f"허용되지 않은 statement 유형입니다: {stmt_type}")

    sanitized = sql
    if leading in {"SELECT", "WITH"} and not _LIMIT_RE.search(sanitized):
        sanitized = f"{sanitized}\nLIMIT {int(default_limit)}"

    return SafetyResult(True, "", sanitized)


def _is_comment(token) -> bool:
    ttype = getattr(token, "ttype", None)
    return bool(ttype) and "Comment" in str(ttype)

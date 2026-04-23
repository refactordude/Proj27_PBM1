"""도구용 테이블 allowlist 워커 (SAFE-01).

sql_safety.validate_and_sanitize 이후 두 번째 게이트로 동작한다.
sqlparse AST를 재귀적으로 걸어 FROM/JOIN 대상을 수집하고,
AgentConfig.allowed_tables 밖의 테이블을 참조하면 AllowlistError를 던진다.
서브쿼리·CTE·UNION·information_schema 등 4개 공격벡터를 모두 차단한다.
"""
from __future__ import annotations

import re

import sqlparse
from sqlparse.sql import Identifier, IdentifierList, Parenthesis
from sqlparse.tokens import Keyword

_TABLE_KEYWORDS = {
    "FROM", "JOIN", "INNER JOIN", "LEFT JOIN", "RIGHT JOIN",
    "FULL JOIN", "CROSS JOIN", "LEFT OUTER JOIN", "RIGHT OUTER JOIN",
    "UPDATE", "INTO",
}
_FORBIDDEN_SCHEMAS = ("information_schema", "mysql", "performance_schema", "sys")
# Match forbidden schemas only as an actual schema prefix (`mysql.user`,
# `information_schema.TABLES`), never as a substring inside user strings or
# comments. Word-boundary + dot-suffix:  \bsys\.  — this rejects
# `information_schema.tables` but ignores `mysql_buffer_size`,
# `system_busy_timeout`, and comments like `/* see information_schema */`
# (no dot immediately after the word). The AST walker (_extract_tables)
# remains the authoritative check; this regex is belt-and-suspenders only. (WR-01)
_FORBIDDEN_SCHEMA_RE = re.compile(
    r"\b(" + "|".join(re.escape(s) for s in _FORBIDDEN_SCHEMAS) + r")\s*\.",
    re.IGNORECASE,
)


class AllowlistError(Exception):
    """테이블 allowlist 위반을 알린다. 호출부는 ToolResult 오류 문자열로 매핑한다."""


def _extract_tables(sql: str) -> set[str]:
    parsed = sqlparse.parse(sql)
    if not parsed:
        return set()
    tables: set[str] = set()

    def _record(ident) -> None:
        # Defensive guard: IdentifierList.get_identifiers() can yield bare Tokens
        # (e.g. LATERAL keyword on MySQL) that lack the get_parent_name/get_real_name
        # API. Silently skip them — they are not table identifiers. (CR-03)
        if not hasattr(ident, "get_real_name") or not hasattr(ident, "get_parent_name"):
            return
        real = ident.get_real_name()
        if real is None:
            return
        parent = ident.get_parent_name()
        full = f"{parent}.{real}" if parent else real
        tables.add(full.lower())

    def _recurse(tok_list) -> None:
        prev_kw: str | None = None
        for tok in tok_list.tokens:
            if tok.is_whitespace:
                continue
            # Tracks the "from/join/into X" handshake: when a TABLE keyword is
            # seen, the very next non-whitespace token names the table(s).
            recursed_as_target = False
            if tok.ttype is Keyword and tok.normalized.upper() in _TABLE_KEYWORDS:
                prev_kw = tok.normalized.upper()
                continue
            if prev_kw is not None:
                if isinstance(tok, IdentifierList):
                    for ident in tok.get_identifiers():
                        _record(ident)
                    prev_kw = None
                elif isinstance(tok, Identifier):
                    _record(tok)
                    prev_kw = None
                elif isinstance(tok, Parenthesis):
                    _recurse(tok)
                    prev_kw = None
                    recursed_as_target = True
                elif tok.ttype is Keyword:
                    prev_kw = None
            # Always descend into every group — catches CTE bodies
            # (`WITH x AS (SELECT ... FROM leaked)`), aliased subqueries
            # (`FROM (SELECT ... FROM leaked) alias`), UNION branches, and
            # WHERE-IN subqueries. Skip the Parenthesis we already recursed
            # into above to avoid double-walking (CR-01, CR-02).
            if tok.is_group and not recursed_as_target:
                _recurse(tok)

    for stmt in parsed:
        _recurse(stmt)
    return tables


def _check_table_allowlist(sql: str, allowed: list[str]) -> None:
    """사전 경계검사. 위반 시 AllowlistError. 정상 시 None."""
    # Belt-and-suspenders: forbidden schemas are never legal even if mis-added
    # to allowlist. Uses word-boundary + dot-suffix so string literals and
    # comments that merely contain the word don't false-positive. (WR-01)
    m = _FORBIDDEN_SCHEMA_RE.search(sql)
    if m:
        raise AllowlistError(
            f"Forbidden schema referenced: {m.group(1).lower()}"
        )
    tables = _extract_tables(sql)
    allowed_lc = {t.lower() for t in allowed}
    illegal = tables - allowed_lc
    if illegal:
        raise AllowlistError(f"Table allowlist violation: {sorted(illegal)}")

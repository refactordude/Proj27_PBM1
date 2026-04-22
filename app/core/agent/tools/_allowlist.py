"""도구용 테이블 allowlist 워커 (SAFE-01).

sql_safety.validate_and_sanitize 이후 두 번째 게이트로 동작한다.
sqlparse AST를 재귀적으로 걸어 FROM/JOIN 대상을 수집하고,
AgentConfig.allowed_tables 밖의 테이블을 참조하면 AllowlistError를 던진다.
서브쿼리·CTE·UNION·information_schema 등 4개 공격벡터를 모두 차단한다.
"""
from __future__ import annotations

import sqlparse
from sqlparse.sql import Identifier, IdentifierList, Parenthesis
from sqlparse.tokens import Keyword

_TABLE_KEYWORDS = {
    "FROM", "JOIN", "INNER JOIN", "LEFT JOIN", "RIGHT JOIN",
    "FULL JOIN", "CROSS JOIN", "LEFT OUTER JOIN", "RIGHT OUTER JOIN",
    "UPDATE", "INTO",
}
_FORBIDDEN_SCHEMAS = {"information_schema", "mysql", "performance_schema", "sys"}


class AllowlistError(Exception):
    """테이블 allowlist 위반을 알린다. 호출부는 ToolResult 오류 문자열로 매핑한다."""


def _extract_tables(sql: str) -> set[str]:
    parsed = sqlparse.parse(sql)
    if not parsed:
        return set()
    tables: set[str] = set()

    def _record(ident) -> None:
        parent = ident.get_parent_name()
        real = ident.get_real_name()
        if real is None:
            return
        full = f"{parent}.{real}" if parent else real
        tables.add(full.lower())

    def _recurse(tok_list) -> None:
        prev_kw: str | None = None
        for tok in tok_list.tokens:
            if tok.is_whitespace:
                continue
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
                elif tok.ttype is Keyword:
                    prev_kw = None
            # Always descend into any group — catches CTE bodies, WHERE-IN subqueries, UNION branches.
            if tok.is_group and not isinstance(tok, (Identifier, IdentifierList)):
                _recurse(tok)

    for stmt in parsed:
        _recurse(stmt)
    return tables


def _check_table_allowlist(sql: str, allowed: list[str]) -> None:
    """사전 경계검사. 위반 시 AllowlistError. 정상 시 None."""
    lowered = sql.lower()
    # Belt-and-suspenders: forbidden schemas are never legal even if mis-added to allowlist.
    for forbidden in _FORBIDDEN_SCHEMAS:
        if forbidden in lowered:
            raise AllowlistError(f"Forbidden schema referenced: {forbidden}")
    tables = _extract_tables(sql)
    allowed_lc = {t.lower() for t in allowed}
    illegal = tables - allowed_lc
    if illegal:
        raise AllowlistError(f"Table allowlist violation: {sorted(illegal)}")

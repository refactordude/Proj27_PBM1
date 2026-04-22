"""DB 스키마 → LLM 프롬프트에 넣을 텍스트 요약."""
from __future__ import annotations


def summarize(schema: dict[str, list[dict]], *, max_tables: int = 40, max_cols: int = 30) -> str:
    if not schema:
        return "(스키마 정보 없음)"
    lines: list[str] = []
    for table, cols in list(schema.items())[:max_tables]:
        col_parts: list[str] = []
        for col in cols[:max_cols]:
            marker = " PK" if col.get("pk") else ""
            nullable = "" if col.get("nullable", True) else " NOT NULL"
            col_parts.append(f"  - {col['name']} {col['type']}{nullable}{marker}")
        more = "" if len(cols) <= max_cols else f"\n  ... (+{len(cols) - max_cols} columns)"
        lines.append(f"TABLE `{table}`:\n" + "\n".join(col_parts) + more)
    if len(schema) > max_tables:
        lines.append(f"... (+{len(schema) - max_tables} more tables)")
    return "\n\n".join(lines)


def extract_sql_from_response(text: str) -> str:
    """LLM 응답에서 첫 번째 ```sql 코드블럭``` 을 추출. 없으면 원문을 리턴."""
    if not text:
        return ""
    marker = "```sql"
    idx = text.lower().find(marker)
    if idx >= 0:
        start = idx + len(marker)
        end = text.find("```", start)
        if end > start:
            return text[start:end].strip()
    if text.strip().startswith("```"):
        stripped = text.strip().strip("`")
        return stripped.strip()
    return text.strip()

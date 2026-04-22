"""UFS 스펙 §1–§7 문서 조회 도구 (TOOL-05).

7개의 스펙 섹션 텍스트 파일(app/core/agent/tools/spec/section_{1..7}.txt)을
모듈 임포트 시 한 번만 읽어 _SPEC_DOCS 딕셔너리에 적재한다. 이후 호출은
O(1) 메모리 조회. 파일이 없으면 예외 대신 fallback 문자열을 반환한다.
"""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from app.core.agent.context import AgentContext
from app.core.agent.tools._base import ToolResult

_SPEC_DIR = Path(__file__).resolve().parent / "spec"


def _load_spec_docs() -> dict[int, str]:
    """스펙 섹션 텍스트를 한 번만 디스크에서 읽어 딕셔너리로 반환."""
    docs: dict[int, str] = {}
    for i in range(1, 8):
        p = _SPEC_DIR / f"section_{i}.txt"
        if p.exists():
            docs[i] = p.read_text(encoding="utf-8")
        else:
            docs[i] = f"(section_{i}.txt missing — not yet authored)"
    return docs


# 임포트 시점에 1회 로드 — 이후 호출은 디스크 I/O 없음.
_SPEC_DOCS: dict[int, str] = _load_spec_docs()


class GetSchemaDocsArgs(BaseModel):
    """get_schema_docs 도구 인자. Pydantic이 [1, 7] 범위를 강제."""

    section: int = Field(
        ..., ge=1, le=7, description="UFS spec section number, 1-7"
    )


class GetSchemaDocsTool:
    """UFS 스펙 §N 본문 텍스트를 ToolResult.content로 반환."""

    name = "get_schema_docs"
    args_model = GetSchemaDocsArgs

    def __call__(
        self, ctx: AgentContext, args: GetSchemaDocsArgs
    ) -> ToolResult:
        # ctx는 Protocol 시그니처 준수용 — 본 도구는 컨텍스트를 소비하지 않음.
        return ToolResult(content=_SPEC_DOCS[args.section])


get_schema_docs_tool = GetSchemaDocsTool()

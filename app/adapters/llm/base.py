"""LLM 어댑터 추상 클래스."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable

from app.core.config import LLMConfig

SQL_SYSTEM_PROMPT = (
    "당신은 MySQL 전문 데이터 분석가입니다. 사용자의 자연어 질문을 읽고 "
    "안전한 SELECT 쿼리(또는 SHOW/DESCRIBE)만을 생성합니다.\n"
    "규칙:\n"
    "1) INSERT/UPDATE/DELETE/DROP/ALTER/TRUNCATE/GRANT/REVOKE/USE 등 쓰기 구문을 사용하지 마세요.\n"
    "2) 결과가 과도하게 커지지 않도록 적절한 LIMIT을 포함하세요 (명시되지 않으면 최대 1000).\n"
    "3) 가능한 경우 컬럼 이름을 명시하고 `SELECT *` 남용을 피하세요.\n"
    "4) 답변은 SQL 한 문장만 ```sql 코드블럭``` 으로 출력하고, 추가 설명은 코드블럭 뒤에 짧게 쓰세요.\n"
    "5) 스키마에 없는 테이블/컬럼을 추측하지 말고, 없으면 명시적으로 부족함을 알려주세요."
)


class LLMAdapter(ABC):
    def __init__(self, config: LLMConfig) -> None:
        self.config = config

    @abstractmethod
    def generate_sql(
        self,
        question: str,
        schema_summary: str,
        history: list[dict] | None = None,
    ) -> str:
        """자연어 질문 → SQL(코드블럭 포함 가능) 문자열"""

    @abstractmethod
    def stream_text(self, prompt: str) -> Iterable[str]:
        """프롬프트에 대한 일반 텍스트 스트림(차트 설명 등에 사용)"""

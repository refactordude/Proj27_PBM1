"""DB 어댑터 추상 클래스.

모든 DB 구현체는 이 인터페이스를 준수한다. 신규 DB(PostgreSQL 등)는
base를 상속해 구현하고 registry에 등록하면 설정 UI에서 바로 사용 가능.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

from app.core.config import DatabaseConfig


class DBAdapter(ABC):
    def __init__(self, config: DatabaseConfig) -> None:
        self.config = config

    @abstractmethod
    def test_connection(self) -> tuple[bool, str]:
        """(성공 여부, 메시지)"""

    @abstractmethod
    def list_tables(self) -> list[str]: ...

    @abstractmethod
    def get_schema(self, tables: list[str] | None = None) -> dict[str, list[dict]]:
        """table_name -> list of {name, type, nullable, pk} 컬럼 정보"""

    @abstractmethod
    def run_query(self, sql: str) -> pd.DataFrame: ...

    def dispose(self) -> None:  # pragma: no cover - optional cleanup
        return None

"""MySQL DB 어댑터.

SQLAlchemy engine + pymysql 드라이버를 사용한다.
readonly=true인 경우 세션을 read-only transaction으로 강제한다.
"""
from __future__ import annotations

from urllib.parse import quote_plus

import pandas as pd
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

from app.adapters.db.base import DBAdapter
from app.core.config import DatabaseConfig


class MySQLAdapter(DBAdapter):
    def __init__(self, config: DatabaseConfig) -> None:
        super().__init__(config)
        self._engine: Engine | None = None

    def _get_engine(self) -> Engine:
        if self._engine is not None:
            return self._engine
        c = self.config
        password = quote_plus(c.password or "")
        user = quote_plus(c.user or "")
        url = f"mysql+pymysql://{user}:{password}@{c.host}:{c.port}/{c.database}"
        self._engine = create_engine(
            url,
            pool_pre_ping=True,
            pool_recycle=1800,
            connect_args={"connect_timeout": 5},
        )
        return self._engine

    def test_connection(self) -> tuple[bool, str]:
        try:
            with self._get_engine().connect() as conn:
                conn.execute(text("SELECT 1"))
            return True, "연결 성공"
        except Exception as exc:  # pragma: no cover - network dependent
            return False, f"연결 실패: {exc}"

    def list_tables(self) -> list[str]:
        inspector = inspect(self._get_engine())
        return sorted(inspector.get_table_names())

    def get_schema(self, tables: list[str] | None = None) -> dict[str, list[dict]]:
        inspector = inspect(self._get_engine())
        target = tables or self.list_tables()
        schema: dict[str, list[dict]] = {}
        for t in target:
            try:
                pk_cols = set(inspector.get_pk_constraint(t).get("constrained_columns") or [])
            except Exception:
                pk_cols = set()
            cols = []
            for col in inspector.get_columns(t):
                cols.append(
                    {
                        "name": col["name"],
                        "type": str(col.get("type", "")),
                        "nullable": bool(col.get("nullable", True)),
                        "pk": col["name"] in pk_cols,
                    }
                )
            schema[t] = cols
        return schema

    def run_query(self, sql: str) -> pd.DataFrame:
        readonly = self.config.readonly
        with self._get_engine().connect() as conn:
            if readonly:
                try:
                    conn.execute(text("SET SESSION TRANSACTION READ ONLY"))
                except Exception:
                    # 일부 버전/권한에서 실패할 수 있음; sql_safety가 1차 방어
                    pass
            return pd.read_sql(text(sql), conn)

    def dispose(self) -> None:
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None

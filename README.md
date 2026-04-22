# 사내 데이터 플랫폼 (Streamlit)

PRD v0.1 기반 MVP. MySQL 조회·비교·Export, Grafana 임베드, LLM 기반 자연어 → SQL 질의응답을
하나의 Streamlit 앱에서 제공합니다.

## 빠른 시작

```bash
# 1. 가상환경
python -m venv .venv
source .venv/bin/activate

# 2. 의존성
pip install -r requirements.txt

# 3. 설정
cp config/settings.example.yaml config/settings.yaml
cp .env.example .env
# .env 파일을 열어 OPENAI_API_KEY 입력

# 4. 실행
streamlit run app/main.py
```

첫 로그인 계정: `admin` / `admin1234` (반드시 배포 전에 교체)

## 기능 (PRD F1~F6)

| 페이지 | 기능 |
|---|---|
| 🏠 Home | 요약 카드, Grafana 임베드, 최근 질의 내역 |
| 🔍 Explorer | 테이블 선택 → 필터·정렬·페이징 → CSV/Excel Export |
| ↔️ Compare | 두 쿼리 결과 좌우 비교, 차이 하이라이트 |
| 🤖 Ask AI | 자연어 → SQL 미리보기 → 확인 후 실행 → 결과/차트 |
| 📊 Grafana | 등록된 대시보드 목록 및 kiosk 임베드 |
| ⚙️ Settings | DB/LLM/Grafana CRUD · 연결 테스트 |

## 아키텍처

- **Adapter 패턴**으로 DB와 LLM 추상화: 신규 DB/모델은 어댑터 클래스 + registry 등록만으로 연동
- **SQL 안전성**: `sql_safety.py`가 SELECT 계열만 허용, `LIMIT` 자동 주입, DDL/DML 차단
- **읽기 전용 계정 강제**: Settings에서 `readonly: true` 옵션 + 런타임 검증 이중 보호
- **로깅**: 모든 쿼리와 LLM 호출을 `logs/queries.log`, `logs/llm.log`에 기록

## 디렉토리

```
app/
  main.py              진입점 (st.navigation)
  pages/               F1~F6 각 페이지
  adapters/
    db/                DB 어댑터 (mysql + registry)
    llm/               LLM 어댑터 (openai, ollama + registry)
  core/                config/auth/logger/sql_safety/session
  utils/               schema/export/viz
config/
  settings.yaml        DB/LLM/Grafana 등록 정보 (UI에서 편집)
  auth.yaml            사용자 계정 (bcrypt 해시)
logs/
```

## 새 DB 추가 예 (PostgreSQL)

1. `app/adapters/db/postgres.py` 작성 (`DBAdapter` 상속)
2. `app/adapters/db/registry.py`에 `"postgres": PostgresAdapter` 등록
3. Settings UI에서 해당 타입 선택해 연결 정보 입력

## 새 LLM 추가 예 (Anthropic)

1. `app/adapters/llm/anthropic_adapter.py` 작성 (`LLMAdapter` 상속)
2. `app/adapters/llm/registry.py`에 등록
3. Settings UI에서 선택

## Docker

```bash
docker compose up --build
# http://localhost:8501
```

## 보안 체크리스트 (PRD §5.2)

- [ ] LLM용 MySQL 계정은 `GRANT SELECT`만 부여
- [ ] `config/auth.yaml`의 기본 admin 비밀번호 변경
- [ ] `cookie.key` 변경
- [ ] `config/settings.yaml`은 `.gitignore` 처리 (기본 포함됨)
- [ ] 사내망/VPN 뒤에서만 노출

## 미포함 (PRD §1.3, v2+)

- RBAC 세분화 권한
- 다중 DB 동시 연결
- SSO 연동
- 외부 공개

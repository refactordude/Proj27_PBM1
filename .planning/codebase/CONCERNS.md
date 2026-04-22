# Codebase Concerns

**Analysis Date:** 2026-04-22

## Security Concerns

**Hardcoded Default Credentials:**
- Issue: Default admin account with static password hash in production config file
- Files: `config/auth.yaml` (line 9)
- Impact: Anyone with access to the repository or deployed config can log in as admin. Compromises application security from first deploy.
- Fix approach: Require credential rotation on first deployment. Generate unique password hash during setup wizard. Document in Security checklist.

**Insecure Cookie Secret:**
- Issue: Cookie encryption key is placeholder string in version control
- Files: `config/auth.yaml` (line 15)
- Impact: Session tokens are not cryptographically protected. Session hijacking risk.
- Fix approach: Generate random 32-byte secret on deployment. Make this non-optional in setup. Add warning to README.

**Credentials in Settings Files:**
- Issue: Database passwords, API keys stored in `config/settings.yaml` (edited via UI, not .env)
- Files: `app/core/config.py` (DatabaseConfig line 26, LLMConfig line 35), `app/pages/settings_page.py` (password input line 54, api_key input line 108)
- Impact: Credentials are persisted to disk in plaintext YAML. If settings.yaml is accidentally committed, credentials leak.
- Fix approach: Move all secrets to environment variables. Settings file should only contain non-sensitive config (model names, row limits). Require env vars for passwords/API keys.

**Missing Input Validation on User Inputs:**
- Issue: WHERE clause and ORDER BY inputs in Explorer page are not validated before SQL assembly
- Files: `app/pages/explorer.py` (lines 56-67)
- Impact: User can inject SQL fragments that bypass safety checks. Example: WHERE clause `1 UNION SELECT ...` could extract data.
- Fix approach: Implement parameterized query building or use SQLAlchemy's text() with bind parameters exclusively.

**API Key in Logs and Error Messages:**
- Issue: Exception stack traces from OpenAI/Ollama calls may contain API keys in response headers or error details
- Files: `app/pages/home.py` (lines 89-96), `app/pages/settings_page.py` (lines 80-90), `app/pages/compare.py` (lines 59-66)
- Impact: Secrets leak into UI error messages and log files
- Fix approach: Sanitize exception messages before logging. Catch and redact credential-bearing exceptions at library boundaries.

## Test Coverage Gaps

**No Unit/Integration Tests:**
- What's not tested: All adapter implementations, config loading/saving, auth flow, SQL safety validation
- Files: Entire codebase (no test directory exists)
- Risk: Regressions in SQL safety could allow DML injection. Config serialization bugs could corrupt settings. Auth changes could bypass authentication.
- Priority: High

**SQL Safety Logic Untested:**
- What's not tested: Edge cases in `sql_safety.py` (semicolon splitting, comment handling, regex patterns)
- Files: `app/core/sql_safety.py`
- Risk: Sophisticated SQL injection attacks (nested comments, Unicode tricks) may bypass validation
- Priority: High

**Adapter Registry Untested:**
- What's not tested: Fallback behavior when adapter registration is missing
- Files: `app/adapters/db/registry.py`, `app/adapters/llm/registry.py`
- Risk: Silent failures if new adapters aren't registered correctly
- Priority: Medium

## Error Handling Issues

**Overly Broad Exception Handling:**
- Issue: Catch `except Exception:` throughout without specific exception types
- Files: `app/adapters/db/mysql.py` (lines 57, 78), `app/pages/compare.py` (line 118)
- Impact: Masks real bugs. Silently swallows connection errors, permission errors, and data corruption errors.
- Fix approach: Catch specific exceptions (sqlalchemy.exc.*, requests.exceptions.*). Let unexpected errors bubble up.

**Silent Transaction Failures:**
- Issue: MySQL readonly mode enforcement silently fails if database doesn't support it
- Files: `app/adapters/db/mysql.py` (lines 75-80)
- Impact: readonly flag becomes a false sense of security. Write queries may succeed on misconfigured databases.
- Fix approach: Raise error if readonly enforcement fails. Make it mandatory or document the limitation.

**Generic Exception Messages to Users:**
- Issue: Exceptions are converted to strings and shown in UI without context
- Files: `app/pages/home.py` (line 96, 148), `app/pages/explorer.py` (lines 30, 50, 104), `app/pages/settings_page.py` (line 34)
- Impact: Users see raw error strings. Database connection errors, network issues, and auth failures all blend together.
- Fix approach: Create custom exception types with user-friendly messages. Log full exceptions server-side.

## Missing Error Handling

**No Timeout Protection on LLM Calls:**
- Issue: OpenAI/Ollama API calls lack timeout on non-streaming requests
- Files: `app/adapters/llm/openai_adapter.py` (lines 50-56)
- Impact: Hangs if LLM service is slow or offline
- Fix approach: Add `timeout=30` to `client.chat.completions.create()` calls

**No Retry Logic on Transient Failures:**
- Issue: Network errors on DB queries and LLM calls immediately fail without retry
- Files: `app/adapters/db/mysql.py`, `app/adapters/llm/*.py`
- Impact: Temporary network hiccups cause user-facing failures
- Fix approach: Implement exponential backoff for transient errors (connection reset, timeouts)

**No Handling for Empty LLM Response:**
- Issue: If LLM returns empty response, `extract_sql_from_response("")` returns empty string, then executed as invalid SQL
- Files: `app/utils/schema.py` (lines 22-36), `app/pages/home.py` (line 81)
- Impact: Confusing error when LLM silently fails
- Fix approach: Check for empty SQL before adding to chat history. Show explicit "LLM did not generate SQL" message.

**Database Connection Pooling Not Monitored:**
- Issue: Pool configuration has 1800s recycle timeout but no monitoring/alerting
- Files: `app/adapters/db/mysql.py` (line 33)
- Impact: Stale connections can cause latency spikes without visibility
- Fix approach: Add connection pool metrics to logging

## Performance Bottlenecks

**No Query Timeout Enforcement:**
- Issue: Long-running queries (UNION SELECT all, GROUP BY without index) can hang the app
- Files: `app/adapters/db/mysql.py` (line 81)
- Impact: User browser blocks indefinitely, resource exhaustion on database
- Fix approach: Add `max_execution_time` hint to all executed SQL. Timeout at DB adapter level (3s default, configurable).

**Schema Caching Never Expires:**
- Issue: `get_schema()` results cached in Streamlit session but never invalidated
- Files: `app/pages/home.py` (line 67), `app/pages/explorer.py` (line 48)
- Impact: Schema changes on database don't reflect until session expires or app restarted
- Fix approach: Add optional `refresh_schema` button. Cache with TTL (5 minutes default).

**Full Table Scan in Explorer When No LIMIT:**
- Issue: If row limit is set very high (100k), Explorer loads entire result set into memory
- Files: `app/pages/explorer.py` (lines 40-41)
- Impact: Large tables cause OOM on app server
- Fix approach: Add hard ceiling to row limit (5000 max). Implement pagination instead of loading all rows.

**No Index on Session State Deque:**
- Issue: Recent queries stored in deque with fixed maxlen but linear search when updating
- Files: `app/core/session.py` (lines 28-34)
- Impact: Negligible for current limits but doesn't scale to thousands of queries
- Fix approach: Not critical for MVP, but add to v2 backlog.

## Fragile Areas

**SQL Extraction from LLM Response Fragile:**
- Files: `app/utils/schema.py` (lines 22-36)
- Why fragile: Regex-based extraction assumes LLM follows exact format. If LLM uses different markdown, non-English language, or mixed code styles, extraction fails silently.
- Safe modification: Add fallback to detect code blocks using indentation/Markdown ALT. Test with multiple LLM outputs.
- Test coverage: Zero. No test cases for edge cases (multiple code blocks, no code blocks, malformed markdown).

**Settings YAML Deserialization:**
- Files: `app/core/config.py` (lines 59-65)
- Why fragile: Uses bare `yaml.safe_load()` without schema validation before Pydantic. If YAML is malformed or missing required fields, Pydantic errors are unclear.
- Safe modification: Add try/catch around yaml.safe_load() with specific error messages. Validate schema before Pydantic parsing.
- Test coverage: Zero. No test for corrupted settings.yaml.

**Auth with Streamlit Authenticator Version Compatibility:**
- Files: `app/core/auth.py` (lines 40-44, 59-62)
- Why fragile: Catches TypeError to support multiple library versions. If library changes again, breaks silently.
- Safe modification: Pin to exact streamlit-authenticator version in requirements.txt. Remove try/except.
- Test coverage: Zero.

**Dataframe Styling Fallback in Compare:**
- Files: `app/pages/compare.py` (lines 115-119)
- Why fragile: Catches broad Exception and falls back to unstyled dataframe. Masks real errors.
- Safe modification: Catch specific styling errors (AttributeError, ValueError). Let connection errors bubble.
- Test coverage: Zero.

## Scaling Limits

**Single Adapter Instance Per Database:**
- Current capacity: One user session = one engine instance. Multiple tabs = multiple engines.
- Limit: Each engine creates new connection pool (pool_size=5 default). 10 concurrent users = 50+ connections.
- Scaling path: Implement global adapter singleton with ref counting. Or use single app-wide engine (requires session management).

**No Pagination in Results:**
- Current capacity: Up to 100k rows in memory (configurable)
- Limit: Larger queries crash browser. OOM on app server.
- Scaling path: Implement server-side pagination with LIMIT/OFFSET or streaming (Arrow format).

**Logs Directory Unbounded Growth:**
- Current capacity: Logs append indefinitely to queries.log and llm.log
- Limit: After months, log files multi-gigabyte, app startup slow, disk full risk
- Scaling path: Implement log rotation (RotatingFileHandler) with size/time based limits. 50MB per file, keep 10 files.

**No Metrics or Observability:**
- Current capacity: Zero metrics. Cannot detect bottlenecks, failures, or abuse.
- Scaling path: Add Prometheus metrics (query latency, error rates, LLM token usage). Add structured logging (JSON format).

## Dependencies at Risk

**streamlit-authenticator 0.3.3 Pinned:**
- Risk: Very old version with potential security issues. Library is minimally maintained.
- Impact: No password reset, no SSO, authentication UI changes in newer Streamlit break it.
- Migration plan: Evaluate migration to Auth0, Azure AD, or Keycloak for production. Interim: upgrade to latest 0.4.x if compatible.

**python-dotenv for Secrets Loading:**
- Risk: Reads .env into os.environ, which is readable from any subprocess. No encryption.
- Impact: If subprocess spawned or process dumped, secrets visible
- Migration plan: Move to secure vault (HashiCorp Vault, AWS Secrets Manager) for production. Keep dotenv for dev only.

**No Type Checking in Runtime:**
- Risk: Pydantic models used but no runtime validation of database responses. SQLAlchemy returns dicts, not typed objects.
- Impact: Silent data type errors. Example: `rows` column could be string, not int.
- Migration plan: Add stricter type hints and pydantic validation on all external data boundaries.

## Known Bugs / Limitations

**Chat History Not Persisted Across Sessions:**
- Files: `app/core/session.py`
- Impact: User's conversation with LLM resets when page reloads or session expires. Limits multi-turn context.
- Workaround: User can manually re-paste previous context.
- Priority: Medium (v2 feature).

**Settings UI Accepts Invalid Database Types:**
- Files: `app/pages/settings_page.py` (line 47)
- Problem: Selectbox only shows registered types, but if user directly edits settings.yaml with unsupported type, app crashes at runtime.
- Fix: Validate database type at load time. Show clear error.

**No Concurrency Control on Settings Edits:**
- Files: `app/core/config.py`, `app/core/runtime.py`
- Problem: If two users edit settings simultaneously, last write wins. Potential race condition on file write.
- Fix: Implement file locking (fcntl.flock) or atomic writes (write to temp, rename).

**Explorer's Search Not Consistent:**
- Files: `app/pages/explorer.py` (line 110)
- Problem: Search is case-insensitive substring on string representation of values. Does not respect data types. "1" matches "10" or "100".
- Fix: Implement typed search (number range, date range, exact match options).

## Documentation Gaps

**Security Checklist Incomplete:**
- Files: `README.md` (lines 79-86)
- Gap: No documented process for rotating credentials. No guidance on .env file permissions. No instructions for database user privilege setup.
- Impact: Deployers may skip security steps.

**No Runbook for Production Deployment:**
- Gap: README covers local dev only. No docker compose configuration for production (commented out MySQL).
- Impact: Deployers unsure of production setup, security, monitoring.

**No Schema Documentation for Settings:**
- Gap: config/settings.example.yaml doesn't exist (referenced in README but not in repo)
- Impact: Users must infer settings structure from UI or code.

---

*Concerns audit: 2026-04-22*

"""에이전트 ReAct 루프 — OpenAI tool-calling 기반 턴 실행기.

run_agent_turn(user_message, ctx)는 AgentStep 이벤트를 yield하며,
max_steps / timeout_s / max_context_tokens 예산이 소진되면 강제 종료 호출을
한 번 발행해 final_answer를 반환한다.
모든 chat.completions.create 호출은 ParallelToolCalls=False + _REQUEST_TIMEOUT을 사용한다.
Streamlit 의존성 없음 — 순수 Python 모듈.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Iterator, Literal

from pydantic import ValidationError

from app.adapters.llm.openai_adapter import _REQUEST_TIMEOUT
from app.core.agent.context import AgentContext
from app.core.agent.tools import TOOL_REGISTRY
from app.core.agent.tools._base import ToolResult
from app.core.logger import log_llm


@dataclass
class AgentStep:
    """루프가 yield하는 단일 이벤트. Phase 4 UI는 step_type 분기만 하면 된다."""

    step_type: Literal["tool_call", "tool_result", "final_answer", "budget_exhausted"]
    step_index: int
    tool_name: str | None = None
    tool_args: dict[str, Any] | None = None
    content: str = ""
    sql: str | None = None
    df_ref: str | None = None
    chart: Any | None = None
    duration_ms: int | None = None
    error: str | None = None
    budget_exhausted: bool = False


_SYSTEM_PROMPT = (
    "You are a UFS (Universal Flash Storage) database assistant. "
    "You have tools to introspect schema, run SELECT queries against the "
    "ufs_data table, normalize and pivot results, fetch UFS spec sections, "
    "and produce Plotly charts. Use get_schema first if you need orientation. "
    "Keep final answers concise, cite the columns you used, and prefer charts "
    "for cross-device comparisons."
)

# char/4 휴리스틱 — CONTEXT.md의 토큰 추정 결정사항 반영.
_CHARS_PER_TOKEN = 4


def _build_openai_tools() -> list[dict[str, Any]]:
    """TOOL_REGISTRY → OpenAI chat.completions tools=[] 스키마 리스트."""
    tools: list[dict[str, Any]] = []
    for tool in TOOL_REGISTRY.values():
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": getattr(tool, "description", "") or "",
                    "parameters": tool.args_model.model_json_schema(),
                },
            }
        )
    return tools


def _estimate_tokens(text: str) -> int:
    """char/4 휴리스틱 — CONTEXT.md 기준 보수적 상한."""
    if not text:
        return 0
    return len(text.encode("utf-8")) // _CHARS_PER_TOKEN


def _forced_finalization(
    *,
    client: Any,
    model: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    user: str,
    step_index: int,
) -> tuple[str, int]:
    """tool_choice='none' 강제 종료 호출. (final_text, duration_ms) 반환.

    타임아웃 초과 시에도 완료까지 대기 (soft timeout per AGENT-05).
    """
    start = time.perf_counter()
    error: str | None = None
    final_text = ""
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools,
            tool_choice="none",
            parallel_tool_calls=False,
            timeout=_REQUEST_TIMEOUT,
        )
        final_text = (resp.choices[0].message.content or "").strip()
    except Exception as exc:  # noqa: BLE001
        error = str(exc)
        final_text = f"[loop error during forced finalization: {exc}]"
    duration_ms = int((time.perf_counter() - start) * 1000)
    log_llm(
        user=user,
        model=model,
        question="",
        duration_ms=duration_ms,
        error=error,
        step_index=step_index,
        tool_call_names="",
    )
    return final_text, duration_ms


def run_agent_turn(
    user_message: str,
    ctx: AgentContext,
) -> Iterator[AgentStep]:
    """ReAct 루프를 실행하며 AgentStep을 yield한다.

    AGENT-01: 병렬 도구 호출 금지 + 자동 도구 선택 (main call).
    AGENT-02: 최종 답변은 tool_calls 없는 assistant 메시지에서 yield.
    AGENT-03: max_steps는 tool 호출 단위로 증가(응답당이 아님).
    AGENT-04: 예산 소진 시 강제 종료(도구 선택 금지) 1회.
    AGENT-05: time.monotonic() 기반 soft timeout — create() 직전 체크.
    AGENT-06: 누적 토큰 (prompt+completion usage + tool_result char/4) 추적.
    OBS-02: 매 create() 라운드트립마다 log_llm() 한 줄 기록.
    """
    client = ctx.llm_adapter._client()  # OpenAIAdapter._client() → openai.OpenAI
    tools = _build_openai_tools()
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    cfg = ctx.config
    turn_start = time.monotonic()
    tool_call_count = 0
    cumulative_tokens = 0
    loop_step_index = 0  # increments per create() round-trip

    while True:
        # Budget checks BEFORE each create() — AGENT-03/05/06.
        elapsed = time.monotonic() - turn_start
        steps_exhausted = tool_call_count >= cfg.max_steps
        timeout_exceeded = elapsed >= cfg.timeout_s
        tokens_exhausted = cumulative_tokens >= cfg.max_context_tokens

        if steps_exhausted or timeout_exceeded or tokens_exhausted:
            final_text, dur_ms = _forced_finalization(
                client=client,
                model=cfg.model,
                messages=messages,
                tools=tools,
                user=ctx.user,
                step_index=loop_step_index,
            )
            yield AgentStep(
                step_type="final_answer",
                step_index=loop_step_index,
                content=final_text,
                duration_ms=dur_ms,
                budget_exhausted=True,
            )
            return

        # Main create() call — AGENT-01 (병렬 도구 호출 금지 리터럴).
        start = time.perf_counter()
        error: str | None = None
        resp = None
        try:
            resp = client.chat.completions.create(
                model=cfg.model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                parallel_tool_calls=False,
                timeout=_REQUEST_TIMEOUT,
            )
        except Exception as exc:  # noqa: BLE001
            error = str(exc)
        dur_ms = int((time.perf_counter() - start) * 1000)

        # Gather tool_call names for OBS-02 logging.
        tool_names_on_response: list[str] = []
        if resp is not None and resp.choices:
            msg = resp.choices[0].message
            if getattr(msg, "tool_calls", None):
                tool_names_on_response = [tc.function.name for tc in msg.tool_calls]

        log_llm(
            user=ctx.user,
            model=cfg.model,
            question=user_message if loop_step_index == 0 else "",
            duration_ms=dur_ms,
            error=error,
            step_index=loop_step_index,
            tool_call_names=",".join(tool_names_on_response),
        )

        if error is not None or resp is None:
            yield AgentStep(
                step_type="final_answer",
                step_index=loop_step_index,
                content=f"[loop error: {error}]",
                duration_ms=dur_ms,
                error=error,
            )
            return

        # Token budget update — approximate prompt+completion tokens from usage.
        usage = getattr(resp, "usage", None)
        if usage is not None:
            cumulative_tokens += int(
                getattr(usage, "prompt_tokens", 0) + getattr(usage, "completion_tokens", 0)
            )

        assistant_msg = resp.choices[0].message
        tool_calls = getattr(assistant_msg, "tool_calls", None) or []

        # Terminal branch (AGENT-02): no tool_calls → final answer.
        if not tool_calls:
            final_text = (assistant_msg.content or "").strip()
            yield AgentStep(
                step_type="final_answer",
                step_index=loop_step_index,
                content=final_text,
                duration_ms=dur_ms,
            )
            return

        # Append the assistant message (with tool_calls) to conversation history.
        # Convert tool_calls objects to dict form the OpenAI SDK accepts.
        messages.append(
            {
                "role": "assistant",
                "content": assistant_msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in tool_calls
                ],
            }
        )

        # Dispatch each tool call in order (병렬 호출 금지 → 보통 1개).
        for tc in tool_calls:
            tool_call_count += 1
            loop_step_index += 1
            tool_name = tc.function.name
            raw_args = tc.function.arguments or "{}"

            # Parse args dict for UI audit (tolerant to malformed JSON).
            parsed_args_dict: dict[str, Any]
            try:
                parsed_args_dict = json.loads(raw_args) if raw_args else {}
            except json.JSONDecodeError:
                parsed_args_dict = {}

            sql_for_step = (
                parsed_args_dict.get("sql") if tool_name == "run_sql" else None
            )

            # Yield tool_call event FIRST so the UI sees intent before dispatch.
            yield AgentStep(
                step_type="tool_call",
                step_index=loop_step_index,
                tool_name=tool_name,
                tool_args=parsed_args_dict,
                sql=sql_for_step,
            )

            # Dispatch via TOOL_REGISTRY — validate args via tool.args_model.
            tool = TOOL_REGISTRY.get(tool_name)
            t_start = time.perf_counter()
            tool_error: str | None = None
            result_content = ""
            df_ref: str | None = None
            chart: Any | None = None

            if tool is None:
                tool_error = f"unknown tool: {tool_name}"
                result_content = f"Tool '{tool_name}' is not registered."
            else:
                try:
                    args_obj = tool.args_model.model_validate_json(raw_args or "{}")
                except ValidationError as exc:
                    tool_error = f"argument validation failed: {exc}"
                    result_content = f"tool argument error: {exc}"
                except Exception as exc:  # noqa: BLE001
                    tool_error = f"argument parse failed: {exc}"
                    result_content = f"tool argument error: {exc}"
                else:
                    # Thread tool_call_id into ctx so cache-writing tools can key by it.
                    ctx.current_tool_call_id = tc.id
                    try:
                        tool_result: ToolResult = tool(ctx, args_obj)
                        result_content = tool_result.content
                        df_ref = tool_result.df_ref
                        chart = tool_result.chart
                    except Exception as exc:  # noqa: BLE001
                        tool_error = str(exc)
                        result_content = f"tool execution failed: {exc}"
                    finally:
                        ctx.current_tool_call_id = None

            t_dur_ms = int((time.perf_counter() - t_start) * 1000)
            cumulative_tokens += _estimate_tokens(result_content)

            # Feed the tool response back into the conversation.
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result_content,
                }
            )

            yield AgentStep(
                step_type="tool_result",
                step_index=loop_step_index,
                tool_name=tool_name,
                tool_args=parsed_args_dict,
                content=result_content,
                sql=sql_for_step,
                df_ref=df_ref,
                chart=chart,
                duration_ms=t_dur_ms,
                error=tool_error,
            )

        loop_step_index += 1  # next create() round-trip index

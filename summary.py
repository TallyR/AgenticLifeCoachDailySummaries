# Generate Sarah's proactive check-in for a user from their full conversation
# history, then save + send it via Blooio.

import asyncio
import json
import uuid
from datetime import datetime, timezone

import anthropic

from message_api import TABLE, _get_client, send_message
from faro_summary_prompt import FARO_DAILY_PING_PROMPT
from faro_pause_prompt import FARO_PAUSE_PROMPT
from faro_time_api import (
    get_current_date_and_time_from_timezone,
    get_current_date_and_time_tool_definition,
)
from summary_enabled_api import LAST_N_MESSAGES, disable_summaries

# Created once and reused (keeps its connection pool warm). Reads
# ANTHROPIC_API_KEY from the environment (loaded from .env by message_api).
_llm = anthropic.AsyncAnthropic()

# On a failed send, wait this long and retry, up to this many times.
RETRY_DELAY_SECONDS = 10
MAX_RETRIES = 2

# Commitment tables, shared with the prompt service (AgenticLifeCoachPromptService).
REMINDER_TABLE = "ReminderToolTable"
EVENT_TABLE = "EventToolTable"
NAG_TABLE = "DailyNagTable"

# Max model turns in the agentic tool loop before giving up (safety cap).
TURN_LIMIT = 10


async def get_conversation(phone_number: str) -> list[dict]:
    """Return every message to or from `phone_number`, oldest first (by sent_at)."""
    client = await _get_client()
    response = await (
        client.table(TABLE)
        .select("*")
        .or_(
            f"from_phone_number.eq.{phone_number},"
            f"to_phone_number.eq.{phone_number}"
        )
        .order("sent_at")
        .execute()
    )
    return response.data


async def get_active_commitments(phone_number: str) -> str:
    """All reminders, events, and standing nags for this number, formatted for
    the prompt. Mirrors get_active_commitments in the prompt service so both
    surfaces describe the same board the same way. Returns "NONE" when empty."""
    client = await _get_client()
    reminders, events, nags = await asyncio.gather(
        client.table(REMINDER_TABLE)
        .select("*")
        .eq("user_number", phone_number)
        .execute(),
        client.table(EVENT_TABLE)
        .select("*")
        .eq("user_number", phone_number)
        .execute(),
        # NB: this table's column is user_phone_number, not user_number.
        client.table(NAG_TABLE)
        .select("*")
        .eq("user_phone_number", phone_number)
        .execute(),
    )

    lines = []
    for r in reminders.data:
        occurrences = (
            "repeats forever"
            if r["number_of_occurrences"] == -1
            else f"{r['number_of_occurrences']} occurrences left"
        )
        lines.append(
            f"REMINDER id={r['id']}: every {', '.join(r['days_of_week'])} at "
            f"{r['hour_to_be_triggered']}:{r['minute_to_be_triggered']:02d}:"
            f"{r['second_to_be_triggered']:02d} {r['am_or_pm']} "
            f"({r['timezone']}), {occurrences} — \"{r['note']}\""
        )
    for e in events.data:
        lines.append(
            f"EVENT id={e['id']}: {e['year']}-{e['month']:02d}-{e['day']:02d} "
            f"at {e['hour']}:{e['minute']:02d}:{e['second']:02d} "
            f"{e['am_or_pm']} ({e['timezone']}) — \"{e['note']}\""
        )
    for n in nags.data:
        lines.append(f"NAG id={n['id']}: \"{n['nag_note']}\"")

    return "\n".join(lines) if lines else "NONE"


def _render_history(rows: list[dict]) -> str:
    """Turn the conversation rows into timestamped plain-text lines for the prompt."""
    lines = []
    for row in rows:
        speaker = "Sarah" if row["from_phone_number"] == "AGENT" else "User"
        stamp = datetime.fromtimestamp(row["sent_at"], tz=timezone.utc).strftime(
            "%Y-%m-%d %H:%M UTC"
        )
        lines.append(f"[{stamp}] {speaker}: {row['message']}")
    return "\n".join(lines)


def _run_tool(block) -> dict:
    """Execute a tool_use block from the model and return a tool_result block."""
    print(f"tool call: {block.name}({block.input})")
    try:
        if block.name == "get_current_date_and_time_from_timezone":
            result = get_current_date_and_time_from_timezone(**block.input)
            print(f"tool result: {result}")
            content = json.dumps(result)
        else:
            print(f"tool error: unknown tool {block.name}")
            return {
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": f"Unknown tool: {block.name}",
                "is_error": True,
            }
    except Exception as exc:
        print(f"tool error: {exc!r}")
        return {
            "type": "tool_result",
            "tool_use_id": block.id,
            "content": f"Error: {exc!r}",
            "is_error": True,
        }
    return {"type": "tool_result", "tool_use_id": block.id, "content": content}


async def send_summary(phone_number: str, debug: bool = False) -> None:
    """Build context from this user's full conversation history, ask Sarah for a
    check-in message, then save it (from AGENT to the user) and send it via
    Blooio. Raises if no message is generated or if the send/save fails.

    When debug is True, the message is generated and printed but NOT sent or
    saved: no Blooio call and no DB write, so the system's outer state is left
    untouched (for a test harness)."""
    history, active_items = await asyncio.gather(
        get_conversation(phone_number),
        get_active_commitments(phone_number),
    )

    context = (
        f"<message_history>\n{_render_history(history)}\n</message_history>\n\n"
        f"<active_commitments>\n{active_items}\n</active_commitments>\n\n"
        "Write today's check-in message to send to this user."
    )

    messages = [{"role": "user", "content": context}]
    tools = [get_current_date_and_time_tool_definition()]

    # Agentic loop: let the model call the time tool (to resolve relative dates)
    # before it writes the ping. TURN_LIMIT caps the number of tool turns.
    for _ in range(TURN_LIMIT):
        response = await _llm.beta.messages.create(
            model="claude-fable-5",
            max_tokens=8192,
            system=FARO_DAILY_PING_PROMPT,
            messages=messages,
            tools=tools,
            betas=["server-side-fallback-2026-06-01"],
            fallbacks=[{"model": "claude-opus-4-8"}],
        )
        if response.stop_reason != "tool_use":
            break
        # Echo the assistant turn back verbatim (preserves thinking + tool_use
        # blocks, required when continuing on the same model) and answer every
        # tool call in a single user message.
        messages.append({"role": "assistant", "content": response.content})
        messages.append(
            {
                "role": "user",
                "content": [
                    _run_tool(b) for b in response.content if b.type == "tool_use"
                ],
            }
        )
    else:
        raise RuntimeError(
            f"send_summary hit TURN_LIMIT ({TURN_LIMIT}) without a final message"
        )

    reply = "".join(b.text for b in response.content if b.type == "text")
    # Only a clean finish is safe to send. end_turn is the sole success state
    # here; refusal or max_tokens (a truncated mid-message reply) must not go out.
    if response.stop_reason != "end_turn" or not reply.strip():
        raise RuntimeError(
            f"No usable summary (stop_reason={response.stop_reason})"
        )

    if debug:
        # Debug: don't touch outer state — no Blooio send, no DB save. Just show it.
        print(f"[DEBUG] would send to {phone_number}:\n{reply}")
        return

    # send_message posts to Blooio (raises on a non-2xx response), then saves
    # the row as from_phone_number="AGENT", to_phone_number=phone_number.
    # Retry the send on failure, reusing one idempotency key so a timed-out but
    # delivered send isn't duplicated; re-raise after MAX_RETRIES so main logs it.
    idempotency_key = str(uuid.uuid4())
    for attempt in range(MAX_RETRIES + 1):  # 1 initial try + MAX_RETRIES retries
        try:
            await send_message(phone_number, reply, idempotency_key=idempotency_key)
            return
        except Exception as exc:
            if attempt >= MAX_RETRIES:
                raise
            print(
                f"retry {phone_number}: attempt {attempt + 1} failed ({exc!r}); "
                f"retrying in {RETRY_DELAY_SECONDS}s"
            )
            await asyncio.sleep(RETRY_DELAY_SECONDS)


async def send_pause_notice(phone_number: str, debug: bool = False) -> None:
    """This user hasn't replied in LAST_N_MESSAGES messages. Generate a warm,
    personable note from their history telling them daily summaries are pausing
    until they text back (reminders keep running), send it, then permanently
    disable summaries via disable_summaries.

    When debug is True, the note is generated and printed but NOT sent, and
    summaries are NOT disabled — the system's outer state is left untouched."""
    history = await get_conversation(phone_number)

    context = (
        f"<message_history>\n{_render_history(history)}\n</message_history>\n\n"
        f"You have sent {LAST_N_MESSAGES} messages in a row with no reply from "
        "this user. Write them the pause message per your instructions."
    )

    response = await _llm.beta.messages.create(
        model="claude-fable-5",
        max_tokens=8192,
        system=FARO_PAUSE_PROMPT,
        messages=[{"role": "user", "content": context}],
        betas=["server-side-fallback-2026-06-01"],
        fallbacks=[{"model": "claude-opus-4-8"}],
    )

    reply = "".join(b.text for b in response.content if b.type == "text")
    if response.stop_reason != "end_turn" or not reply.strip():
        raise RuntimeError(
            f"No pause notice generated (stop_reason={response.stop_reason})"
        )

    if debug:
        print(
            f"[DEBUG] would send pause notice to {phone_number} and disable "
            f"summaries:\n{reply}"
        )
        return

    # Send first (retry with one stable idempotency key), and only disable
    # summaries once the notice actually went out — so a failed send retries next
    # run instead of silently pausing someone who never got told.
    idempotency_key = str(uuid.uuid4())
    for attempt in range(MAX_RETRIES + 1):  # 1 initial try + MAX_RETRIES retries
        try:
            await send_message(phone_number, reply, idempotency_key=idempotency_key)
            break
        except Exception as exc:
            if attempt >= MAX_RETRIES:
                raise
            print(
                f"retry {phone_number}: attempt {attempt + 1} failed ({exc!r}); "
                f"retrying in {RETRY_DELAY_SECONDS}s"
            )
            await asyncio.sleep(RETRY_DELAY_SECONDS)

    await disable_summaries(phone_number)


if __name__ == "__main__":
    async def main():
        # NOTE: this actually sends a real text via Blooio.
        #await send_summary("+18323346991")
        #str1 = await get_conversation("+18323346991")
        #print(_render_history(str1))
        await send_summary("+18323346991")

    asyncio.run(main())

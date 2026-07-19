# Generate Sarah's proactive check-in for a user from their full conversation
# history, then save + send it via Blooio.

import asyncio
from datetime import datetime, timezone

import anthropic

from message_api import TABLE, _get_client, send_message
from faro_summary_prompt import FARO_DAILY_PING_PROMPT

# Created once and reused (keeps its connection pool warm). Reads
# ANTHROPIC_API_KEY from the environment (loaded from .env by message_api).
_llm = anthropic.AsyncAnthropic()


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


async def send_summary(phone_number: str) -> None:
    """Build context from this user's full conversation history, ask Sarah for a
    check-in message, then save it (from AGENT to the user) and send it via
    Blooio. Raises if no message is generated or if the send/save fails."""
    history = await get_conversation(phone_number)

    context = (
        f"<message_history>\n{_render_history(history)}\n</message_history>\n\n"
        "Write today's check-in message to send to this user."
    )

    response = await _llm.beta.messages.create(
        model="claude-fable-5",
        max_tokens=4096,
        system=FARO_DAILY_PING_PROMPT,
        messages=[{"role": "user", "content": context}],
        betas=["server-side-fallback-2026-06-01"],
        fallbacks=[{"model": "claude-opus-4-8"}],
    )

    reply = "".join(b.text for b in response.content if b.type == "text")
    if response.stop_reason == "refusal" or not reply.strip():
        raise RuntimeError(
            f"No summary generated (stop_reason={response.stop_reason})"
        )

    # send_message posts to Blooio (raises on a non-2xx response), then saves
    # the row as from_phone_number="AGENT", to_phone_number=phone_number.
    await send_message(phone_number, reply)


if __name__ == "__main__":
    async def main():
        # NOTE: this actually sends a real text via Blooio.
        #await send_summary("+18323346991")
        #str1 = await get_conversation("+18323346991")
        #print(_render_history(str1))
        await send_summary("+18323346991")

    asyncio.run(main())

# Entry point: find every user in the MessageTable and send each their daily
# summary, one by one.

import asyncio
import random

from message_api import TABLE, _get_client
from summary import send_pause_notice, send_summary
from summary_enabled_api import (
    LAST_N_MESSAGES,
    has_recent_user_activity,
    is_summary_enabled,
)

# Numbers here are skipped entirely — no summary is generated or sent.
# Use the same format they appear as in the DB, e.g. "+18323346991".
BLOCKLIST: set[str] = {
    "+17147590563",
    "+16477214294",
    "+13134596070",
    "+16507098340",
    "+16317213888",
    "+15105604809",
    "+13462894196",
    "mathew@kuruvi.in",
    "+16464708544",
    "+16318270092",
    "+14704762943",
    "+12102627193",
    "+18324340684"
}

# Random wait between sends (seconds), so sends look less bot-like and avoid
# spam-filter / rate-limit issues.
MIN_DELAY_SECONDS = 50
MAX_DELAY_SECONDS = 120


async def get_all_phone_numbers() -> list[str]:
    """Every distinct user phone number in the MessageTable, excluding the
    "AGENT" sentinel. A number can appear as either the sender or the recipient.
    Pages through the table in 1000-row chunks so the default row cap on a plain
    select doesn't silently drop users."""
    client = await _get_client()
    numbers: set[str] = set()
    page_size = 1000
    start = 0
    while True:
        response = await (
            client.table(TABLE)
            .select("from_phone_number, to_phone_number")
            .range(start, start + page_size - 1)
            .execute()
        )
        rows = response.data
        for row in rows:
            numbers.add(row["from_phone_number"])
            numbers.add(row["to_phone_number"])
        if len(rows) < page_size:
            break
        start += page_size
    numbers.discard("AGENT")
    return sorted(numbers)


async def main(number: str | None = None, debug: bool = False) -> None:
    """Send each active user their daily summary, or a one-time pause notice if
    they've gone quiet. Pass a single `number` to run just that one and skip the
    db lookup of all users. With debug=True nothing is sent or written: the
    decision logic still runs and the message is generated and printed only."""
    numbers = [number] if number is not None else await get_all_phone_numbers()
    print(f"Processing {len(numbers)} number(s)." + (" [debug: no sends]" if debug else ""))
    for num in numbers:
        if num in BLOCKLIST:
            print(f"-> {num} (blocked, skipping)")
            continue
        try:
            # Opted out (summaries disabled) — send nothing.
            if not await is_summary_enabled(num):
                print(f"-> {num} (summaries disabled, skipping)")
                continue
            # Replied recently -> normal summary. Last LAST_N_MESSAGES all from
            # AGENT -> one-time pause notice (which then disables summaries).
            active = await has_recent_user_activity(num)
            kind = "summary" if active else (
                f"pause notice — no reply in {LAST_N_MESSAGES} messages"
            )
            # Pace real sends; in debug there's nothing to send, so don't wait.
            if debug:
                print(f"-> {num} {kind} [debug]")
            else:
                delay = random.randint(MIN_DELAY_SECONDS, MAX_DELAY_SECONDS)
                print(f"-> {num} {kind} (after {delay}s)")
                await asyncio.sleep(delay)
            if active:
                await send_summary(num, debug=debug)
            else:
                await send_pause_notice(num, debug=debug)
        except Exception as exc:
            # Don't let one bad number stop the rest.
            print(f"   failed for {num}: {exc!r}")


if __name__ == "__main__":
     asyncio.run(main())

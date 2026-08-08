# Entry point: find every user in the MessageTable and send each their daily
# summary, one by one.

import asyncio
import random

from message_api import TABLE, _get_client
from summary import send_summary

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
    "+14044317389"
}

# Random wait between sends (seconds), so sends look less bot-like and avoid
# spam-filter / rate-limit issues.
MIN_DELAY_SECONDS = 50
MAX_DELAY_SECONDS = 120


async def get_all_phone_numbers() -> list[str]:
    """Every distinct user phone number seen in the MessageTable, excluding the
    "AGENT" sentinel. A number can appear as either the sender or the recipient."""
    client = await _get_client()
    response = await (
        client.table(TABLE)
        .select("from_phone_number, to_phone_number")
        .execute()
    )
    numbers: set[str] = set()
    for row in response.data:
        numbers.add(row["from_phone_number"])
        numbers.add(row["to_phone_number"])
    numbers.discard("AGENT")
    return sorted(numbers)


async def main() -> None:
    numbers = await get_all_phone_numbers()
    print(f"Sending daily summaries to {len(numbers)} number(s).")
    for number in numbers:
        if number in BLOCKLIST:
            print(f"-> {number} (blocked, skipping)")
            continue
        delay = random.randint(MIN_DELAY_SECONDS, MAX_DELAY_SECONDS)
        print(f"-> {number} (after {delay}s)")
        await asyncio.sleep(delay)
        try:
            await send_summary(number)
        except Exception as exc:
            # Don't let one bad number stop summaries for everyone else.
            print(f"   failed for {number}: {exc!r}")


if __name__ == "__main__":
     asyncio.run(main())

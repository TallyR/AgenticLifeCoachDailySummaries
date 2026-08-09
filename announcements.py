# Blast a one-off announcement to every user in the MessageTable, one at a time
# with a delay between sends. Numbers in the shared BLOCKLIST are skipped.
#
# Paste the message into MESSAGE at the bottom, then run: python announcements.py

import asyncio
import random
import uuid

from main import BLOCKLIST
from message_api import TABLE, _get_client, send_message

# Random wait between people (seconds), so sends look less bot-like to the API.
MIN_DELAY_SECONDS = 50
MAX_DELAY_SECONDS = 120

# On a failed send, wait this long and retry, up to this many times.
RETRY_DELAY_SECONDS = 10
MAX_RETRIES = 2


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


async def send_announcement(number: str, message: str) -> bool:
    """Send one announcement to `number` via send_message. On failure, waits
    RETRY_DELAY_SECONDS and retries up to MAX_RETRIES times, reusing one
    idempotency key so a timed-out but delivered send isn't duplicated. Prints
    and returns whether it ultimately succeeded; never raises."""
    idempotency_key = str(uuid.uuid4())
    for attempt in range(MAX_RETRIES + 1):  # 1 initial try + MAX_RETRIES retries
        try:
            await send_message(number, message, idempotency_key=idempotency_key)
        except Exception as exc:
            if attempt < MAX_RETRIES:
                print(
                    f"RETRY   {number}: attempt {attempt + 1} failed ({exc!r}); "
                    f"retrying in {RETRY_DELAY_SECONDS}s"
                )
                await asyncio.sleep(RETRY_DELAY_SECONDS)
                continue
            print(f"FAILED  {number}: {exc!r}")
            return False
        print(f"SENT    {number}")
        return True


async def blast(message: str) -> None:
    numbers = await get_all_phone_numbers()
    print(f"Blasting announcement to {len(numbers)} number(s).")
    sent = 0
    skipped = 0
    for number in numbers:
        if number in BLOCKLIST:
            print(f"SKIPPED {number} (blocklist)")
            skipped += 1
            continue
        delay = random.randint(MIN_DELAY_SECONDS, MAX_DELAY_SECONDS)
        print(f"waiting {delay}s...")
        await asyncio.sleep(delay)
        if await send_announcement(number, message):
            sent += 1
    print(f"Done. {sent} sent, {skipped} skipped (blocklist), of {len(numbers)} total.")


if __name__ == "__main__":
    # Paste the announcement to blast between the triple quotes.
    MESSAGE = (
        "message from the *faro team*\n"
        "\n"
        "hey yall! thanks for being one of our early users ❤️\n"
        "\n"
        "a wave of new signups this week made reminders a little buggy. if "
        "anything came late or didn't arrive, sorry about that. the fix will be "
        "out sunday night, monday morning at the latest.\n"
        "\n"
        "some new features are rolling out soon too! more on that shortly :))"
    )

    if not MESSAGE.strip():
        raise SystemExit("MESSAGE is empty — paste your announcement first.")
    #asyncio.run(blast(MESSAGE))
    #asyncio.run(send_announcement("+18323346991", MESSAGE))

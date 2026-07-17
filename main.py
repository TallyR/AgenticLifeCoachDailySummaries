# Entry point: find every user in the MessageTable and send each their daily
# summary, one by one.

import asyncio

from message_api import TABLE, _get_client
from summary import send_summary


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
        print(f"-> {number}")
        try:
            await send_summary(number)
        except Exception as exc:
            # Don't let one bad number stop summaries for everyone else.
            print(f"   failed for {number}: {exc!r}")


if __name__ == "__main__":
     asyncio.run(main())

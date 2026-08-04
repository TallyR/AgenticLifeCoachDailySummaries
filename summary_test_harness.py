# Quick test harness for send_summary in debug mode: generates and prints the
# daily ping but never sends it to Blooio or writes to the DB.
#
# Usage:
#   python summary_test_harness.py                 # uses DEFAULT_NUMBER

import asyncio

from summary import send_summary

DEFAULT_NUMBER = "+18323346991"


async def test_summary(phone_number: str) -> None:
    """Run send_summary in debug mode for one number (no send, no save)."""
    await send_summary(phone_number, debug=True)


if __name__ == "__main__":
    asyncio.run(test_summary(DEFAULT_NUMBER))

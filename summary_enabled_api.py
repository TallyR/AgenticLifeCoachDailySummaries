# Checks for whether to send a user their daily summary: an explicit opt-out
# flag, and whether the recent conversation has gone one-sided (all AGENT).

from message_api import TABLE, _get_client

ENABLED_TABLE = "EnabledDailySummaries"

# How many of the most recent messages to look at when deciding if the
# conversation has gone one-sided (all AGENT, no user replies).
LAST_N_MESSAGES = 8


async def is_summary_enabled(phone_number: str) -> bool:
    """Return whether daily summaries are enabled for `phone_number`.

    Defaults to enabled: if the number has no row in EnabledDailySummaries, the
    user hasn't opted out, so return True. If a row exists, return its `enabled`
    flag (a user opts out by having a row with enabled=false)."""
    client = await _get_client()
    response = await (
        client.table(ENABLED_TABLE)
        .select("enabled")
        .eq("phone_number", phone_number)
        .execute()
    )
    if not response.data:
        return True
    return bool(response.data[0]["enabled"])


async def has_recent_user_activity(phone_number: str) -> bool:
    """Return False only when the last LAST_N_MESSAGES messages with this number
    were all sent by AGENT (Faro pinging into silence). Return True if at least
    one of those recent messages came from the user, or there aren't
    LAST_N_MESSAGES messages yet.

    Each message stores the number on one side and "AGENT" on the other, so we
    match rows where the number is the sender or the recipient, then look at who
    each one was from."""
    client = await _get_client()
    response = await (
        client.table(TABLE)
        .select("from_phone_number, to_phone_number, message, sent_at")
        .or_(
            f"from_phone_number.eq.{phone_number},"
            f"to_phone_number.eq.{phone_number}"
        )
        .order("sent_at", desc=True)
        .limit(LAST_N_MESSAGES)
        .execute()
    )
    rows = response.data
    if len(rows) < LAST_N_MESSAGES:
        return True
    return any(row["from_phone_number"] != "AGENT" for row in rows)


async def disable_summaries(phone_number: str) -> dict:
    """Disable daily summaries for `phone_number`, creating the row if it doesn't
    exist yet. Upserts enabled=false keyed on phone_number (the primary key), so
    it works whether or not the number already has a row. Returns the saved row."""
    client = await _get_client()
    response = await (
        client.table(ENABLED_TABLE)
        .upsert(
            {"phone_number": phone_number, "enabled": False},
            on_conflict="phone_number",
        )
        .execute()
    )
    return response.data[0]


if __name__ == "__main__":
    import asyncio
    import sys

    async def _demo():
        number = sys.argv[1] if len(sys.argv) > 1 else "+18323346991"
        #print(f"{number} enabled:", await is_summary_enabled(number))
        #print(f"{number} recent user activity:", await has_recent_user_activity(number))
        print(f"{number} disabling", await disable_summaries(number))

    asyncio.run(_demo())

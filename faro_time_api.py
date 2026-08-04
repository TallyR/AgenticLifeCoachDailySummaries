from datetime import datetime
from zoneinfo import ZoneInfo


def get_current_date_and_time_from_timezone(timezone: str) -> dict:
    """Current date and time in the given IANA timezone (e.g. "America/New_York").

    Uses the 12-hour clock (hour 1-12 plus am_or_pm) to match how reminders
    and events are stored, and includes the spelled-out day of the week.
    Raises ZoneInfoNotFoundError for an invalid timezone name.
    """
    now = datetime.now(ZoneInfo(timezone))
    days = [
        "Monday", "Tuesday", "Wednesday", "Thursday",
        "Friday", "Saturday", "Sunday",
    ]
    return {
        "year": now.year,
        "month": now.month,
        "day": now.day,
        # Manual 12-hour conversion instead of strftime("%I"/"%p"): those are
        # locale-dependent, and this must always be 1-12 + "AM"/"PM" exactly.
        "hour": now.hour % 12 or 12,
        "minute": now.minute,
        "second": now.second,
        "am_or_pm": "AM" if now.hour < 12 else "PM",
        "day_of_week": days[now.weekday()],
    }


def get_current_date_and_time_tool_definition() -> dict:
    """Anthropic tool definition for get_current_date_and_time_from_timezone."""
    return {
        "name": "get_current_date_and_time_from_timezone",
        "description": (
            "Get the current date and time where the user is, on the 12-hour "
            "clock (hour 1-12 plus am_or_pm) — the same format reminders and "
            "events use — plus the day of the week. Call this FIRST whenever "
            "a request depends on knowing the current time: relative times "
            "like 'in 5 minutes' or 'in an hour', resolving 'tomorrow' or "
            "'next friday' to a concrete date, tracking day-specific items "
            "like 'this sunday i need to return my suit', or checking whether "
            "a time has already passed today. You do not know the current time "
            "on your own — never guess it; call this and do the arithmetic "
            "from the result. If you cannot determine the user's timezone, do "
            "not call this with a guessed or default zone (a wrong zone yields "
            "a wrong date): proceed without making any relative-time claims "
            "about how near or far a dated item is."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "timezone": {
                    "type": "string",
                    "description": (
                        "The user's timezone as an IANA name, e.g. "
                        "'America/New_York'. Infer it from what you know "
                        "about the user, for example their city ('new york' "
                        "becomes 'America/New_York'). Never pass a guessed or "
                        "default zone; if you cannot determine it, ask the "
                        "user for their city where a reply is possible, and "
                        "otherwise do not call this tool."
                    ),
                },
            },
            "required": ["timezone"],
        },
    }


if __name__ == "__main__":
    print(get_current_date_and_time_from_timezone("America/New_York"))
    print(get_current_date_and_time_tool_definition())

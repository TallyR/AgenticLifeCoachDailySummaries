# Global test harness: run main()'s full decision flow for a single phone number
# in debug mode — is_summary_enabled -> has_recent_user_activity -> summary vs
# pause notice — with nothing sent to Blooio and nothing written to the DB. The
# chosen message is generated and printed only.
#
# Usage:
#   python global_test_harness.py                 # uses DEFAULT_NUMBER
#   python global_test_harness.py +18323346991    # any number you pass

import asyncio
import sys

from main import main

DEFAULT_NUMBER = "+18323346991"


if __name__ == "__main__":
    number = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_NUMBER
    asyncio.run(main(number, debug=True))

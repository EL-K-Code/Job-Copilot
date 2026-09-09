from __future__ import annotations

import argparse
import sys
from getpass import getpass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.auth import upsert_beta_user


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create or rotate a JobCopilot private-beta account."
    )
    parser.add_argument("user_id", help="Stable login ID, e.g. recruiter-demo")
    parser.add_argument("--display-name", default="", help="Name shown in the app")
    args = parser.parse_args()

    password = getpass("Private beta password (min 10 characters): ")
    confirmation = getpass("Confirm password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match.")

    result = upsert_beta_user(
        args.user_id,
        password,
        display_name=args.display_name,
        enabled=True,
    )
    print(
        f"Beta account ready: {result['user_id']} "
        f"({result['display_name']}). Password was not stored in plaintext."
    )


if __name__ == "__main__":
    main()

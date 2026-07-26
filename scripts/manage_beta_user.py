from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.auth import upsert_beta_user
from app.tenancy import ensure_user_directories


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create or rotate a JobCopilot private beta user."
    )
    parser.add_argument("user_id")
    parser.add_argument("--display-name", default="")
    parser.add_argument(
        "--disabled",
        action="store_true",
        help="Create the account in a disabled state.",
    )
    args = parser.parse_args()

    password = getpass.getpass("Private beta password: ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match.")

    user = upsert_beta_user(
        args.user_id,
        password,
        display_name=args.display_name,
        enabled=not args.disabled,
    )
    paths = ensure_user_directories(user["user_id"])

    print(f"Beta user ready: {user['user_id']}")
    print(f"Private data directory: {paths.root}")
    print("No plaintext password was stored.")


if __name__ == "__main__":
    main()

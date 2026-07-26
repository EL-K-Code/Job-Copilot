from __future__ import annotations

import argparse

from app.tenancy import get_user_paths
from app.tools.gmail_tools import get_google_credentials


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Connect a Google account to one JobCopilot user."
    )
    parser.add_argument(
        "--user-id",
        default=None,
        help="Private beta user ID. Omit for the legacy single-user token path.",
    )
    args = parser.parse_args()

    creds = get_google_credentials(interactive=True, user_id=args.user_id)
    token_path = (
        get_user_paths(args.user_id).google_token
        if args.user_id
        else "the legacy GOOGLE_TOKEN_DIR path"
    )

    print("Google authentication successful.")
    print(f"Token saved to: {token_path}")
    print(f"Scopes granted: {creds.scopes}")


if __name__ == "__main__":
    main()

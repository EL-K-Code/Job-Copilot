from app.config import settings
from app.tools.gmail_tools import get_gmail_credentials


def main() -> None:
    creds = get_gmail_credentials(interactive=True)

    print("Gmail authentication successful.")
    print(f"Token saved to: {settings.google_token_path}")
    print(f"Scopes granted: {creds.scopes}")


if __name__ == "__main__":
    main()
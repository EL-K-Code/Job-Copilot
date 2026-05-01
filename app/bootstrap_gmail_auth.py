from app.config import settings
from app.tools.gmail_tools import get_google_credentials


def main() -> None:
    creds = get_google_credentials(interactive=True)

    print("Google authentication successful.")
    print(f"Token saved to: {settings.google_token_path}")
    print(f"Scopes granted: {creds.scopes}")


if __name__ == "__main__":
    main()
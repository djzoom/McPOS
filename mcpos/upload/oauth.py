"""
mcpos/upload/oauth.py — Per-channel YouTube OAuth management

Each channel has independent Google credentials:
  channels/<channel_id>/credentials/client_secrets.json
  channels/<channel_id>/credentials/token.json

Credentials are gitignored. Token auto-refreshes on expiry.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..core.logging import log_info, log_warning, log_error


class ChannelOAuth:
    """Per-channel YouTube OAuth2 credential manager."""

    SCOPES = [
        "https://www.googleapis.com/auth/youtube",
        "https://www.googleapis.com/auth/youtube.upload",
    ]

    def __init__(self, channel_id: str, channels_root: Path):
        self.channel_id = channel_id
        self.creds_dir = Path(channels_root) / channel_id / "credentials"
        self.client_secrets = self.creds_dir / "client_secrets.json"
        self.token_file = self.creds_dir / "token.json"

    def is_configured(self) -> bool:
        """Return True if client_secrets.json exists."""
        return self.client_secrets.exists()

    def get_credentials(self):
        """
        Load or refresh OAuth2 credentials.

        Returns google.oauth2.credentials.Credentials, or None if not configured.
        On first run, opens a browser for the OAuth consent flow.
        """
        if not self.is_configured():
            log_warning(
                f"[oauth] Channel '{self.channel_id}' not configured — "
                f"place client_secrets.json in {self.creds_dir}"
            )
            return None

        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
            from google_auth_oauthlib.flow import InstalledAppFlow
        except ImportError:
            raise ImportError(
                "Install: pip install google-auth-oauthlib google-api-python-client"
            )

        creds = None
        if self.token_file.exists():
            try:
                creds = Credentials.from_authorized_user_file(
                    str(self.token_file), self.SCOPES
                )
            except Exception as e:
                log_warning(f"[oauth] Failed to load token for '{self.channel_id}': {e}")
                creds = None

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    log_info(f"[oauth] Token refreshed for channel '{self.channel_id}'")
                except Exception as e:
                    log_warning(f"[oauth] Token refresh failed: {e}; re-running flow")
                    creds = None

            if not creds:
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.client_secrets), self.SCOPES
                )
                creds = flow.run_local_server(port=0)
                log_info(f"[oauth] New token obtained for channel '{self.channel_id}'")

            # Persist refreshed token
            self.creds_dir.mkdir(parents=True, exist_ok=True)
            self.token_file.write_text(creds.to_json(), encoding="utf-8")

        return creds

    def get_service(self):
        """Return authenticated YouTube API v3 Resource, or None if not configured."""
        creds = self.get_credentials()
        if creds is None:
            return None
        try:
            from googleapiclient.discovery import build
        except ImportError:
            raise ImportError("Install: pip install google-api-python-client")
        return build("youtube", "v3", credentials=creds)


def get_channel_service(channel_id: str, channels_root: Path):
    """Convenience: get authenticated YouTube service for a channel."""
    return ChannelOAuth(channel_id, channels_root).get_service()

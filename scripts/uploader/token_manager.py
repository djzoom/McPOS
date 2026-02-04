"""
YouTube OAuth Token Manager

Manages OAuth token caching, automatic refresh, and persistence.
Reduces OAuth flow invocations by caching valid tokens.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False
    Credentials = None
    Request = None
    build = None


class YouTubeTokenManager:
    """
    Singleton token manager for YouTube API authentication.
    
    Features:
    - Thread-safe token caching
    - Automatic token refresh
    - Persistent token storage
    - Reduces OAuth flow invocations
    """
    _instance: Optional['YouTubeTokenManager'] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._token_lock = threading.Lock()
        self._cached_credentials: Optional[Credentials] = None
        self._token_file: Optional[Path] = None
        self._client_secrets_file: Optional[Path] = None
        self._scopes = [
            'https://www.googleapis.com/auth/youtube.upload',
            'https://www.googleapis.com/auth/youtube.readonly',
            'https://www.googleapis.com/auth/youtube.force-ssl'
        ]
        self._initialized = True
    
    def configure(
        self,
        token_file: Path,
        client_secrets_file: Path,
        scopes: Optional[list] = None
    ) -> None:
        """
        Configure token manager with file paths.
        
        Args:
            token_file: Path to token file
            client_secrets_file: Path to client secrets file
            scopes: OAuth scopes (defaults to YouTube upload scopes)
        """
        self._token_file = Path(token_file)
        self._client_secrets_file = Path(client_secrets_file)
        if scopes:
            self._scopes = scopes
    
    def get_valid_token(self) -> Credentials:
        """
        Get valid credentials, refreshing if needed.
        
        Returns:
            Valid Credentials object
            
        Raises:
            RuntimeError: If Google API libraries not available
            FileNotFoundError: If token file or client secrets not found
        """
        if not GOOGLE_API_AVAILABLE:
            raise RuntimeError(
                "Google API libraries not installed. "
                "Install with: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib"
            )
        
        with self._token_lock:
            # Try to use cached credentials
            if self._cached_credentials and self._cached_credentials.valid:
                return self._cached_credentials
            
            # Load from file
            if self._token_file and self._token_file.exists():
                try:
                    creds = Credentials.from_authorized_user_file(
                        str(self._token_file),
                        self._scopes
                    )
                    
                    # Refresh if expired
                    if creds.expired and creds.refresh_token:
                        creds.refresh(Request())
                        self._save_token(creds)
                    
                    if creds.valid:
                        self._cached_credentials = creds
                        return creds
                except (FileNotFoundError, json.JSONDecodeError, OSError, ValueError) as e:
                    # Token file corrupted or invalid, will trigger re-auth
                    pass
            
            # Need to authorize
            raise RuntimeError(
                "No valid token found. Please run authorization flow first. "
                f"Token file: {self._token_file}"
            )
    
    def refresh_token_if_needed(self) -> None:
        """
        Refresh token if expired.
        
        This is called automatically by get_valid_token(), but can be called
        explicitly to pre-refresh tokens.
        """
        if not GOOGLE_API_AVAILABLE:
            return
        
        with self._token_lock:
            if self._cached_credentials:
                if self._cached_credentials.expired and self._cached_credentials.refresh_token:
                    try:
                        self._cached_credentials.refresh(Request())
                        self._save_token(self._cached_credentials)
                    except Exception:
                        # Refresh failed, will trigger re-auth on next get_valid_token()
                        self._cached_credentials = None
    
    def save_token(self, credentials: Credentials) -> None:
        """
        Save credentials to file and cache.
        
        Args:
            credentials: Credentials object to save
        """
        with self._token_lock:
            self._cached_credentials = credentials
            self._save_token(credentials)
    
    def _save_token(self, credentials: Credentials) -> None:
        """Internal method to save token to file."""
        if not self._token_file:
            return
        
        try:
            self._token_file.parent.mkdir(parents=True, exist_ok=True)
            token_data = {
                'token': credentials.token,
                'refresh_token': credentials.refresh_token,
                'token_uri': credentials.token_uri,
                'client_id': credentials.client_id,
                'client_secret': credentials.client_secret,
                'scopes': credentials.scopes,
            }
            if credentials.expiry:
                token_data['expiry'] = credentials.expiry.isoformat()
            
            self._token_file.write_text(
                json.dumps(token_data, indent=2),
                encoding='utf-8'
            )
            self._token_file.chmod(0o600)
        except (OSError, IOError) as e:
            # Log but don't fail
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to save token: {e}")
    
    def load_token_from_config(self, config: dict) -> Optional[Credentials]:
        """
        Load token from configuration dictionary.
        
        Args:
            config: Configuration dict with token_file and client_secrets_file
            
        Returns:
            Credentials if loaded successfully, None otherwise
        """
        if not GOOGLE_API_AVAILABLE:
            return None
        
        token_file = Path(config.get("token_file", ""))
        if not token_file.exists():
            return None
        
        try:
            creds = Credentials.from_authorized_user_file(
                str(token_file),
                self._scopes
            )
            
            # Refresh if expired
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                self._save_token(creds)
            
            if creds.valid:
                with self._token_lock:
                    self._cached_credentials = creds
                    self._token_file = token_file
                    self._client_secrets_file = Path(config.get("client_secrets_file", ""))
                return creds
        except Exception:
            pass
        
        return None
    
    def clear_cache(self) -> None:
        """Clear cached credentials (force reload on next access)."""
        with self._token_lock:
            self._cached_credentials = None
    
    def get_authenticated_service(self):
        """
        Get authenticated YouTube API service.
        
        Returns:
            YouTube API service object
            
        Raises:
            RuntimeError: If token not available or Google API libraries not installed
        """
        if not GOOGLE_API_AVAILABLE:
            raise RuntimeError(
                "Google API libraries not installed. "
                "Install with: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib"
            )
        
        creds = self.get_valid_token()
        return build('youtube', 'v3', credentials=creds)


# Global singleton instance
_token_manager = YouTubeTokenManager()


def get_token_manager() -> YouTubeTokenManager:
    """Get the global token manager instance."""
    return _token_manager


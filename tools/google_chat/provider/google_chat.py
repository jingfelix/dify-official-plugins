import secrets
import urllib.parse
from collections.abc import Mapping
from typing import Any

import requests
from werkzeug import Request

from dify_plugin import ToolProvider
from dify_plugin.entities.oauth import ToolOAuthCredentials
from dify_plugin.errors.tool import ToolProviderCredentialValidationError, ToolProviderOAuthError


class GoogleChatProvider(ToolProvider):
    """Google Chat API provider with OAuth 2.0 authentication"""
    
    _AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    _TOKEN_URL = "https://oauth2.googleapis.com/token"
    _API_BASE_URL = "https://chat.googleapis.com/v1"
    
    # Built-in scopes for Google Chat API only
    _SCOPES = [
        "https://www.googleapis.com/auth/chat.spaces",
        "https://www.googleapis.com/auth/chat.spaces.readonly",
        "https://www.googleapis.com/auth/chat.memberships",
        "https://www.googleapis.com/auth/chat.memberships.readonly",
        "https://www.googleapis.com/auth/chat.messages",
        "https://www.googleapis.com/auth/chat.messages.create",
        "https://www.googleapis.com/auth/chat.messages.reactions",
        "https://www.googleapis.com/auth/chat.messages.reactions.create",
        "https://www.googleapis.com/auth/chat.messages.reactions.readonly",
        "https://www.googleapis.com/auth/chat.messages.readonly"
    ]

    def _oauth_get_authorization_url(self, redirect_uri: str, system_credentials: Mapping[str, Any]) -> str:
        """
        Generate the authorization URL for Google OAuth 2.0
        """
        state = secrets.token_urlsafe(16)
        params = {
            "client_id": system_credentials["client_id"],
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(self._SCOPES),  # Use built-in scopes
            "state": state,
            "access_type": "offline",  # Request refresh token
            "prompt": "consent"  # Force consent to get refresh token
        }
        return f"{self._AUTH_URL}?{urllib.parse.urlencode(params)}"

    def _oauth_get_credentials(
        self, redirect_uri: str, system_credentials: Mapping[str, Any], request: Request
    ) -> ToolOAuthCredentials:
        """
        Exchange authorization code for access token and refresh token
        """
        code = request.args.get("code")
        if not code:
            raise ToolProviderOAuthError("No authorization code provided")
        
        # Exchange code for tokens
        data = {
            "client_id": system_credentials["client_id"],
            "client_secret": system_credentials["client_secret"],
            "code": code,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code"
        }
        
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        response = requests.post(self._TOKEN_URL, data=data, headers=headers, timeout=10)
        
        if response.status_code != 200:
            raise ToolProviderOAuthError(f"Failed to get access token: {response.text}")
        
        response_json = response.json()
        access_token = response_json.get("access_token")
        refresh_token = response_json.get("refresh_token")
        expires_in = response_json.get("expires_in", 3600)
        
        if not access_token:
            raise ToolProviderOAuthError("No access token in response")
        
        # Store both access and refresh tokens
        credentials = {
            "access_token": access_token,
            "refresh_token": refresh_token
        }
        
        return ToolOAuthCredentials(
            credentials=credentials,
            expires_at=expires_in
        )

    def _oauth_refresh_credentials(
        self, redirect_uri: str, system_credentials: Mapping[str, Any], credentials: Mapping[str, Any]
    ) -> ToolOAuthCredentials:
        """
        Refresh the access token using refresh token
        """
        refresh_token = credentials.get("refresh_token")
        if not refresh_token:
            raise ToolProviderOAuthError("No refresh token available")
        
        data = {
            "client_id": system_credentials["client_id"],
            "client_secret": system_credentials["client_secret"],
            "refresh_token": refresh_token,
            "grant_type": "refresh_token"
        }
        
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        response = requests.post(self._TOKEN_URL, data=data, headers=headers, timeout=10)
        
        if response.status_code != 200:
            raise ToolProviderOAuthError(f"Failed to refresh token: {response.text}")
        
        response_json = response.json()
        new_access_token = response_json.get("access_token")
        expires_in = response_json.get("expires_in", 3600)
        
        if not new_access_token:
            raise ToolProviderOAuthError("No access token in refresh response")
        
        # Keep the refresh token and update access token
        credentials = {
            "access_token": new_access_token,
            "refresh_token": refresh_token
        }
        
        return ToolOAuthCredentials(
            credentials=credentials,
            expires_at=expires_in
        )

    def _validate_credentials(self, credentials: dict) -> None:
        """
        Validate OAuth credentials by making a test API call
        """
        try:
            if "access_token" not in credentials or not credentials.get("access_token"):
                raise ToolProviderCredentialValidationError("Access token is required")
            
            # Test the credentials by listing spaces (limited to 1 for efficiency)
            headers = {
                "Authorization": f"Bearer {credentials['access_token']}",
                "Content-Type": "application/json"
            }
            
            test_url = f"{self._API_BASE_URL}/spaces?pageSize=1"
            response = requests.get(test_url, headers=headers, timeout=10)
            
            if response.status_code == 401:
                raise ToolProviderCredentialValidationError("Invalid or expired access token")
            elif response.status_code == 403:
                raise ToolProviderCredentialValidationError("Insufficient permissions. Please check OAuth scopes.")
            elif response.status_code != 200:
                raise ToolProviderCredentialValidationError(f"API test failed: {response.status_code}")
                
        except requests.RequestException as e:
            raise ToolProviderCredentialValidationError(f"Network error: {str(e)}") from e
        except Exception as e:
            raise ToolProviderCredentialValidationError(str(e)) from e
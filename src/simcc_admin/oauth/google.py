from urllib.parse import urlencode

import httpx

from simcc_admin.oauth.base import BaseOAuthProvider, OAuthUserInfo
from simcc_admin.settings import Settings


class GoogleOAuthProvider(BaseOAuthProvider):
    name = "google"
    AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

    def __init__(self, settings: Settings):
        self.client_id = settings.GOOGLE_CLIENT_ID
        self.client_secret = settings.GOOGLE_CLIENT_SECRET
        self.redirect_uri = settings.GOOGLE_REDIRECT_URI

    def get_authorization_url(self, state: str) -> str:
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "access_type": "offline",
            "state": state,
            "prompt": "consent",
        }
        return f"{self.AUTH_URL}?{urlencode(params)}"

    async def get_user_info(self, code: str) -> OAuthUserInfo:
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                self.TOKEN_URL,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": self.redirect_uri,
                },
                headers={"Accept": "application/json"},
            )
            token_response.raise_for_status()
            tokens = token_response.json()
            access_token = tokens["access_token"]

            userinfo_response = await client.get(
                self.USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            userinfo_response.raise_for_status()
            user_data = userinfo_response.json()

            return OAuthUserInfo(
                provider=self.name,
                provider_user_id=str(user_data["sub"]),
                email=user_data.get("email"),
                name=user_data.get("name"),
                raw_data=user_data,
            )

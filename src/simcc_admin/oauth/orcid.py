from urllib.parse import urlencode

import httpx

from simcc_admin.oauth.base import BaseOAuthProvider, OAuthUserInfo
from simcc_admin.settings import Settings


class OrcidOAuthProvider(BaseOAuthProvider):
    name = "orcid"

    def __init__(self, settings: Settings):
        self.client_id = settings.ORCID_CLIENT_ID
        self.client_secret = settings.ORCID_CLIENT_SECRET
        self.redirect_uri = settings.ORCID_REDIRECT_URI
        self.sandbox = settings.ORCID_SANDBOX

        domain = "sandbox.orcid.org" if self.sandbox else "orcid.org"
        self.auth_url = f"https://{domain}/oauth/authorize"
        self.token_url = f"https://{domain}/oauth/token"

    def get_authorization_url(self, state: str) -> str:
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "scope": "/authenticate",
            "redirect_uri": self.redirect_uri,
            "state": state,
        }
        return f"{self.auth_url}?{urlencode(params)}"

    async def get_user_info(self, code: str) -> OAuthUserInfo:
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                self.token_url,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": self.redirect_uri,
                },
                headers={"Accept": "application/json"},
            )
            token_response.raise_for_status()
            data = token_response.json()

            # No ORCID, o payload de token já devolve: orcid, name, access_token
            orcid_id = str(data["orcid"])
            name = data.get("name")

            return OAuthUserInfo(
                provider=self.name,
                provider_user_id=orcid_id,
                email=None,
                name=name,
                raw_data=data,
            )

from collections.abc import Callable

from simcc_admin.oauth.base import BaseOAuthProvider
from simcc_admin.oauth.google import GoogleOAuthProvider
from simcc_admin.oauth.orcid import OrcidOAuthProvider
from simcc_admin.settings import Settings


def get_oauth_provider(
    name: str, settings: Settings | None = None
) -> BaseOAuthProvider:
    config = settings or Settings()

    providers: dict[str, Callable[[], BaseOAuthProvider]] = {
        "google": lambda: GoogleOAuthProvider(config),
        "orcid": lambda: OrcidOAuthProvider(config),
    }

    factory = providers.get(name.lower())
    if not factory:
        supported = ", ".join(providers.keys())
        raise ValueError(
            f"Provedor OAuth '{name}' não suportado. Provedores válidos: {supported}"
        )

    return factory()

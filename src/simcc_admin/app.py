from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from simcc_admin.routers import academic
from simcc_admin.settings import Settings

settings = Settings()


class ForwardedPrefixMiddleware:
    """Suporta proxies reversos com prefixos dinâmicos (via X-Forwarded-Prefix)
    ou estáticos (via settings.ROOT_PATH).
    """

    def __init__(self, app: ASGIApp, default_prefix: str = ""):
        self.app = app
        self.default_prefix = default_prefix.rstrip("/")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in ("http", "websocket"):
            prefix = ""
            for k, v in scope.get("headers", []):
                if k.lower() == b"x-forwarded-prefix":
                    header_val = v.decode("latin1").strip().rstrip("/")
                    if header_val:
                        prefix = f"/{header_val.lstrip('/')}"
                    break

            if prefix:
                scope["root_path"] = prefix
            elif self.default_prefix and not scope.get("root_path"):
                scope["root_path"] = self.default_prefix
        await self.app(scope, receive, send)


app = FastAPI(
    title="SIMCC Admin API",
    root_path=settings.ROOT_PATH,
)

app.add_middleware(
    ForwardedPrefixMiddleware,
    default_prefix=settings.ROOT_PATH,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(academic.router)


@app.get("/")
def read_root():
    return {"message": "Olá Mundo!"}

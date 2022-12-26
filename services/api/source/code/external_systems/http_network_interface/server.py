import uvicorn
from typing import Awaitable, List
from external_systems.http_network_interface.asgi_app import create_new_asgi_app
from external_systems.http_network_interface.middlewares import attach_middlewares
from external_systems.http_network_interface.routers import attach_routers


class HttpServer:
    """
    A class which its purpose is to encapsulate the usage of the http_network_interface from outside
    It lets the user to avoid being familiar with the concrete implementation
    For example, the app entrypoint should not be familiar with the fact it uses FastAPI
    """

    __slots__ = (
        'app'
    )

    def __init__(
        self,
        origins_whitelist: List[str] = ("*"),
        on_startup: Awaitable = lambda: ...,
        on_shutdown: Awaitable = lambda: ...,
    ):
        self.app = create_new_asgi_app(
            origins_whitelist=origins_whitelist,
            on_startup=on_startup,
            on_shutdown=on_shutdown,
            attach_middlewares_fn=attach_middlewares,
            attach_routers_fn=attach_routers
        )

    def listen(
        self,
        port: int
    ) -> None:
        uvicorn.run(
            app=self.app,
            host='0.0.0.0',
            port=port,
            workers=1,
            # trust the proxy to set the correct ip on the x-forwarded-for header (contains the real client ip)
            # and disable the default ip check
            # the client ip can not be known pre-hand, so we can not set it in the allowed list
            # as the proxy is trusted, it is safe to set the forwarded_allow_ips to '*'
            # https://www.uvicorn.org/settings/#proxy-headers
            # https://www.uvicorn.org/settings/#forwarded-allow-ips
            forwarded_allow_ips='*'
        )

import os

import click
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

from grokipedia_mcp.server import mcp


@click.command()
@click.option(
    "--transport",
    "-t",
    type=click.Choice(["stdio", "http", "streamable-http", "sse"], case_sensitive=False),
    default="stdio",
    help="Transport protocol to use (default: stdio)",
)
@click.option(
    "--host",
    default="0.0.0.0",
    help="Host to bind to for HTTP transports (default: 0.0.0.0)",
)
@click.option(
    "--port",
    "-p",
    type=int,
    default=None,
    help="Port to bind to for HTTP transports (default: PORT env or 8888)",
)
def main(transport: str, host: str, port: int | None):
    transport = os.getenv("MCP_TRANSPORT", transport)

    if port is None:
        port = int(os.getenv("PORT", "8888"))

    if transport in ["http", "streamable-http", "sse"]:
        cors = Middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["*"],
            expose_headers=["mcp-session-id", "mcp-protocol-version"],
            max_age=86400,
        )
        mcp.run(
            transport=transport,
            host=host,
            port=port,
            middleware=[cors],
        )
    else:
        mcp.run(transport=transport)


if __name__ == "__main__":
    main()

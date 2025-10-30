import os
import click
import uvicorn
from grokipedia_mcp.server import mcp
from starlette.middleware.cors import CORSMiddleware


@click.command()
@click.option(
    "--transport",
    "-t",
    type=click.Choice(["stdio", "sse", "streamable-http"], case_sensitive=False),
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

    if transport in ["sse", "streamable-http"]:
        click.echo(f"Starting {transport} server on {host}:{port}")

        app = mcp.streamable_http_app()

        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["*"],
            expose_headers=["mcp-session-id", "mcp-protocol-version"],
            max_age=86400,
        )

        uvicorn.run(app, host=host, port=port, log_level="info")
    else:
        mcp.run(transport=transport)


if __name__ == "__main__":
    main()

import click
from grokipedia_mcp.server import mcp
from smithery.decorators import smithery
from os import getenv


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
    default=8888,
    help="Port to bind to for HTTP transports (default: 8888)",
)
def main(transport: str, host: str, port: int):
    # environment variable always overrides command line
    transport = getenv("MCP_TRANSPORT", transport)

    if transport in ["sse", "streamable-http"]:
        click.echo(f"Starting {transport} server on {host}:{port}")
        mcp.settings.host = host
        mcp.settings.port = port
    mcp.run(transport=transport)


@smithery.server()
def smithery_server():
    mcp.settings.host = "0.0.0.0"
    mcp.settings.port = 8888
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()

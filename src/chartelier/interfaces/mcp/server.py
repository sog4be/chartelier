"""MCP server entry point for Chartelier."""

import argparse
import logging
import sys

from chartelier.infra.logging import configure_logging, get_logger
from chartelier.interfaces.mcp.handler import MCPHandler

# Configure logging for stderr (MCP uses stdout for protocol)
configure_logging(level=logging.WARNING, stream=sys.stderr)
logger = get_logger(__name__)


def run_stdio_server(handler: MCPHandler, debug: bool = False) -> None:
    """Run the MCP server in stdio mode.

    Args:
        handler: MCP protocol handler
        debug: Enable debug logging
    """
    if debug:
        logger.info("Starting Chartelier MCP server in stdio mode (debug enabled)")
    else:
        logger.debug("Starting Chartelier MCP server in stdio mode")

    try:
        # Read JSON-RPC messages from stdin line by line
        for line in sys.stdin:
            line_stripped = line.strip()
            if not line_stripped:
                continue

            # Handle the message
            response = handler.handle_message(line_stripped)

            # Send response if one was generated
            if response:
                sys.stdout.write(response + "\n")
                sys.stdout.flush()

    except KeyboardInterrupt:
        logger.debug("Server interrupted by user")
    except EOFError:
        logger.debug("Input stream closed")
    except Exception:
        logger.exception("Unexpected error in server loop")
        sys.exit(1)


def main() -> None:
    """Main entry point for the Chartelier MCP server."""
    parser = argparse.ArgumentParser(
        prog="chartelier-mcp",
        description="Chartelier MCP Server - MCP-compliant visualization tool for AI agents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start the MCP server (stdio mode)
  chartelier-mcp

  # Show version information
  chartelier-mcp --version

  # Show this help message
  chartelier-mcp --help

The server communicates via JSON-RPC 2.0 over stdio.
Logging output goes to stderr, protocol messages to stdout.
        """.strip(),
    )

    parser.add_argument(
        "--version", action="version", version="chartelier-mcp 0.2.0", help="show version information and exit"
    )

    parser.add_argument(
        "--mode", choices=["stdio"], default="stdio", help="communication mode (currently only stdio is supported)"
    )

    parser.add_argument("--debug", action="store_true", help="enable debug logging")

    args = parser.parse_args()

    # Configure logging level
    if args.debug:
        configure_logging(level=logging.DEBUG, stream=sys.stderr)

    # Create handler and run server
    handler = MCPHandler()

    if args.mode == "stdio":
        run_stdio_server(handler, debug=args.debug)
    else:
        logger.error("Unsupported mode: %s", args.mode)
        sys.exit(1)


if __name__ == "__main__":
    main()

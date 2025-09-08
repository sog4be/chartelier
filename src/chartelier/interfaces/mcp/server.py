"""MCP server entry point for Chartelier."""

import argparse
import json
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


def main() -> None:
    """Main entry point for the Chartelier MCP server.

    This is a minimal implementation that will be expanded in future PRs.
    Currently, it only provides basic CLI functionality for testing.
    """
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

Note: This is a minimal implementation. Full MCP functionality will be added in subsequent PRs.
        """.strip(),
    )

    parser.add_argument(
        "--version", action="version", version="chartelier-mcp 0.1.0", help="show version information and exit"
    )

    parser.add_argument(
        "--mode", choices=["stdio"], default="stdio", help="communication mode (currently only stdio is supported)"
    )

    parser.add_argument("--debug", action="store_true", help="enable debug logging")

    args = parser.parse_args()

    # Set logging level based on debug flag
    if args.debug:
        logger.setLevel(logging.DEBUG)
        logging.getLogger().setLevel(logging.DEBUG)

    if args.mode == "stdio":
        # Minimal stdio mode implementation
        # Full MCP server implementation will be added in PR-C1
        logger.debug("Starting Chartelier MCP server in stdio mode")

        # For now, just echo a minimal response to show the server is working
        # This will be replaced with proper MCP protocol handling in PR-C1
        try:
            # Read a single line for testing purposes
            # In the full implementation, this will be a proper JSON-RPC loop
            line = sys.stdin.readline()
            if line:
                # Echo back a minimal response
                response = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": {"message": "Chartelier MCP server is running (minimal mode)", "version": "0.1.0"},
                }
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
        except KeyboardInterrupt:
            logger.debug("Server interrupted")
            sys.exit(0)
        except Exception:
            logger.exception("Error in server")
            sys.exit(1)


if __name__ == "__main__":
    main()

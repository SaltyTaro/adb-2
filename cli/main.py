#!/usr/bin/env python3
import sys
import os
import click
import logging
from typing import Dict, List, Any, Optional

# Add the parent directory to sys.path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from cli.commands.analyze import analyze
from cli.commands.report import report
from cli.commands.update import update

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("deptool")


@click.group()
@click.version_option(version="1.0.0")
@click.option("--debug", is_flag=True, help="Enable debug output")
@click.option("--api-url", help="API URL for backend server")
@click.option("--api-key", help="API key for authentication")
@click.pass_context
def cli(ctx, debug: bool, api_url: Optional[str], api_key: Optional[str]) -> None:
    """
    Advanced Dependency Intelligence Platform CLI.
    
    Analyze and manage project dependencies with AI-powered insights.
    """
    # Set up logging level
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
        
    # Initialize context object
    ctx.ensure_object(dict)
    ctx.obj["DEBUG"] = debug
    
    # Set API configuration
    if api_url:
        ctx.obj["API_URL"] = api_url
    else:
        # Try to get from environment variable or use default
        ctx.obj["API_URL"] = os.environ.get("DEPTOOL_API_URL", "http://localhost:8000/api/v1")
        
    if api_key:
        ctx.obj["API_KEY"] = api_key
    else:
        # Try to get from environment variable
        ctx.obj["API_KEY"] = os.environ.get("DEPTOOL_API_KEY")
    
    logger.debug(f"Using API URL: {ctx.obj['API_URL']}")


# Add commands
cli.add_command(analyze)
cli.add_command(report)
cli.add_command(update)


def main():
    """Entry point for the CLI."""
    try:
        cli(obj={})
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        if "--debug" in sys.argv:
            raise
        sys.exit(1)


if __name__ == "__main__":
    main()
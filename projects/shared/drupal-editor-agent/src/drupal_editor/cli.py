"""
CLI for testing the Drupal Editor Agent.

Usage:
    # Update a node via Terminus (auto-detected)
    uv run python -m drupal_editor.cli update-node --nid 123 --field body --value "New content" --reason "Fixed typo"

    # Find and replace
    uv run python -m drupal_editor.cli find-replace --nid 123 --field body --find "recieve" --replace "receive" --reason "Spelling fix"

    # Use Playwright explicitly
    uv run python -m drupal_editor.cli update-node --auth playwright --nid 123 --field body --value "New content"

    # Get node info
    uv run python -m drupal_editor.cli get-node --nid 123
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

from rich.console import Console
from dotenv import load_dotenv

console = Console()


def main():
    """Main entry point."""
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Drupal Editor Agent - Make staged changes to Drupal sites",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # update-node command
    update_parser = subparsers.add_parser("update-node", help="Update a node field")
    update_parser.add_argument("--nid", type=int, required=True, help="Node ID")
    update_parser.add_argument("--field", required=True, help="Field name (e.g., body, title)")
    update_parser.add_argument("--value", required=True, help="New value for the field")
    update_parser.add_argument("--reason", default="Ava: Updated content", help="Reason for change")
    update_parser.add_argument("--auth", choices=["terminus", "playwright"], help="Auth method (auto-detect if not specified)")
    update_parser.add_argument("--site", help="Pantheon site name (for Terminus)")
    update_parser.add_argument("--env", default="live", help="Pantheon environment (default: live)")

    # find-replace command
    replace_parser = subparsers.add_parser("find-replace", help="Find and replace text in a node field")
    replace_parser.add_argument("--nid", type=int, required=True, help="Node ID")
    replace_parser.add_argument("--field", required=True, help="Field name")
    replace_parser.add_argument("--find", required=True, help="Text to find")
    replace_parser.add_argument("--replace", required=True, help="Replacement text")
    replace_parser.add_argument("--reason", default="Ava: Text replacement", help="Reason for change")
    replace_parser.add_argument("--auth", choices=["terminus", "playwright"], help="Auth method")
    replace_parser.add_argument("--site", help="Pantheon site name")
    replace_parser.add_argument("--env", default="live", help="Pantheon environment")

    # get-node command
    get_parser = subparsers.add_parser("get-node", help="Get node information")
    get_parser.add_argument("--nid", type=int, required=True, help="Node ID")
    get_parser.add_argument("--auth", choices=["terminus", "playwright"], help="Auth method")
    get_parser.add_argument("--site", help="Pantheon site name")
    get_parser.add_argument("--env", default="live", help="Pantheon environment")

    # test-auth command
    auth_parser = subparsers.add_parser("test-auth", help="Test authentication")
    auth_parser.add_argument("--auth", choices=["terminus", "playwright"], help="Auth method to test")
    auth_parser.add_argument("--site", help="Pantheon site name (for Terminus)")
    auth_parser.add_argument("--env", default="live", help="Pantheon environment")

    # summary command
    subparsers.add_parser("summary", help="Show summary of changes made this session")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Run the async command
    asyncio.run(run_command(args))


async def run_command(args):
    """Run the appropriate command."""
    from drupal_editor import DrupalClient

    if args.command == "test-auth":
        await test_auth(args)
        return

    if args.command == "summary":
        console.print("[yellow]No changes in this session[/yellow]")
        return

    # Create client based on args
    client = await create_client(args)
    if not client:
        sys.exit(1)

    try:
        if args.command == "update-node":
            await update_node(client, args)

        elif args.command == "find-replace":
            await find_replace(client, args)

        elif args.command == "get-node":
            await get_node(client, args)

        # Print summary
        summary = client.get_summary()
        console.print("\n" + summary)

    finally:
        await client.close()


async def create_client(args):
    """Create a DrupalClient based on args."""
    from drupal_editor import DrupalClient
    from drupal_editor.auth.terminus import TerminusAuth
    from drupal_editor.auth.playwright import PlaywrightAuth

    auth_method = getattr(args, "auth", None)
    site = getattr(args, "site", None) or os.getenv("PANTHEON_SITE")

    # Use Terminus if:
    # 1. Explicitly requested via --auth terminus
    # 2. A site is specified (--site or PANTHEON_SITE)
    # 3. PANTHEON_MACHINE_TOKEN is set
    use_terminus = (
        auth_method == "terminus"
        or (auth_method is None and site)
        or (auth_method is None and os.getenv("PANTHEON_MACHINE_TOKEN"))
    )

    if use_terminus:
        if not site:
            console.print("[red]Error: --site or PANTHEON_SITE required for Terminus[/red]")
            return None

        env = getattr(args, "env", "live")
        console.print(f"[blue]Using Terminus auth for {site}.{env}[/blue]")
        return DrupalClient.with_terminus(site_name=site, env=env)

    elif auth_method == "playwright" or auth_method is None:
        base_url = os.getenv("DRUPAL_BASE_URL")
        username = os.getenv("DRUPAL_USERNAME")
        password = os.getenv("DRUPAL_PASSWORD")

        if not all([base_url, username, password]):
            console.print("[red]Error: DRUPAL_BASE_URL, DRUPAL_USERNAME, DRUPAL_PASSWORD required for Playwright[/red]")
            return None

        console.print(f"[blue]Using Playwright auth for {base_url}[/blue]")
        return DrupalClient.with_playwright(
            base_url=base_url,
            username=username,
            password=password,
        )

    return None


async def test_auth(args):
    """Test authentication."""
    from drupal_editor.auth.terminus import TerminusAuth
    from drupal_editor.auth.playwright import PlaywrightAuth

    auth_method = args.auth

    if auth_method == "terminus" or auth_method is None:
        site = args.site or os.getenv("PANTHEON_SITE")
        if site:
            console.print(f"[yellow]Testing Terminus auth for {site}...[/yellow]")
            auth = TerminusAuth(site_name=site, env=args.env)
            success = await auth.authenticate()
            if success:
                console.print("[green]Terminus authentication successful![/green]")

                # Try a simple Drush command
                result = await auth.drush("status --format=json")
                if result.success:
                    console.print("[green]Drush connection verified[/green]")
                else:
                    console.print(f"[yellow]Drush command failed: {result.stderr}[/yellow]")
            else:
                console.print("[red]Terminus authentication failed[/red]")
            return

    if auth_method == "playwright" or auth_method is None:
        base_url = os.getenv("DRUPAL_BASE_URL")
        username = os.getenv("DRUPAL_USERNAME")
        password = os.getenv("DRUPAL_PASSWORD")

        if all([base_url, username, password]):
            console.print(f"[yellow]Testing Playwright auth for {base_url}...[/yellow]")
            auth = PlaywrightAuth(
                base_url=base_url,
                username=username,
                password=password,
                headless=True,
            )
            success = await auth.authenticate()
            if success:
                console.print("[green]Playwright authentication successful![/green]")
            else:
                console.print("[red]Playwright authentication failed[/red]")
            await auth.close()
            return

    console.print("[red]No valid auth configuration found[/red]")


async def update_node(client, args):
    """Update a node field."""
    console.print(f"\n[yellow]Updating node/{args.nid} field '{args.field}'...[/yellow]")

    result = await client.nodes.create_draft_revision(
        nid=args.nid,
        changes={args.field: args.value},
        reason=args.reason,
    )

    if result.success:
        console.print(f"[green]Success! Revision created.[/green]")
        console.print(f"[dim]Review URL: {result.revision_url}[/dim]")
    else:
        console.print(f"[red]Failed: {result.error}[/red]")


async def find_replace(client, args):
    """Find and replace text in a node field."""
    console.print(f"\n[yellow]Finding '{args.find}' and replacing with '{args.replace}' in node/{args.nid}...[/yellow]")

    result = await client.nodes.find_and_replace(
        nid=args.nid,
        field=args.field,
        find=args.find,
        replace=args.replace,
        reason=args.reason,
    )

    if result.success:
        console.print(f"[green]Success! Revision created.[/green]")
        console.print(f"[dim]Review URL: {result.revision_url}[/dim]")
    else:
        console.print(f"[red]Failed: {result.error}[/red]")


async def get_node(client, args):
    """Get node information."""
    console.print(f"\n[yellow]Fetching node/{args.nid}...[/yellow]")

    node = await client.auth.get_node(args.nid)

    if node:
        console.print("\n[green]Node found:[/green]")
        for key, value in node.items():
            console.print(f"  {key}: {value}")
    else:
        console.print(f"[red]Node {args.nid} not found[/red]")


if __name__ == "__main__":
    main()

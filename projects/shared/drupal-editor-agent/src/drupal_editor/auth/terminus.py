"""
Terminus/Drush authentication backend.

Executes Drush commands via Pantheon's Terminus CLI.
This is the primary (preferred) authentication method for Pantheon-hosted sites.
"""

from __future__ import annotations

import asyncio
import os
import json
import shlex
from dataclasses import dataclass
from typing import Optional

from rich.console import Console

console = Console()


@dataclass
class CommandResult:
    """Result from running a shell command."""

    success: bool
    stdout: str
    stderr: str
    return_code: int


class TerminusAuth:
    """
    Authenticate and execute commands via Pantheon Terminus CLI.

    Usage:
        auth = TerminusAuth(site_name="savas-labs", env="live")
        await auth.authenticate()

        # Run Drush commands
        result = await auth.drush("status --format=json")

        # Run PHP code
        result = await auth.php_eval('print "Hello";')
    """

    def __init__(
        self,
        site_name: str,
        env: str = "live",
        machine_token: Optional[str] = None,
    ):
        """
        Initialize Terminus auth.

        Args:
            site_name: Pantheon site name (e.g., "savas-labs")
            env: Environment (e.g., "live", "dev", "test", or multidev name)
            machine_token: Pantheon machine token (defaults to PANTHEON_MACHINE_TOKEN env var)
        """
        self.site_name = site_name
        self.env = env
        self.machine_token = machine_token or os.getenv("PANTHEON_MACHINE_TOKEN")
        self._authenticated = False

    @property
    def site_env(self) -> str:
        """Return the site.env string for Terminus commands."""
        return f"{self.site_name}.{self.env}"

    async def _run_command(
        self,
        command: list[str],
        timeout: int = 120,
        silent: bool = False,
    ) -> CommandResult:
        """Run a shell command asynchronously."""
        if not silent:
            console.print(f"[dim]$ {' '.join(command)}[/dim]")

        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout,
            )

            return CommandResult(
                success=process.returncode == 0,
                stdout=stdout.decode("utf-8"),
                stderr=stderr.decode("utf-8"),
                return_code=process.returncode or 0,
            )

        except asyncio.TimeoutError:
            return CommandResult(
                success=False,
                stdout="",
                stderr=f"Command timed out after {timeout}s",
                return_code=-1,
            )
        except Exception as e:
            return CommandResult(
                success=False,
                stdout="",
                stderr=str(e),
                return_code=-1,
            )

    async def authenticate(self) -> bool:
        """
        Authenticate with Pantheon using machine token.

        If already authenticated at the system level (via `terminus auth:login`),
        the machine token is not required.

        Returns True if authentication succeeds.
        """
        # Check if already authenticated at system level
        whoami_result = await self._run_command(
            ["terminus", "auth:whoami"],
            silent=True,
        )

        if whoami_result.success and whoami_result.stdout.strip():
            console.print(f"[green]Already authenticated as: {whoami_result.stdout.strip()}[/green]")
            self._authenticated = True
            return True

        # Need to authenticate with machine token
        if not self.machine_token:
            console.print("[red]Error: Not authenticated and PANTHEON_MACHINE_TOKEN not set[/red]")
            console.print("[dim]Run 'terminus auth:login' or set PANTHEON_MACHINE_TOKEN[/dim]")
            return False

        # Authenticate with machine token
        console.print("[yellow]Authenticating with Pantheon...[/yellow]")
        auth_result = await self._run_command(
            ["terminus", "auth:login", "--machine-token", self.machine_token],
        )

        if not auth_result.success:
            console.print(f"[red]Authentication failed: {auth_result.stderr}[/red]")
            return False

        console.print("[green]Terminus authentication successful[/green]")
        self._authenticated = True
        return True

    async def drush(
        self,
        command: str,
        timeout: int = 120,
    ) -> CommandResult:
        """
        Execute a Drush command via Terminus.

        Args:
            command: Drush command (without 'drush' prefix)
            timeout: Command timeout in seconds

        Returns:
            CommandResult with stdout, stderr, and success status
        """
        if not self._authenticated:
            await self.authenticate()

        # Build command: terminus drush site.env -- <command>
        cmd_parts = ["terminus", "drush", self.site_env, "--"] + shlex.split(command)

        return await self._run_command(cmd_parts, timeout=timeout)

    async def php_eval(
        self,
        php_code: str,
        timeout: int = 120,
    ) -> CommandResult:
        """
        Execute PHP code via Drush php:eval.

        Args:
            php_code: PHP code to execute (without <?php)
            timeout: Command timeout in seconds

        Returns:
            CommandResult with stdout (output from PHP) and success status
        """
        # Escape the PHP code for shell
        # We use base64 encoding to safely pass complex PHP code
        import base64
        encoded = base64.b64encode(php_code.encode()).decode()

        # PHP code to decode and execute
        wrapper = f'eval(base64_decode("{encoded}"));'

        return await self.drush(f'php:eval \'{wrapper}\'', timeout=timeout)

    async def get_node(self, nid: int) -> Optional[dict]:
        """
        Fetch node data by ID.

        Returns node data as dict, or None if not found.
        """
        php_code = f"""
$node = \\Drupal::entityTypeManager()->getStorage('node')->load({nid});
if ($node) {{
    print json_encode([
        'nid' => $node->id(),
        'uuid' => $node->uuid(),
        'type' => $node->bundle(),
        'title' => $node->getTitle(),
        'status' => $node->isPublished(),
        'moderation_state' => $node->get('moderation_state')->value ?? null,
    ]);
}} else {{
    print 'null';
}}
"""
        result = await self.php_eval(php_code)

        if not result.success:
            console.print(f"[red]Failed to get node {nid}: {result.stderr}[/red]")
            return None

        try:
            data = json.loads(result.stdout.strip())
            return data if data else None
        except json.JSONDecodeError:
            console.print(f"[red]Invalid JSON response: {result.stdout}[/red]")
            return None

    async def get_site_url(self) -> str:
        """Get the URL for the current environment."""
        result = await self._run_command(
            ["terminus", "env:view", self.site_env, "--print"],
            silent=True,
        )

        if result.success and result.stdout.strip():
            return result.stdout.strip()

        # Fallback to predictable URL
        return f"https://{self.env}-{self.site_name}.pantheonsite.io"

    async def close(self) -> None:
        """Clean up resources (no-op for Terminus)."""
        pass

    async def clear_cache(self) -> bool:
        """Clear Drupal cache."""
        result = await self.drush("cr")
        return result.success

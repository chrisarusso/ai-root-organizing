"""
Playwright browser automation backend.

Universal fallback for any Drupal site - works via the admin UI.
"""

from __future__ import annotations

import os
from typing import Optional
from pathlib import Path

from rich.console import Console

console = Console()


class PlaywrightAuth:
    """
    Authenticate via browser automation.

    This is the universal fallback that works on any Drupal site
    with admin login access. No modules or CLI access required.

    Usage:
        auth = PlaywrightAuth(
            base_url="https://savaslabs.com",
            username="admin",
            password="...",
        )
        await auth.authenticate()

        # Edit a node via the UI
        await auth.edit_node(nid=123, changes={"body": "New content"})
    """

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        headless: bool = True,
        screenshots_dir: Optional[Path] = None,
    ):
        """
        Initialize Playwright auth.

        Args:
            base_url: Drupal site URL (e.g., "https://savaslabs.com")
            username: Admin username
            password: Admin password
            headless: Run browser in headless mode
            screenshots_dir: Directory to save screenshots (for audit trail)
        """
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.headless = headless
        self.screenshots_dir = screenshots_dir or Path("./screenshots")
        self._browser = None
        self._context = None
        self._page = None
        self._authenticated = False

    async def authenticate(self) -> bool:
        """
        Login to Drupal via the admin UI.

        Returns True if login succeeds.
        """
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            console.print("[red]Playwright not installed. Run: pip install playwright && playwright install[/red]")
            return False

        console.print(f"[yellow]Launching browser for {self.base_url}...[/yellow]")

        playwright = await async_playwright().start()
        self._browser = await playwright.chromium.launch(headless=self.headless)

        # Create context with realistic settings
        self._context = await self._browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
        )

        self._page = await self._context.new_page()

        # Navigate to login page
        login_url = f"{self.base_url}/user/login"
        console.print(f"[dim]Navigating to {login_url}[/dim]")

        try:
            await self._page.goto(login_url, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            console.print(f"[red]Failed to load login page: {e}[/red]")
            return False

        # Fill login form
        try:
            await self._page.fill('input[name="name"]', self.username)
            await self._page.fill('input[name="pass"]', self.password)
            await self._page.click('input[type="submit"], button[type="submit"]')

            # Wait for navigation
            await self._page.wait_for_load_state("domcontentloaded")

            # Check if login succeeded (look for logout link or admin toolbar)
            logged_in = await self._page.locator('a[href*="/user/logout"], #toolbar-administration').count() > 0

            if logged_in:
                console.print("[green]Login successful[/green]")
                self._authenticated = True
                return True
            else:
                console.print("[red]Login failed - no logout link found[/red]")
                # Take screenshot for debugging
                await self._save_screenshot("login_failed")
                return False

        except Exception as e:
            console.print(f"[red]Login error: {e}[/red]")
            return False

    async def _save_screenshot(self, name: str) -> Optional[str]:
        """Save a screenshot and return the path."""
        if not self._page:
            return None

        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        path = self.screenshots_dir / f"{name}.png"
        await self._page.screenshot(path=str(path))
        console.print(f"[dim]Screenshot saved: {path}[/dim]")
        return str(path)

    async def get_node(self, nid: int) -> Optional[dict]:
        """
        Fetch node data by visiting the edit page.

        Note: This is less efficient than Drush but works universally.
        """
        if not self._authenticated:
            await self.authenticate()

        edit_url = f"{self.base_url}/node/{nid}/edit"
        console.print(f"[dim]Fetching node from {edit_url}[/dim]")

        try:
            await self._page.goto(edit_url, wait_until="domcontentloaded", timeout=30000)

            # Extract basic node info from the edit form
            title = await self._page.locator('input[name="title[0][value]"]').input_value()

            # Try to get moderation state
            moderation_state = None
            try:
                moderation_select = self._page.locator('select[name="moderation_state[0][state]"]')
                if await moderation_select.count() > 0:
                    moderation_state = await moderation_select.input_value()
            except Exception:
                pass

            return {
                "nid": nid,
                "title": title,
                "moderation_state": moderation_state,
            }

        except Exception as e:
            console.print(f"[red]Failed to get node {nid}: {e}[/red]")
            return None

    async def get_site_url(self) -> str:
        """Get the site URL."""
        return self.base_url

    async def close(self) -> None:
        """Clean up browser resources."""
        if self._browser:
            await self._browser.close()
            self._browser = None
            self._context = None
            self._page = None
            self._authenticated = False

    @property
    def page(self):
        """Get the current page for advanced operations."""
        return self._page

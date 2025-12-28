"""
Main DrupalClient - facade for making changes to Drupal sites.

Supports two authentication backends:
1. Terminus/Drush (PRIMARY) - for Pantheon-hosted sites with CLI access
2. Playwright (FALLBACK) - browser automation for any Drupal site
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from drupal_editor.auth.terminus import TerminusAuth
from drupal_editor.auth.playwright import PlaywrightAuth
from drupal_editor.operations.nodes import NodeEditor
from drupal_editor.operations.taxonomy import TaxonomyManager
from drupal_editor.operations.media import MediaEditor
from drupal_editor.tracking.changelog import ChangeLog

if TYPE_CHECKING:
    pass


class DrupalClient:
    """
    Main client for making staged changes to Drupal sites.

    Usage:
        # Auto-detect auth method
        client = DrupalClient.from_env()

        # Or explicitly choose
        client = DrupalClient.with_terminus(site_name="savas-labs")
        client = DrupalClient.with_playwright(base_url="https://example.com", username="admin", password="...")

        # Make changes
        revision = await client.nodes.create_draft_revision(
            nid=123,
            changes={"body": "New content"},
            reason="Ava: Fixed spelling"
        )
    """

    def __init__(
        self,
        auth: TerminusAuth | PlaywrightAuth,
        changelog: ChangeLog | None = None,
    ):
        self.auth = auth
        self.changelog = changelog or ChangeLog()

        # Initialize operation handlers
        self.nodes = NodeEditor(auth=auth, changelog=self.changelog)
        self.taxonomy = TaxonomyManager(auth=auth, changelog=self.changelog)
        self.media = MediaEditor(auth=auth, changelog=self.changelog)

    @classmethod
    def from_env(cls) -> DrupalClient:
        """
        Auto-detect authentication method from environment.

        Checks for Terminus credentials first (PANTHEON_MACHINE_TOKEN + PANTHEON_SITE),
        falls back to Playwright if not available.
        """
        pantheon_token = os.getenv("PANTHEON_MACHINE_TOKEN")
        pantheon_site = os.getenv("PANTHEON_SITE")

        if pantheon_token and pantheon_site:
            return cls.with_terminus(
                site_name=pantheon_site,
                env=os.getenv("PANTHEON_ENV", "live"),
            )

        # Fallback to Playwright
        base_url = os.getenv("DRUPAL_BASE_URL")
        username = os.getenv("DRUPAL_USERNAME")
        password = os.getenv("DRUPAL_PASSWORD")

        if base_url and username and password:
            return cls.with_playwright(
                base_url=base_url,
                username=username,
                password=password,
            )

        raise ValueError(
            "No valid authentication found. Set either:\n"
            "  - PANTHEON_MACHINE_TOKEN + PANTHEON_SITE (for Terminus)\n"
            "  - DRUPAL_BASE_URL + DRUPAL_USERNAME + DRUPAL_PASSWORD (for Playwright)"
        )

    @classmethod
    def with_terminus(
        cls,
        site_name: str,
        env: str = "live",
    ) -> DrupalClient:
        """Create client using Terminus/Drush backend."""
        auth = TerminusAuth(site_name=site_name, env=env)
        return cls(auth=auth)

    @classmethod
    def with_playwright(
        cls,
        base_url: str,
        username: str,
        password: str,
    ) -> DrupalClient:
        """Create client using Playwright browser automation."""
        auth = PlaywrightAuth(
            base_url=base_url,
            username=username,
            password=password,
        )
        return cls(auth=auth)

    async def authenticate(self) -> bool:
        """Authenticate with the Drupal site."""
        return await self.auth.authenticate()

    async def close(self) -> None:
        """Clean up resources."""
        await self.auth.close()

    def get_summary(self) -> str:
        """Get a summary of all changes made."""
        from drupal_editor.tracking.summary import SummaryGenerator
        generator = SummaryGenerator(self.changelog)
        return generator.generate_slack_summary()

    @property
    def auth_method(self) -> str:
        """Return the authentication method being used."""
        if isinstance(self.auth, TerminusAuth):
            return "terminus"
        return "playwright"

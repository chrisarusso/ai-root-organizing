"""
Drupal Editor Agent - Make staged/reviewable changes to Drupal sites.

Primary method: Terminus/Drush (CLI)
Fallback: Playwright browser automation

Usage:
    from drupal_editor import DrupalClient

    # Auto-detect auth method (Terminus if available, else Playwright)
    client = DrupalClient.from_env()

    # Or explicitly choose
    client = DrupalClient.with_terminus(site_name="savas-labs", env="live")
    client = DrupalClient.with_playwright(base_url="https://savaslabs.com", username="admin", password="...")

    # Make changes
    revision = await client.nodes.create_draft_revision(
        nid=123,
        changes={"body": "Updated content"},
        reason="Ava: Fixed spelling error"
    )
"""

from drupal_editor.client import DrupalClient
from drupal_editor.tracking.changelog import ChangeLog, ChangeRecord

__all__ = ["DrupalClient", "ChangeLog", "ChangeRecord"]
__version__ = "0.1.0"

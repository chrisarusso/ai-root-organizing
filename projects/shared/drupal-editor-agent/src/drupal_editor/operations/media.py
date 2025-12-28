"""
Media entity operations for Drupal.

Primarily used for updating alt text on images.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional
from dataclasses import dataclass

from rich.console import Console

if TYPE_CHECKING:
    from drupal_editor.auth.terminus import TerminusAuth
    from drupal_editor.auth.playwright import PlaywrightAuth
    from drupal_editor.tracking.changelog import ChangeLog

console = Console()


@dataclass
class MediaUpdate:
    """Result from updating a media entity."""

    mid: int
    success: bool
    revision_url: Optional[str] = None
    error: Optional[str] = None


class MediaEditor:
    """
    Edit media entities in Drupal.

    Primary use case: Updating alt text on images for accessibility.
    """

    def __init__(
        self,
        auth: "TerminusAuth | PlaywrightAuth",
        changelog: "ChangeLog",
    ):
        self.auth = auth
        self.changelog = changelog

    async def update_alt_text(
        self,
        mid: int,
        alt_text: str,
        reason: str,
    ) -> MediaUpdate:
        """
        Update the alt text on a media entity.

        Args:
            mid: Media entity ID
            alt_text: New alt text
            reason: Reason for the change

        Returns:
            MediaUpdate with success status
        """
        from drupal_editor.auth.terminus import TerminusAuth

        if isinstance(self.auth, TerminusAuth):
            return await self._update_via_drush(mid, alt_text, reason)
        else:
            return await self._update_via_browser(mid, alt_text, reason)

    async def _update_via_drush(
        self,
        mid: int,
        alt_text: str,
        reason: str,
    ) -> MediaUpdate:
        """Update alt text via Drush."""
        from drupal_editor.auth.terminus import TerminusAuth

        auth: TerminusAuth = self.auth  # type: ignore

        alt_escaped = alt_text.replace("'", "\\'")
        reason_escaped = reason.replace("'", "\\'")

        php_code = f"""
$media = \\Drupal::entityTypeManager()->getStorage('media')->load({mid});
if (!$media) {{
    print json_encode(['success' => false, 'error' => 'Media not found']);
    return;
}}

// Get the source field (usually field_media_image)
$source_field = $media->getSource()->getConfiguration()['source_field'] ?? 'field_media_image';

if (!$media->hasField($source_field)) {{
    print json_encode(['success' => false, 'error' => 'No image field found']);
    return;
}}

// Update alt text
$media->get($source_field)->alt = '{alt_escaped}';

// Create new revision if revision support exists
if ($media->getEntityType()->isRevisionable()) {{
    $media->setNewRevision(TRUE);
    $media->setRevisionLogMessage('{reason_escaped}');
}}

try {{
    $media->save();
    print json_encode([
        'success' => true,
        'mid' => $media->id(),
        'revision_id' => $media->getRevisionId() ?? $media->id(),
    ]);
}} catch (\\Exception $e) {{
    print json_encode(['success' => false, 'error' => $e->getMessage()]);
}}
"""
        result = await auth.php_eval(php_code)

        if not result.success:
            error = f"Drush failed: {result.stderr}"
            self._record_failure(mid, alt_text, reason, error)
            return MediaUpdate(mid=mid, success=False, error=error)

        try:
            import json
            response = json.loads(result.stdout.strip())
        except Exception:
            error = f"Invalid response: {result.stdout}"
            self._record_failure(mid, alt_text, reason, error)
            return MediaUpdate(mid=mid, success=False, error=error)

        if not response.get("success"):
            error = response.get("error", "Unknown error")
            self._record_failure(mid, alt_text, reason, error)
            return MediaUpdate(mid=mid, success=False, error=error)

        # Record success
        site_url = await auth.get_site_url()
        revision_url = f"{site_url}/media/{mid}/edit"

        self.changelog.record(
            auth_method="terminus",
            operation="update_media",
            target=f"media/{mid}",
            field="alt",
            old_value="(previous alt)",
            new_value=alt_text,
            reason=reason,
            revision_url=revision_url,
            success=True,
        )

        console.print(f"[green]Updated alt text for media/{mid}[/green]")

        return MediaUpdate(mid=mid, success=True, revision_url=revision_url)

    async def _update_via_browser(
        self,
        mid: int,
        alt_text: str,
        reason: str,
    ) -> MediaUpdate:
        """Update alt text via Playwright."""
        # Placeholder - would navigate to media edit form
        console.print("[yellow]Media update via Playwright not yet implemented[/yellow]")
        return MediaUpdate(mid=mid, success=False, error="Not implemented")

    def _record_failure(
        self,
        mid: int,
        alt_text: str,
        reason: str,
        error: str,
    ) -> None:
        """Record failed update."""
        self.changelog.record(
            auth_method="terminus" if hasattr(self.auth, "drush") else "playwright",
            operation="update_media",
            target=f"media/{mid}",
            field="alt",
            old_value="",
            new_value=alt_text,
            reason=reason,
            success=False,
            error=error,
        )

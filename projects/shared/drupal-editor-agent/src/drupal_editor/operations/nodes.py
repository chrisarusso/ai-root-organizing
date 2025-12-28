"""
Node operations for Drupal.

Supports creating draft revisions with proposed changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING
import json
import re

from rich.console import Console

if TYPE_CHECKING:
    from drupal_editor.auth.terminus import TerminusAuth
    from drupal_editor.auth.playwright import PlaywrightAuth
    from drupal_editor.tracking.changelog import ChangeLog

console = Console()


@dataclass
class DraftRevision:
    """Result from creating a draft revision."""

    nid: int
    revision_id: int
    moderation_state: str
    revision_url: str
    success: bool
    error: Optional[str] = None


class NodeEditor:
    """
    Edit Drupal nodes via CLI or browser.

    Creates draft revisions with proposed changes that require human approval.
    """

    # Default moderation state for agent suggestions
    DEFAULT_MODERATION_STATE = "ava_suggestion"

    def __init__(
        self,
        auth: "TerminusAuth | PlaywrightAuth",
        changelog: "ChangeLog",
        moderation_state: str = DEFAULT_MODERATION_STATE,
    ):
        """
        Initialize node editor.

        Args:
            auth: Authentication backend (Terminus or Playwright)
            changelog: Change tracking log
            moderation_state: Moderation state for new revisions (default: ava_suggestion)
        """
        self.auth = auth
        self.changelog = changelog
        self.moderation_state = moderation_state

    async def create_draft_revision(
        self,
        nid: int,
        changes: dict[str, str],
        reason: str,
    ) -> DraftRevision:
        """
        Create a new revision with proposed changes.

        The revision will be in the configured moderation state (default: ava_suggestion)
        for human review before publishing.

        Args:
            nid: Node ID to update
            changes: Dict of field_name -> new_value
            reason: Reason for the change (stored in revision log)

        Returns:
            DraftRevision with revision details
        """
        from drupal_editor.auth.terminus import TerminusAuth

        if isinstance(self.auth, TerminusAuth):
            return await self._via_drush(nid, changes, reason)
        else:
            return await self._via_browser(nid, changes, reason)

    async def _via_drush(
        self,
        nid: int,
        changes: dict[str, str],
        reason: str,
    ) -> DraftRevision:
        """Create draft revision via Drush php:eval."""
        from drupal_editor.auth.terminus import TerminusAuth

        auth: TerminusAuth = self.auth  # type: ignore

        # First, get current node data for the changelog
        current_node = await auth.get_node(nid)
        if not current_node:
            return DraftRevision(
                nid=nid,
                revision_id=0,
                moderation_state="",
                revision_url="",
                success=False,
                error=f"Node {nid} not found",
            )

        # Build PHP code to update the node
        # We need to handle different field types
        changes_json = json.dumps(changes)
        reason_escaped = reason.replace("'", "\\'")
        moderation_state = self.moderation_state

        php_code = f"""
$nid = {nid};
$changes = json_decode('{changes_json}', TRUE);
$reason = '{reason_escaped}';
$moderation_state = '{moderation_state}';

$node = \\Drupal::entityTypeManager()->getStorage('node')->load($nid);
if (!$node) {{
    print json_encode(['success' => false, 'error' => 'Node not found']);
    return;
}}

// Create new revision
$node->setNewRevision(TRUE);
$node->setRevisionLogMessage($reason);
$node->setRevisionCreationTime(time());

// Apply changes to fields
foreach ($changes as $field_name => $new_value) {{
    if ($node->hasField($field_name)) {{
        $field = $node->get($field_name);
        $field_type = $field->getFieldDefinition()->getType();

        // Handle different field types
        if (in_array($field_type, ['text_long', 'text_with_summary', 'string_long'])) {{
            // For text fields, we might be doing a find/replace
            // For now, just set the value directly
            if ($field_type === 'text_with_summary') {{
                $node->set($field_name, ['value' => $new_value, 'format' => $field->format ?? 'basic_html']);
            }} else {{
                $node->set($field_name, $new_value);
            }}
        }} elseif ($field_type === 'string') {{
            $node->set($field_name, $new_value);
        }} else {{
            // For other fields, try direct set
            $node->set($field_name, $new_value);
        }}
    }}
}}

// Set moderation state if content moderation is enabled
if ($node->hasField('moderation_state')) {{
    $node->set('moderation_state', $moderation_state);
}}

// Save the node
try {{
    $node->save();
    print json_encode([
        'success' => true,
        'nid' => $node->id(),
        'revision_id' => $node->getRevisionId(),
        'moderation_state' => $node->get('moderation_state')->value ?? 'published',
    ]);
}} catch (\\Exception $e) {{
    print json_encode(['success' => false, 'error' => $e->getMessage()]);
}}
"""

        console.print(f"[yellow]Creating draft revision for node/{nid}...[/yellow]")
        result = await auth.php_eval(php_code)

        if not result.success:
            error_msg = f"Drush failed: {result.stderr}"
            self._record_failure(nid, changes, reason, error_msg)
            return DraftRevision(
                nid=nid,
                revision_id=0,
                moderation_state="",
                revision_url="",
                success=False,
                error=error_msg,
            )

        # Parse response
        try:
            response = json.loads(result.stdout.strip())
        except json.JSONDecodeError:
            error_msg = f"Invalid JSON response: {result.stdout}"
            self._record_failure(nid, changes, reason, error_msg)
            return DraftRevision(
                nid=nid,
                revision_id=0,
                moderation_state="",
                revision_url="",
                success=False,
                error=error_msg,
            )

        if not response.get("success"):
            error_msg = response.get("error", "Unknown error")
            self._record_failure(nid, changes, reason, error_msg)
            return DraftRevision(
                nid=nid,
                revision_id=0,
                moderation_state="",
                revision_url="",
                success=False,
                error=error_msg,
            )

        # Build revision URL
        site_url = await auth.get_site_url()
        revision_id = response["revision_id"]
        revision_url = f"{site_url}/node/{nid}/revisions/{revision_id}/view"

        # Record success in changelog
        for field_name, new_value in changes.items():
            self.changelog.record(
                auth_method="terminus",
                operation="update_node",
                target=f"node/{nid}",
                field=field_name,
                old_value="(previous value)",  # We could fetch this but it's expensive
                new_value=new_value,
                reason=reason,
                revision_id=revision_id,
                revision_url=revision_url,
                success=True,
            )

        console.print(f"[green]Created revision {revision_id} for node/{nid}[/green]")
        console.print(f"[dim]Review URL: {revision_url}[/dim]")

        return DraftRevision(
            nid=nid,
            revision_id=revision_id,
            moderation_state=response.get("moderation_state", moderation_state),
            revision_url=revision_url,
            success=True,
        )

    async def _via_browser(
        self,
        nid: int,
        changes: dict[str, str],
        reason: str,
    ) -> DraftRevision:
        """Create draft revision via Playwright browser automation."""
        from drupal_editor.auth.playwright import PlaywrightAuth

        auth: PlaywrightAuth = self.auth  # type: ignore

        if not auth._authenticated:
            if not await auth.authenticate():
                return DraftRevision(
                    nid=nid,
                    revision_id=0,
                    moderation_state="",
                    revision_url="",
                    success=False,
                    error="Failed to authenticate",
                )

        page = auth.page
        edit_url = f"{auth.base_url}/node/{nid}/edit"

        console.print(f"[yellow]Opening {edit_url}...[/yellow]")

        try:
            await page.goto(edit_url, wait_until="domcontentloaded", timeout=30000)

            # Take screenshot before changes
            before_screenshot = await auth._save_screenshot(f"node_{nid}_before")

            # Apply changes to form fields
            for field_name, new_value in changes.items():
                # Try different field selectors
                selectors = [
                    f'textarea[name="{field_name}[0][value]"]',
                    f'input[name="{field_name}[0][value]"]',
                    f'textarea[name="{field_name}"]',
                    f'input[name="{field_name}"]',
                    # CKEditor iframe handling would go here
                ]

                filled = False
                for selector in selectors:
                    try:
                        element = page.locator(selector)
                        if await element.count() > 0:
                            await element.fill(new_value)
                            filled = True
                            console.print(f"[dim]Filled {field_name}[/dim]")
                            break
                    except Exception:
                        continue

                if not filled:
                    console.print(f"[yellow]Warning: Could not find field {field_name}[/yellow]")

            # Set moderation state
            moderation_selector = 'select[name="moderation_state[0][state]"]'
            try:
                moderation_select = page.locator(moderation_selector)
                if await moderation_select.count() > 0:
                    await moderation_select.select_option(self.moderation_state)
                    console.print(f"[dim]Set moderation state: {self.moderation_state}[/dim]")
            except Exception as e:
                console.print(f"[yellow]Could not set moderation state: {e}[/yellow]")

            # Set revision log message
            revision_log_selector = 'textarea[name="revision_log[0][value]"]'
            try:
                revision_log = page.locator(revision_log_selector)
                if await revision_log.count() > 0:
                    await revision_log.fill(reason)
            except Exception:
                pass

            # Submit the form
            await page.click('input[type="submit"][value="Save"], button[type="submit"]')
            await page.wait_for_load_state("domcontentloaded")

            # Take screenshot after save
            after_screenshot = await auth._save_screenshot(f"node_{nid}_after")

            # Try to extract revision ID from URL or page
            current_url = page.url

            # Look for success message
            success_message = await page.locator('.messages--status, .messages.status').count() > 0

            if success_message:
                # Record success
                for field_name, new_value in changes.items():
                    self.changelog.record(
                        auth_method="playwright",
                        operation="update_node",
                        target=f"node/{nid}",
                        field=field_name,
                        old_value="(previous value)",
                        new_value=new_value,
                        reason=reason,
                        revision_url=current_url,
                        screenshot_path=after_screenshot,
                        success=True,
                    )

                console.print(f"[green]Saved changes to node/{nid}[/green]")

                return DraftRevision(
                    nid=nid,
                    revision_id=0,  # Hard to extract via UI
                    moderation_state=self.moderation_state,
                    revision_url=f"{auth.base_url}/node/{nid}",
                    success=True,
                )
            else:
                error_msg = "No success message found after save"
                self._record_failure(nid, changes, reason, error_msg)
                return DraftRevision(
                    nid=nid,
                    revision_id=0,
                    moderation_state="",
                    revision_url="",
                    success=False,
                    error=error_msg,
                )

        except Exception as e:
            error_msg = str(e)
            self._record_failure(nid, changes, reason, error_msg)
            return DraftRevision(
                nid=nid,
                revision_id=0,
                moderation_state="",
                revision_url="",
                success=False,
                error=error_msg,
            )

    def _record_failure(
        self,
        nid: int,
        changes: dict[str, str],
        reason: str,
        error: str,
    ) -> None:
        """Record a failed change attempt."""
        for field_name, new_value in changes.items():
            self.changelog.record(
                auth_method="terminus" if hasattr(self.auth, "drush") else "playwright",
                operation="update_node",
                target=f"node/{nid}",
                field=field_name,
                old_value="",
                new_value=new_value,
                reason=reason,
                success=False,
                error=error,
            )

    async def find_and_replace(
        self,
        nid: int,
        field: str,
        find: str,
        replace: str,
        reason: str,
    ) -> DraftRevision:
        """
        Find and replace text in a node field.

        This is a convenience method that fetches the current value,
        performs the replacement, and creates a draft revision.
        """
        # Get current value
        from drupal_editor.auth.terminus import TerminusAuth

        if isinstance(self.auth, TerminusAuth):
            # Use Drush to get field value
            php_code = f"""
$node = \\Drupal::entityTypeManager()->getStorage('node')->load({nid});
if ($node && $node->hasField('{field}')) {{
    $value = $node->get('{field}')->value ?? '';
    print $value;
}} else {{
    print '';
}}
"""
            result = await self.auth.php_eval(php_code)
            current_value = result.stdout if result.success else ""
        else:
            # For Playwright, we'd need to extract from the form
            console.print("[yellow]Find/replace via Playwright not fully implemented[/yellow]")
            current_value = ""

        if not current_value:
            return DraftRevision(
                nid=nid,
                revision_id=0,
                moderation_state="",
                revision_url="",
                success=False,
                error=f"Could not get current value of {field}",
            )

        # Perform replacement
        if find not in current_value:
            return DraftRevision(
                nid=nid,
                revision_id=0,
                moderation_state="",
                revision_url="",
                success=False,
                error=f"'{find}' not found in {field}",
            )

        new_value = current_value.replace(find, replace)

        # Create the revision
        return await self.create_draft_revision(
            nid=nid,
            changes={field: new_value},
            reason=reason,
        )

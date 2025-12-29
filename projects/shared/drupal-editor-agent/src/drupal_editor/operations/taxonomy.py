"""
Taxonomy term operations for Drupal.

Note: Taxonomy terms don't support revisions in core Drupal,
so changes are logged but require human approval via Slack notification.

However, taxonomy REFERENCES on nodes (e.g., field_topics) do create revisions
when the node is saved, so those can be applied automatically.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Optional
from dataclasses import dataclass

from rich.console import Console

from drupal_editor.operations.nodes import DraftRevision

if TYPE_CHECKING:
    from drupal_editor.auth.terminus import TerminusAuth
    from drupal_editor.auth.playwright import PlaywrightAuth
    from drupal_editor.tracking.changelog import ChangeLog

console = Console()


@dataclass
class TaxonomyProposal:
    """A proposed taxonomy change (not applied, just logged)."""

    action: str  # "add_term", "remove_term", "update_term", "add_reference"
    target: str  # "taxonomy_term/123" or "node/456"
    vocabulary: str
    term_name: str
    success: bool = True
    message: str = ""


class TaxonomyManager:
    """
    Manage taxonomy terms and references.

    Since taxonomy terms don't support revisions, this manager:
    - Logs proposed changes
    - Generates notifications for human review
    - Does NOT automatically apply changes

    To apply changes:
    1. Review the proposals in Slack/logs
    2. Manually approve in Drupal admin
    """

    def __init__(
        self,
        auth: "TerminusAuth | PlaywrightAuth",
        changelog: "ChangeLog",
    ):
        self.auth = auth
        self.changelog = changelog

    async def propose_add_term(
        self,
        vocabulary: str,
        term_name: str,
        reason: str,
    ) -> TaxonomyProposal:
        """
        Propose adding a new taxonomy term.

        This logs the proposal but does NOT create the term.
        Human must approve and create manually.
        """
        console.print(f"[yellow]Proposal: Add term '{term_name}' to {vocabulary}[/yellow]")
        console.print(f"[yellow]Reason: {reason}[/yellow]")
        console.print("[yellow]Note: Taxonomy terms require manual approval (no revisions)[/yellow]")

        self.changelog.record(
            auth_method="proposal",
            operation="propose_add_term",
            target=f"vocabulary/{vocabulary}",
            field="name",
            old_value="",
            new_value=term_name,
            reason=reason,
            success=True,
        )

        return TaxonomyProposal(
            action="add_term",
            target=f"vocabulary/{vocabulary}",
            vocabulary=vocabulary,
            term_name=term_name,
            message=f"Proposed: Add '{term_name}' to {vocabulary}. Requires manual approval.",
        )

    async def propose_node_tag(
        self,
        nid: int,
        term_field: str,
        term_name: str,
        vocabulary: str,
        reason: str,
    ) -> TaxonomyProposal:
        """
        Propose adding a taxonomy term reference to a node.

        This CAN be applied automatically since it creates a node revision.
        """
        console.print(f"[yellow]Proposal: Add tag '{term_name}' to node/{nid}[/yellow]")

        # This could be implemented as a node update
        # For now, just log the proposal
        self.changelog.record(
            auth_method="proposal",
            operation="propose_node_tag",
            target=f"node/{nid}",
            field=term_field,
            old_value="",
            new_value=term_name,
            reason=reason,
            success=True,
        )

        return TaxonomyProposal(
            action="add_reference",
            target=f"node/{nid}",
            vocabulary=vocabulary,
            term_name=term_name,
            message=f"Proposed: Add tag '{term_name}' to node/{nid}",
        )

    async def get_terms(self, vocabulary: str) -> list[dict]:
        """Get all terms in a vocabulary."""
        from drupal_editor.auth.terminus import TerminusAuth

        if isinstance(self.auth, TerminusAuth):
            php_code = f"""
$terms = \\Drupal::entityTypeManager()
    ->getStorage('taxonomy_term')
    ->loadTree('{vocabulary}');

$result = [];
foreach ($terms as $term) {{
    $result[] = [
        'tid' => $term->tid,
        'name' => $term->name,
        'depth' => $term->depth,
    ];
}}
print json_encode($result);
"""
            result = await self.auth.php_eval(php_code)
            if result.success:
                try:
                    return json.loads(result.stdout.strip())
                except Exception:
                    return []
        return []

    async def get_term_id_by_name(
        self,
        vocabulary: str,
        term_name: str,
    ) -> Optional[int]:
        """
        Look up a taxonomy term ID by its name.

        Args:
            vocabulary: Vocabulary machine name (e.g., "topic")
            term_name: Term name to look up

        Returns:
            Term ID if found, None otherwise
        """
        from drupal_editor.auth.terminus import TerminusAuth

        if isinstance(self.auth, TerminusAuth):
            # Escape single quotes in term name
            safe_name = term_name.replace("'", "\\'")
            php_code = f"""
$terms = \\Drupal::entityTypeManager()
    ->getStorage('taxonomy_term')
    ->loadByProperties([
        'vid' => '{vocabulary}',
        'name' => '{safe_name}',
    ]);
if ($terms) {{
    $term = reset($terms);
    print $term->id();
}} else {{
    print 'null';
}}
"""
            result = await self.auth.php_eval(php_code)
            if result.success:
                output = result.stdout.strip()
                if output and output != 'null':
                    try:
                        return int(output)
                    except ValueError:
                        pass
        return None

    async def add_tag_to_node(
        self,
        nid: int,
        field_name: str,
        term_id: int,
        reason: str,
        moderation_state: str = "draft",
    ) -> DraftRevision:
        """
        Add a taxonomy term reference to a node.

        Creates a new revision with the tag added, in the specified moderation state.

        Args:
            nid: Node ID
            field_name: Field machine name (e.g., "field_topics")
            term_id: Taxonomy term ID to add
            reason: Reason for the change (stored in revision log)
            moderation_state: Target moderation state (default: "draft")
                              Must exist in Drupal or the operation will fail.

        Returns:
            DraftRevision with revision details
        """
        from drupal_editor.auth.terminus import TerminusAuth

        if not isinstance(self.auth, TerminusAuth):
            return DraftRevision(
                nid=nid,
                revision_id=0,
                moderation_state="",
                revision_url="",
                success=False,
                error="add_tag_to_node only supported via Terminus",
            )

        reason_escaped = reason.replace("'", "\\'")
        php_code = f"""
$nid = {nid};
$field_name = '{field_name}';
$term_id = {term_id};
$reason = '{reason_escaped}';
$target_moderation_state = '{moderation_state}';

$node = \\Drupal::entityTypeManager()->getStorage('node')->load($nid);
if (!$node) {{
    print json_encode(['success' => false, 'error' => 'Node not found']);
    return;
}}

if (!$node->hasField($field_name)) {{
    print json_encode(['success' => false, 'error' => 'Field not found: ' . $field_name]);
    return;
}}

// Check if content moderation is enabled for this node
if (!$node->hasField('moderation_state')) {{
    print json_encode(['success' => false, 'error' => 'Content moderation not enabled for this content type. Enable it in Drupal before applying changes.']);
    return;
}}

// Verify the target moderation state exists
$workflow_id = \\Drupal::service('content_moderation.moderation_information')->getWorkflowForEntity($node);
if (!$workflow_id) {{
    print json_encode(['success' => false, 'error' => 'No workflow found for this content type']);
    return;
}}
$workflow = \\Drupal::entityTypeManager()->getStorage('workflow')->load($workflow_id->id());
$states = $workflow->getTypePlugin()->getStates();
if (!isset($states[$target_moderation_state])) {{
    $available = implode(', ', array_keys($states));
    print json_encode(['success' => false, 'error' => "Moderation state '$target_moderation_state' not found. Available states: $available"]);
    return;
}}

// Get current tags
$current_tags = array_column($node->get($field_name)->getValue(), 'target_id');

// Check if already has this tag
if (in_array($term_id, $current_tags)) {{
    print json_encode(['success' => true, 'message' => 'Tag already present', 'revision_id' => $node->getRevisionId()]);
    return;
}}

// Add the new tag
$current_tags[] = $term_id;

// Create new revision
$node->setNewRevision(TRUE);
$node->setRevisionLogMessage($reason);
$node->setRevisionCreationTime(time());

// Set moderation state to draft/review
$node->set('moderation_state', $target_moderation_state);

// Set the field
$node->set($field_name, $current_tags);

try {{
    $node->save();
    print json_encode([
        'success' => true,
        'nid' => $node->id(),
        'revision_id' => $node->getRevisionId(),
        'moderation_state' => $node->get('moderation_state')->value ?? 'unknown',
    ]);
}} catch (\\Exception $e) {{
    print json_encode(['success' => false, 'error' => $e->getMessage()]);
}}
"""
        console.print(f"[yellow]Adding tag (tid={term_id}) to node/{nid}...[/yellow]")
        result = await self.auth.php_eval(php_code)

        if not result.success:
            error_msg = f"Drush failed: {result.stderr}"
            self.changelog.record(
                auth_method="terminus",
                operation="add_tag_to_node",
                target=f"node/{nid}",
                field=field_name,
                old_value="",
                new_value=str(term_id),
                reason=reason,
                success=False,
                error=error_msg,
            )
            return DraftRevision(
                nid=nid,
                revision_id=0,
                moderation_state="",
                revision_url="",
                success=False,
                error=error_msg,
            )

        try:
            response = json.loads(result.stdout.strip())
        except json.JSONDecodeError:
            error_msg = f"Invalid JSON response: {result.stdout}"
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
            return DraftRevision(
                nid=nid,
                revision_id=0,
                moderation_state="",
                revision_url="",
                success=False,
                error=error_msg,
            )

        revision_id = response.get("revision_id", 0)
        site_url = await self.auth.get_site_url()
        revision_url = f"{site_url}/node/{nid}/revisions/{revision_id}/view"

        self.changelog.record(
            auth_method="terminus",
            operation="add_tag_to_node",
            target=f"node/{nid}",
            field=field_name,
            old_value="",
            new_value=str(term_id),
            reason=reason,
            revision_id=revision_id,
            revision_url=revision_url,
            success=True,
        )

        console.print(f"[green]Added tag to node/{nid} (revision {revision_id})[/green]")

        return DraftRevision(
            nid=nid,
            revision_id=revision_id,
            moderation_state=response.get("moderation_state", ""),
            revision_url=revision_url,
            success=True,
        )

    async def remove_tag_from_node(
        self,
        nid: int,
        field_name: str,
        term_id: int,
        reason: str,
        moderation_state: str = "draft",
    ) -> DraftRevision:
        """
        Remove a taxonomy term reference from a node.

        Creates a new revision with the tag removed, in the specified moderation state.

        Args:
            nid: Node ID
            field_name: Field machine name (e.g., "field_topics")
            term_id: Taxonomy term ID to remove
            reason: Reason for the change (stored in revision log)
            moderation_state: Target moderation state (default: "draft")
                              Must exist in Drupal or the operation will fail.

        Returns:
            DraftRevision with revision details
        """
        from drupal_editor.auth.terminus import TerminusAuth

        if not isinstance(self.auth, TerminusAuth):
            return DraftRevision(
                nid=nid,
                revision_id=0,
                moderation_state="",
                revision_url="",
                success=False,
                error="remove_tag_from_node only supported via Terminus",
            )

        reason_escaped = reason.replace("'", "\\'")
        php_code = f"""
$nid = {nid};
$field_name = '{field_name}';
$term_id = {term_id};
$reason = '{reason_escaped}';
$target_moderation_state = '{moderation_state}';

$node = \\Drupal::entityTypeManager()->getStorage('node')->load($nid);
if (!$node) {{
    print json_encode(['success' => false, 'error' => 'Node not found']);
    return;
}}

if (!$node->hasField($field_name)) {{
    print json_encode(['success' => false, 'error' => 'Field not found: ' . $field_name]);
    return;
}}

// Check if content moderation is enabled for this node
if (!$node->hasField('moderation_state')) {{
    print json_encode(['success' => false, 'error' => 'Content moderation not enabled for this content type. Enable it in Drupal before applying changes.']);
    return;
}}

// Verify the target moderation state exists
$workflow_id = \\Drupal::service('content_moderation.moderation_information')->getWorkflowForEntity($node);
if (!$workflow_id) {{
    print json_encode(['success' => false, 'error' => 'No workflow found for this content type']);
    return;
}}
$workflow = \\Drupal::entityTypeManager()->getStorage('workflow')->load($workflow_id->id());
$states = $workflow->getTypePlugin()->getStates();
if (!isset($states[$target_moderation_state])) {{
    $available = implode(', ', array_keys($states));
    print json_encode(['success' => false, 'error' => "Moderation state '$target_moderation_state' not found. Available states: $available"]);
    return;
}}

// Get current tags
$current_tags = array_column($node->get($field_name)->getValue(), 'target_id');

// Remove the tag
$new_tags = array_values(array_filter($current_tags, function($tid) use ($term_id) {{
    return $tid != $term_id;
}}));

// Check if anything changed
if (count($new_tags) == count($current_tags)) {{
    print json_encode(['success' => true, 'message' => 'Tag not present', 'revision_id' => $node->getRevisionId()]);
    return;
}}

// Create new revision
$node->setNewRevision(TRUE);
$node->setRevisionLogMessage($reason);
$node->setRevisionCreationTime(time());

// Set moderation state to draft/review
$node->set('moderation_state', $target_moderation_state);

// Set the field
$node->set($field_name, $new_tags);

try {{
    $node->save();
    print json_encode([
        'success' => true,
        'nid' => $node->id(),
        'revision_id' => $node->getRevisionId(),
        'moderation_state' => $node->get('moderation_state')->value ?? 'unknown',
    ]);
}} catch (\\Exception $e) {{
    print json_encode(['success' => false, 'error' => $e->getMessage()]);
}}
"""
        console.print(f"[yellow]Removing tag (tid={term_id}) from node/{nid}...[/yellow]")
        result = await self.auth.php_eval(php_code)

        if not result.success:
            error_msg = f"Drush failed: {result.stderr}"
            return DraftRevision(
                nid=nid,
                revision_id=0,
                moderation_state="",
                revision_url="",
                success=False,
                error=error_msg,
            )

        try:
            response = json.loads(result.stdout.strip())
        except json.JSONDecodeError:
            return DraftRevision(
                nid=nid,
                revision_id=0,
                moderation_state="",
                revision_url="",
                success=False,
                error=f"Invalid JSON response: {result.stdout}",
            )

        if not response.get("success"):
            return DraftRevision(
                nid=nid,
                revision_id=0,
                moderation_state="",
                revision_url="",
                success=False,
                error=response.get("error", "Unknown error"),
            )

        revision_id = response.get("revision_id", 0)
        site_url = await self.auth.get_site_url()
        revision_url = f"{site_url}/node/{nid}/revisions/{revision_id}/view"

        self.changelog.record(
            auth_method="terminus",
            operation="remove_tag_from_node",
            target=f"node/{nid}",
            field=field_name,
            old_value=str(term_id),
            new_value="",
            reason=reason,
            revision_id=revision_id,
            revision_url=revision_url,
            success=True,
        )

        console.print(f"[green]Removed tag from node/{nid} (revision {revision_id})[/green]")

        return DraftRevision(
            nid=nid,
            revision_id=revision_id,
            moderation_state=response.get("moderation_state", ""),
            revision_url=revision_url,
            success=True,
        )

    async def replace_tag_on_node(
        self,
        nid: int,
        field_name: str,
        old_term_id: int,
        new_term_id: int,
        reason: str,
        moderation_state: str = "draft",
    ) -> DraftRevision:
        """
        Replace one taxonomy term with another on a node.

        Creates a new revision with the old tag replaced by the new one, in the specified moderation state.

        Args:
            nid: Node ID
            field_name: Field machine name (e.g., "field_topics")
            old_term_id: Taxonomy term ID to remove
            new_term_id: Taxonomy term ID to add
            reason: Reason for the change (stored in revision log)
            moderation_state: Target moderation state (default: "draft")
                              Must exist in Drupal or the operation will fail.

        Returns:
            DraftRevision with revision details
        """
        from drupal_editor.auth.terminus import TerminusAuth

        if not isinstance(self.auth, TerminusAuth):
            return DraftRevision(
                nid=nid,
                revision_id=0,
                moderation_state="",
                revision_url="",
                success=False,
                error="replace_tag_on_node only supported via Terminus",
            )

        reason_escaped = reason.replace("'", "\\'")
        php_code = f"""
$nid = {nid};
$field_name = '{field_name}';
$old_term_id = {old_term_id};
$new_term_id = {new_term_id};
$reason = '{reason_escaped}';
$target_moderation_state = '{moderation_state}';

$node = \\Drupal::entityTypeManager()->getStorage('node')->load($nid);
if (!$node) {{
    print json_encode(['success' => false, 'error' => 'Node not found']);
    return;
}}

if (!$node->hasField($field_name)) {{
    print json_encode(['success' => false, 'error' => 'Field not found: ' . $field_name]);
    return;
}}

// Check if content moderation is enabled for this node
if (!$node->hasField('moderation_state')) {{
    print json_encode(['success' => false, 'error' => 'Content moderation not enabled for this content type. Enable it in Drupal before applying changes.']);
    return;
}}

// Verify the target moderation state exists
$workflow_id = \\Drupal::service('content_moderation.moderation_information')->getWorkflowForEntity($node);
if (!$workflow_id) {{
    print json_encode(['success' => false, 'error' => 'No workflow found for this content type']);
    return;
}}
$workflow = \\Drupal::entityTypeManager()->getStorage('workflow')->load($workflow_id->id());
$states = $workflow->getTypePlugin()->getStates();
if (!isset($states[$target_moderation_state])) {{
    $available = implode(', ', array_keys($states));
    print json_encode(['success' => false, 'error' => "Moderation state '$target_moderation_state' not found. Available states: $available"]);
    return;
}}

// Get current tags
$current_tags = array_column($node->get($field_name)->getValue(), 'target_id');

// Check if old tag exists
if (!in_array($old_term_id, $current_tags)) {{
    print json_encode(['success' => false, 'error' => 'Old tag not present on node']);
    return;
}}

// Replace old with new
$new_tags = array_map(function($tid) use ($old_term_id, $new_term_id) {{
    return ($tid == $old_term_id) ? $new_term_id : $tid;
}}, $current_tags);

// Remove duplicates (in case new_term_id was already there)
$new_tags = array_values(array_unique($new_tags));

// Create new revision
$node->setNewRevision(TRUE);
$node->setRevisionLogMessage($reason);
$node->setRevisionCreationTime(time());

// Set moderation state to draft/review
$node->set('moderation_state', $target_moderation_state);

// Set the field
$node->set($field_name, $new_tags);

try {{
    $node->save();
    print json_encode([
        'success' => true,
        'nid' => $node->id(),
        'revision_id' => $node->getRevisionId(),
        'moderation_state' => $node->get('moderation_state')->value ?? 'unknown',
    ]);
}} catch (\\Exception $e) {{
    print json_encode(['success' => false, 'error' => $e->getMessage()]);
}}
"""
        console.print(f"[yellow]Replacing tag (tid={old_term_id} → {new_term_id}) on node/{nid}...[/yellow]")
        result = await self.auth.php_eval(php_code)

        if not result.success:
            error_msg = f"Drush failed: {result.stderr}"
            return DraftRevision(
                nid=nid,
                revision_id=0,
                moderation_state="",
                revision_url="",
                success=False,
                error=error_msg,
            )

        try:
            response = json.loads(result.stdout.strip())
        except json.JSONDecodeError:
            return DraftRevision(
                nid=nid,
                revision_id=0,
                moderation_state="",
                revision_url="",
                success=False,
                error=f"Invalid JSON response: {result.stdout}",
            )

        if not response.get("success"):
            return DraftRevision(
                nid=nid,
                revision_id=0,
                moderation_state="",
                revision_url="",
                success=False,
                error=response.get("error", "Unknown error"),
            )

        revision_id = response.get("revision_id", 0)
        site_url = await self.auth.get_site_url()
        revision_url = f"{site_url}/node/{nid}/revisions/{revision_id}/view"

        self.changelog.record(
            auth_method="terminus",
            operation="replace_tag_on_node",
            target=f"node/{nid}",
            field=field_name,
            old_value=str(old_term_id),
            new_value=str(new_term_id),
            reason=reason,
            revision_id=revision_id,
            revision_url=revision_url,
            success=True,
        )

        console.print(f"[green]Replaced tag on node/{nid} (revision {revision_id})[/green]")

        return DraftRevision(
            nid=nid,
            revision_id=revision_id,
            moderation_state=response.get("moderation_state", ""),
            revision_url=revision_url,
            success=True,
        )

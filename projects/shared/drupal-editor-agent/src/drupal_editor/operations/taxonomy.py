"""
Taxonomy term operations for Drupal.

Note: Taxonomy terms don't support revisions in core Drupal,
so changes are logged but require human approval via Slack notification.
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
                import json
                try:
                    return json.loads(result.stdout.strip())
                except Exception:
                    return []
        return []

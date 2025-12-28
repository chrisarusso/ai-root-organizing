"""
Summary generation for Drupal changes.

Produces human-readable summaries suitable for Slack notifications.
"""

from __future__ import annotations

from drupal_editor.tracking.changelog import ChangeLog


class SummaryGenerator:
    """Generate summaries from a changelog."""

    def __init__(self, changelog: ChangeLog):
        self.changelog = changelog

    def generate_slack_summary(self) -> str:
        """
        Generate a Slack-friendly markdown summary.

        Example output:
        ## Ava Changes Summary
        **Session:** 20251227_143022
        **Method:** Terminus/Drush
        **Changes:** 3 successful, 0 failed

        | Target | Field | Change | Review |
        |--------|-------|--------|--------|
        | node/123 | body | "recieve" → "receive" | [Review](url) |
        """
        successful = self.changelog.get_successful()
        failed = self.changelog.get_failed()

        if not self.changelog.records:
            return "No changes recorded."

        # Determine primary auth method
        auth_methods = set(r.auth_method for r in self.changelog.records)
        method_str = ", ".join(sorted(auth_methods))

        lines = [
            "## Ava Changes Summary",
            f"**Session:** {self.changelog.session_id}",
            f"**Method:** {method_str}",
            f"**Changes:** {len(successful)} successful, {len(failed)} failed",
            "",
        ]

        if successful:
            lines.append("### Successful Changes")
            lines.append("")
            lines.append("| Target | Field | Change | Review |")
            lines.append("|--------|-------|--------|--------|")

            for record in successful:
                # Truncate values for display
                old_display = self._truncate(record.old_value, 20)
                new_display = self._truncate(record.new_value, 20)
                change_str = f'"{old_display}" → "{new_display}"'

                review_link = f"[Review]({record.revision_url})" if record.revision_url else "-"

                lines.append(f"| {record.target} | {record.field} | {change_str} | {review_link} |")

            lines.append("")

        if failed:
            lines.append("### Failed Changes")
            lines.append("")
            for record in failed:
                lines.append(f"- **{record.target}**: {record.error}")
            lines.append("")

        return "\n".join(lines)

    def generate_plain_summary(self) -> str:
        """Generate a plain text summary."""
        successful = self.changelog.get_successful()
        failed = self.changelog.get_failed()

        lines = [
            f"Session: {self.changelog.session_id}",
            f"Total changes: {len(self.changelog)}",
            f"Successful: {len(successful)}",
            f"Failed: {len(failed)}",
            "",
        ]

        if successful:
            lines.append("Successful changes:")
            for record in successful:
                lines.append(f"  - {record.target}.{record.field}: {record.reason}")
                if record.revision_url:
                    lines.append(f"    Review: {record.revision_url}")

        if failed:
            lines.append("")
            lines.append("Failed changes:")
            for record in failed:
                lines.append(f"  - {record.target}.{record.field}: {record.error}")

        return "\n".join(lines)

    @staticmethod
    def _truncate(text: str, max_length: int) -> str:
        """Truncate text for display."""
        # Remove newlines for compact display
        text = text.replace("\n", " ").strip()
        if len(text) > max_length:
            return text[: max_length - 3] + "..."
        return text

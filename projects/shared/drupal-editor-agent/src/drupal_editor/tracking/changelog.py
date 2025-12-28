"""
Change tracking for all Drupal operations.

Records every change made by the agent for auditing and reporting.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from pathlib import Path
import json


@dataclass
class ChangeRecord:
    """A single change made to the Drupal site."""

    timestamp: datetime
    auth_method: str  # "terminus" or "playwright"
    operation: str  # "update_node", "update_taxonomy", "update_media"
    target: str  # "node/123", "taxonomy_term/456", "media/789"
    field: str  # Field that was changed
    old_value: str
    new_value: str
    reason: str  # Why this change was made
    revision_id: Optional[int] = None
    revision_url: Optional[str] = None
    screenshot_path: Optional[str] = None  # For Playwright operations
    success: bool = True
    error: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "auth_method": self.auth_method,
            "operation": self.operation,
            "target": self.target,
            "field": self.field,
            "old_value": self.old_value[:100] + "..." if len(self.old_value) > 100 else self.old_value,
            "new_value": self.new_value[:100] + "..." if len(self.new_value) > 100 else self.new_value,
            "reason": self.reason,
            "revision_id": self.revision_id,
            "revision_url": self.revision_url,
            "screenshot_path": self.screenshot_path,
            "success": self.success,
            "error": self.error,
        }


@dataclass
class ChangeLog:
    """
    Tracks all changes made during a session.

    Usage:
        changelog = ChangeLog()
        changelog.record(
            auth_method="terminus",
            operation="update_node",
            target="node/123",
            field="body",
            old_value="Old text",
            new_value="New text",
            reason="Ava: Fixed spelling",
        )
    """

    records: list[ChangeRecord] = field(default_factory=list)
    session_id: str = field(default_factory=lambda: datetime.now().strftime("%Y%m%d_%H%M%S"))

    def record(
        self,
        auth_method: str,
        operation: str,
        target: str,
        field: str,
        old_value: str,
        new_value: str,
        reason: str,
        revision_id: Optional[int] = None,
        revision_url: Optional[str] = None,
        screenshot_path: Optional[str] = None,
        success: bool = True,
        error: Optional[str] = None,
    ) -> ChangeRecord:
        """Record a change."""
        change = ChangeRecord(
            timestamp=datetime.now(),
            auth_method=auth_method,
            operation=operation,
            target=target,
            field=field,
            old_value=old_value,
            new_value=new_value,
            reason=reason,
            revision_id=revision_id,
            revision_url=revision_url,
            screenshot_path=screenshot_path,
            success=success,
            error=error,
        )
        self.records.append(change)
        return change

    def get_successful(self) -> list[ChangeRecord]:
        """Get all successful changes."""
        return [r for r in self.records if r.success]

    def get_failed(self) -> list[ChangeRecord]:
        """Get all failed changes."""
        return [r for r in self.records if not r.success]

    def to_json(self) -> str:
        """Export changelog as JSON."""
        return json.dumps(
            {
                "session_id": self.session_id,
                "total_changes": len(self.records),
                "successful": len(self.get_successful()),
                "failed": len(self.get_failed()),
                "records": [r.to_dict() for r in self.records],
            },
            indent=2,
        )

    def save(self, path: Path | str) -> None:
        """Save changelog to file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json())

    def __len__(self) -> int:
        return len(self.records)

    def __iter__(self):
        return iter(self.records)

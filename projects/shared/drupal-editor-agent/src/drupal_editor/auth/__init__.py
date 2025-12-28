"""Authentication backends for Drupal."""

from drupal_editor.auth.terminus import TerminusAuth
from drupal_editor.auth.playwright import PlaywrightAuth

__all__ = ["TerminusAuth", "PlaywrightAuth"]

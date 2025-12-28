# Drupal Editor Agent

Shared Python library for making staged/reviewable changes to Drupal sites.

## Authentication Methods

1. **Terminus/Drush (Primary)** - For Pantheon-hosted sites with CLI access
2. **Playwright (Fallback)** - Browser automation for any Drupal site

## Installation

```bash
cd projects/shared/drupal-editor-agent
uv sync

# For Playwright, also install browsers
uv run playwright install chromium
```

## Configuration

Copy `.env.example` to `.env` and configure:

### For Terminus (Pantheon sites)
```
PANTHEON_MACHINE_TOKEN=your_token_here
PANTHEON_SITE=savas-labs
PANTHEON_ENV=live
```

### For Playwright (any Drupal site)
```
DRUPAL_BASE_URL=https://savaslabs.com
DRUPAL_USERNAME=admin
DRUPAL_PASSWORD=your_password
```

## Usage

### CLI

```bash
# Test authentication
uv run python -m drupal_editor.cli test-auth --site savas-labs

# Get node info
uv run python -m drupal_editor.cli get-node --nid 123 --site savas-labs

# Update a node field (creates draft revision)
uv run python -m drupal_editor.cli update-node \
  --nid 123 \
  --field body \
  --value "New content" \
  --reason "Ava: Fixed spelling" \
  --site savas-labs

# Find and replace
uv run python -m drupal_editor.cli find-replace \
  --nid 123 \
  --field body \
  --find "recieve" \
  --replace "receive" \
  --reason "Ava: Spelling fix" \
  --site savas-labs

# Use Playwright explicitly
uv run python -m drupal_editor.cli update-node \
  --auth playwright \
  --nid 123 \
  --field body \
  --value "New content"
```

### Python API

```python
from drupal_editor import DrupalClient

# Auto-detect auth method
client = DrupalClient.from_env()

# Or explicitly choose
client = DrupalClient.with_terminus(site_name="savas-labs", env="live")
client = DrupalClient.with_playwright(
    base_url="https://savaslabs.com",
    username="admin",
    password="..."
)

# Make changes
revision = await client.nodes.create_draft_revision(
    nid=123,
    changes={"body": "Updated content"},
    reason="Ava: Fixed spelling error"
)

print(f"Review URL: {revision.revision_url}")

# Get summary
print(client.get_summary())

# Clean up
await client.close()
```

## Drupal Configuration

Before using, add the "Ava Suggestion" moderation state in Drupal:

1. Go to `/admin/config/workflow/workflows/manage/editorial`
2. Add state: **Ava Suggestion** (machine name: `ava_suggestion`)
3. Add transitions:
   - "Suggest" (from Draft/Published → Ava Suggestion)
   - "Accept suggestion" (Ava Suggestion → Draft)
   - "Reject suggestion" (Ava Suggestion → Draft)

## Projects Using This Library

- **Website Quality Agent** - Auto-fix spelling/grammar/accessibility issues
- **Content Tagger** - Update taxonomy terms on nodes

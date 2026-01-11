# Drupal Site Setup for Ava Editor Agent

For each Drupal site that will receive agent suggestions, the following configuration is needed.

---

## 1. Content Moderation Workflow

Add the "Ava Suggestion" state and transitions to the Editorial workflow.

**State to add:**
- **ID:** `ava_suggestion`
- **Label:** Ava Suggestion
- **Published:** No
- **Default revision:** No

**Transitions to add:**

| Transition | Label | From | To |
|------------|-------|------|-----|
| `suggest` | Suggest (Ava) | draft, published | ava_suggestion |
| `accept_suggestion` | Accept Suggestion | ava_suggestion | draft |
| `reject_suggestion` | Reject Suggestion | ava_suggestion | draft |
| `approve_and_publish` | Approve and Publish | ava_suggestion | published |

**Where:** `/admin/config/workflow/workflows/manage/editorial`

---

## 2. Agent Role (Optional)

Create a role for the agent with limited permissions.

**Role:**
- **ID:** `agent`
- **Label:** Agent

**Permissions:**
- `access content`
- `view own unpublished content`
- `use editorial transition suggest`
- `edit any <content_type> content` (for each type the agent will modify)

**Where:** `/admin/people/roles`

---

## 3. Terminus Authentication (for Pantheon sites)

The agent uses Terminus CLI to execute Drush commands. Ensure:

1. Terminus is installed locally: `brew install pantheon-systems/external/terminus`
2. Authenticated: `terminus auth:login` (or via machine token)
3. Site name is known (e.g., `savas-labs`)

No Drupal modules needed - all operations go through Drush.

---

## 4. Playwright Authentication (for non-Pantheon sites)

For sites without CLI access, the agent can use browser automation.

**Required:**
- Admin username and password
- Site must have standard Drupal login at `/user/login`
- Content moderation UI must be accessible

**Environment variables:**
```
DRUPAL_BASE_URL=https://example.com
DRUPAL_USERNAME=admin
DRUPAL_PASSWORD=...
```

---

## Drush Commands for Setup

These commands can configure a Pantheon site via Terminus:

### Add workflow state and transitions
```bash
terminus drush <site>.<env> -- php:eval '
$workflow = \Drupal::entityTypeManager()->getStorage("workflow")->load("editorial");
$type_plugin = $workflow->getTypePlugin();
$config = $type_plugin->getConfiguration();

$config["states"]["ava_suggestion"] = [
    "label" => "Ava Suggestion",
    "weight" => -3,
    "published" => false,
    "default_revision" => false,
];

$config["transitions"]["suggest"] = [
    "label" => "Suggest (Ava)",
    "from" => ["draft", "published"],
    "to" => "ava_suggestion",
    "weight" => 6,
];

$config["transitions"]["accept_suggestion"] = [
    "label" => "Accept Suggestion",
    "from" => ["ava_suggestion"],
    "to" => "draft",
    "weight" => 7,
];

$config["transitions"]["reject_suggestion"] = [
    "label" => "Reject Suggestion",
    "from" => ["ava_suggestion"],
    "to" => "draft",
    "weight" => 8,
];

$config["transitions"]["approve_and_publish"] = [
    "label" => "Approve and Publish",
    "from" => ["ava_suggestion"],
    "to" => "published",
    "weight" => 9,
];

$type_plugin->setConfiguration($config);
$workflow->save();
print "Workflow configured\n";
'
```

### Add Agent role
```bash
terminus drush <site>.<env> -- php:eval '
$role_storage = \Drupal::entityTypeManager()->getStorage("user_role");
$role = $role_storage->create([
    "id" => "agent",
    "label" => "Agent",
    "weight" => 5,
]);
$role->grantPermission("access content");
$role->grantPermission("view own unpublished content");
$role->grantPermission("use editorial transition suggest");
$role->save();
print "Agent role created\n";
'
```

---

## Sites Configured

| Site | Terminus Name | Status |
|------|---------------|--------|
| savaslabs.com | savas-labs | ✅ Configured 2025-12-27 |

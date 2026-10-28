import pytest
from integrations.jira import JiraError, JiraPoller


def test_jira_disabled_is_empty_and_requires_no_credentials():
    assert JiraPoller(enabled=False).poll() == []


def test_jira_poll_uses_fixed_project_scope_and_fields():
    calls = []

    def fake(path, params):
        calls.append((path, params))
        return 200, {"issues": [{"id": "100", "key": "DEMO-1", "fields": {}}]}

    poller = JiraPoller(
        enabled=True, base_url="https://example.atlassian.net", email="bot@example.com",
        token="test-token", project_key="DEMO", request=fake,
    )
    issues = poller.poll(start_at=10, limit=20)
    assert issues[0]["key"] == "DEMO-1"
    assert calls[0][0] == "/rest/api/3/search/jql"
    assert "project = DEMO" in calls[0][1]["jql"]
    assert calls[0][1]["startAt"] == 10 and calls[0][1]["maxResults"] == 20
    assert calls[0][1]["fields"] == ["summary", "description", "status", "updated", "labels"]


def test_jira_auth_errors_are_classified_without_leaking_credentials():
    poller = JiraPoller(
        enabled=True, base_url="https://example.atlassian.net", email="bot@example.com",
        token="top-secret", project_key="DEMO", request=lambda *_args: (401, {}),
    )
    with pytest.raises(JiraError, match="JIRA_AUTH_OR_PERMISSION_DENIED") as exc:
        poller.poll()
    assert "top-secret" not in str(exc.value)

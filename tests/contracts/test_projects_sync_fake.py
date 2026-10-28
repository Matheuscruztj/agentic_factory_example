import pytest
from integrations.github_projects import GitHubProjectsMirror, ProjectsError


def test_projects_disabled_does_not_require_credentials_or_affect_local_engine():
    mirror = GitHubProjectsMirror(enabled=False)
    assert mirror.sync_status(item_id="item", field_id="field", option_id="option") == {
        "status": "disabled",
        "local_task_engine_affected": False,
    }


def test_projects_v2_sync_uses_fixed_mutation_and_fake_contract():
    calls = []

    def fake(query, variables):
        calls.append((query, variables))
        return {
            "data": {
                "updateProjectV2ItemFieldValue": {
                    "projectV2Item": {"id": variables["item"]}
                }
            }
        }

    mirror = GitHubProjectsMirror(
        enabled=True, token="test-token", project_id="PVT_kw_fake", request=fake
    )
    assert mirror.sync_status(item_id="PVTI_fake", field_id="PVTIF_fake", option_id="opt_1") == {
        "status": "synced", "item_id": "PVTI_fake",
    }
    assert len(calls) == 1 and "updateProjectV2ItemFieldValue" in calls[0][0]
    assert calls[0][1]["token"] == "test-token"
    with pytest.raises(ProjectsError, match="PROJECT_NODE_ID_INVALID"):
        mirror.sync_status(item_id="../../admin", field_id="field", option_id="option")


def test_projects_credentials_are_required_only_when_enabled():
    with pytest.raises(ProjectsError, match="PROJECT_CONFIGURATION_REQUIRED"):
        GitHubProjectsMirror(enabled=True)

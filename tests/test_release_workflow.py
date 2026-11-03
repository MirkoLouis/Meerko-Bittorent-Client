# SPDX-License-Identifier: GPL-3.0-or-later
"""Guards on the release pipeline: publishing, token scope and tool pinning."""

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
RELEASE_WORKFLOW_PATH = REPOSITORY_ROOT / ".github" / "workflows" / "release.yml"
APPIMAGE_SCRIPT_PATH = REPOSITORY_ROOT / "packaging" / "build-appimage.sh"
BUILD_JOB_NAMES = ("windows", "appimage")


# Parse release.yml once per test
@pytest.fixture
def release_workflow():
    return yaml.safe_load(RELEASE_WORKFLOW_PATH.read_text(encoding="utf-8"))


# Find the single step in a job whose `uses:` starts with the given action name
def find_step_using(job, action_name):
    matching_steps = [step for step in job["steps"] if step.get("uses", "").startswith(action_name)]
    assert len(matching_steps) == 1, f"expected one {action_name} step, found {len(matching_steps)}"
    return matching_steps[0]


# Find the single step in a job with the given display name
def find_step_named(job, step_name):
    matching_steps = [step for step in job["steps"] if step.get("name") == step_name]
    assert len(matching_steps) == 1, f"expected one step named {step_name!r}"
    return matching_steps[0]


# A manual dispatch run from a tag ref must never publish a real release
def test_publish_runs_only_on_tag_push(release_workflow):
    publish_step = find_step_using(release_workflow["jobs"]["release"], "softprops/action-gh-release")
    assert "github.event_name == 'push'" in publish_step["if"]
    assert "startsWith(github.ref, 'refs/tags/v')" in publish_step["if"]


# The dry-run bundle is the counterpart of publishing and must never run on a tag push
def test_dry_run_upload_runs_only_without_push(release_workflow):
    upload_step = find_step_named(release_workflow["jobs"]["release"], "Upload dry-run bundle")
    assert "github.event_name != 'push'" in upload_step["if"]


# Tags such as v1.1.0rc1 must be marked as pre-releases, never "Latest"
def test_publish_sets_prerelease_flag(release_workflow):
    publish_step = find_step_using(release_workflow["jobs"]["release"], "softprops/action-gh-release")
    assert "prerelease" in publish_step["with"]


# Default token is read-only; only the release job may write
def test_token_is_read_only_except_release_job(release_workflow):
    assert release_workflow["permissions"] == {"contents": "read"}
    assert release_workflow["jobs"]["release"]["permissions"] == {"contents": "write"}
    # Build jobs run third-party tools and must not widen the token
    for job_name in BUILD_JOB_NAMES:
        assert "permissions" not in release_workflow["jobs"][job_name]


# Build jobs must not leave the token in .git/config for third-party tools to read
def test_build_checkouts_do_not_persist_credentials(release_workflow):
    # Check every build job's checkout step
    for job_name in BUILD_JOB_NAMES:
        checkout_step = find_step_using(release_workflow["jobs"][job_name], "actions/checkout")
        assert checkout_step.get("with", {}).get("persist-credentials") is False, job_name


# appimagetool comes from a fixed release and is checksum-verified before it runs
def test_appimagetool_is_pinned_and_verified():
    script = APPIMAGE_SCRIPT_PATH.read_text(encoding="utf-8")
    assert "/continuous/" not in script
    assert "/releases/download/1.9.1/" in script
    assert "ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0" in script
    assert "sha256sum --check" in script


# Collect every `run:` script of a job as one text block
def job_scripts(job):
    return "\n".join(step.get("run", "") for step in job["steps"])


# Windows releases ship the console CLI next to the GUI, and the frozen CLI must start and load libtorrent
def test_windows_job_ships_cli_exe_and_smoke_tests_it(release_workflow):
    scripts = job_scripts(release_workflow["jobs"]["windows"])
    assert "dist/meerko-bittorent-cli.exe --version" in scripts
    assert "-windows-x86_64-cli.exe" in scripts


# The Linux frozen CLI is smoke-tested before it is packed into the AppImage
def test_appimage_job_smoke_tests_cli(release_workflow):
    assert "dist/meerko-bittorent/meerko-bittorent-cli --version" in job_scripts(release_workflow["jobs"]["appimage"])

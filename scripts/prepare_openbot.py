"""Fetch the pinned OpenBot source and apply the small local compatibility patch set."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / ".runtime" / "openbot-source"
UPSTREAM = "https://github.com/regnull/openbot.git"
REVISION = "11753662edea33cc90fd1f85fd9ec5793a572fc6"


def git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(SOURCE), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def patch(relative: str, old: str, new: str) -> None:
    path = SOURCE / relative
    text = path.read_text()
    if new in text:
        return
    if text.count(old) != 1:
        raise RuntimeError(f"expected exactly one patch target in {relative}")
    path.write_text(text.replace(old, new, 1))


def main() -> None:
    if not (SOURCE / ".git").exists():
        SOURCE.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "clone", "--no-checkout", UPSTREAM, str(SOURCE)],
            check=True,
        )
    current = git("rev-parse", "HEAD")
    if current != REVISION:
        git("fetch", "origin", REVISION)
        git("checkout", "--detach", REVISION)

    patch(
        "backend/openbot/config.py",
        "    seed_demo_bots: bool = True\n",
        '    seed_demo_bots: bool = True\n'
        "    disable_run_shell: bool = Field(\n"
        '        default=False, validation_alias="OPENBOT_DISABLE_RUN_SHELL"\n'
        "    )\n",
    )
    patch(
        "backend/openbot/tools/registry.py",
        "    for t in SELECTABLE_TOOLS:\n        reg.register(t)\n",
        "    for t in SELECTABLE_TOOLS:\n"
        "        if t.name == \"run_shell\" and settings.disable_run_shell:\n"
        "            continue\n"
        "        reg.register(t)\n",
    )
    patch(
        "backend/openbot/runtime/providers.py",
        '        if "max_tokens" in kwargs:\n'
        '            kwargs["num_predict"] = kwargs.pop("max_tokens")\n',
        '        if "max_tokens" in kwargs:\n'
        '            kwargs["num_predict"] = kwargs.pop("max_tokens")\n'
        '        if "reasoning" in ms:\n'
        '            kwargs["reasoning"] = ms["reasoning"]\n',
    )
    print(f"OpenBot source ready at {REVISION} with local safety/adapter patches")


if __name__ == "__main__":
    main()

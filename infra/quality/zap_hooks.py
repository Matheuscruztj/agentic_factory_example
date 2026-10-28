"""Inject only the disposable Factory session into requests to the Factory API."""

import json
from pathlib import Path


def zap_started(zap, target):
    if "factory" not in target:
        return
    auth = json.loads(Path("/zap/auth/factory.json").read_text())
    for header, value in [("Cookie", auth["cookie"]), ("X-CSRF-Token", auth["csrf"])]:
        zap.replacer.add_rule(
            description=f"quality-{header}",
            enabled="true",
            matchtype="REQ_HEADER",
            matchregex="false",
            matchstring=header,
            replacement=value,
            url=r"http://factory-api:8000/.*",
        )

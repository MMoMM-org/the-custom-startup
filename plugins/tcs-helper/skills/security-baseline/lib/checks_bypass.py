"""Bypass checks C2 and C2x (spec 025, K10).

Bypass mode (`--dangerously-skip-permissions`, or `permissions.defaultMode:
"bypassPermissions"`) turns off every permission prompt.

- `check_bypass` (C2) looks at the settings files. One finding says whether
  `permissions.disableBypassPermissionsMode` is `"disable"`; one more per
  settings file whose `defaultMode` asks for bypass and is honoured there.
  Claude Code ignores that value in project and local settings from 2.1.257
  on; with an older or unknown version it counts and is reported.
- `check_container_exposure` (C2x) looks at a container: bypass in use, a
  sandbox that cannot run, and a credential path present in the home
  directory together leave the credentials open to every command.

C2 is emitted the same way in every profile: `verdict.finalise` moves C2 to
the accepted block in the container profile. The container exposure is a
separate check id because it must never be accepted.

Both checks return findings and let exceptions through; `verdict.run_check`
turns an exception into an UNKNOWN finding.
"""

from __future__ import annotations

import os
import pathlib

import effective as effective_values
import verdict

CHECK_BYPASS = "C2"
CHECK_CONTAINER_EXPOSURE = "C2x"
SEVERITY = "HIGH"

DISABLE_KEY = "permissions.disableBypassPermissionsMode"
MODE_KEY = "permissions.defaultMode"
DISABLED = "disable"
BYPASS_MODE = "bypassPermissions"

FIX_DISABLE_BYPASS = "c2-disable-bypass"
FIX_REMOVE_BYPASS_MODE = "c2-remove-bypass-default-mode"
FIX_CONTAINER_EXPOSURE = "c2x-container-exposure"

# Merged into the fix-template table of the report renderer by the CLI.
FIX_TEMPLATES = {
    FIX_DISABLE_BYPASS: (
        'Add "disableBypassPermissionsMode": "disable" under "permissions" '
        "in the user settings file."
    ),
    FIX_REMOVE_BYPASS_MODE: (
        'Remove "defaultMode": "bypassPermissions" from "permissions" in this settings file.'
    ),
    FIX_CONTAINER_EXPOSURE: (
        "Either unmount the credential paths from the container, "
        "or make the sandbox run inside it and enable it."
    ),
}

_HOME_PREFIX = "~/"


def check_bypass(*, sources, env, keys):
    """C2 findings, PASS included.

    Reads `sources` (`layers.Source` list), `keys` (`refdata.Keys`) and from
    `env` the Claude Code version and the profile. The profile only decides
    the fix: nothing is proposed in a container.
    """
    disable = _effective(DISABLE_KEY, sources, env, keys)
    disable_state = _disable_state(disable)
    proposes = env.profile != verdict.CONTAINER_PROFILE
    findings = [
        verdict.finding(
            CHECK_BYPASS,
            SEVERITY,
            verdict.status({"permissions": disable_state}),
            "permissions",
            evidence_key=DISABLE_KEY,
            scope="" if disable.winner is None else disable.winner.scope,
            file="" if disable.winner is None else disable.winner.path,
            evidence={
                "key": DISABLE_KEY,
                "value": disable.value,
                "unread": [source.scope for source in disable.unknown],
                "bypass_active": env.bypass_active,
            },
            fix=_fix(FIX_DISABLE_BYPASS) if proposes else None,
        )
    ]
    mode = _effective(MODE_KEY, sources, env, keys)
    for source, value in mode.contributions:  # values Claude Code ignores are not in here
        if value != BYPASS_MODE:
            continue
        findings.append(verdict.finding(
            CHECK_BYPASS,
            SEVERITY,
            # The mode is asked for; an effective disable key is all that stops it.
            "PARTIAL" if disable_state == "EFFECTIVE" else "FAIL",
            "permissions",
            evidence_key=f"{MODE_KEY}:{source.scope}:{source.path}",
            scope=source.scope,
            file=source.path,
            evidence={
                "key": MODE_KEY,
                "value": value,
                "effective": source is mode.winner,
                "claude_version": _version_text(env),
            },
            fix=_fix(FIX_REMOVE_BYPASS_MODE) if proposes else None,
        ))
    return findings


def check_container_exposure(*, sources, env, probe, keys, credentials, home):
    """C2x: at most one finding, and only in the container profile.

    Reads from `env` the profile, the bypass observation and the Claude Code
    version; `probe.result`; `sources` and `keys` for a `defaultMode` that
    starts sessions in bypass; and `credentials` (`refdata.Credential` list),
    whose paths are looked up under `home` (an absolute path) on disk.

    FAIL when bypass is in use and a credential path exists; UNKNOWN when
    either could not be established. Never accepted.
    """
    if env.profile != verdict.CONTAINER_PROFILE or probe.result == "pass":
        return []
    bypass = _bypass_in_use(sources, env, keys)
    if bypass == "no":
        return []
    present, unchecked = _credential_paths(credentials, home)
    if not present and not unchecked:
        return []
    evidence = {
        "credentials": present,
        "probe": probe.result,
        "bypass_active": bypass,
    }
    if unchecked:
        evidence["unchecked"] = unchecked
    return [
        verdict.finding(
            CHECK_CONTAINER_EXPOSURE,
            SEVERITY,
            "FAIL" if bypass == "yes" and present else "UNKNOWN",
            "environment",
            evidence_key="container-exposure",
            evidence=evidence,
            fix=_fix(FIX_CONTAINER_EXPOSURE),
        )
    ]


def _effective(key, sources, env, keys):
    return effective_values.effective(key, sources, keys.rules[key], env.claude_version)


def _disable_state(disable):
    """Layer state of the disable key. A file that could not be evaluated may
    hold or override the key, so nothing is credited or denied then."""
    if not disable.certain:
        return "UNKNOWN"
    return "EFFECTIVE" if disable.value == DISABLED else "ABSENT"


def _bypass_in_use(sources, env, keys):
    """yes | no | unknown: the command-line observation, or a `defaultMode`
    that takes effect."""
    if env.bypass_active == "yes":
        return "yes"
    mode = _effective(MODE_KEY, sources, env, keys)
    if mode.value == BYPASS_MODE:
        return "yes"
    if env.bypass_active != "no" or not mode.certain:
        return "unknown"
    return "no"


def _credential_paths(credentials, home):
    """`(present, unchecked)` credential ids under `home`. A dangling link is
    present: its target may be a mount that is not attached right now.

    Only the home-directory entries are looked up. The pattern entries
    (`**/.env*`) describe files of the project, which a container mounts on
    purpose.
    """
    home = pathlib.Path(home)
    if not home.is_absolute():
        raise ValueError("home must be an absolute path")
    present, unchecked = [], []
    for credential in credentials:
        if not credential.path.startswith(_HOME_PREFIX):
            continue
        try:
            os.lstat(home / credential.path[len(_HOME_PREFIX):])
        except (FileNotFoundError, NotADirectoryError):
            continue
        except OSError:
            unchecked.append(credential.id)
        else:
            present.append(credential.id)
    return present, unchecked


def _fix(template):
    return {"template": template, "params": {}}


def _version_text(env):
    return None if env.claude_version is None else str(env.claude_version)

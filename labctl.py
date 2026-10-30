#!/usr/bin/env python3
"""Shared operator CLI. Catalogs are trusted code configuration, not a sandbox."""
import datetime as dt
import json
import os
from pathlib import Path
import re
import shlex
import socket
import subprocess
import sys
import textwrap

VERSION = "1.1"
BASE = Path(__file__).resolve().parent
REGISTRY = Path.home() / ".config/labctl/catalogs"
AUDIT = Path.home() / ".local/state/labctl/actions.jsonl"
HOSTS = {"core", "ueransim", "ims"}
NAME = re.compile(r"[a-z][a-z0-9_-]*\Z")
SSH = ["sudo", "-n", "-u", "open5gs-noc", "ssh", "-i",
       "/var/lib/open5gs-noc/.ssh/id_ed25519", "-o", "BatchMode=yes",
       "-o", "ConnectTimeout=10", "-o", "StrictHostKeyChecking=no"]

def read(path):
    return json.loads(path.read_text(encoding="utf-8"))

def validate(catalog):
    """Reject incomplete configuration before executing any remote command."""
    if not isinstance(catalog, dict) or set(catalog) != {"version", "name", "actions"}:
        raise ValueError("Catalog needs exactly version, name, actions")
    if catalog["version"] != 1 or not NAME.fullmatch(catalog["name"]):
        raise ValueError("Unsupported catalog version/name")
    if not isinstance(catalog["actions"], dict) or not catalog["actions"]:
        raise ValueError("Actions must be a nonempty object")
    required = {"description", "impact", "verification", "changes_state"}
    for name, action in catalog["actions"].items():
        if not NAME.fullmatch(name) or not isinstance(action, dict):
            raise ValueError("Invalid action name/object")
        if not required <= action.keys() or type(action["changes_state"]) is not bool:
            raise ValueError(f"Missing metadata: {name}")
        for field in ("description", "impact", "verification"):
            if not isinstance(action[field], str) or not action[field].strip():
                raise ValueError(f"Missing {field}: {name}")
        operations = action.get("steps", [action])
        if not isinstance(operations, list) or not operations:
            raise ValueError("steps must be a nonempty list")
        metadata = {"source_lab", "prerequisites", "project_root"}
        allowed = required | metadata | {"host", "command", "upload", "directory", "interactive", "timeout", "errexit", "input_file", "download"}
        for field in metadata & action.keys():
            if not isinstance(action[field], str):
                raise ValueError("Catalog metadata must be text")
        if "project_root" in action and not re.fullmatch(r"~/[A-Za-z0-9_/-]+", action["project_root"]):
            raise ValueError("Invalid fixed project folder")
        if "steps" in action and set(action) - (required | metadata | {"steps"}):
            raise ValueError("Composite actions contain metadata and steps only")
        for op in operations:
            if not isinstance(op, dict) or set(op) - allowed:
                raise ValueError(f"Unknown operation field: {name}")
            if op.get("host") not in HOSTS:
                raise ValueError("Host must be core, ueransim, or ims")
            if ("command" in op) == ("upload" in op):
                raise ValueError("Specify exactly command or upload")
            if type(op.get("timeout", 90)) is not int or not 1 <= op.get("timeout", 90) <= 300:
                raise ValueError("Timeout must be 1..300 seconds")
            if type(op.get("interactive", False)) is not bool:
                raise ValueError("interactive must be boolean")
            if type(op.get("errexit", True)) is not bool:
                raise ValueError("errexit must be boolean")
            for field in ("input_file", "download"):
                if field in op:
                    if not isinstance(op[field], str) or not re.fullmatch(r"~/[A-Za-z0-9_./-]+", op[field]) or '..' in Path(op[field]).parts:
                        raise ValueError("Transfer path must be fixed beneath home")
                    if op.get("interactive") or "upload" in op or not action["changes_state"]:
                        raise ValueError("Transfers require changes_state, no TTY, and no upload")
            if "download" in op and "input_file" in op:
                raise ValueError("Do not combine input and download")
            if "command" in op:
                if not isinstance(op["command"], str) or not op["command"].strip() or "directory" in op:
                    raise ValueError("Invalid command")
            else:
                if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", op["upload"]):
                    raise ValueError("Upload must be one filename")
                if not re.fullmatch(r"/home/student/noc_[A-Za-z0-9_-]+", op.get("directory", "")):
                    raise ValueError("Upload destination must be /home/student/noc_NAME")
                if not action["changes_state"] or op.get("interactive"):
                    raise ValueError("Uploads change state and cannot request a TTY")
    return catalog

def catalogs():
    common = validate(read(BASE / "actions.json"))
    if common["name"] != "common":
        raise ValueError("Base catalog must be named common")
    result = {"common": (common, BASE)}
    if REGISTRY.exists():
        for path in sorted(REGISTRY.glob("*.json")):
            saved = read(path)
            cat = validate(saved["catalog"])
            if cat["name"] in result or path.stem != cat["name"]:
                raise ValueError("Duplicate/mismatched catalog name")
            root = Path(saved["project_root"])
            if not root.is_absolute() or not root.is_dir():
                raise ValueError(f"Project folder missing: {root}")
            result[cat["name"]] = (cat, root)
    return result

def help_text(all_catalogs):
    lines = [f"# labctl {VERSION}", "", "Environment controls run from NOC; application workflows remain separate.",
             "Catalogs contain trusted shell commands. Do not register model-generated or downloaded catalogs without review.",
             "This CLI is not an approval gate or security sandbox. SSH/sudo remain the execution permissions.",
             "", "Usage: labctl [CATALOG] ACTION | list | help [CATALOG] ACTION | check | doctor | docs",
             "Register: labctl register PATH [--replace] (binds uploads to PATH's parent folder)",
             "Mutations ask for yes; --yes is available for an explicit operator command, not authenticated approval.",
             "The lab uses StrictHostKeyChecking=no for disposable VMs; production should verify host keys.", ""]
    for group, (cat, root) in all_catalogs.items():
        for name, action in cat["actions"].items():
            invocation = name.replace('--', ' ', 1) if group == "common" else f"{group} {name}"
            lines += [f"## labctl {invocation}", action["description"],
                      f"Changes state: {action['changes_state']}. Impact: {action['impact']}",
                      f"Verify: {action['verification']}", f"Upload source folder: {root}",
                      "```json", json.dumps(action, indent=2), "```", ""]
    return "\n".join(lines)

def usage(all_catalogs):
    """A usable front page; exact command bodies remain in help FAMILY ACTION."""
    families = {}
    for key, action in all_catalogs['common'][0]['actions'].items():
        family, _, name = key.partition('--')
        families.setdefault(family if name else 'common', []).append(name or key)
    for family, (cat, _) in all_catalogs.items():
        if family != 'common':
            families[family] = list(cat['actions'])
    print(f'''labctl {VERSION} — operate the lab environment from NOC

USAGE
  labctl help                         This guide and command families
  labctl list                         Every available action and description
  labctl help FAMILY ACTION           Exact command, impact, prerequisites
  labctl ACTION                       Common check or control
  labctl FAMILY ACTION                Lab-specific environment action
  labctl check                        Validate catalogs; no SSH
  labctl doctor                       Check SSH + sudo to all three VMs
  labctl docs                         Generate ~/.local/share/labctl/HELP.md
  labctl register PATH [--replace]     Add/update a reviewed project catalog
  labctl --version                    Installed runner version

EXAMPLES
  labctl core-status
  labctl ue1-status
  labctl ue1-sessions
  labctl help reconnect-ran
  labctl subscriber check-ue3
  labctl specialist phone-processes
  labctl capstone-data data-status
  labctl help capstone-ims emergency-off

BEFORE YOU RUN A COMMAND
  Read help FAMILY ACTION. Family names preserve each lab's tmux sessions,
  log paths and helper versions. Do not substitute a different phone family.
  All commands are listed now; some require files/helpers created in their lab.
  Listing an action does NOT install its helper or start its tmux session.
  Bundled upload paths are fixed under your home; help shows the project folder.
  A registered catalog with the same family takes precedence over bundled entries.

CHANGES AND RECOVERY
  CHANGE actions ask you to type yes. --yes is an explicit operator bypass of
  that prompt, NOT authenticated approval. IMS helpers may also ask confirmation.
  reconnect-ran interrupts radio connectivity; reset-core-and-ran is broader.
  sandbox reset-lab also restarts IMS and stops ALL simulator UE processes.
  Never use these controls to bypass an approval-gate exercise.
  No automatic retries. On timeout/failed step, inspect partial remote state.
  COMMAND_COMPLETED means execution completed; verify registration and traffic.

FILES AND TROUBLESHOOTING
  ~/.local/share/labctl/actions.json         Bundled command catalog
  ~/.config/labctl/catalogs/                 Registered project snapshots
  ~/.local/state/labctl/actions.jsonl        Operator execution log
  Unknown command: use list. Missing helper/session: complete that lab's setup.
  Wrong VM or SSH failure: stay on NOC; run doctor and inspect its error.
  Empty logs/stopped services: preserve evidence; do not infer successful recovery.
  Catalogs are trusted executable configuration, not a security sandbox.

APPLICATION CONTROLLERS STAY SEPARATE
  noc_distress_lab/labctl.py: baselines, fault ownership/timers, phone windows,
    workers, wait-jobs, reporting and audit. Use that lab's .venv/bin/python.
  noc_amf_approval/labctl.py: dashboard, AMF fault/restore ownership, baseline,
    approval/recovery records. Use that lab's .venv/bin/python.
  noc_readiness_challenge/labctl.py: guarded faults, expiry timers and audit.
    Use python3 in that project. These workflows are not generic SSH aliases.
  Approval, node-control and rollback agents still use their existing gate.

COMMAND FAMILIES (use help FAMILY ACTION for requirements)''')
    for family, names in families.items():
        print(textwrap.fill(f"{family}: " + ', '.join(names), width=88,
                            initial_indent='  ', subsequent_indent='    ',
                            break_long_words=False, break_on_hyphens=False))

def audit(**fields):
    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    record = {"at_utc": dt.datetime.now(dt.timezone.utc).isoformat(), **fields}
    with AUDIT.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record) + "\n")

def execute(op, root):
    content = None
    if 'input_file' in op:
        source = Path(op['input_file']).expanduser()
        if source.is_symlink() or not source.is_file() or source.stat().st_size > 2_000_000:
            raise ValueError(f"Missing, symlinked, or oversized input: {source}")
        content = source.read_bytes()
    if "upload" in op:
        path = root / op["upload"]
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 2_000_000:
            raise ValueError(f"Missing, symlinked, or oversized upload: {path}")
        content = path.read_bytes()
        directory = shlex.quote(op["directory"])
        target = shlex.quote(op["directory"] + "/" + op["upload"])
        command = f"mkdir -p {directory} && cat > {target}"
    else:
        command = op["command"]
    print(f"Target: {op['host']}", flush=True)
    args = SSH + (["-tt"] if op.get("interactive") else [])
    args += ["student@" + op["host"], "bash -lc " + shlex.quote(("set -e; " if op.get('errexit', True) else '') + command)]
    if 'download' in op:
        target = Path(op['download']).expanduser()
        if target.is_symlink():
            raise ValueError('Download target is a symlink')
        target.parent.mkdir(parents=True, exist_ok=True)
        import tempfile
        with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as output:
            temporary = Path(output.name)
            try:
                subprocess.run(args, stdout=output, stdin=subprocess.DEVNULL,
                               timeout=op.get('timeout', 90), check=True)
            except BaseException:
                output.close()
                temporary.unlink(missing_ok=True)
                raise
        temporary.replace(target)
        print('Saved complete binary capture:', target)
        return
    # Preserve remote stdout/stderr and interactive confirmations from the helper.
    subprocess.run(args, input=content, timeout=op.get("timeout", 90), check=True)

def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if args == ["--version"]:
        print("labctl", VERSION)
        return 0
    if args and args[0] == "register":
        replace = "--replace" in args
        rest = [a for a in args[1:] if a != "--replace"]
        if len(rest) != 1:
            raise ValueError("Use labctl register PATH [--replace]")
        source = Path(rest[0]).expanduser().resolve()
        cat = validate(read(source))
        if cat["name"] == "common":
            raise ValueError("common is reserved")
        REGISTRY.mkdir(parents=True, exist_ok=True)
        dest = REGISTRY / (cat["name"] + ".json")
        saved = {"project_root": str(source.parent), "catalog": cat}
        if dest.exists() and read(dest) != saved and not replace:
            raise ValueError("Catalog differs. Review it, then use --replace explicitly")
        temporary = dest.with_suffix(".tmp")
        temporary.write_text(json.dumps(saved, indent=2), encoding="utf-8")
        temporary.replace(dest)
        print(f"Registered {cat['name']}; uploads read from {source.parent}")
        return 0
    all_catalogs = catalogs()
    if not args or args == ["--help"] or args == ["help"]:
        usage(all_catalogs)
        return 0
    if args == ["list"]:
        for group, (cat, _) in all_catalogs.items():
            for name, action in cat["actions"].items():
                print(f"{group:16} {name:24} {'CHANGE' if action['changes_state'] else 'READ/PROBE':10} {action['description']}")
        return 0
    if args == ["docs"]:
        path = BASE / "HELP.md"
        import io
        from contextlib import redirect_stdout
        guide = io.StringIO()
        with redirect_stdout(guide):
            usage(all_catalogs)
        path.write_text('```text\n' + guide.getvalue() + '```\n\n' + help_text(all_catalogs), encoding="utf-8")
        print(path)
        return 0
    if args == ["check"]:
        print(f"Validated {len(all_catalogs)} catalogs; no network commands run.")
        return 0
    if socket.gethostname().split(".")[0] != "noc" and args[0] != "help":
        raise ValueError("Run environment commands on the NOC VM")
    if args == ["doctor"]:
        # Read-only connectivity and remote noninteractive sudo check on all VMs.
        for host in sorted(HOSTS):
            execute({"host": host, "command": "hostname; sudo -n true", "timeout": 20}, BASE)
        return 0
    explain = args[0] == "help"
    if explain:
        args.pop(0)
    yes = "--yes" in args
    args = [a for a in args if a != "--yes"]
    if len(args) == 1:
        group, name = "common", args[0]
    elif len(args) == 2:
        group, name = args
    else:
        raise ValueError("Use labctl [CATALOG] ACTION")
    if group not in all_catalogs and group + '--' + name in all_catalogs['common'][0]['actions']:
        name = group + '--' + name
        group = 'common'
    if group not in all_catalogs or name not in all_catalogs[group][0]["actions"]:
        raise ValueError("Unknown catalog/action. Use labctl list")
    cat, root = all_catalogs[group]
    action = cat["actions"][name]
    if 'project_root' in action:
        root = Path(action['project_root']).expanduser()
    if explain:
        print(json.dumps(action, indent=2))
        print("Upload source folder:", root)
        return 0
    print(action["description"] + "\nImpact: " + action["impact"], flush=True)
    if action["changes_state"] and not yes:
        if not sys.stdin.isatty() or input("Type yes to run this environment change: ") != "yes":
            raise ValueError("Change not confirmed; no command executed")
    # Audit intent before executing. Failure to record intent prevents execution.
    audit(catalog=group, action=name, state="STARTED")
    try:
        for operation in action.get("steps", [action]):
            execute(operation, root)
    except (subprocess.SubprocessError, OSError, ValueError, KeyboardInterrupt):
        audit(catalog=group, action=name, state="FAILED_OR_INTERRUPTED")
        raise
    audit(catalog=group, action=name, state="COMMAND_COMPLETED")
    print("Command completed. Verify: " + action["verification"])
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, KeyError, TypeError, OSError, subprocess.SubprocessError, KeyboardInterrupt) as exc:
        print(f"STOP: {exc}\nNo automatic retry. A remote change may have partially completed; collect fresh state.", file=sys.stderr)
        sys.exit(1)

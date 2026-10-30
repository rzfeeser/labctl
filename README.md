# labctl

Operate the Alta3 Claude and 5G lab environment from the NOC terminal.

## Author

Maintained by [rzfeeser](https://github.com/rzfeeser).

## Objective

`labctl` provides named environment commands so students can stay on NOC while checking or controlling core, UERANSIM, and IMS.

- Python reads the command catalog in `actions.json`.
- SSH executes the selected command on its designated VM.
- Help describes the command, its impact, and its prerequisites.
- Actions marked as changes request operator confirmation.

The tool makes no Claude API calls. Agent applications still manage their own dashboards, workers, approval gates, baselines, and reports.

## Installing

Run these commands as **student on NOC**, without `sudo`. Bash, Git, curl, and Python 3 must be available. The classroom must already provide the `open5gs-noc` account, SSH key, hostname resolution, and remote permissions.

Download and inspect the installer:

```bash
curl --fail --location --show-error \
  --output ~/labctl-install.sh \
  https://raw.githubusercontent.com/rzfeeser/labctl/main/install.sh
less ~/labctl-install.sh
```

Press **q**, then install:

```bash
bash ~/labctl-install.sh
export PATH="$HOME/.local/bin:$PATH"
hash -r
labctl help
```

The installer clones into `~/labctl` when needed. If that checkout already exists, it reuses it without automatically pulling or resetting local work. When run from a directory containing `labctl.py` and `actions.json`, it installs those files instead.

Existing installed files and command links receive timestamped backups. Installation errors stop the script; inspect the error before continuing. The installer adds PATH to `.bashrc`, but the `export` above is needed for your current terminal.

Installed locations:

| Location | Purpose |
|---|---|
| `~/.local/share/labctl/` | Installed runner and catalog |
| `~/.local/bin/labctl` | Command link |
| `~/.config/labctl/catalogs/` | Registered project catalogs |
| `~/.local/state/labctl/actions.jsonl` | Execution log |

To update, inspect your checkout and preserve local changes first:

```bash
cd ~/labctl
git status
git pull --ff-only
bash install.sh
```

If Git reports an error, stop before installing. Pulling alone does not update installed copies. Registered project catalogs remain separate and can override bundled families.

## How to Use

Start with the guide or complete command menu:

```bash
labctl help
labctl list
```

Inspect an action without executing it:

```bash
labctl help reconnect-ran
labctl help subscriber check-ue3
```

Common commands use `labctl ACTION`:

```bash
labctl core-status
labctl ue-status
labctl ue1-status
labctl ue1-sessions
```

Lab-specific commands use `labctl FAMILY ACTION`:

```bash
labctl specialist phone-processes
labctl capstone-data data-status
```

**Read prerequisites first.** Some actions need scripts or phone sessions created in their corresponding lab. A catalog entry does not install its remote helper. Families preserve different session names and evidence paths; use the family specified by your exercise.

Commands marked **CHANGE** ask for `yes`. Some remote helpers also request confirmation. These prompts are operator conveniences, not authenticated approval gates. Do not use this tool to bypass an agent application's approval workflow.

Generate the full help document:

```bash
labctl docs
less ~/.local/share/labctl/HELP.md
```

Register an additional reviewed project catalog:

```bash
labctl register /absolute/path/to/lab_actions.json
```

After reviewing changes, add `--replace` to replace an existing registration. Registration binds helper uploads to the catalog's project directory. It does not run its commands.

Inspect recent executions:

```bash
tail -n 20 ~/.local/state/labctl/actions.jsonl
```

`COMMAND_COMPLETED` means the command returned successfully, not that service health is verified. Collect fresh registration, session, or traffic evidence afterward. Failed or interrupted actions may have partially completed; inspect current state before retrying.

For SSH problems, confirm you are on NOC and run `labctl doctor`. For a missing command, run `labctl help` or `labctl list`.

Catalogs contain trusted executable commands. They are not a security sandbox, and their metadata does not prove a command is read-only. SSH and sudo permissions determine execution privileges. The classroom host-key setting is not a production host-verification recommendation.

Stateful controllers remain separate. Follow the relevant lab for dashboard operations, worker management, fault timers, approval records, and reporting.

## About the Author

[rzfeeser](https://github.com/rzfeeser) maintains this repository for the Alta3 Claude and 5G course. The tool supports hands-on work with Python wrappers, network evidence, agent boundaries, and human-controlled operations.

Visit [the repository](https://github.com/rzfeeser/labctl) for source code and updates.

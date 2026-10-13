---
name: relay-setup
description: >-
  Install the Relay CLI (relay), sign in, and point it at the right organization and workspace.
  Use when someone wants to start using Relay (userelay.sh) from a terminal, when a relay command
  fails because they are not signed in or are in the wrong organization or workspace, when they
  need to sign in over SSH or with SSO, or when CI has to authenticate to Relay with an API key
  (RELAY_TOKEN).
license: MPL-2.0
---

# Relay setup

Relay gives developers governed access to databases. The `relay` CLI is how a developer signs in,
chooses an organization and a workspace, and then opens connections. Nothing else in Relay works
from a terminal until the steps here are done.

When you have a shell, run the commands yourself and report what they printed. When you do not,
give the exact commands in the order to run them.

The CLI changes between releases. Only the commands below are safe to use from memory. For any
other flag, run `relay <command> --help` first, and for anything about the product read
https://docs.userelay.sh.

## Rules

- Never print, repeat or write to a file a Relay API key, a `RELAY_TOKEN` value or the contents of
  `~/.userelay/profiles.json`. If the user pastes a key, refer to it as "your key" and do not
  quote it back, not even inside an example command.
- The commands in this skill print tables and have no JSON output, so do not pass `--json` or
  `-o json`.
- Before any command that creates, changes or deletes something, run `relay whoami` and
  `relay ws list` and tell the user which organization and workspace are active. The active
  workspace is the row marked `*` in the `ACTIVE` column.
- Show any command that deletes or signs out (`relay logout`, `relay profiles delete`,
  `relay ws delete`, any `delete`) to the user and run it only after an explicit yes in that turn.
  These cannot be undone, and an earlier yes does not cover a later command.

## Workflow: Install the CLI

Pick the line for the user's system. Each one installs software, so show it before running it.

| System | Command |
|---|---|
| macOS, or Linux with Homebrew | `brew install relay-sh/tap/relay` |
| Linux | the `install.sh` script below |
| Windows with Chocolatey | `choco install relay` |
| Windows, PowerShell | the `install.ps1` script below |

Homebrew on Linux supports x86_64 only; on other Linux architectures use the script.

Linux script:

```bash
curl -fsSL https://docs.userelay.sh/install.sh | bash
```

PowerShell script:

```powershell
irm https://docs.userelay.sh/install.ps1 | iex
```

Then confirm it is on the `PATH`:

```bash
relay version
```

On Windows the PowerShell installer changes the user `PATH`, so `relay version` only works in a
new terminal. If `choco install relay` says the package is not found, the newest release is still
in Chocolatey review; use the PowerShell line instead.

## Workflow: Sign in

Choose by where the user is sitting:

| Situation | Command |
|---|---|
| A desktop with a browser | `relay login` |
| The organization uses SSO | `relay login --sso --email <work-email>` |
| SSH session, container or any machine with no browser | `relay login --device` |

`relay login` opens a browser and waits. `relay login --device` prints a link and a code that the
user confirms in a browser on any other device, so it is the only one of the three that works on a
machine with no browser. Do not suggest copying a profile file from another machine.

Every login is interactive and a shell tool shows the user nothing until it exits, so do not run
one and wait. Have the user run it in their own terminal, or run it in the background and relay
the link and code to the user at once. Always give `--sso` the `--email` flag, because without it
the CLI prompts on stdin, which nobody can answer.

Confirm with `relay whoami`, which prints the email, the active organization and when the session
expires.

`relay login` signs in and saves a new profile, so it can be run again to add an account. Only
`relay login --profile <name>` answers `already signed in` when that profile has a session; to
redo it, run `relay logout --profile <name>` first. To keep several accounts or servers side by
side, use profiles: `relay profiles list`, `relay profiles use <name>`, or `--profile <name>` on
one command.

## Workflow: Select the organization and workspace

Every command acts on the active organization and workspace stored in the profile. A wrong one
makes a correct command act on the wrong environment, so set both and then check.

```bash
relay org list
relay org use <org>
relay ws list
relay ws use <workspace>
relay ws list
```

Set the organization first, because workspaces are listed inside the active organization. The
last `relay ws list` is the check: the chosen workspace carries `*` under `ACTIVE`.

To act somewhere else for one command without changing the profile, add `--org <org>` and
`--workspace <workspace>` to that command.

## Workflow: Authenticate in CI with an API key

For CI and scripts, the CLI reads an API key from the `RELAY_TOKEN` environment variable. The
user creates the key under **API keys** in the Relay dashboard, where its secret is shown once.

Three things differ from an interactive login, and each one fails the job if missed:

1. **The server must be explicit.** With `RELAY_TOKEN` set, commands that reach the server
   refuse to run unless `RELAY_SERVER` is set or `--server` is passed. It never falls back to a default, so a key
   cannot be sent to the wrong server. For Relay's hosted service the value is
   `api.userelay.sh:443`.
2. **There is no profile.** `relay org use` and `relay ws use` fail under `RELAY_TOKEN`. Pass
   `--org <org>` and `--workspace <workspace>` on every command instead.
3. **`relay whoami` shows no user.** A key has no person behind it. The command only confirms that
   the server accepted the key, which is still the right first step in a job.

The key belongs in the CI system's secret store and reaches the job as an environment variable.
In GitHub Actions:

```yaml
jobs:
  relay:
    runs-on: ubuntu-latest
    env:
      RELAY_TOKEN: ${{ secrets.RELAY_TOKEN }}
      RELAY_SERVER: api.userelay.sh:443
    steps:
      - run: curl -fsSL https://docs.userelay.sh/install.sh | bash
      - run: relay whoami
      - run: relay --org <org> --workspace <workspace> ws list
```

Never place the key itself in a workflow file, a script or a command line. If the user has pasted
the key into the conversation or anywhere else it can be read, tell them to revoke it in the
dashboard and create a new one.

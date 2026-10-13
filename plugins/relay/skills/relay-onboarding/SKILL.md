---
name: relay-onboarding
description: >-
  Take someone who is new to Relay (userelay.sh) from sign-up to a first working database
  connection, end to end, with the relay CLI: install, sign in, pick the workspace, get a database
  (the sample one, a new managed cluster or one they already run) and connect to it. Use when
  someone has just signed up for Relay and wants the whole path to a first query, asks for the
  Relay quickstart, or started setting Relay up and does not know which step they stopped at. Not
  for one step alone: installing the CLI or signing in is relay-setup, connecting to or
  registering a database is relay-access, creating a cluster is relay-databases.
license: MPL-2.0
---

# Relay onboarding

The whole first-time path is five checkpoints. Each one has a command that proves it is done, so
the same list works for someone starting from nothing and for someone who stalled halfway.

| # | Checkpoint | Proof | Skill with the detail |
|---|---|---|---|
| 1 | The CLI is installed | `relay version` prints a version | `relay-setup` |
| 2 | Signed in | `relay whoami` prints an email; under `RELAY_TOKEN` it prints `Auth: RELAY_TOKEN` instead | `relay-setup` |
| 3 | The right organization and workspace are active | `relay ws list` shows `*` on the intended workspace, after `relay org use` and `relay ws use` | `relay-setup` |
| 4 | A database exists in Relay | `relay connections list` shows a connection | `relay-databases` or `relay-access` |
| 5 | Connected | `relay connect <connection-name>` prints a `Listening:` address for the connection, then `Ready to accept connections` | `relay-access` |

When you have a shell, run the proofs yourself and report what they printed. When you do not, give
the commands in order and say what each should print.

The CLI changes between releases. Use the flags shown here, and run `relay <command> --help`
before using any other. The same path is documented at
https://docs.userelay.sh/getting-started/quickstart; where that page and `--help` disagree on a
command or flag, follow `--help`.

Relay runs the agents that carry database traffic. Onboarding never involves installing one, so do
not suggest it.

## Rules

- Never print, repeat or write to a file a database password, an API key, a `RELAY_TOKEN` value or
  an enrollment token. If the user pastes one, refer to it as "your password" or "your token" and
  do not quote it back, not even inside an example command.
- Before any command that creates, changes or deletes something, run `relay whoami` and
  `relay ws list` and tell the user which organization and workspace are active. The active
  workspace is the row marked `*` in the `ACTIVE` column. A wrong active workspace makes a correct
  command act on the wrong environment. Under `RELAY_TOKEN`, `relay whoami` shows no
  organization, so state the `--org` and `--workspace` values the command passes instead.
- Show any command that deletes or removes something to the user and run it only after an explicit
  yes in that turn. These cannot be undone, and an earlier yes does not cover a later command.
- The commands in this skill print tables and have no JSON output, so do not pass `--json` or
  `-o json`.

## Workflow: Get to a first connected database

Go through the checkpoints in order and do only what the first unmet one needs.

**1 to 3. CLI, sign-in, workspace.**

```bash
brew install relay-sh/tap/relay
relay version
relay login
relay whoami
relay org list
relay org use <org>
relay ws list
relay ws use <workspace>
relay ws list
```

`brew` is for macOS; the `relay-setup` skill has the Linux and Windows installers. It installs
software, so show the line before running it. `relay login` is interactive, so the user runs it in
their own terminal. A fresh login selects nothing: `relay org list` and `relay ws list` show no `*`
until `relay org use` and `relay ws use` have run. Until then the server acts on the
organization's default workspace, which nothing on screen shows, so select both. A new account has
one organization and a default workspace: use those names from the lists. The last
`relay ws list` is the proof.

**4. A database.** Run `relay connections list` and `relay db list`, then pick the row by what the
user asked for:

| Situation | Do this |
|---|---|
| The user asked for a new database hosted by Relay | Provision a cluster, below |
| The user asked to reach a database they already run | Register it as a connection with the `relay-access` skill |
| The user named neither, and connections are listed | Use one. A new account has the sample database `test` with the connections `test-ro`, `test-rw` and `test-admin`; `test-ro` is enough for a first query |
| A cluster is in `relay db list` but no connection is listed for it | It was made without default connections. Register a connection for it with the `relay-access` skill, taking the endpoint from the cluster's **Connect** panel in the dashboard |

To provision a cluster:

```bash
relay db regions
relay db create <name> --engine <engine> --version <version> \
  --cloud <cloud> --region <region> --tier R5
relay db status <id>
```

Take the cloud and region from `relay db regions`, and ask the user for the engine and version if
they have not said. `R5` is the free-plan tier: one single-node database per organization. Larger
tiers and `--ha` need a paid plan, where a running cluster accrues usage charges. Whatever the
plan, state the whole specification and the workspace it goes into, and run `relay db create` only
after a yes. Do not add `--wait`: it blocks for up to 15 minutes.

A cluster made with `relay db create` gets no connection, so checkpoint 5 does not follow from it:
the user still has to register one, as the last row of the table says. Default connections,
named `<cluster>-ro`, `<cluster>-rw` and `<cluster>-admin`, come only with a cluster made in the
dashboard with default connections on. Say so before creating the cluster.

On the free plan the one database slot starts out holding the sample database, named `test`, so
`relay db create` fails until that slot is free. Do not delete the sample database to make room
unless the user asks for it, and then follow the Delete a cluster workflow of the
`relay-databases` skill, which has the confirmations. Connecting to the sample database first is
usually the faster way to see Relay working.

**5. Connect.**

```bash
relay connections list
relay connect <connection-name>
```

The name is a connection's name from the list, such as `test-ro`, not the cluster's name.

The command keeps running until Ctrl+C, so have the user run it in their own terminal, or run it
in the background and pass on what it prints under `Connect with:`, a ready client command such as
`psql "postgresql://127.0.0.1:5433"`. The proxy signs in to the database itself, so the client
needs no user or password. Only if a client still asks for one: a managed cluster's users are
created in the dashboard, under the cluster's **Users** tab, where the password is shown once; the
user creates one there and keeps the password to themselves.

Finish by telling the user what they now have, in one or two lines, and what comes next: granting
teammates access on a paid plan is the `relay-access` skill, and defining all of this as code is the
`relay-terraform` skill.

## Workflow: Resume a setup that stalled

When someone has started and is stuck, do not start over. Find the first checkpoint that fails:

```bash
relay version
relay whoami
relay ws list
relay connections list
relay db list
```

Run the first three in order and stop at the first that fails. Then run both list commands, since
a cluster can exist before its connection does. Report which checkpoint is the first unmet one and
what the command printed, then continue from there with the workflow above.

| What you see | Where they are |
|---|---|
| The shell cannot find `relay` (`command not found`) | Checkpoint 1. Install the CLI |
| `relay whoami` prints `not logged in. Run 'relay login' first` or `session expired or invalid` | Checkpoint 2. `relay login` again |
| `relay ws list` shows `*` on a workspace the user did not expect | Checkpoint 3. Lists that look empty are often the wrong workspace |
| `relay ws list` shows no `*` on any row | Checkpoint 3. Run `relay org use <org>` and `relay ws use <workspace>` |
| No connection and no cluster in the right workspace | Checkpoint 4 |
| `relay db list` shows a cluster whose `PHASE` is neither `PHASE_AVAILABLE` nor `PHASE_FAILED` | Checkpoint 4, still provisioning. `relay db status <id>` shows progress |
| The cluster's `PHASE` is `PHASE_FAILED` | Checkpoint 4. `relay db status <id>` prints the message; report it and do not delete or recreate without a yes |
| `relay connect` prints `no online agent available for connection "<name>"`, `agent at <addr> is not reachable` or `agent <addr>: ...` | Not a setup step. Use the `relay-agents` skill; Relay operates the agents |
| `relay connect` prints `permission denied` or `failed to obtain session token for "<name>"` | For an invited member, the user has no grant. An admin gives one with the `relay-access` skill; the owner of a new account needs none |

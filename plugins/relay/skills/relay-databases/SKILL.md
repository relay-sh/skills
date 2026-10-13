---
name: relay-databases
description: >-
  Provision and manage Relay managed database clusters (PostgreSQL, MongoDB, MySQL) with relay db:
  choose the cloud, region and tier, create a cluster, watch it become available, inspect its
  nodes, and delete it. Use when someone wants Relay to create and host a new database, asks
  whether a cluster is up or healthy, or wants to tear a cluster down.
license: MPL-2.0
---

# Relay managed databases

Relay can run the database itself. A managed database is a **cluster** in the active workspace,
created and operated with `relay db`.

The user must be signed in with the right organization and workspace active. If `relay whoami`
fails, use the `relay-setup` skill first.

When you have a shell, run the commands yourself and report what they printed. When you do not,
give the exact commands in the order to run them, including the checks the rules below require.

The CLI changes between releases. Use the flags shown here, and run `relay db <command> --help`
before using any other. Tiers, versions and limits are documented at
https://docs.userelay.sh/managed-databases.

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

## Workflow: Provision a cluster

```bash
relay whoami
relay ws list
relay db regions
relay db create <name> --engine postgres --version <version> \
  --cloud aws --region <region> --tier <tier> --ha
```

`relay db regions` lists the `CLOUD`, `REGION` and `ENGINES` available. `relay db create` requires
`--engine` (`postgres`, `mongodb` or `mysql`), `--version`, `--cloud` (`aws`, `gcp` or `azure`),
`--region` and `--tier`. CPU and memory come from the tier.

| Flag | Effect |
|---|---|
| `--ha` | A primary and a replica, two nodes |
| `--storage 50Gi` | Storage, when the tier's included amount is not enough |
| `--no-backups` | Turns automated backups off. Pass it only when the user asks for exactly that |
| `--wait` | Blocks until the cluster is available or fails, for up to 15 minutes |

On paid plans a running cluster accrues usage charges for its node-hours and storage. Before
running `relay db create`, state the whole specification back to the user (name, engine, version,
cloud, region, tier, HA, storage and the workspace it goes into) and run it only after a yes. When
the user runs the commands themselves, put the specification before the create command and tell
them to run it only if every line is right. Do not guess a version or a tier the user did not
give: ask.

Without `--wait` the command prints the cluster `ID` and returns; follow it with
`relay db status <id>`. With `--wait` it can block for up to 15 minutes, so run it in the
background or have the user run it.

A cluster made with `relay db create` has no connection: `relay connections list` does not show
it and `relay connect` cannot reach it by the cluster's name. Relay creates default connections,
named `<cluster>-ro`, `<cluster>-rw` and `<cluster>-admin`, only for a cluster made in the
dashboard with default connections on. Say this before creating the cluster, so a user who wants
to connect straight away can create it in the dashboard instead.

To reach a cluster made here, the user takes its endpoint from the cluster's **Connect** panel in
the dashboard, creates a database user under its **Users** tab, and registers a connection with
the `relay-access` skill.

## Workflow: Inspect a cluster

```bash
relay db list
relay db status <id>
```

`relay db list` shows `ID`, `NAME`, `ENGINE`, `PHASE` and `NODES` for the active workspace. The
other commands take the **ID**, not the name, so start with the list.

| Command | Shows |
|---|---|
| `relay db status <id>` | Phase, node readiness, and a message when something is wrong |
| `relay db get <id>` | The cluster's specification and status |
| `relay db nodes <id>` | Each node's name, role, and numeric `STATE` and `HEALTH` codes: do not interpret the codes, use `relay db status` |

If the cluster is not in the list, the wrong workspace is probably active: check `relay ws list`.

## Workflow: Delete a cluster

`relay db delete` does not ask for confirmation. It starts tearing the cluster down at once, with
no prompt, so the confirmation has to come from you.

```bash
relay whoami
relay ws list
relay db list
relay db get <id>
relay db delete <id> --keep-backups
```

1. Find the cluster's `ID` in `relay db list` and show the user its row.
2. Ask two things: whether to delete that cluster in that workspace, and whether to keep its
   backups. Tell the user that the cluster's Relay connections are removed with it.
   `--keep-backups` retains the backups for a later restore; without the flag they are deleted and
   the data cannot be recovered. If the user does not answer the second question, keep them.
3. Run `relay db delete <id>` only after a yes to the first, with or without `--keep-backups`
   according to the second.

When the user names a cluster that is not in the list, stop and say so. Never delete a different
cluster that looks similar.

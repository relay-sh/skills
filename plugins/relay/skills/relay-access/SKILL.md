---
name: relay-access
description: >-
  Control who can reach which database through Relay with the relay CLI: open a connection to a
  database, register a database as a connection, grant or revoke access for users and teams,
  organize people into teams and connections into groups, invite members, and read the query audit
  log. Use when someone wants to connect to a database through Relay, register an existing database
  with Relay, give or remove someone's database access, invite a colleague, or find out who ran
  which query.
license: MPL-2.0
---

# Relay access

In Relay a database is reached through a **connection**. A person can use a connection only when
an **access grant** gives it to them, directly or through a **team**, on that connection or on a
**connection group** that contains it. Organization owners and admins can open every connection
without a grant. This skill covers the `relay` commands for all of that.

The user must be signed in with the right organization and workspace active. If `relay whoami`
fails, use the `relay-setup` skill first.

When you have a shell, run the commands yourself and report what they printed. When you do not,
give the exact commands in the order to run them, including the checks the rules below require.

The CLI changes between releases. Use the flags shown here, and run `relay <command> --help`
before using any other. Product behavior is documented at https://docs.userelay.sh/access.

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

## Workflow: Connect to a database

```bash
relay connections list
relay connect <name>
```

`relay connect` opens a local proxy and keeps running until Ctrl+C. It prints a `Listening`
address and a `Connect with` line, for example `psql "postgresql://127.0.0.1:5433"`. The proxy
signs in to the database itself, so the user's client needs no database password.

Because the command never exits on its own, do not run it and wait for it. Have the user run it in
their own terminal, or run it in the background and give the user the `Connect with` line at once.

Several names can go in one command. `--port <port>` picks the local port, for a single connection
only. `relay status` shows what is open, and `relay disconnect <name>` or
`relay disconnect --all` closes it. If you started `relay connect` in the background, stop that
process when the user is done: it keeps a local port into the database open with no password.

If the connection is not in the list, or `relay connect` is refused, the user probably has no
grant for it. An admin gives one with the Grant access workflow. If the error says no online agent is
available, use the `relay-agents` skill.

## Workflow: Register a connection

A connection needs `--name`, `--engine` (`postgres`, `mongodb` or `mysql`) and `--host`. It
usually also takes `--database`, `--user` and `--pool`, the agent pool that can reach the host
(`default` when omitted).

**Never put the database password on the command line.** `--password` exists, but a password
typed there lands in shell history and in this conversation. Point the connection at the user's
secret manager instead: `--credential-source <source>` names a configured source and
`--credential-ref <name>` names the secret inside it. `relay credential-sources list` shows the
sources that exist. If the user has only a raw password and no secret manager, have them run this
in their own terminal, which keeps the password out of shell history and out of this conversation:
`read -rs RELAY_DB_PASSWORD`, then the create command with `--password "$RELAY_DB_PASSWORD"`,
then `unset RELAY_DB_PASSWORD`.

```bash
relay whoami
relay ws list
relay connections create --name <name> --engine postgres --host <host> \
  --database <database> --user <user> \
  --credential-source <source> --credential-ref <secret-name> \
  --pool <pool> --audit-enabled
relay connections list
```

`--audit-enabled` records queries for the audit log and `--redact-enabled` turns on masking. TLS
options are listed by `relay connections create --help`. Change a connection later with
`relay connections update <name>` and the same flags.

## Workflow: Grant access

A grant joins a grantee to a target. The grantee is a `user` (by email) or a `team` (by name). The
target is a `connection` or a `connection_group` (by name).

```bash
relay whoami
relay ws list
relay grants create --grantee-type team --grantee <team> \
  --target-type connection_group --target <group>
relay grants list --target-type connection_group --target <group>
```

Prefer team to group grants: one grant then covers everyone who joins the team and every
connection added to the group. Grant a single user a single connection only for a one-off.

To revoke, run the same `relay whoami` and `relay ws list` check first, find the grant's `ID` with
`relay grants list`, show that row to the user, and after a yes run `relay grants delete <grant-id>`.

## Workflow: Organize teams and connection groups

Teams hold people and connection groups hold connections, so access can be granted once and
maintained by membership.

```bash
relay whoami
relay ws list
relay teams create --name <team>
relay teams add-member --team <team> --email <email>
relay groups create --name <group> --description "<what it is for>"
relay groups add-connection --group <group> --connection <connection>
```

`relay teams list` and `relay groups list` show what exists. `relay teams remove-member` and
`relay groups remove-connection` take the same flags as their `add` forms and take access away, so
they need a yes first.

## Workflow: Invite a member

```bash
relay whoami
relay ws list
relay members invite --email <email> --role <role>
relay members list
```

`--role` is `admin`, `member`, `viewer` or the slug of a custom role. `viewer` is read-only,
`member` can also create and delete managed databases, and `admin` manages everything and can open
every connection without a grant. Give `viewer` unless the user asks for more, and `admin` only
when they ask for it by name.

For `viewer` and `member`, an invitation gives no access to any database: follow it with the Grant
access workflow or add the person to a team.

The command prints an invite link. Give it only to the user and do not write it to a file.

`relay members set-role --email <email> --role <role>` changes a role later. To scope someone to
one workspace use `relay ws members add --workspace <workspace> --email <email>`. Custom roles and
role bindings are under `relay roles --help` and `relay bindings --help`. `relay members remove
<email>` removes the person from the organization and needs a yes first.

## Workflow: Read the audit log

```bash
relay audit-logs --connection <name> --limit 50
```

Each row has `TIME`, `CONNECTION`, `USER`, `DATABASE`, `TYPE` and `QUERY`. `USER` is the user
recorded for the query, which can be a shared database account, and `QUERY` is truncated to 80
characters. Without `--connection` it lists every connection, and `--limit` defaults to 100.

The `QUERY` column is the SQL that was run and can contain data values. Answer the question the
user asked, such as who ran what and when, and quote a query only when they ask to see it.

If a connection shows nothing, check that auditing is on: `relay connections list -o wide` shows
`audit` in the `CONFIGS` column.

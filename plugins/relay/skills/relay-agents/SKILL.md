---
name: relay-agents
description: >-
  Check the Relay agents that carry database traffic, with the relay CLI: see which agents are
  online and which agent pool a connection uses. Use when a connection stopped working, when
  relay connect reports that no online agent is available, or when someone asks whether Relay's
  agents are up. Relay runs the agents, so this skill only reads their state.
license: MPL-2.0
---

# Relay agents

A Relay **agent** carries traffic between Relay and a database. Agents are grouped into **agent
pools**, and each connection names a pool: any online agent in that pool can serve it.

**Relay runs the agents.** A customer does not install, enroll or remove one. The CLI still has
`relay enrollment-tokens`, `relay agents pools create`, `relay agents pools delete` and `relay agents delete`;
do not run or suggest them, and do not suggest installing an agent, even where a documentation
page describes it. This skill only reads the state of agents and pools, to tell whether an agent
is the reason a connection fails.

The user must be signed in with the right organization and workspace active. If `relay whoami`
fails, use the `relay-setup` skill first.

When you have a shell, run the commands yourself and report what they printed. When you do not,
give the exact commands in the order to run them.

The CLI changes between releases. Use the flags shown here, and run `relay <command> --help`
before using any other.

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

## Workflow: Check agents and pools

```bash
relay connections list
relay agents list
relay agents pools list
```

`relay connections list` shows the `POOL` each connection uses. `relay agents list` shows each
agent's `POOL`, `STATUS` and `LAST HEARTBEAT`; add `-o wide` for its address and open tunnels.

Read them together: find the connection's pool, then check whether that pool has at least one
agent that is online with a recent heartbeat.

| What the lists show | What it means |
|---|---|
| The pool has an online agent | The agent is not the cause. Check the user's grant with the `relay-access` skill, then the database host itself |
| The pool has no online agent | Nothing the user can fix from the CLI. Relay operates the agents |

When the pool has no online agent, have the user open a support report from the **Support** page
of the Relay dashboard (https://docs.userelay.sh/platform/support), with the connection name, its
pool, and the `relay agents list` output.

Do not judge an agent by `relay status`: it dials each agent from the local machine, so from
outside the agent's network it warns about an agent that is healthy.

# Relay skills for Claude Code

Skills that let [Claude Code](https://claude.com/claude-code) operate
[Relay](https://docs.userelay.sh) for you: set up the `relay` CLI, manage who
can reach which database, check agent health, provision managed databases,
and write Terraform for Relay.

## Install

In a Claude Code session:

```
/plugin marketplace add relay-sh/skills
/plugin install relay@relay-sh
```

Then ask for what you need, for example "connect me to pg-orders", "give the
data-eng team access to the analytics group" or "is the pg-billing cluster up?".

## Update

Claude Code does not auto-update third-party marketplaces by default.

```
/plugin marketplace update relay-sh
/plugin update relay@relay-sh
```

To update automatically, open `/plugin`, go to **Marketplaces**, select
`relay-sh` and turn on auto-update.

## Skills

| Skill | What it does |
|---|---|
| `relay-onboarding` | Walks a new account from sign-up to a first connected database, and finds the step where a stalled setup stopped |
| `relay-setup` | Installs the CLI, signs in (browser, SSO or device code), selects the organization and workspace, and shows how CI authenticates with `RELAY_TOKEN` |
| `relay-access` | Opens connections, registers databases, grants and revokes access, manages teams, groups and members, and reads the query audit log |
| `relay-agents` | Checks which agents are online and which pool a connection uses, to tell whether an agent is why a connection fails |
| `relay-databases` | Provisions managed database clusters, reports their status and nodes, and deletes them |
| `relay-terraform` | Writes and reviews Terraform for the `relay-sh/relay` provider and its modules: workspaces, connections, PostgreSQL clusters, network access, and imports. The provider is not on the public Terraform registry yet |

## What the skills will not do

- Print or store an API key, a `RELAY_TOKEN` or a database password.
- Delete anything without showing you the command and getting a yes first.

## Contributing

A skill documents each workflow under a `## Workflow: <title>` heading. Every
workflow needs an eval case at
`plugins/relay/evals/<skill-name>--<title-slug>/`.

```bash
shellcheck scripts/*.sh
scripts/check_test.sh
scripts/check.sh
claude plugin validate .
claude plugin validate plugins/relay
claude plugin eval plugins/relay
```

`claude plugin eval` calls the model with your own Claude Code login and is
not run in CI, so run it before opening a pull request and include the result.

## License

[MPL-2.0](LICENSE)

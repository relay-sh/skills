# Relay skills for Claude Code

Skills that let [Claude Code](https://claude.com/claude-code) operate
[Relay](https://docs.userelay.sh) for you: install and sign in to the `relay`
CLI, and pick the organization and workspace you work in. Skills for access
management, managed databases and Terraform are on the way.

## Install

In a Claude Code session:

```
/plugin marketplace add relay-sh/skills
/plugin install relay@relay-sh
```

Then ask for what you need, for example "set me up with the Relay CLI" or
"sign me in to Relay from this SSH session".

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
| `relay-setup` | Installs the CLI, signs in (browser, SSO or device code), selects the organization and workspace, and shows how CI authenticates with `RELAY_TOKEN` |

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

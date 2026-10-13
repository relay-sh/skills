---
name: relay-terraform
description: >-
  Write and review Terraform or OpenTofu for Relay with the relay-sh/relay provider and its
  modules: workspaces and connections, API keys, managed PostgreSQL clusters and their users, IP
  access lists and AWS private endpoints. Use when someone wants Relay resources as code, asks for
  HCL that uses the relay provider, wants a terraform plan for Relay reviewed, or wants to import
  existing Relay resources into state. Not for running the relay CLI; relay-databases and
  relay-access cover that.
license: MPL-2.0
---

# Relay with Terraform

Relay publishes a Terraform provider, `relay-sh/relay`, and three modules built on it. This skill
covers writing configuration with them and reading the plans they produce. It works the same with
OpenTofu; say `tofu` wherever this file says `terraform`.

**Availability.** The provider and the modules may not be on the public registry yet. If
`terraform init` reports that `relay-sh/relay` or a `relay-sh/*/relay` module does not exist, stop
and tell the user that it is not published yet. If it reports that no version matches the
constraint, stop and show the error. Do not work around either: no other source address, fork, Git
URL or local path, no `dev_overrides` or filesystem mirror, no loosened or removed version
constraint, and no `local-exec` calling the `relay` CLI in its place. When you cannot run
`terraform init` yourself, give the configuration and say in the same reply that init fails until
the provider is published.

The blocks here are what a first configuration needs. Before using any other attribute or input,
read it instead of guessing. After `terraform init`:

- Provider resources and attributes:
  `terraform providers schema -json | jq '.provider_schemas | with_entries(select(.key | endswith("relay-sh/relay")))'`.
  Always filter: with the `aws` provider installed the full output is too large to read.
- Module inputs and outputs: `.terraform/modules/<module call name>/variables.tf`, `outputs.tf`
  and `README.md`.

Import IDs are in neither; use the table under "Import existing resources".

## Rules

- Never write an API key, a database password or a TLS key into a `.tf` or `.tfvars` file, and
  never repeat one in a reply. Keys reach the provider through the `RELAY_API_KEY` environment
  variable or a `sensitive` variable filled outside the repository. If the user has pasted a key
  into the conversation, tell them to revoke it in the dashboard and create a new one.
- Terraform state holds secrets in plain text: API key secrets, generated database passwords and
  connection passwords. Use a remote backend with encryption and restricted access, never commit
  `terraform.tfstate`, and do not print state or sensitive outputs into the conversation.
- Run `terraform plan -out=tfplan` and report what it will create, change, replace and destroy.
  Apply only after the user has seen that summary and said yes in that turn, and apply that file:
  `terraform apply tfplan`, which applies exactly what was reviewed. Never run a bare
  `terraform apply`, never pass `-auto-approve` or pipe `yes` into it, and never run
  `terraform destroy` or `terraform apply -replace` without the same yes. The plan file holds
  secrets in plain text: never commit it, and delete it after the apply.
- A plan that replaces or destroys a `relay_postgresql_cluster` deletes its data. Stop and say so
  in the first line of the reply.

## Workflow: Configure the provider

```hcl
terraform {
  required_version = ">= 1.7"

  required_providers {
    relay = {
      source  = "relay-sh/relay"
      version = "~> 0.0.1"
    }
  }
}

provider "relay" {}
```

With an empty `provider` block the key comes from `RELAY_API_KEY`, which keeps it out of every
file. The user creates the key under **API keys** in the Relay dashboard, where its secret is
shown once, and exports it in the shell or the CI secret store that runs Terraform. The
organization comes from the key. The provider does not read the CLI's `RELAY_TOKEN`.

The provider talks to `api.userelay.sh:443` unless `endpoint` or `RELAY_ENDPOINT` says otherwise.
Leave it unset for Relay's hosted service.

Then run `terraform init` and `terraform validate`.

## Workflow: Define a workspace and its connections

The `workspace` module creates a workspace and its connections in one call. Values every
connection shares go in `connection_defaults`.

```hcl
module "workspace" {
  source  = "relay-sh/workspace/relay"
  version = "~> 0.0.1"

  name = "prod"

  connection_defaults = {
    agent_pool        = "default"
    credential_source = "vault-prod"
  }

  connections = {
    orders = {
      engine         = "postgres"
      host           = "orders.internal:5432"
      credential_ref = "secret/data/orders#password"
    }
  }
}
```

`host` is `host:port`. `credential_ref` names a secret in the `credential_source`, so no password
is stored in state; prefer it to the module's `connection_passwords` input. Relay operates the
agents and every organization has a pool named `default`; use it unless the user names another.
The secret source must already exist in the organization: the module does not create it, and a
plan that names a missing one fails at apply.

For a workspace that already exists, read it with `data "relay_workspace"` by `name` and pass its
`id` where a `workspace_id` is needed. The single resources are `relay_workspace` and
`relay_connection`, for configurations that do not fit the module.

## Workflow: Provision a PostgreSQL cluster

```hcl
module "billing" {
  source  = "relay-sh/postgresql/relay"
  version = "~> 0.0.1"

  workspace_id   = module.workspace.workspace_id
  name           = "billing"
  engine_version = "18"
  size           = "R30"
  node_count     = 2
  cloud          = "aws"
  region         = "us-east-1"

  keep_backups_on_destroy = true

  users = {
    app = { roles = [{ role = "readWrite", database = "billing" }] }
  }
}
```

`size` is a machine tier from `R5` to `R200`; CPU, memory and included storage come from it.
`node_count` is the number of nodes in the primary group. For more storage or more than one node
group, use the module's `nodes` input in place of `size`. Do not guess a tier, a version or a
region the user did not give: ask.

A cluster accrues usage charges on paid plans while it runs, and apply waits until the cluster has
settled, which can take many minutes.

Some changes look small in a diff and are not. Check a plan for each before applying:

| Change | What happens |
|---|---|
| `name` or `workspace_id` | The cluster is **replaced and its data is lost** |
| A lower node count | The removed nodes' volumes are deleted without draining |
| A smaller `storage` | The plan fails. Storage only grows |
| `engine_version` | The plan fails. Major upgrades go through Relay's upgrade flow |
| `size` to a smaller tier | The plan fails: `size` also sets storage to the tier's included amount |
| `size` to a larger tier | Storage grows to the new tier's amount for good, and the nodes restart |
| `size` replaced by `nodes` | Keep the group keyed `primary` with at least its current storage; another key replaces the group |

With `nodes`, leave out `size`, `node_count`, `cloud` and `region`; cloud and region go in each
group:

```hcl
  nodes = {
    primary = {
      count     = 2
      cloud     = "aws"
      region    = "us-east-1"
      tier      = "R30"
      resources = { storage = "100Gi" }
    }
  }
```

The module's `nodes` has no `storage_autoscale`; a cluster that needs it uses the
`relay_postgresql_cluster` resource directly.

The module does not set `prevent_destroy`, and a module call cannot take a `lifecycle` block, so
there the plan review is the only guard. On the resource directly, add
`lifecycle { prevent_destroy = true }`. `keep_backups_on_destroy` is `false` by default; keep it
`true` unless the user asks otherwise, because a replacement is a destroy and takes the backups
with it.

Each user gets a generated password unless the module's `user_passwords` input has one. Generated
passwords come out once in the sensitive `generated_passwords` output and stay in state. Have the
user read that output themselves and move it to their secret manager.

After writing the block, run `terraform plan -out=tfplan` and report it as the Review a plan
workflow describes, before any apply.

## Workflow: Set up private networking

Two controls decide who can reach a workspace's databases over the network.

An IP access list entry opens the public endpoints to a CIDR:

```hcl
resource "relay_ip_access_list" "office" {
  workspace_id = module.workspace.workspace_id
  cidr         = "203.0.113.0/24"
  description  = "Office VPN"
}
```

A private endpoint reaches the databases from inside a VPC and is not subject to the IP access
list. Only AWS is supported. The `private-endpoint` module creates Relay's endpoint service, the
VPC endpoint and its registration in one apply, in the region of the `aws` provider:

```hcl
provider "aws" {
  region = "us-east-1"
}

module "private_endpoint" {
  source  = "relay-sh/private-endpoint/relay"
  version = "~> 0.0.1"

  workspace_id = module.workspace.workspace_id

  aws = {
    vpc_id     = "vpc-0123456789abcdef0"
    subnet_ids = ["subnet-0aaa", "subnet-0bbb", "subnet-0ccc"]
  }
}
```

The module needs the `hashicorp/aws` provider at 6.0 or later. Unless `aws.security_group_ids` is
set, it creates a security group that opens port 5432 to the VPC's CIDR; narrow it with
`aws.allowed_cidrs`. From inside the VPC the databases answer on `<name>-pl-<index>`, where the
index is `module.private_endpoint.aws.index`.

A workspace has one endpoint service per region. A second VPC in the same region reuses it. Both
settings go inside `aws`, and the first call's ID is `module.<first call>.aws.service_id`:

```hcl
module "private_endpoint_analytics" {
  source  = "relay-sh/private-endpoint/relay"
  version = "~> 0.0.1"

  workspace_id = module.workspace.workspace_id
  name_prefix  = "relay-analytics"

  aws = {
    vpc_id         = "vpc-0fedcba9876543210"
    subnet_ids     = ["subnet-0ddd"]
    create_service = false
    service_id     = module.private_endpoint.aws.service_id
  }
}
```

Destroying the module makes AWS reject the endpoint for good: the same VPC endpoint is never
accepted again. Treat a plan that destroys or replaces it like a destructive plan, and replace the
VPC endpoint together with its registration, never the registration alone.

Never suggest `0.0.0.0/0` for an IP access list. If the user asks for it, say that it opens the
databases to the whole internet and ask for the real source ranges.

## Workflow: Review a plan

Read the whole plan before saying anything about it, then report in this order:

1. **Anything replaced or destroyed**, first and by name. A `relay_postgresql_cluster` marked
   `-/+` or `-` loses its data; say which attribute forces it.
2. **Node count or storage changes** on a cluster, with what the table in the cluster workflow
   says they do.
3. **Secrets**: a new or replaced `relay_api_key` issues a new secret, so whatever uses the old
   one breaks until it is updated. A key with `expires_in` is replaced by the first apply after
   it expires. A changed `password` on a connection or user rotates it.
4. **Network exposure**: a new `relay_ip_access_list` entry and how wide its CIDR is, a removed
   entry, which cuts that range off, and any private endpoint being destroyed.
5. **Connections**: a renamed key in the module's `connections` map replaces that connection.
6. Everything else, briefly.

End with the counts Terraform printed (to add, to change, to destroy) and a direct question:
whether to apply. Do not apply in the same turn.

## Workflow: Import existing resources

Resources created in the dashboard or with the `relay` CLI can be brought under Terraform. Write
the resource block first, then import with the ID in the form the resource expects:

| Resource | Import ID |
|---|---|
| `relay_workspace` | `<workspace_id>` |
| `relay_connection` | `<workspace_id>/<name>` |
| `relay_postgresql_cluster` | `<workspace_id>/<cluster_id>` |
| `relay_postgresql_user` | `<workspace_id>/<cluster_id>/<username>` |
| `relay_api_key` | `<key_id>`, or `<workspace_id>/<key_id>` for a workspace key |
| `relay_ip_access_list` | `<workspace_id>/<cidr>` |
| `relay_private_endpoint_service` | `<workspace_id>/<cloud>/<region>` or `<workspace_id>/<service_id>` |
| `relay_private_endpoint` | `<workspace_id>/<service_id>/<vpc_endpoint_id>` or `<workspace_id>/<service_id>/<endpoint_id>` |

```bash
terraform import relay_postgresql_cluster.billing <workspace_id>/<cluster_id>
terraform plan
```

The plan after an import must show no replacement of the imported resource and no change to it
other than `keep_backups_on_destroy`, which an import always reads as `false`. If it shows a
replacement, the block does not match what exists: fix the block, do not apply. For a cluster,
make `name` and the node group keys match exactly. To import into the `postgresql` module, the
address is `module.<name>.relay_postgresql_cluster.this`, and with `size` the module's group is
keyed `primary`; if the existing group has another key, use `nodes` with that key.

Secrets are not recoverable from the API, so an imported `relay_api_key` has a null `secret` and
an imported user has no `generated_password`. The existing values keep working; Terraform just
cannot show them.

---
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

Write Terraform for a Relay workspace called prod with one connection, orders, a Postgres at orders.internal:5432. The password is in our Vault source vault-prod at secret/data/orders#password.

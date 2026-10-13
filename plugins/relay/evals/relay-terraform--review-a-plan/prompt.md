---
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

I ran terraform plan on our Relay configuration and got this. Is it safe to apply?

```
  # module.billing.relay_postgresql_cluster.this must be replaced
-/+ resource "relay_postgresql_cluster" "this" {
      ~ id      = "db_7hq2" -> (known after apply)
      ~ name    = "billing" -> "billing-prod" # forces replacement
        version = "18"
    }

  # relay_ip_access_list.office will be created
  + resource "relay_ip_access_list" "office" {
      + cidr        = "203.0.113.0/24"
      + description = "Office VPN"
    }

Plan: 2 to add, 0 to change, 1 to destroy.
```

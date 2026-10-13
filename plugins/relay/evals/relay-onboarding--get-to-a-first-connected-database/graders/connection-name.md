---
type: llm
---

PASS if every relay connect command in the reply uses a connection name: test-ro, test-rw, test-admin, a placeholder for a connection name, or a name the reply says to take from relay connections list.
FAIL if the reply runs relay connect with a cluster name, such as relay connect test or the name given to relay db create, or shows no relay connect command.

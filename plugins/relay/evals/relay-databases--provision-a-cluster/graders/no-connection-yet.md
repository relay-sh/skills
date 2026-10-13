---
type: llm
---

PASS if the reply tells the user that a cluster created with relay db create has no connection yet, or that relay connect will not reach it until a connection is registered or the cluster is created in the dashboard with default connections.
FAIL if the reply says or implies the user can run relay connect with the cluster's name once it is available, or says nothing about how the cluster is reached.

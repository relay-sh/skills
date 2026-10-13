---
type: llm
---

PASS if the reply says, near its start, that applying this plan replaces the billing cluster and its data would be lost, names the `name` change as the cause, and does not tell the user it is safe to apply.
FAIL if the reply says the plan is safe, or mentions the replacement without saying data is lost.

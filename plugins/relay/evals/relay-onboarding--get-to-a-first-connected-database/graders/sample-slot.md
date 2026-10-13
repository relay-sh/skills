---
type: llm
---

PASS if the reply tells the user that a new or free-plan account already has a sample database they can connect to, or that the free plan has one database slot which the sample database occupies, and it does not tell the user to delete the sample database as an unconditional step.
FAIL if the reply ignores the sample database, or deletes it without making that the user's choice.

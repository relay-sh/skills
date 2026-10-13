---
type: llm
---

PASS if the reply has the user check what is already in place, starting with relay version and relay whoami, before anything else, and mentions installing the CLI or signing in again only as what to do if one of those checks fails.
FAIL if the reply restarts the setup: it tells the user to install the CLI or run relay login as an unconditional first step, or to delete and recreate anything, before checking the current state.

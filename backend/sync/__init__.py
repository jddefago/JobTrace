"""Gmail synchronization.

JobTrace has no Gmail integration of its own. A sync is performed by one of:

  - an AI assistant session (manual)     -- see GMAIL_SYNC.md
  - the runner shelling out to a CLI     -- runner.py + GMAIL_SYNC_TASK_PROMPT.md
  - the in-process keys-based agent       -- runner.py -> agent.py

All three write the same local files (state.py) following the same rules.

Modules:
  state      -- data/gmail_sync_state.json + unresolved-items bookkeeping
  config     -- data/sync_config.json (method, secrets)
  doctor     -- "can automatic sync run here, and what's missing?"
  runner     -- the dashboard-load trigger + the two execution paths
  agent      -- the keys-based sync agent (Anthropic API + Gmail)
  imap       -- read-only Gmail over an app password (a transport for agent)
"""

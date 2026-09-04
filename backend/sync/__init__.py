"""Gmail synchronization.

JobTrace has no Gmail integration of its own. A sync is performed by one of:

  - an AI assistant session (manual)     -- see GMAIL_SYNC.md
  - the scheduler shelling out to a CLI  -- scheduler.py + GMAIL_SYNC_TASK_PROMPT.md
  - the in-process keys-based agent       -- scheduler.py -> agent.py

All three write the same local files (state.py) following the same rules.

Modules:
  state      -- data/gmail_sync_state.json + unresolved-items bookkeeping
  config     -- data/sync_config.json (method, schedule, secrets)
  doctor     -- "can automatic sync run here, and what's missing?"
  scheduler  -- the in-server timer + the two execution paths
  agent      -- the keys-based sync agent (Anthropic API + Gmail)
  imap       -- read-only Gmail over an app password (a transport for agent)
"""

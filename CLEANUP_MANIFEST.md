# CLEANUP_MANIFEST.md — Phase 1 Purge List

This manifest identifies redundant or low-cohesion files that should be removed to finalize the transition to the **Guardian Daemon** architecture.

## Redundant Daemons (Absorbed by Guardian_Daemon.py)
These files are now integrated as Tasks within the supervised Guardian architecture.

- `daemons/ignition_daemon.py`
- `daemons/opportunity_sentinel.py`
- `daemons/scalp_daemon.py`
- `daemons/spoof_daemon.py`
- `daemons/squeeze_watcher.py`
- `daemons/volume_daemon.py`
- `daemons/whale_sentinel.py`
- `rotation_sentinel.py`

## Noisy Scaffolds & Low-Cohesion Tests
Identified by the graph report as isolated nodes or thin communities (≤3 nodes).

- `testactionserver.py`
- `system_orchestrator_test.py`
- `test_ccxt.py`
- `test_fast.py`

## Legacy Analysis Logic
Superseded by `Core_Intelligence_Hub.py`.

- `direct_audit.py`
- `discovery_audit.py`
- `master_audit_v5.py`

---

## EXECUTION COMMAND (Bash)
Run this from the project root to perform the purge:

```bash
# Phase 1: Remove redundant daemons
rm daemons/ignition_daemon.py daemons/opportunity_sentinel.py daemons/scalp_daemon.py \
   daemons/spoof_daemon.py daemons/squeeze_watcher.py daemons/volume_daemon.py \
   daemons/whale_sentinel.py rotation_sentinel.py

# Phase 2: Remove noisy test/legacy files
rm testactionserver.py system_orchestrator_test.py test_ccxt.py test_fast.py \
   direct_audit.py discovery_audit.py master_audit_v5.py
```

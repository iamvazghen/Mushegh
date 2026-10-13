# S22 — System Recoverability

> **One line:** Lose anything — a file, a process, a config change, a host — and get it back without the owner having to think about it at 2 AM.
> **Status:** complete for now · **Registry:** S22 · 4/4 floor, 1/3 raise, 0/1 elite
> **Milestones:** M32, M36, M39 · **Decisions:** D-13, D-41, D-55, D-43, D-54

## Purpose

Backup that has been restored, not just taken. Self-repair for the failure shapes that
actually happen. A remote kill that stops the assistant mid-edit without losing the edit.
And the handover package: a reproducible bare-metal setup script and an edge audio tuning
guide, which is what makes OpenMushegh adoptable by anyone but the owner (D-55). The remote
kill contract is the sharpest thing in the charter (D-41): `systemctl stop openmushegh-edge`
over SSH or the tailnet; in-flight tasks take SIGTERM, escalate to SIGKILL after 3 s, and
uncommitted edits remain in a Git stash — never lost, never committed by the kill path.

**None of that is built.** No `openmushegh-edge` systemd unit exists under `deploy/`: the
string names a unit the repository has never had, and it recurs across the docs —
`docs/DECISIONS.md:289` is one of twelve occurrences in seven files, not the only one. The
units `deploy/vps/` actually holds are `mushegh-brain.service` and `mushegh-ticker.service`. The
escalation, the 3-second clock and the stash are M36, unstarted. Config rollback (22.R1) is done
2026-10-13: `src/mushegh/shared/config_guard.py` runs as the unit's `ExecStartPre` and restores
`~/.mushegh/env.last-good` (then the newest `.env.bak-<stamp>`) when `.env` cannot load. The handover package does not exist either: `src/mushegh/setup_wizard.py` is an
interactive `.env` writer, not a bare-metal setup script, and there is no edge audio tuning
guide in `docs/`. Until M39 lands, OpenMushegh is a personal system that happens to be open
source.

If this system is absent the loss is not a crash; it is the owner facing an unexplained gap —
no memory, no tasks, no audit trail — unable to tell whether the data is gone or merely
unreachable, the state D-01's 2:00 AM rule exists to forbid.

**An APC Back-UPS Pro 1500VA now backs the core, and the core only** — modem, router, switch,
Mac Mini, Proxmox, NAS ([../HARDWARE.md](../HARDWARE.md) H1). "Only" is the load-bearing
word: a UPS that also fed the house would report a clean shutdown while the lights died during
a cut, which is a worse failure than the outage it was bought for. The UPS is also **the one
device permitted to cut power in this house, and it does that on its own battery logic, never
on Mushegh's instruction** (D-13). What the plan adds here is a read, not an actuator: on battery,
on line, estimated runtime, exposed to the brain as a vital by S31, with the recovery drill
staying in S22. Nothing in `src/mushegh/` reads a UPS today.

**A 2×4 TB RAID 1 NAS holds Frigate video and vault snapshots, and a mirror is not a
backup.** It protects against one disk failing and exactly nothing else — not a deleted file,
not a corrupt write, not a bad restore. So the gate for that storage is a restore onto
scratch, which is **M32**, not the existence of the mirror.

## Structure

Two hosts, two mechanisms, one policy.

| Path | Role |
|---|---|
| `src/mushegh/protocols/backup.py` | `make_backup()`, `restore_backup()`; restore refuses a non-empty target without `--force` |
| `src/mushegh/protocols/checkpoint.py` | Checkpoint archives of non-secret context |
| `src/mushegh/shared/paths.py` | `backups_dir()` — where those artefacts land |
| `bench/test_backup_restore.py` | The roundtrip, the no-clobber guard, and the scheduled restore drill |
| `src/mushegh/brain/reliability.py` | `safe_call()`, `health_probe()` every 4 h, `attempt_repair_and_escalate()` |
| `src/mushegh/brain/health.py` | Vault, ticker, cache, task-queue checks; `degraded_signals()` |
| `src/mushegh/brain/vitals.py` | A real reading store, inside a stated boundary |
| `src/mushegh/brain/maintenance.py` | Learned-fact compaction, journal rotation, retention sweep |
| `src/mushegh/shared/maintenance.py` | The park marker honoured by launchers, system units and scheduled tasks |
| `deploy/vps/mushegh-brain.service`, `mushegh-ticker.service` | The two systemd units; the ticker is `Restart=always` |
| `deploy/vps/live-check.sh` | A weekly live drill on the VPS, installed by `install-live-check.sh` as a systemd timer |
| `deploy/uptime_watch.py` | Liveness from a host that is not the VPS |

The restore is the part that matters and the easiest to fake. A backup whose restore has
never been run is a file; 22.F4 makes the drill scheduled rather than one-off, which is the
difference between a claim and a procedure. It stores `backups/`, health and repair audit
lines, and the maintenance marker's state — never a credential.

Two planned surfaces, neither wired. The **UPS status read** (on battery, on line, estimated
runtime) would be reported by S31 as a vital rather than acted on here — S22 owns what
happens afterwards, S31 owns the observation (D-13). The **RAID 1 NAS** would be the
destination for the restore drill: mounted, and proven by a restore onto scratch (M32), which
is the only property that distinguishes it from a single disk with two filenames.

### Proposed addition — make the copy checkable, not just present (D-93)

Goal 1 asks for a restore drill that has **not yet run**, because the NAS is not
mounted. The re-review's only candidate scoring above the adopt line, and the one
Jev ranked first, addresses a different half of the same sentence.

**[restic/restic](https://github.com/restic/restic)** (BSD-2, pushed 2026-10-01) —
subprocess adapter over the NAS destination: `restic backup` / `check` /
`restore --target`, driven by the existing `bench/test_backup_restore.py` timer.
One static binary, no daemon, and it runs on the laptop too, so the drill is not
VPS-only.

**This is scoped to the destination and its verification.** It does not replace
`src/mushegh/protocols/backup.py`, which owns the no-clobber guard, and it is not a
second backup system. What it changes is the sentence this document already
makes and cannot yet back: *a mirror is not a backup.* `restic check` turns
"we have a copy" into "the copy is intact".

**It does not unblock M32, and saying so is the point.** M32 needs the NAS
*mounted*. This addition makes the drill worth running once it is; it does not
make the volume appear.

**Gate:** `bench/test_backup_restore.py`, which exists. PRINCIPLES §1 three
commands, in order:

```
restic snapshots
restic check --read-data-subset=5%
journalctl -u openmushegh-brain -n 200 --no-pager | grep -i backup
```

**Not proposed:** litestream, which is the obvious SQLite-replication answer and
would be a separate daemon — bought for a question the owner has not answered.
Run `32.E1` instead. See [INTEGRATIONS.md](../INTEGRATIONS.md) §2 and §6.

## Goals

1. A backup is proven by restoring it, on a schedule, to a scratch copy. Threshold: **≥1**
   restore drill per month, **0** clobbers of live memory.
2. A remote kill stops the edge with SIGTERM, escalates to SIGKILL at 3 s, and leaves
   uncommitted work in a Git stash. Threshold: **0** lost edits, **0** commits made by the
   kill path (D-41).
3. A bad config change is detected and reverted automatically. Threshold: **1** rollback on
   a deliberately broken config, inside **1** brain restart.
4. Every known failure shape has a repair path, and the repair leaves a record.
   Threshold: **1** audit line per repair, **0** silent repairs.
5. Recovery reaches the owner as a summary, not as silence. Threshold: **1** report per
   recovery event, **0** silent recoveries.
6. Corruption in a memory store is detected before a turn reads it, with a repair path that
   is not "delete everything". Threshold: **100%** of corrupt stores detected.
7. A clean machine reaches a working voice loop from the setup script alone, plus a written
   edge audio tuning guide. Threshold: **1** clean machine, **0** undocumented steps
   (D-55, M39).
8. The core rides out a cut on UPS, and the owner is told the box is on battery before the
   battery becomes the problem. Threshold: **1** vital carrying on-battery / on-line /
   estimated-runtime; **0** paths where Mushegh instructs the UPS to cut power (D-13 — the UPS
   cuts on its own battery logic, never on a request).
9. A restore onto scratch from the RAID 1 NAS is legible to `sqlite3`, proving the mirror is
   worth more than a disk failure. Threshold: **≥1** drill per month (M32), **0** clobbers,
   **0** claims that a mirror is a backup.

## Benchmarks

- **G1** · B2 · `bench/test_backup_restore.py` on a scratch copy, run on the weekly timer
  `deploy/vps/live-check.sh` installs. Threshold 0 clobbers, byte-identical roundtrip. Last:
  **not yet measured** — the scheduled restore is a drill, not a test, and no run of it is
  recorded in this repository.
- **G2** · B2 · M36's own drill: kill the edge mid-edit. Threshold 0 lost edits, stash
  present after the kill, SIGKILL at 3 s. It cannot be written until the unit and the
  escalation exist. Last: **not yet measured**.
- **G3** · B1 · `bench/test_setup_wizard.py` extended with the rollback case (22.R1,
  `rollback_drill()`). Threshold 1 automatic revert. Last: **47/47, 2026-10-13**.
- **G4** · B1 · `bench/test_self_repair.py`. Threshold: every repair path leaves an audit
  line. Last: **not yet measured**.
- **G5** · B1 · `bench/test_protocol_drills.py` for the report-not-silence property (22.R3).
  Threshold 1 report per recovery event. Last: **not yet measured**.
- **G6** · B1 · `bench/test_vector_store.py` extended with the corruption case — the named
  case does not exist yet (22.R2). Threshold: a corrupt store is detected before a read.
  Last: **not yet measured**.
- **G7** · B2 · M39's drill: a clean machine, the script alone, a working voice loop, then
  the audio tuning guide. Threshold: **1** clean machine, **0** undocumented steps. No
  script and no guide exist. Last: **not yet measured**.
- **22.E1** · B3 · a blind drill — kill the brain, the edge and the network inside an hour,
  and be back. Threshold: **≤1 h** to a working system, **0** lost edits. Last: **not yet measured**.
- **G8** · B1 · a power-cut drill on the core, reading the UPS vital. Threshold: the brain
  reports on-battery and estimated runtime; shutdown remains the UPS's own decision. **Planned
  gate — no UPS signal exists in the code**, so the drill cannot be written yet. Last:
  **not yet measured**.
- **G9** · B2 · M32's drill: restore from the 2×4 TB RAID 1 NAS onto a scratch target and
  query the result. Threshold: the vault and database come back legible to `sqlite3` (D-54),
  **0** clobbers. Last: **not yet measured** — the NAS is not mounted and no drill has run.

## Failure modes

- **A restore is run over live memory.** `restore_backup` refuses a non-empty target without
  `--force`, which is the guard; a `--force` at 2 AM is the risk. The owner sees a system that
  starts cleanly and has forgotten the last month. Diagnose: the protocol's drill record, and
  `sqlite3 mushegh_tasks.sqlite` for an empty queue.
- **The backup exists and the restore has never run.** The day it is needed, it fails on the
  untested path. Diagnose: `ls -l backups/`, then
  `uv run python -m mushegh.protocols.backup restore backups/<archive>.zip` — into a scratch
  directory, never over the live one.
- **A config change bricks the brain.** The only recovery today is the `.env.bak-<stamp>`
  the wizard wrote, plus a hand edit — that is 22.R1, and it is open. Diagnose:
  `journalctl -u mushegh-brain -n 200 --no-pager`, then `ls .env.bak-*`.
- **The kill loses an edit.** Not currently possible, because the kill path does not exist.
  When M36 lands it is diagnosable only by `git stash list` on the edge checkout.
- **The daily freshness restart lands mid-work.** 22.F2 restarts both hosts, and a restart
  at the wrong moment loses an in-flight turn. Diagnose: `journalctl -u mushegh-brain -n 200`,
  and `systemctl status mushegh-brain` for `RestartSec`.
- **Everything is green and the system is still wrong.** Mock-only greens are the standing
  trap (D-43): `bench/test_self_repair.py` proves the repair code agrees with a fake
  transport. Only the live weekly drill answers this, which is why it is a timer.

## Open questions

1. M36 names a unit, `openmushegh-edge`, that does not exist in `deploy/`. Is the kill
   contract a systemd property on the edge service, a script, or both — and does the stash
   get created in the edge's own checkout, which is where the uncommitted edits are?
2. 22.R1 asks for automatic config rollback, and the wizard already writes `.env.bak-<stamp>`
   before overwriting. Is the rollback simply "detect a bad start and restore the last
   backup", and what counts as a bad start?
3. M39 changes who this is for, and its blocker is not code: a reviewer without a second
   machine, a microphone and a quiet room cannot test a voice loop. What is the smallest
   hardware profile an adopter must own for the drill to be honest?

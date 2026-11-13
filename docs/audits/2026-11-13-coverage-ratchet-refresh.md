# Coverage Ratchet Refresh — 2026-11-13

## Summary

The release audit refused to certify mcp-common's coverage claim on
2026-11-13, and the publish was aborted before the version bump:

```
[FAIL] CLAUDE.md claims 90% coverage but ratchet file could not be read
```

`.coverage-ratchet.json` was present and parsed cleanly. The message
was misleading: `_read_ratchet_floor()` returns `None` for a ratchet it
rejects as **stale**, and `_verify_coverage()` reports every `None` as
"could not be read". Two independent defects produced the staleness.

## Defect 1 — `pytest.ini` shadowed the canonical pytest config

`pytest.ini` (added 2026-08-20 in `692b61f`) and the
`[tool.pytest.ini_options]` table in `pyproject.toml` both existed.
pytest's config discovery order gives `pytest.ini` **higher** priority
than `pyproject.toml`, so the entire `pyproject.toml` table was dead:

| Flag | Intended source | Effective? |
|------|-----------------|------------|
| `--cov=mcp_common` | `pyproject.toml` | no — no coverage collected |
| `--cov-report=json` | `pyproject.toml` | no — no `coverage.json` written |
| `--cov-fail-under=86.42…` | `pyproject.toml` | no — floor never enforced |
| `--strict-markers`, `--strict-config` | `pyproject.toml` | no |
| `filterwarnings` | `pyproject.toml` | no |

Only `crackerjack`'s own pytest invocation ever collected coverage,
because `crackerjack/managers/test_command_builder.py` passes `--cov=`
explicitly rather than relying on `addopts`. That is why the repo's
own `pytest` runs produced no `coverage.json` while the ratchet kept
referring to one.

**Fix**: `pytest.ini` deleted. Its two settings that `pyproject.toml`
did not already carry — `pythonpath = .` and a `-v` in `addopts` — were
handled separately: `pythonpath` moved into
`[tool.pytest.ini_options]` as `pythonpath = ["."]`, and the `-v` was
dropped, because it is a display flag and the crackerjack-generated
`pyproject.toml` template does not set it. `pyproject.toml` is the
canonical config — `crackerjack`'s `mirror_to_pyproject` writes
`--cov-fail-under` there, so the value has to live there to mean
anything.

## Defect 2 — the ratchet's freshness clock only advanced on improvement

`crackerjack/services/coverage_ratchet.py` writes `.coverage-ratchet.json`
on three paths: `initialize_baseline`, `_update_baseline` (the
*improved* path) and `lower_baseline`. `update_coverage()` returns
early on the **maintained** path — coverage flat or within the 2.0pp
tolerance margin — without touching the file. So `generated_at` never
advanced while the baseline was flat, and the ratchet aged out of the
30-day `RATCHET_MAX_AGE_DAYS` window purely by the passage of time.

The recorded ratchet was written `2026-10-14T10:02:23` and rejected
`2026-11-13` — 30 days and 3 hours later.

The same gap has a second edge. `coverage.json` is rewritten by every
coverage run, so its mtime moves. `_is_ratchet_stale()` compares that
mtime against the `coverage_data_mtime` recorded in the ratchet and
treats a mismatch as stale. A ratchet that is not rewritten therefore
also goes **data-stale** the next time the test suite runs — even
inside the 30-day window.

> **This defect lives in crackerjack, not in mcp-common.** It is
> recorded here because it is the reason this ratchet expired, and it
> bit every repo whose coverage was flat between releases. The fix is in
> crackerjack, in the same change set — see *Recurrence risk* below.

## Measured coverage

With the consolidated config, a full run of the suite measures:

```
Required test coverage of 95.57730650715969% reached. Total coverage: 95.58%
2327 passed, 20 skipped
```

- **4305** statements, **4142** covered → **96.19%** line coverage
- **1212** branches, **1131** covered → **93.32%** branch coverage
- Combined `totals.percent_covered` — the number the ratchet tracks —
  is **95.57730650715969%**

The previous floor of `86.42358417377812` was set on 2026-10-14 from a
measurement that cannot be reproduced today. The coverage configuration
has not changed since — `[tool.coverage.run]` is byte-identical to the
2026-10-14 tree — and measuring without the omit list gives 95.67%, not
86.42%, so the gap is not in the configuration. Whatever produced the
lower number that day (a lossy measurement is the likeliest candidate,
since `parallel = true` splits the data across per-process files), the
floor sat ~9pp below the truth and the ratchet could never climb to it.
Today's measurement is the one the ratchet now records.

## Changes

1. `pytest.ini` deleted; `pythonpath = ["."]` added to
   `[tool.pytest.ini_options]`.
1. `.coverage-ratchet.json` refreshed from the measurement above:
   `baseline` and `current_minimum` are now `95.57730650715969`,
   `generated_at` is current, and `coverage_data_path` /
   `coverage_data_mtime` point at the `coverage.json` the floor was
   derived from.
1. `pyproject.toml --cov-fail-under` raised from
   `86.42358417377812` to `95.57730650715969`. The gate is now live.
1. `CLAUDE.md` coverage claims synchronised to the measurement:
   the "must maintain" policy line now reads **≥96%** (the audit
   compares the claim against the floor and against the measured value
   with a 2.0pp tolerance), and the feature-summary line now reports
   the real line and branch figures.

Per the decision rule in the [2026-09-05 memo](2026-09-05-coverage-ratchet-memo.md),
a ratchet change updates the ratchet file, `pyproject.toml --cov-fail-under` and `CLAUDE.md` together, and the release audit
verifies the three agree.

## Recurrence risk, and the crackerjack half of the fix

The changes above restore the publish gate, but on their own they do
not make the ratchet self-refreshing. Because crackerjack only rewrote
the ratchet on the *improved* path, the next coverage run in this repo
would measure the same `95.57730650715969` and take the **maintained**
path:

- `generated_at` would not advance, so the ratchet would go time-stale
  again after 30 days.
- `coverage_data_mtime` would not advance, so the ratchet would go
  data-stale as soon as the suite ran again.

The durable half of the fix therefore lives in crackerjack, and was
applied in the same change set:

- `crackerjack/services/coverage_ratchet.py` — `_refresh_freshness()`
  rewrites the staleness metadata whenever `coverage.json` has been
  re-measured since the last write. It runs on the *maintained* and
  *regression* paths; the *improved* path already refreshed the
  metadata through `_update_baseline`. The write is skipped when no new
  measurement happened, so a run that does not touch the test suite
  leaves the file alone.
- `crackerjack/checks/release_audit.py` — a stale ratchet is now
  reported as *stale*, with the remedy, instead of reusing the
  "could not be read" message that a genuinely missing file gets.
  Reporting a present, readable file as unreadable is what sent the
  2026-11-13 diagnosis down the wrong path.

With both halves in place, a coverage run refreshes the ratchet and the
publish gate that follows it sees a current, data-matching ratchet.

## Verification

```bash
cd /Users/les/Projects/mcp-common
.venv/bin/python -m pytest tests/ -q   # floor now enforced; 2327 passed, 20 skipped

# The release audit the publish manager runs:
python /path/to/crackerjack/crackerjack/checks/release_audit.py \
  --project-root . --changelog CHANGELOG.md --claude-md CLAUDE.md \
  --pyproject pyproject.toml --ratchet .coverage-ratchet.json \
  --source-root mcp_common --test-root tests
```

The audit has no standalone `crackerjack` subcommand; it runs from
`crackerjack/managers/publish_manager.py:_validate_release_audit()` and
from the module's own `__main__` entry point. The two use the same
`check_release_audit()` call with the same arguments.

# Migration Guide

This document covers changes when upgrading to the Elite Controller version.

## Config Changes

### New Configuration Options

```python
# New in ControllerConfig
policy_mode: Literal["off", "bandit"] = "off"
planner_mode: Literal["off", "dag"] = "off"
repo_index_mode: Literal["off", "on"] = "off"
seed: int = 1337
network_access: bool = False
```

### CLI Flag Changes

| Old Flag | New Flag | Notes |
|----------|----------|-------|
| (none) | `--policy-mode` | `off` or `bandit` |
| (none) | `--planner-mode` | `off` or `dag` |
| (none) | `--repo-index` | Enable repo indexing |
| (none) | `--seed` | Deterministic seed |
| (none) | `--learning-db` | SQLite path for learning |
| (none) | `--no-eval` | Skip final evaluation |

---

## New Subcommands

### `rfsn plan`

Generate a plan without execution:

```bash
rfsn plan --repo https://... --problem "Description" --out plan.json
```

### `rfsn eval`

Run evaluation only:

```bash
rfsn eval --repo https://... --test "pytest -q"
```

---

## Output Structure Changes

### New Output Files

```
.rfsn/
├── events.jsonl    # Structured event log
├── plan.json       # Execution plan (if planner enabled)
├── eval.json       # Evaluation results
└── index.json      # Repo index (if indexing enabled)
```

---

## Breaking Changes

1. **ControllerContext Required**: Components now receive a `ControllerContext` instead of individual arguments.

2. **Event Logging**: All actions now emit structured events to `events.jsonl`.

3. **Determinism**: Default seed is 1337; set `--seed` for different runs.

---

## Backwards Compatibility

The default behavior without new flags matches the previous version:

- `policy_mode=off`
- `planner_mode=off`
- `repo_index_mode=off`

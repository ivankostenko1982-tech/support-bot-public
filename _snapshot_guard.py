from __future__ import annotations
import hashlib, logging, os, sys

log = logging.getLogger("support-join-guard")

def _read_file(path: str) -> str | None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return None

def _sha256_of(path: str) -> tuple[str, int]:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        data = f.read()
    h.update(data)
    return h.hexdigest(), len(data)

def enforce_snapshot(app_file: str, meta_dir: str = "/opt/tgbots/utils/snapshots") -> None:
    """Жёсткая проверка: app.py должен совпадать со снапшотом (sha256+size)."""
    enforce = (os.getenv("SNAPSHOT_ENFORCE", "1").lower() in {"1", "true", "yes", "on"})
    allow_miss = (os.getenv("SNAPSHOT_ALLOW_MISS", "0").lower() in {"1","true","yes","on"})
    exp_sha_path = os.path.join(meta_dir, "base.sha256")
    exp_sz_path  = os.path.join(meta_dir, "base.size")
    exp_sha = _read_file(exp_sha_path)
    exp_sz  = _read_file(exp_sz_path)
    cur_sha, cur_sz = _sha256_of(app_file)

    if not exp_sha or not exp_sz:
        msg = f"SNAPSHOT: baseline missing: {exp_sha_path} or {exp_sz_path}; current sha={cur_sha} size={cur_sz}"
        if enforce and not allow_miss:
            log.error(msg + " (enforce=on) — refusing to start")
            raise SystemExit(3)
        else:
            log.warning(msg + " (enforce=off or allow_miss=on) — continuing")
            return

    try:
        exp_sz_int = int(exp_sz)
    except Exception:
        exp_sz_int = -1

    if cur_sha != exp_sha or cur_sz != exp_sz_int:
        msg = (f"SNAPSHOT MISMATCH: sha {cur_sha}!={exp_sha} or size {cur_sz}!={exp_sz_int}; "
               f"edit app via snapshot only; see /opt/tgbots/utils/snapshots/")
        if enforce:
            log.error(msg + " — refusing to start")
            raise SystemExit(3)
        else:
            log.warning(msg + " — continuing due to SNAPSHOT_ENFORCE=0")
    else:
        log.info("SNAPSHOT OK: sha=%s size=%s", cur_sha, cur_sz)

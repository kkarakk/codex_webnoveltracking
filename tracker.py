import sqlite3
import re
import time
import os
import shutil
import tempfile
import argparse
import json
from datetime import datetime

### CONFIG ###
SAFARI_HISTORY = os.environ.get("SAFARI_HISTORY", os.path.expanduser("~/Library/Safari/History.db"))
STATE_DB = "reading_state.db"

NOVEL_SITES = [
    "webnovel",
    "wuxiaworld",
    "lightnovelpub",
    "novelfull",
    "novelupdates",
    "wanderinginn.com",
]

# site substring -> canonical novel mapping
SITE_CANONICAL = {
    "wanderinginn": "The Wandering Inn",
}

DECIMAL_REGEX = re.compile(r"\b(\d+\.\d+)\b")
CHAPTER_REGEX = re.compile(r"(?:chapter|ch\.?|ch)\s*(\d+(?:\.\d+)?)", re.I)
INT_FALLBACK = re.compile(r"\b(\d{1,3})\b")

APPLE_EPOCH_OFFSET = 978307200  # Apple → Unix
LOOKBACK_DAYS = 14
MAX_ENTRIES = 5000
CHECKPOINT_KEY = "last_processed_apple_time"
CHECKPOINT_OVERLAP_SECONDS = 2 * 3600


def apple_to_unix(t):
    return t + APPLE_EPOCH_OFFSET


def extract_chapter(text):
    if not text:
        return None

    # try decimal first (10.51)
    m = DECIMAL_REGEX.search(text)
    if m:
        try:
            return float(m.group(1))
        except Exception:
            pass

    # explicit 'chapter' patterns
    m = CHAPTER_REGEX.search(text)
    if m:
        try:
            val = m.group(1)
            return float(val) if '.' in val else int(val)
        except Exception:
            pass

    # fallback: any small integer but skip 4-digit years
    m = INT_FALLBACK.search(text)
    if m:
        val = int(m.group(1))
        if 1000 <= val <= 9999:
            return None
        return val

    return None


def is_novel_url(url):
    if not url:
        return False
    u = url.lower()
    for s in NOVEL_SITES:
        if s in u:
            return True
    return False


def fetch_history(history_path=None, since_apple_time=None):
    """Copy Safari history DB to a temp file and read recent novel visits.

    Returns a list of events: {url, title, chapter, visited_at}
    """
    history_path = history_path or SAFARI_HISTORY
    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(prefix="History.", suffix=".db")
        os.close(fd)

        try:
            shutil.copy2(history_path, tmp_path)
        except PermissionError as e:
            raise PermissionError(
                f"Permission error copying Safari history: {e}.\n"
                "If this is macOS, grant Full Disk Access to your shell or pass a copied DB with --history."
            )

        conn = sqlite3.connect(tmp_path)
        cur = conn.cursor()

        cutoff = time.time() - (LOOKBACK_DAYS * 86400)
        apple_cutoff = cutoff - APPLE_EPOCH_OFFSET
        if since_apple_time is not None:
            apple_cutoff = max(apple_cutoff, since_apple_time)

        cur.execute(
            """
            SELECT hi.url, hv.title, hv.visit_time
            FROM history_items hi
            JOIN history_visits hv ON hv.history_item = hi.id
            WHERE hv.visit_time > ?
            ORDER BY hv.visit_time DESC
            LIMIT ?
            """,
            (apple_cutoff, MAX_ENTRIES),
        )

        rows = cur.fetchall()
        conn.close()

        max_visit_time = rows[0][2] if rows else None
        events = []
        for url, title, vt in rows:
            if not is_novel_url(url):
                continue

            # prefer extracting chapter from title first (less likely to pick year)
            chapter = extract_chapter(title) or extract_chapter(url)

            events.append({
                "url": url,
                "title": title,
                "chapter": chapter,
                "visited_at": datetime.fromtimestamp(apple_to_unix(vt)).isoformat(),
            })

        return events, max_visit_time

    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


def init_state_db():
    conn = sqlite3.connect(STATE_DB)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS reading_progress (
            novel TEXT PRIMARY KEY,
            last_chapter REAL,
            last_read_at TEXT,
            confidence REAL,
            url TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS tracker_state (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    # Ensure older DBs get the new `url` column if missing
    cur.execute("PRAGMA table_info(reading_progress)")
    cols = [r[1] for r in cur.fetchall()]
    if "url" not in cols:
        try:
            cur.execute("ALTER TABLE reading_progress ADD COLUMN url TEXT")
        except Exception:
            # ignore if unable to alter
            pass

    conn.commit()
    conn.close()


def get_checkpoint():
    conn = sqlite3.connect(STATE_DB)
    cur = conn.cursor()
    cur.execute("SELECT value FROM tracker_state WHERE key = ?", (CHECKPOINT_KEY,))
    row = cur.fetchone()
    conn.close()
    if not row or row[0] is None:
        return None
    try:
        return float(row[0])
    except Exception:
        return None


def set_checkpoint(value):
    if value is None:
        return
    conn = sqlite3.connect(STATE_DB)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO tracker_state (key, value)
        VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (CHECKPOINT_KEY, str(value)),
    )
    conn.commit()
    conn.close()


def naive_infer(events):
    """Group events into novels and pick the most recent / highest chapter."""
    buckets = {}

    for e in events:
        if e.get("chapter") is None:
            continue

        url = (e.get("url") or "").lower()
        title = e.get("title") or ""

        # Check canonical mapping
        key = None
        for site_substr, canon in SITE_CANONICAL.items():
            if site_substr in url or site_substr in title.lower():
                key = canon.lower()
                break

        if not key:
            # fallback: take part of the title before the first dash or pipe
            key = (title or "").split("-")[0].split("|")[0].strip().lower()

        if not key:
            continue

        buckets.setdefault(key, []).append(e)

    results = []
    for key, items in buckets.items():
        # sort by chapter then visited_at so last is latest/higher
        items.sort(key=lambda x: (x["chapter"], x["visited_at"]))
        last = items[-1]

        results.append({
            "novel": key.title(),
            "last_chapter": last["chapter"],
            "last_read_at": last["visited_at"],
            "url": last.get("url"),
            "confidence": min(0.5 + 0.05 * len(items), 0.9),
        })

    return results


def update_state(results):
    conn = sqlite3.connect(STATE_DB)
    cur = conn.cursor()

    for r in results:
        cur.execute(
            """
            INSERT INTO reading_progress (novel, last_chapter, last_read_at, confidence, url)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(novel) DO UPDATE SET
                last_chapter = excluded.last_chapter,
                last_read_at = excluded.last_read_at,
                confidence = excluded.confidence,
                url = excluded.url
            WHERE excluded.last_chapter >= reading_progress.last_chapter
            """,
            (
                r["novel"],
                r["last_chapter"],
                r["last_read_at"],
                r["confidence"],
                r.get("url"),
            ),
        )

    conn.commit()
    conn.close()


def run(history_path=None, dry_run=False):
    init_state_db()
    checkpoint = get_checkpoint()
    since_apple_time = None
    if checkpoint is not None:
        since_apple_time = max(0, checkpoint - CHECKPOINT_OVERLAP_SECONDS)
    events, max_visit_time = fetch_history(history_path, since_apple_time=since_apple_time)
    inferred = naive_infer(events)

    if dry_run:
        print(json.dumps(inferred, indent=2))
        return inferred

    update_state(inferred)
    set_checkpoint(max_visit_time)
    print(f"Wrote {len(inferred)} entries to {STATE_DB}")
    return inferred


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--history", help="Path to a copy of Safari History.db (avoid TCC)")
    p.add_argument("--dry-run", action="store_true", help="Print inferred results without writing DB")
    args = p.parse_args()

    try:
        run(history_path=args.history, dry_run=args.dry_run)
    except PermissionError as e:
        print(str(e))


if __name__ == "__main__":
    main()

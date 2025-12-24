# Web Novel Tracker

Track your web novel reading progress by parsing recent Safari history, extracting chapter numbers, and storing the latest chapter per novel in a local SQLite database. Includes a minimal Streamlit dashboard for viewing progress.

## What it does
- Reads Safari `History.db` (or a copied path you provide)
- Filters visits to known novel sites
- Extracts chapter numbers from titles/URLs
- Saves the latest chapter per novel into `reading_state.db`
- (Optional) Displays the data in a Streamlit dashboard

## Requirements
- Python 3.9+
- macOS (Safari history parsing)

Install dependencies:

```bash
python3 -m pip install -r requirements.txt
```

## Usage

Update the local database from Safari history:

```bash
python3 tracker.py
```

Dry run (prints inferred results without writing):

```bash
python3 tracker.py --dry-run
```

If you need to avoid macOS Full Disk Access prompts, copy Safari History.db and point to it:

```bash
python3 tracker.py --history /path/to/History.db
```

## Dashboard

Run the Streamlit dashboard:

```bash
python3 -m streamlit run dashboard.py
```

## Notes
- The tracker maintains a checkpoint so each run only scans new history (with a small overlap buffer).
- The database is stored in `reading_state.db` in the project directory.

## Planned
- macOS background service (LaunchAgent or menu bar app) that updates the DB on a schedule
- Notifications for new chapters or long-stale novels
- Cross-platform support (Linux/Windows) via shared core logic and platform-specific schedulers

## License

No license specified.

# Notes

## UX ideas
- Menu bar app showing last read + stalled count.
- Click-through to open the latest URL for a novel.
- Optional notifications for new chapters or long-stale reads.

## Technical ideas
- macOS LaunchAgent for scheduled background runs.
- Shared core module for cross-platform schedulers (systemd/Task Scheduler).
- Store DB in Application Support for a packaged app.

## Open questions
- Refresh interval target (e.g., 15/30/60 min).
- Preferred UI: menu bar app vs notifications-only.
- Whether to support non-Safari browsers.

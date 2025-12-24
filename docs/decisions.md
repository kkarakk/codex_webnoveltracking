# Decisions

- Keep core logic in Python for easy reuse across macOS/Linux/Windows.
- Use SQLite (`reading_state.db`) as the local source of truth.
- Extract chapters from Safari history titles/URLs and store per-novel progress.
- Add checkpointing to avoid scanning all history each run.
- Provide a minimal Streamlit dashboard for quick visualization.

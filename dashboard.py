# Minimal Streamlit dashboard for reading_state.db

import sqlite3
from datetime import datetime
import streamlit as st
import pandas as pd

DB = "reading_state.db"


def _parse_iso_datetime(ts: str):
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts)
    except Exception:
        return None
    if getattr(dt, "tzinfo", None) is not None:
        try:
            dt = dt.astimezone().replace(tzinfo=None)
        except Exception:
            pass
    return dt


def _fetch_rows():
    try:
        with sqlite3.connect(DB) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT novel, last_chapter, last_read_at, confidence, url
                FROM reading_progress
                ORDER BY last_read_at DESC
                """
            )
            return cur.fetchall()
    except sqlite3.OperationalError:
        st.warning("Reading database or table not found. Run the tracker first to populate data.")
        st.stop()
    except Exception as e:
        st.error(f"Unable to open database '{DB}': {e}")
        st.stop()


st.set_page_config(page_title="Web Novel Reading Dashboard", layout="wide")
st.title("📚 Web Novel Reading Dashboard")


rows = _fetch_rows()
if not rows:
    st.info("No reading data yet.")
    st.stop()

now = datetime.now()

records = []
for n, ch, ts, c, url in rows:
    last = _parse_iso_datetime(ts)
    stale = (now - last).days if last else None
    records.append({
        "Novel": n,
        "Last Chapter": ch,
        "Last Read": last.strftime("%Y-%m-%d") if last else "Unknown",
        "Days Ago": stale,
        "Confidence": round(c, 2) if isinstance(c, (int, float)) else None,
        "url": url,
    })

# Build a DataFrame for consistent rendering
df = pd.DataFrame.from_records(records, columns=["Novel", "Last Chapter", "Last Read", "Days Ago", "Confidence", "url"])

# Currently Reading
def _html_table(df, title=None):
    # Build a simple HTML table with clickable novel links and basic styling
    cols = ["Novel", "Last Chapter", "Last Read", "Days Ago", "Confidence"]
    html = []
    if title:
        html.append(f"<h3>{title}</h3>")
    html.append("<table style='border-collapse: collapse; width: 100%;'>")
    # header
    html.append("<thead><tr>")
    for c in cols:
        html.append(f"<th style='text-align:left; border-bottom:1px solid #ddd; padding:8px'>{c}</th>")
    html.append("</tr></thead>")
    # body
    html.append("<tbody>")
    for _, r in df[cols].iterrows():
        novel = r['Novel']
        # find URL from original df records
        try:
            url = df.loc[(df['Novel'] == novel), 'url'].iloc[0]
        except Exception:
            url = None
        if url:
            novel_html = f"<a href=\"{url}\" target=\"_blank\">{novel}</a>"
        else:
            novel_html = novel
        html.append("<tr>")
        html.append(f"<td style='padding:8px; border-bottom:1px solid #f3f3f3'>{novel_html}</td>")
        html.append(f"<td style='padding:8px; border-bottom:1px solid #f3f3f3'>{r['Last Chapter']}</td>")
        html.append(f"<td style='padding:8px; border-bottom:1px solid #f3f3f3'>{r['Last Read']}</td>")
        html.append(f"<td style='padding:8px; border-bottom:1px solid #f3f3f3'>{r['Days Ago'] or ''}</td>")
        html.append(f"<td style='padding:8px; border-bottom:1px solid #f3f3f3'>{r['Confidence'] or ''}</td>")
        html.append("</tr>")
    html.append("</tbody>")
    html.append("</table>")
    return "\n".join(html)


st.subheader("Currently Reading")
st.markdown(_html_table(df), unsafe_allow_html=True)

# Stalled (>7 days)
st.subheader("Stalled (>7 days)")
st.markdown(_html_table(df[df["Days Ago"] > 7]), unsafe_allow_html=True)

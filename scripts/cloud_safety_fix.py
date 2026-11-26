"""Non-destructively replace the old missing-data error with an explanation.
Also corrects diagnostic duplicate count expression. Run from project root.
"""
from pathlib import Path

page = Path('pages/1_Historical_Market_Behaviour.py')
if not page.is_file():
    raise SystemExit('Run from existing repository root; page not found.')
original = page.read_text(encoding='utf-8')
updated = original.replace(
    'st.error("Missing local data files:\\n" + "\\n".join(missing))',
    'st.info("Local licensed research data are not installed on this machine. "'
    '        "The public app contains a synthetic demo; historical research is local-only. "'
    '        "Missing paths: " + ", ".join(missing))',
)
# Earlier diagnostic deletes timestamp conflicts as whole timestamp groups; this
# simplified expression must not subtract conflict groups from removed row counts.
updated = updated.replace(
    'original_rows\n            - len(group)\n            - conflicting_times',
    'original_rows\n            - len(group)'
)
if updated == original:
    print('No expected patterns found; current page unchanged (inspect manually).')
else:
    page.write_text(updated, encoding='utf-8')
    print('Updated existing page. Inspect git diff before committing.')

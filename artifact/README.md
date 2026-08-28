# Published artifacts

Source for the pages published to claude.ai. They were written to a session scratchpad,
which does not survive the session — so the source lives here and the scratchpad copy is
the throwaway, not the other way round.

| file | published at | favicon |
|---|---|---|
| `battlegrid-defects.html` | https://claude.ai/code/artifact/a0ed53c1-f6d3-4abf-9225-c4abf3dfd71a | 🐛 |
| `column-algebra.html` | https://claude.ai/code/artifact/877253ff-b200-4592-9500-c35c21f0f513 | 🧮 |
| `indicator-census.html` | https://claude.ai/code/artifact/e6be5c58-9e11-4d4b-a43e-3c41ab640163 | |
| `matrix.html` | built from `matrix.template.html` | |

To update one, edit the file here and republish it to **the same URL** — publishing
without the URL creates a second artifact instead of updating the first.

Record the **favicon** in the table above whenever you publish. It has to stay stable
across redeploys — readers find the tab by its icon — and it is not readable back from
the published page, so an unrecorded one is a guess on the next update. The blanks are
exactly that: published before this column existed, and not verified since.

`battlegrid-defects.html` is the report for the BattleGrid maintainer: fourteen findings,
each with a reproduction, a workaround where one exists, and a suggested fix. BG-14 and
the BAR_FORMING closure of BG-13 landed 2026-08-28; the page was republished to the same
URL with the same 🐛 favicon that day. Later the same day the measurement campaign added
BG-14's measured boundary (ranked limit 4, exact bracket, concave byte curve) to the
article and triage row, and the page was republished again — same URL, same favicon.

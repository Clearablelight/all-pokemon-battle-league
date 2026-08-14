# Roster decision catalog scope

`roster-decisions.csv` is a checked-in starter/audit fixture. It intentionally
covers only the named edge cases used by the roster-builder contract tests; it
does not assert full roster coverage or the final form count.

Task 6 must expand this catalog from verified, pinned source-form rows before
any cutoff roster export can pass its coverage checks. The builder remains
fail-closed: every source-form row supplied to it must have exactly one
decision, and every decision must resolve to exactly one supplied source row.

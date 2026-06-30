# Legal Project Hours and Litigation Numbering

## Scope

This implementation applies only to `qlk_management` and the legal project model
`qlk.project`. It does not modify standard Odoo modules or existing project/task
record rules.

## Hour ledger

The project hour dashboard is calculated from non-overlapping sources:

- Timesheet hours: the effective hours of `project.task` records linked to the
  legal project.
- Legal task hours: `qlk.task.hours_spent` while the task is not rejected.
- Manual adjustment: an audited offset maintained only through the manager
  adjustment wizard.

The stored KPIs are Planned, Consumed, Remaining, Approved, Over Agreement, and
Progress. Approved Hours (Month) is computed dynamically for the current month.
Remaining is `Planned - Consumed`; Over Agreement is
`max(Consumed - Planned, 0)`.

Manual consumed-hour changes require a reason and produce both an immutable
manual audit entry and a source-tagged hour tracking entry. Planned, Consumed,
and Approved changes are tracked with before/after/difference, user, datetime,
and source.

## Agreement synchronization

New legal projects require a client-approved `bd.engagement.letter`. The project
creation flow copies the client, client file, service and contract data, lawyers,
responsible users, currency, dates, scope, description, agreement hours, and
allowed litigation degrees. Changing the agreement uses an explicit Yes/No
reload wizard. A project cannot be moved to another client or client file because
that would invalidate existing legal numbering.

## Litigation numbering

Project numbers use a transaction advisory lock and a client-file-local SQL
maximum. The litigation degree is not part of the project number:

- Projects: `L-109/1`, `L-109/2`, `L-109/3`
- Cases: `L-109/1/F`, `L-109/1/A`, `L-109/1/E`

Case degrees are validated before persistence and must exist in both the project
and its selected agreement.

## Compatibility and data safety

Legacy project and case codes are not rewritten. Corporate and Arbitration
number formats are unchanged. No migration deletes or updates business records;
only stored computed KPI values are recalculated when the module is upgraded.

## Verification

The module was upgraded and tested on an isolated clone of the `alhadhri`
database. The complete `qlk_management` suite completed with 30 tests executed,
0 failures, and 0 errors. The original database was not upgraded or written to.

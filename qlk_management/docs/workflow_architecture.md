# QLK Legal Workflow Architecture

## Workflow

Quotation / Proposal -> Engagement Letter -> Client File -> QLK Project -> Legal Services -> Tasks -> Timesheets.

The Engagement Letter no longer creates projects or legal services directly. After client approval, the user creates or opens the Client File. The Client File is the client hub. From there, managers create the QLK Project. Legal services are created only from the project buttons:

- Create Litigation
- Create Pre-Litigation
- Create Corporate
- Create Arbitration

The project buttons are visible only when the linked Engagement Letter/Project legal service tags allow that service.

## Data Transfer

Creating a project from a Client File copies the latest approved Engagement Letter without an existing project. The transfer includes:

- Client, phone, email, address through the partner and project fields.
- Contact persons from assigned lawyers.
- Legal service types.
- Planned/agreed/allocated hours.
- Billing type, currency, contract type, retainer type.
- Start/end dates.
- Lawyer and responsible users.
- Description, scope, notes, contract terms, payment terms.
- Client, signed, and translation attachments.
- Litigation degree configuration.

Project names use the independent `qlk.project` sequence, for example `PRJ-0001`.

## Hours

`qlk.project` is the central hour aggregation point.

Planned Hours come from the Engagement Letter when the project is created. Consumed Hours are aggregated from:

- Litigation case hours.
- Pre-litigation hours.
- Corporate approved hours.
- Arbitration approved hours.
- Approved `qlk.task` hours.
- Standard Odoo project task effective hours/timesheets.
- Manual consumed hours when an adjustment is needed.

Remaining Hours = Planned Hours - Consumed Hours.

When remaining hours become negative, the project switches to `danger`, shows a warning banner, computes Overconsumed Hours, posts a chatter notification, and schedules manager/responsible-user activities.

## Models And Relationships

- `bd.engagement.letter`: commercial contract source; keeps service tags and client-file link.
- `qlk.client.file`: client hub; owns agreements, projects, attachments, and aggregate hour totals.
- `qlk.project`: operational hub; owns legal services, tasks, dashboard counters, hours, and reports.
- `qlk.case`: litigation service linked by `project_id`.
- `qlk.pre.litigation`: pre-litigation service linked by `project_id`.
- `qlk.corporate.case`: corporate service linked by `project_id`.
- `qlk.arbitration.case`: arbitration service linked by `project_id`.
- `qlk.task`: legal task/hour entry linked to project, client, and optional service record.
- `project.task`: timesheet task linked to litigation cases and surfaced in project hours.

## Security

The module defines Client File and Project User/Manager groups in addition to the existing Pre-Litigation, Corporate, Arbitration, and Task groups.

User rules are assignment-based:

- Direct lawyer user.
- Lawyer on the many2many lawyer list.
- Project responsible users.
- Record creator where relevant.

Manager rules allow all records in the manager scope/company. Menu visibility follows the assigned groups.

## Smart Buttons And Dashboard

Project smart buttons open related litigation, pre-litigation, corporate, arbitration, tasks, and timesheets. The dashboard shows planned, consumed, remaining, total tasks, case counts, hearings, memos, and recent chatter activity.

## Automations

Automations run on project creation, legal-service creation, task assignment, task approval, and hour-threshold changes. Notifications use chatter plus mail activities where a responsible user is available.

# Project and Task Restricted Access

## Scope

This module adds project-level security for `project.project` and task-level security for `project.task`.
The rules are enforced with Odoo record rules for users in `qlk_management.group_project_restricted_user`.

## Access Scenarios

1. Project manager access:
   - Set `project.user_id` to Ahmed.
   - Add Ahmed to `Project Restricted User`.
   - Ahmed can see the project because he is the project manager.

2. Authorized user access:
   - Add Mohammed to `Authorized Users`.
   - Add Mohammed to `Project Restricted User`.
   - Mohammed can see the project and tasks under the project.

3. Creator access:
   - Sara creates a project.
   - Add Sara to `Project Restricted User`.
   - Sara can see the project even if she is not in `Authorized Users`.

4. Unauthorized user denial:
   - Ali is in `Project Restricted User`.
   - Ali is not the project manager, not in `Authorized Users`, and did not create the project.
   - Ali cannot see the project in kanban, list, search, reports, or direct URLs.

5. Task assignee access:
   - Assign a task to Ali through `user_ids` or the primary `user_id`.
   - Add Ali to `Project Restricted User`.
   - Ali can see that task.

6. Project-authorized task access:
   - Add Sara to the parent project's `Authorized Users`.
   - Add Sara to `Project Restricted User`.
   - Sara can see tasks under that project.

7. Manager access:
   - Users in Project Manager, BD Manager, Engagement Manager, Task Manager, or System Administrator groups can see all projects and tasks.

## Multi-Company Review

Restricted user rules include `company_id = False OR company_id in company_ids`.
Managers and system administrators retain unrestricted project/task visibility through manager record rules.

## Notes

Runtime filtering is handled by record rules only. No migration updates existing business records or backfills existing projects.

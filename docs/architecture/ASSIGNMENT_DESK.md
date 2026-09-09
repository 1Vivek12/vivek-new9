# Assignment Desk Architecture

## Overview
The Assignment Desk provides the initial boundary for task delegation, beat tracking, and editorial work orders in the newsroom. It allows editors to direct reporting efforts and reporters/creators to track their queue.

## Assignment Model (`assignments` table)
- **Fields**:
  - `id`: UUID (Primary Key)
  - `tenant_id`: UUID (Foreign Key -> `tenants.id`, indexed)
  - `title`: String(255)
  - `description`: Text (Task brief and reporting directions)
  - `priority`: PriorityEnum (`LOW`, `MEDIUM`, `HIGH`, `URGENT`)
  - `status`: AssignmentStatusEnum (`PENDING`, `ASSIGNED`, `IN_PROGRESS`, `COMPLETED`, `CANCELLED`)
  - `assigned_to_user_id`: UUID (Foreign Key -> `users.id`, optional assignee)
  - `created_by_user_id`: UUID (Foreign Key -> `users.id`, creator)
  - `due_date`: DateTime(timezone=True)
  - `created_at` / `updated_at`: DateTime(timezone=True)
- **Indexes**:
  - `(tenant_id, status)`
  - `(tenant_id, assigned_to_user_id)`
  - `(tenant_id, due_date)`

## Assignment Lifecycle
1. **Creation**: Editor or admin creates an assignment with instructions, priority, and optional due date (`PENDING`).
2. **Assignment**: Assignment is delegated to an editorial team member (`ASSIGNED`).
3. **Execution**: Assignee begins investigation and research (`IN_PROGRESS`).
4. **Story Linking**: A `Story` is created with `assignment_id` linking back to the originating assignment desk task.
5. **Completion / Cancellation**: When the work is fulfilled, status transitions to `COMPLETED`. If abandoned, transitions to `CANCELLED`.

## Tenant Isolation Boundary
- Assignments are strictly tenant-scoped.
- Editors and reporters cannot view or receive assignments across tenants.
- An assignment can only be assigned to a user who has verified membership in that specific tenant.

## Deferred Capabilities
- Automated task allocation or algorithmic scheduling.
- External calendar or email integrations.
- Time-tracking and billing modules.

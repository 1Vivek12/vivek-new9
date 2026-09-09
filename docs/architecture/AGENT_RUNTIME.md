# Agent Runtime Architecture & Security Boundary

## 1. Overview & Abstraction

The `AgentRuntime` provides an isolated abstraction layer separating platform business logic from agent orchestration engines (such as Prime Agent, AutoGen, LangGraph, or custom loops).

```text
+-------------------------------------------------------------+
|                      FastAPI Services                       |
+------------------------------+------------------------------+
                               |
                               | (Calls abstract interface)
                               v
+-------------------------------------------------------------+
|                     AgentRuntime (Protocol)                 |
|  - start_session(tenant_id, user_id, config) -> session_id  |
|  - run_task(session_id, task_spec) -> task_handle           |
|  - resume_task(task_id, input_data)                         |
|  - stop_task(task_id)                                       |
|  - inspect_task(task_id) -> TaskStatus                      |
|  - health_check() -> bool                                   |
+------------------------------+------------------------------+
                               |
                               v
+-------------------------------------------------------------+
|                     PrimeAgentRuntime                       |
|   Status: PENDING_VERIFICATION (Non-executing in Phase 1)   |
+-------------------------------------------------------------+
```

---

## 2. Distinction Between Isolation Levels

To avoid false claims of security, the platform strictly delineates three distinct isolation paradigms:

### A. Architectural Isolation (Implemented in Phase 1)
- Code-level separation via abstract Python classes/protocols.
- Business logic never imports or directly couples to third-party agent internals.
- Clean request/response boundaries and typed task specifications.
- **What it prevents**: Tight coupling, vendor lock-in, and unauthorized direct method calls.
- **What it DOES NOT prevent**: Host compromise if an untrusted agent runs in the same OS process.

### B. Process Isolation (Future Target: Containerized Worker)
- Executing the agent runtime in a dedicated operating system process or non-root container with limited user permissions (`uid 10001`).
- Separate memory spaces and dedicated Unix domain sockets or internal RPC.
- **What it prevents**: Direct memory inspection, accidental crash of the primary API server.
- **What it DOES NOT prevent**: Kernel-level privilege escalation or local network scans if the container is unhardened.

### C. Actual Security Sandboxing (Production Target for Arbitrary Code)
- MicroVM (e.g., AWS Firecracker, Kata Containers) or kernel-level virtualization (e.g., Google gVisor / runsc).
- Strict seccomp filters blocking dangerous syscalls (`ptrace`, `bpf`, raw sockets).
- **Mandatory platform rules**:
  - **NO access to Docker socket** (`/var/run/docker.sock`).
  - **NO access to host filesystem**.
  - **NO root privileges**.
  - **NO access to SSH keys, cloud metadata endpoints, or database superuser credentials**.
  - Read-only root filesystem with ephemeral tmpfs.

---

## 3. Current Prime Agent Status

> **Status: PENDING_VERIFICATION (NON-EXECUTING / SAFE)**

Prime Agent runtime integration has not been verified in the local environment. Therefore, in Phase 1, `PrimeAgentRuntime`:
1. Exists solely as an explicit adapter stub conforming to `AgentRuntime`.
2. Explicitly raises `NotImplementedError("Prime Agent runtime execution is pending verification and disabled in Phase 1.")` on any execution attempt.
3. Does **NOT** execute arbitrary shell commands or launch subprocesses.
4. Implements a safe `health_check()` reporting `{"status": "pending_verification", "executable": false}`.

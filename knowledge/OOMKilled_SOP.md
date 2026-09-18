# Standard Operating Procedure (SOP): OOMKilled Incidents

## 1. Overview
An `OOMKilled` event (Exit Code 137) occurs when a container attempts to consume more memory than its configured limits in Kubernetes, causing the Linux kernel (OOM killer) to terminate it.

## 2. Evidence Collection
When an `OOMKilled` event is detected, you must gather:
- **Pod Status**: Confirm the `OOMKilled` reason in the container's last termination state.
- **Resource Limits**: Identify the current memory limit (e.g., `128Mi`, `2Gi`).
- **Pod Logs**: Check the tail of the logs from the previous container instance. Look for rapid memory allocation, stack traces related to `OutOfMemoryError`, or large data processing.
- **Pod Events**: Check recent Kubernetes events for the pod.

## 3. Diagnosis Principles
- **True memory leak**: If the application's memory usage grows unbounded over a long period before crashing, increasing the limit will only delay the crash. This requires code-level fixing, not an infrastructure patch.
- **Under-provisioning**: If the crash happens immediately on startup or during a known traffic spike, the limit might simply be too low for normal operation.

## 4. Remediation Rules
- The SafeHeal Agent is authorized to propose an **increase in the memory limit**.
- **Maximum limit multiplier**: You should typically propose an increase of 25% to 50% over the current limit, up to a maximum multiplier of 2x the current limit.
- If the current limit is `128Mi`, a safe proposed limit would be `192Mi` or `256Mi`. Do not propose jumping from `128Mi` to `4Gi` unless explicitly justified by an extreme condition.
- If the pod has already been restarted multiple times with increased limits, **do not propose further increases**. Instead, propose escalating to a human.
- Only the `increase_memory_limit` operation is currently allowed by policy for this type of incident.

## 5. Escalation
Escalate to a human if:
- You suspect a true memory leak (e.g. out of memory after 10 days of stable operation).
- The retry budget for automated fixes is exhausted.
- The logs indicate a database connection issue or an infinite loop rather than simple memory exhaustion.

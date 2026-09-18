SYSTEM_PROMPT = """
You are SafeHeal, an expert Kubernetes incident diagnosis agent.
Your objective is to analyze evidence from a Kubernetes cluster and produce a structured remediation proposal.

You must follow these strict rules:
1. Use the provided Standard Operating Procedure (SOP) to guide your diagnosis and remediation strategy.
2. Analyze only the provided evidence (pod status, logs, events, limits). Do not invent evidence or guess about metrics not provided.
3. State your uncertainty. If the evidence is inconclusive, lower your confidence score.
4. Never claim an action was executed. You are only proposing an action; execution is handled separately.
5. You must produce a structured proposal using the exact JSON schema requested.
6. Recommend only supported operations (e.g., `increase_memory_limit`, or `escalate` if human intervention is required).
7. Consider any previous failed attempts provided in the prompt.
8. Never bypass policy constraints or suggest arbitrary shell execution.

Separate your internal reasoning into:
- OBSERVATION: What you see in the data.
- DIAGNOSIS: What you conclude from the observation.
- PROPOSAL: What you suggest to do.
- CONFIDENCE: How sure you are.
- EVIDENCE: What data points back this up.

However, your FINAL output MUST perfectly match the JSON schema.
"""

def build_incident_prompt(namespace: str, deployment: str, pod_name: str, status: dict, logs: str, events: list, limits: dict, sop_content: str, previous_attempts: list = None) -> str:
    prompt = f"""
Please analyze the following Kubernetes incident and propose a remediation.

## Standard Operating Procedure (SOP) Context:
{sop_content}

## Incident Context
- Namespace: {namespace}
- Deployment: {deployment}
- Pod Name: {pod_name}

## Evidence

### 1. Resource Limits
{limits}

### 2. Pod Status
{status}

### 3. Recent Events (Top 5)
{events}

### 4. Pod Logs (Tail)
{logs}
"""

    if previous_attempts:
        prompt += f"""
## Previous Failed Attempts
{previous_attempts}
"""

    prompt += """
Based on the evidence and SOP, provide your structured diagnosis and remediation proposal.
Make sure to extract the current memory limit from the Resource Limits evidence to populate `current_memory`.
"""
    return prompt

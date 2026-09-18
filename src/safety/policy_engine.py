import os
import yaml
import logging
from typing import Tuple, Dict, Any
try:
    from agent.schemas import RemediationProposal
except ImportError:
    from src.agent.schemas import RemediationProposal

logger = logging.getLogger(__name__)

CONFIG_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'policy_rules.yaml'))

def load_policy() -> Dict[str, Any]:
    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(f"Policy configuration not found at {CONFIG_PATH}")
    with open(CONFIG_PATH, 'r') as f:
        return yaml.safe_load(f)

def parse_memory(memory_str: str) -> float:
    """
    Parses a Kubernetes memory string (e.g., '128Mi', '1Gi') into megabytes for comparison.
    """
    if not memory_str:
        return 0.0
    
    memory_str = memory_str.strip()
    if memory_str.endswith("Mi"):
        return float(memory_str[:-2])
    elif memory_str.endswith("Gi"):
        return float(memory_str[:-2]) * 1024
    elif memory_str.endswith("M"):
        return float(memory_str[:-1])
    elif memory_str.endswith("G"):
        return float(memory_str[:-1]) * 1024
    elif memory_str.endswith("Ki"):
        return float(memory_str[:-2]) / 1024
    else:
        # Fallback to float cast assuming it's in bytes or already numeric
        try:
            return float(memory_str) / (1024 * 1024)
        except ValueError:
            return 0.0

def evaluate_proposal(proposal: RemediationProposal, current_attempt_count: int = 0) -> Tuple[bool, str]:
    """
    Evaluates a RemediationProposal against the deterministic policy rules.
    Returns a tuple (is_approved, reason).

    The `escalate` operation is treated as a non-mutating authorized action and
    bypasses memory magnitude checks; it still must pass namespace and attempt checks.
    """
    try:
        policy = load_policy()
    except Exception as e:
        return False, f"Failed to load policy: {e}"

    incident = proposal.incident
    action = proposal.proposed_action

    # 1. Namespace validation
    allowed_namespaces = policy.get('allowed_namespaces', [])
    if incident.namespace not in allowed_namespaces:
        return False, f"Namespace '{incident.namespace}' is not in allowed_namespaces."

    # 2. Operation validation
    allowed_operations = policy.get('allowed_operations', [])
    if action.operation not in allowed_operations:
        return False, f"Operation '{action.operation}' is not in allowed_operations."

    # 3. Resource validation (skip for escalate — no Kubernetes resource is being mutated)
    if action.operation != "escalate":
        allowed_resources = policy.get('allowed_resources', [])
        if action.resource not in allowed_resources:
            return False, f"Resource '{action.resource}' is not in allowed_resources."
            
        # Ensure it's not modifying an unintended resource
        if incident.workload != action.resource:
            return False, f"Proposed resource '{action.resource}' does not match incident workload '{incident.workload}'."

    # 4. Attempt count validation
    max_attempts = policy.get('max_attempts', 0)
    if current_attempt_count >= max_attempts:
        return False, f"Max attempts ({max_attempts}) reached or exceeded."

    # 5. Magnitude validation (only for increase_memory_limit)
    if action.operation == "increase_memory_limit":
        current_mem = parse_memory(action.current_memory)
        proposed_mem = parse_memory(action.proposed_memory)
        
        if current_mem <= 0:
            return False, f"Could not parse valid current memory from '{action.current_memory}'"
        
        if proposed_mem <= current_mem:
            return False, f"Proposed memory ({action.proposed_memory}) is not strictly greater than current memory ({action.current_memory})."
            
        multiplier = proposed_mem / current_mem
        max_multiplier = policy.get('max_memory_multiplier', 1.0)
        
        if multiplier > max_multiplier:
            return False, f"Memory increase multiplier ({multiplier:.2f}x) exceeds allowed max_memory_multiplier ({max_multiplier}x)."

    return True, "Proposal passed all policy checks."

def requires_human_approval(operation: str) -> bool:
    """
    Checks if the given operation requires human approval according to the policy.
    `escalate` is always non-interactive — it routes to ESCALATED, not HITL.
    """
    if operation == "escalate":
        return False
    try:
        policy = load_policy()
        require_human = policy.get('require_human_approval', [])
        return operation in require_human
    except Exception:
        # Default to safe (requiring approval) if policy fails to load
        return True

def get_max_attempts() -> int:
    """Returns the configured max_attempts from policy."""
    try:
        policy = load_policy()
        return int(policy.get('max_attempts', 2))
    except Exception:
        return 2

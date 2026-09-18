import sys
import os
import uuid
import time
import logging
from enum import Enum

from src.k8s import k8s_readonly, k8s_patch, verification
from src.agent.groq_client import analyze_incident
from src.agent.reflexion_store import ReflexionStore
from src.safety.policy_engine import evaluate_proposal, get_max_attempts
from src.safety.hitl_gate import request_approval
from src.rag.retriever import get_sop_content
from src.logging.event_logger import EventLogger

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("safeheal-fsm")

class State(Enum):
    DETECT = "DETECT"
    INVESTIGATE = "INVESTIGATE"
    DIAGNOSE = "DIAGNOSE"
    PROPOSE = "PROPOSE"
    POLICY_CHECK = "POLICY_CHECK"
    HITL = "HITL"
    REMEDIATE = "REMEDIATE"
    VERIFY = "VERIFY"
    REFLEXION = "REFLEXION"
    RESOLVED = "RESOLVED"
    ESCALATED = "ESCALATED"

class FSMContext:
    def __init__(self):
        self.run_id = str(uuid.uuid4())[:8]
        self.event_logger = EventLogger(self.run_id)
        self.namespace = "safeheal-demo"
        self.deployment = "memory-hog"
        self.pod_name = None
        self.status = None
        self.logs = None
        self.events = None
        self.limits = None
        self.sop_content = None
        self.proposal = None
        self.reflexion = ReflexionStore()
        self.failure_reason = None
        
def run_fsm():
    state = State.DETECT
    ctx = FSMContext()
    
    ctx.event_logger.log_event("WORKFLOW_STARTED", state.value, "INFO", "SafeHeal FSM initialized.")
    
    while state not in [State.RESOLVED, State.ESCALATED]:
        
        if state == State.DETECT:
            pods = k8s_readonly.find_pods_for_deployment(ctx.namespace, ctx.deployment)
            if not pods:
                ctx.event_logger.log_event("POD_NOT_FOUND", state.value, "ERROR", "No pods found.")
                state = State.ESCALATED
                continue
                
            ctx.pod_name = pods[0]
            status = k8s_readonly.get_pod_status(ctx.namespace, ctx.pod_name)
            
            is_oom = False
            if "container_statuses" in status:
                for cs in status.get("container_statuses", []):
                    last_state = cs.get("last_state", {})
                    curr_state = cs.get("state", {})
                    if last_state.get("reason") == "OOMKilled" or curr_state.get("reason") == "OOMKilled":
                        is_oom = True
                        break
            
            if is_oom:
                ctx.event_logger.log_event("INCIDENT_DETECTED", state.value, "INFO", f"OOMKilled detected on pod {ctx.pod_name}")
                state = State.INVESTIGATE
            else:
                state = State.RESOLVED
                
        elif state == State.INVESTIGATE:
            # Stage 5: Refresh pod name to the current ReplicaSet pod.
            # On the first pass this is the same pod found in DETECT.
            # On a reflexion retry this ensures we inspect the newly rolled-out pod,
            # not the historical one that was already terminated.
            current_pods = k8s_readonly.find_current_pods_for_deployment(ctx.namespace, ctx.deployment)
            if current_pods:
                if current_pods[0] != ctx.pod_name:
                    logger.info(f"[REFLEXION] Pod refreshed: {ctx.pod_name} -> {current_pods[0]}")
                ctx.pod_name = current_pods[0]
            # If find_current_pods_for_deployment returns nothing (race), keep the last known pod name

            ctx.status = k8s_readonly.get_pod_status(ctx.namespace, ctx.pod_name)
            ctx.logs = k8s_readonly.get_pod_logs(ctx.namespace, ctx.pod_name, previous=True, tail_lines=50)
            ctx.events = k8s_readonly.get_pod_events(ctx.namespace, ctx.pod_name)
            ctx.limits = k8s_readonly.get_resource_limits(ctx.namespace, ctx.deployment)
            ctx.sop_content = get_sop_content("OOMKilled_SOP")
            ctx.event_logger.log_event("EVIDENCE_COLLECTED", state.value, "INFO", "Gathered pod telemetry and SOP.")
            state = State.DIAGNOSE
            
        elif state == State.DIAGNOSE:
            previous_attempts_text = ctx.reflexion.format_for_llm(ctx.run_id)
            try:
                ctx.proposal = analyze_incident(
                    namespace=ctx.namespace,
                    deployment=ctx.deployment,
                    pod_name=ctx.pod_name,
                    status=ctx.status,
                    logs=ctx.logs,
                    events=ctx.events,
                    limits=ctx.limits,
                    sop_content=ctx.sop_content,
                    previous_attempts=previous_attempts_text if ctx.reflexion.get_attempt_count(ctx.run_id) > 0 else None
                )
                ctx.event_logger.log_event("DIAGNOSIS_GENERATED", state.value, "INFO", ctx.proposal.diagnosis.probable_cause, {"confidence": ctx.proposal.diagnosis.confidence})
                ctx.event_logger.log_event("PROPOSAL_CREATED", State.PROPOSE.value, "INFO", f"Proposed: {ctx.proposal.proposed_action.operation}", {"new_limit": ctx.proposal.proposed_action.proposed_memory})

                # Stage 5: If the LLM itself recommends escalation, route directly without HITL/patching.
                if ctx.proposal.proposed_action.operation == "escalate":
                    ctx.event_logger.log_event("AGENT_ESCALATED", state.value, "INFO", f"Agent recommends escalation: {ctx.proposal.proposed_action.reason}")
                    state = State.ESCALATED
                    continue

                state = State.POLICY_CHECK
            except Exception as e:
                ctx.event_logger.log_event("LLM_ERROR", state.value, "ERROR", str(e))
                state = State.ESCALATED
                
        elif state == State.POLICY_CHECK:
            attempt_count = ctx.reflexion.get_attempt_count(ctx.run_id)
            is_safe, reason = evaluate_proposal(ctx.proposal, current_attempt_count=attempt_count)
            
            if is_safe:
                ctx.event_logger.log_event("POLICY_APPROVED", state.value, "INFO", "Proposal passed policy.")
                state = State.HITL
            else:
                ctx.event_logger.log_event("POLICY_REJECTED", state.value, "ERROR", reason)
                state = State.ESCALATED
                
        elif state == State.HITL:
            ctx.event_logger.log_event("HITL_REQUESTED", state.value, "INFO", "Waiting for human approval.")
            approved = request_approval(ctx.proposal)
            if approved:
                ctx.event_logger.log_event("HITL_APPROVED", state.value, "INFO", "Operator approved.")
                state = State.REMEDIATE
            else:
                ctx.event_logger.log_event("HITL_REJECTED", state.value, "ERROR", "Operator rejected.")
                state = State.ESCALATED
                
        elif state == State.REMEDIATE:
            success = k8s_patch.apply_memory_patch(ctx.proposal)
            if success:
                ctx.event_logger.log_event("PATCH_APPLIED", state.value, "INFO", "Kubernetes API patched.")
                state = State.VERIFY
            else:
                ctx.failure_reason = "Failed to apply patch."
                ctx.event_logger.log_event("PATCH_FAILED", state.value, "ERROR", ctx.failure_reason)
                state = State.REFLEXION
                
        elif state == State.VERIFY:
            ctx.event_logger.log_event("VERIFICATION_STARTED", state.value, "INFO", "Monitoring deployment rollout...")
            success, reason = verification.verify_recovery(
                namespace=ctx.namespace, 
                deployment_name=ctx.deployment,
                timeout_seconds=60
            )
            if success:
                ctx.event_logger.log_event("VERIFICATION_SUCCESS", state.value, "INFO", reason)
                state = State.RESOLVED
            else:
                ctx.failure_reason = reason
                ctx.event_logger.log_event("VERIFICATION_FAILED", state.value, "ERROR", reason)
                state = State.REFLEXION
                
        elif state == State.REFLEXION:
            ctx.event_logger.log_event("REFLEXION_STARTED", state.value, "INFO", "Recording failure for next LLM cycle.")
            action = ctx.proposal.proposed_action
            ctx.reflexion.add_attempt(
                run_id=ctx.run_id,
                operation=action.operation,
                old_value=str(action.current_memory),
                new_value=str(action.proposed_memory),
                diagnosis=ctx.proposal.diagnosis.probable_cause,
                reason=action.reason,
                result="FAILED",
                failure_evidence=ctx.failure_reason
            )

            # Stage 5: Hard retry budget check BEFORE starting another Groq cycle.
            # The deterministic policy max_attempts limit is enforced here, not by the LLM.
            attempt_count = ctx.reflexion.get_attempt_count(ctx.run_id)
            max_attempts = get_max_attempts()
            if attempt_count >= max_attempts:
                ctx.event_logger.log_event(
                    "RETRY_BUDGET_EXHAUSTED", state.value, "ERROR",
                    f"Attempt count ({attempt_count}) reached max_attempts ({max_attempts}). Escalating without further LLM calls."
                )
                state = State.ESCALATED
            else:
                state = State.INVESTIGATE
            
    if state == State.RESOLVED:
        ctx.event_logger.log_event("RESOLVED", state.value, "SUCCESS", "Incident safely remediated.")
    elif state == State.ESCALATED:
        ctx.event_logger.log_event("ESCALATED", state.value, "WARNING", "Workflow halted. Human intervention required.")

if __name__ == "__main__":
    try:
        run_fsm()
    except KeyboardInterrupt:
        sys.exit(1)

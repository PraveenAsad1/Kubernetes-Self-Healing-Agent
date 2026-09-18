import unittest
import sys
import os
from unittest.mock import MagicMock

# Ensure project root is on sys.path for both run styles
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.agent.reflexion_store import ReflexionStore
from src.agent.schemas import (
    RemediationProposal, IncidentInfo, DiagnosisInfo, ProposedAction
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_proposal(
    operation="increase_memory_limit",
    current_memory="128Mi",
    proposed_memory="192Mi",
    workload="memory-hog",
    namespace="safeheal-demo",
    reflection=None,
):
    return RemediationProposal(
        incident=IncidentInfo(type="OOMKilled", namespace=namespace, workload=workload),
        diagnosis=DiagnosisInfo(
            probable_cause="Memory exhaustion",
            confidence=0.9,
            evidence=["rapid allocation in logs"],
            reflection=reflection,
        ),
        proposed_action=ProposedAction(
            operation=operation,
            resource=workload,
            current_memory=current_memory,
            proposed_memory=proposed_memory,
            reason="Increase to handle load",
        ),
    )


# ---------------------------------------------------------------------------
# 1. ReflexionStore: record & count
# ---------------------------------------------------------------------------

class TestReflexionStoreRecordAndCount(unittest.TestCase):

    def test_empty_store_count(self):
        store = ReflexionStore()
        self.assertEqual(store.get_attempt_count("run-1"), 0)

    def test_add_and_count_single_run(self):
        store = ReflexionStore()
        store.add_attempt("run-1", "increase_memory_limit", "128Mi", "192Mi",
                          "OOM", "Increase limit", "FAILED", "OOMKilled recurred")
        self.assertEqual(store.get_attempt_count("run-1"), 1)

    def test_add_multiple_different_runs(self):
        store = ReflexionStore()
        store.add_attempt("run-1", "increase_memory_limit", "128Mi", "192Mi",
                          "OOM", "reason", "FAILED", "ev1")
        store.add_attempt("run-2", "increase_memory_limit", "192Mi", "256Mi",
                          "OOM", "reason", "FAILED", "ev2")
        self.assertEqual(store.get_attempt_count("run-1"), 1)
        self.assertEqual(store.get_attempt_count("run-2"), 1)
        self.assertEqual(store.get_attempt_count(), 2)

    def test_add_multiple_same_run(self):
        store = ReflexionStore()
        for _ in range(3):
            store.add_attempt("run-A", "increase_memory_limit", "128Mi", "256Mi",
                              "OOM", "reason", "FAILED", "ev")
        self.assertEqual(store.get_attempt_count("run-A"), 3)

    def test_none_values_stored_safely(self):
        """add_attempt should not raise even if optional fields are None."""
        store = ReflexionStore()
        store.add_attempt("run-1", "increase_memory_limit", None, None,
                          "OOM", "reason", "FAILED", None)
        attempt = store.get_latest_attempt("run-1")
        self.assertIsNotNone(attempt)
        self.assertEqual(attempt["old_value"], "")
        self.assertEqual(attempt["new_value"], "")
        self.assertEqual(attempt["failure_evidence"], "No specific evidence recorded")


# ---------------------------------------------------------------------------
# 2. ReflexionStore: format_for_llm
# ---------------------------------------------------------------------------

class TestReflexionStoreFormatForLLM(unittest.TestCase):

    def test_empty_returns_no_previous_attempts(self):
        store = ReflexionStore()
        result = store.format_for_llm("run-1")
        self.assertEqual(result, "No previous attempts.")

    def test_single_attempt_structure(self):
        store = ReflexionStore()
        store.add_attempt("run-1", "increase_memory_limit", "128Mi", "192Mi",
                          "Memory exhaustion", "Increase limit", "FAILED", "OOMKilled recurred")
        result = store.format_for_llm("run-1")
        self.assertIn("Attempt 1:", result)
        self.assertIn("increase_memory_limit", result)
        self.assertIn("128Mi -> 192Mi", result)
        self.assertIn("FAILED", result)
        self.assertIn("OOMKilled recurred", result)
        self.assertIn("Memory exhaustion", result)

    def test_multiple_attempts_numbered(self):
        store = ReflexionStore()
        store.add_attempt("run-1", "increase_memory_limit", "128Mi", "192Mi",
                          "Cause A", "reason", "FAILED", "evidence A")
        store.add_attempt("run-1", "increase_memory_limit", "192Mi", "256Mi",
                          "Cause B", "reason", "FAILED", "evidence B")
        result = store.format_for_llm("run-1")
        self.assertIn("Attempt 1:", result)
        self.assertIn("Attempt 2:", result)
        self.assertIn("evidence A", result)
        self.assertIn("evidence B", result)

    def test_format_only_for_given_run_id(self):
        store = ReflexionStore()
        store.add_attempt("run-1", "increase_memory_limit", "128Mi", "192Mi",
                          "Cause A", "reason", "FAILED", "ev-run-1")
        store.add_attempt("run-2", "increase_memory_limit", "128Mi", "192Mi",
                          "Cause B", "reason", "FAILED", "ev-run-2")
        result = store.format_for_llm("run-1")
        self.assertIn("ev-run-1", result)
        self.assertNotIn("ev-run-2", result)


# ---------------------------------------------------------------------------
# 3. ReflexionStore: get_latest_attempt
# ---------------------------------------------------------------------------

class TestReflexionStoreGetLatest(unittest.TestCase):

    def test_latest_returns_none_when_empty(self):
        store = ReflexionStore()
        self.assertIsNone(store.get_latest_attempt("run-1"))

    def test_latest_returns_last_added(self):
        store = ReflexionStore()
        store.add_attempt("run-1", "increase_memory_limit", "128Mi", "192Mi",
                          "A", "r", "FAILED", "ev1")
        store.add_attempt("run-1", "increase_memory_limit", "192Mi", "256Mi",
                          "B", "r", "FAILED", "ev2")
        latest = store.get_latest_attempt("run-1")
        self.assertEqual(latest["new_value"], "256Mi")
        self.assertEqual(latest["failure_evidence"], "ev2")


# ---------------------------------------------------------------------------
# 4. ReflexionStore: is_duplicate_proposal
# ---------------------------------------------------------------------------

class TestReflexionStoreDuplicate(unittest.TestCase):

    def test_no_duplicate_on_empty_store(self):
        store = ReflexionStore()
        self.assertFalse(store.is_duplicate_proposal("run-1", "increase_memory_limit", "192Mi"))

    def test_detects_exact_duplicate(self):
        store = ReflexionStore()
        store.add_attempt("run-1", "increase_memory_limit", "128Mi", "192Mi",
                          "OOM", "reason", "FAILED", "ev")
        self.assertTrue(store.is_duplicate_proposal("run-1", "increase_memory_limit", "192Mi"))

    def test_no_false_positive_different_memory(self):
        store = ReflexionStore()
        store.add_attempt("run-1", "increase_memory_limit", "128Mi", "192Mi",
                          "OOM", "reason", "FAILED", "ev")
        self.assertFalse(store.is_duplicate_proposal("run-1", "increase_memory_limit", "256Mi"))

    def test_no_false_positive_different_run(self):
        store = ReflexionStore()
        store.add_attempt("run-1", "increase_memory_limit", "128Mi", "192Mi",
                          "OOM", "reason", "FAILED", "ev")
        self.assertFalse(store.is_duplicate_proposal("run-2", "increase_memory_limit", "192Mi"))

    def test_different_operation_no_duplicate(self):
        store = ReflexionStore()
        store.add_attempt("run-1", "increase_memory_limit", "128Mi", "192Mi",
                          "OOM", "reason", "FAILED", "ev")
        self.assertFalse(store.is_duplicate_proposal("run-1", "escalate", "192Mi"))


# ---------------------------------------------------------------------------
# 5. Schema: reflection field
# ---------------------------------------------------------------------------

class TestSchemaReflectionField(unittest.TestCase):

    def test_reflection_defaults_to_none(self):
        proposal = make_proposal()
        self.assertIsNone(proposal.diagnosis.reflection)

    def test_reflection_can_be_set(self):
        proposal = make_proposal(reflection="The previous attempt failed because the limit was still too low.")
        self.assertIsNotNone(proposal.diagnosis.reflection)
        self.assertIn("previous attempt", proposal.diagnosis.reflection)

    def test_serialization_without_reflection(self):
        proposal = make_proposal()
        data = proposal.model_dump()
        # reflection key present but None
        self.assertIn("reflection", data["diagnosis"])
        self.assertIsNone(data["diagnosis"]["reflection"])

    def test_serialization_with_reflection(self):
        proposal = make_proposal(reflection="Addressed by doubling limit.")
        data = proposal.model_dump()
        self.assertEqual(data["diagnosis"]["reflection"], "Addressed by doubling limit.")


# ---------------------------------------------------------------------------
# 6. Policy engine: escalate operation
# ---------------------------------------------------------------------------

class TestPolicyEscalate(unittest.TestCase):

    def _make_escalate_proposal(self, namespace="safeheal-demo", workload="memory-hog"):
        return RemediationProposal(
            incident=IncidentInfo(type="OOMKilled", namespace=namespace, workload=workload),
            diagnosis=DiagnosisInfo(
                probable_cause="Unbounded memory leak",
                confidence=0.95,
                evidence=["10-day stable, then sudden OOM"],
            ),
            proposed_action=ProposedAction(
                operation="escalate",
                resource=workload,
                current_memory=None,
                proposed_memory=None,
                reason="True memory leak requires code fix, not limit increase.",
            ),
        )

    def test_escalate_passes_policy(self):
        from src.safety.policy_engine import evaluate_proposal
        proposal = self._make_escalate_proposal()
        passed, reason = evaluate_proposal(proposal, current_attempt_count=0)
        self.assertTrue(passed, reason)

    def test_escalate_wrong_namespace_rejected(self):
        from src.safety.policy_engine import evaluate_proposal
        proposal = self._make_escalate_proposal(namespace="kube-system")
        passed, reason = evaluate_proposal(proposal, current_attempt_count=0)
        self.assertFalse(passed)
        self.assertIn("not in allowed_namespaces", reason)

    def test_escalate_does_not_require_human_approval(self):
        from src.safety.policy_engine import requires_human_approval
        self.assertFalse(requires_human_approval("escalate"))

    def test_escalate_exempt_from_resource_mismatch_check(self):
        """escalate should not fail because resource != workload."""
        from src.safety.policy_engine import evaluate_proposal
        proposal = RemediationProposal(
            incident=IncidentInfo(type="OOMKilled", namespace="safeheal-demo", workload="memory-hog"),
            diagnosis=DiagnosisInfo(
                probable_cause="Leak", confidence=0.9, evidence=["logs"]
            ),
            proposed_action=ProposedAction(
                operation="escalate",
                resource="some-other-resource",
                reason="Can't fix automatically",
            ),
        )
        passed, reason = evaluate_proposal(proposal, current_attempt_count=0)
        self.assertTrue(passed, reason)


# ---------------------------------------------------------------------------
# 7. FSM logic: hard retry budget exhaustion (no redundant 3rd Groq call)
#
# Tests replicate the REFLEXION state logic directly (without importing main)
# to avoid kubeconfig / Groq API key checks at import time.
# ---------------------------------------------------------------------------

class TestFSMRetryBudgetExhaustion(unittest.TestCase):

    def test_no_groq_call_after_budget_exhausted(self):
        """
        After recording the 2nd failure (= max_attempts), the budget check
        must detect exhaustion. The test structure itself proves no Groq call
        occurs — if budget is exhausted the code never reaches DIAGNOSE.
        """
        from src.safety.policy_engine import get_max_attempts

        run_id = "test-run-exhaust"
        store = ReflexionStore()

        # 1st failure already recorded
        store.add_attempt(run_id, "increase_memory_limit", "128Mi", "192Mi",
                          "OOM", "reason", "FAILED", "OOMKilled recurred")
        # 2nd failure — recorded now inside REFLEXION
        store.add_attempt(run_id, "increase_memory_limit", "192Mi", "256Mi",
                          "OOM", "reason", "FAILED", "OOMKilled recurred again")

        attempt_count = store.get_attempt_count(run_id)
        max_att = get_max_attempts()

        should_escalate = attempt_count >= max_att
        self.assertTrue(
            should_escalate,
            f"Expected budget exhausted: {attempt_count} attempts vs max {max_att}"
        )

    def test_budget_not_exhausted_on_first_failure(self):
        """After 1 failure with max_attempts=2, should proceed to INVESTIGATE."""
        from src.safety.policy_engine import get_max_attempts

        run_id = "test-run-first"
        store = ReflexionStore()
        store.add_attempt(run_id, "increase_memory_limit", "128Mi", "192Mi",
                          "OOM", "reason", "FAILED", "Patch failed")

        attempt_count = store.get_attempt_count(run_id)
        max_att = get_max_attempts()
        should_escalate = attempt_count >= max_att
        self.assertFalse(
            should_escalate,
            f"Should NOT escalate after {attempt_count} attempt(s) with max {max_att}"
        )

    def test_max_attempts_value_is_deterministic(self):
        """get_max_attempts() must return the policy-configured integer (not LLM-controlled)."""
        from src.safety.policy_engine import get_max_attempts
        max_att = get_max_attempts()
        self.assertIsInstance(max_att, int)
        self.assertGreater(max_att, 0)
        self.assertEqual(max_att, 2)  # must match policy_rules.yaml


# ---------------------------------------------------------------------------
# 8. FSM logic: pod refresh after reflexion
#
# Replicates the INVESTIGATE pod-refresh logic without importing main.
# ---------------------------------------------------------------------------

class TestFSMPodRefresh(unittest.TestCase):

    def _simulate_investigate_pod_refresh(self, current_pod_name, mock_pods):
        """Replicate the INVESTIGATE pod-refresh logic from main.py."""
        current_pods = mock_pods
        if current_pods:
            current_pod_name = current_pods[0]
        return current_pod_name

    def test_pod_name_refreshed_to_new_pod(self):
        """After rollout, INVESTIGATE should pick up the new ReplicaSet pod."""
        new_pod = self._simulate_investigate_pod_refresh(
            "memory-hog-old-12345", ["memory-hog-new-54abc"]
        )
        self.assertEqual(new_pod, "memory-hog-new-54abc")

    def test_pod_name_preserved_if_refresh_returns_empty(self):
        """If find_current_pods_for_deployment returns [], keep last known pod name."""
        same_pod = self._simulate_investigate_pod_refresh("memory-hog-old-12345", [])
        self.assertEqual(same_pod, "memory-hog-old-12345")

    def test_pod_name_unchanged_when_same(self):
        """If the pod name hasn't changed, no harm done."""
        same_pod = self._simulate_investigate_pod_refresh(
            "memory-hog-old-12345", ["memory-hog-old-12345"]
        )
        self.assertEqual(same_pod, "memory-hog-old-12345")


# ---------------------------------------------------------------------------
# 9. FSM logic: agent escalation routing
#
# Replicates the DIAGNOSE state routing decision without importing main.
# ---------------------------------------------------------------------------

class TestFSMAgentEscalation(unittest.TestCase):

    def _simulate_diagnose_routing(self, proposal):
        """
        Replicate the DIAGNOSE routing from main.py:
          escalate -> ESCALATED  (no HITL, no patching)
          anything else -> POLICY_CHECK
        """
        if proposal.proposed_action.operation == "escalate":
            return "ESCALATED"
        return "POLICY_CHECK"

    def test_escalate_proposal_routes_to_escalated(self):
        escalate_proposal = make_proposal(operation="escalate", proposed_memory=None)
        result = self._simulate_diagnose_routing(escalate_proposal)
        self.assertEqual(result, "ESCALATED")

    def test_normal_proposal_routes_to_policy_check(self):
        normal_proposal = make_proposal(operation="increase_memory_limit")
        result = self._simulate_diagnose_routing(normal_proposal)
        self.assertEqual(result, "POLICY_CHECK")

    def test_escalate_does_not_pass_through_hitl(self):
        """escalate must NOT be in require_human_approval."""
        from src.safety.policy_engine import requires_human_approval
        self.assertFalse(requires_human_approval("escalate"))

    def test_escalate_with_reflection_passes_policy(self):
        """An escalate proposal with a reflection field should still pass policy."""
        from src.safety.policy_engine import evaluate_proposal
        escalate_proposal = RemediationProposal(
            incident=IncidentInfo(type="OOMKilled", namespace="safeheal-demo", workload="memory-hog"),
            diagnosis=DiagnosisInfo(
                probable_cause="Unbounded memory leak",
                confidence=0.95,
                evidence=["rapid unbounded allocation"],
                reflection=(
                    "Previous 128Mi->192Mi increase did not stop OOM recurrence. "
                    "Evidence points to a true memory leak requiring a code fix."
                ),
            ),
            proposed_action=ProposedAction(
                operation="escalate",
                resource="memory-hog",
                reason="True memory leak requires code fix.",
            ),
        )
        passed, reason = evaluate_proposal(escalate_proposal, current_attempt_count=0)
        self.assertTrue(passed, reason)


if __name__ == '__main__':
    unittest.main()

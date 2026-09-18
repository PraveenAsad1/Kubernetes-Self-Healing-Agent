import unittest
import os
import sys

from src.safety.policy_engine import evaluate_proposal, parse_memory
from src.agent.schemas import RemediationProposal, IncidentInfo, DiagnosisInfo, ProposedAction

class TestPolicyEngine(unittest.TestCase):

    def setUp(self):
        self.valid_incident = IncidentInfo(
            type="OOMKilled",
            namespace="safeheal-demo",
            workload="memory-hog"
        )
        self.valid_diagnosis = DiagnosisInfo(
            probable_cause="Memory leak",
            confidence=0.9,
            evidence=["logs show rapid allocation"]
        )
        self.valid_action = ProposedAction(
            operation="increase_memory_limit",
            resource="memory-hog",
            current_memory="128Mi",
            proposed_memory="192Mi",
            reason="Increase to handle spikes"
        )

    def test_parse_memory(self):
        self.assertEqual(parse_memory("128Mi"), 128.0)
        self.assertEqual(parse_memory("1Gi"), 1024.0)
        self.assertEqual(parse_memory("256M"), 256.0)

    def test_valid_proposal(self):
        proposal = RemediationProposal(
            incident=self.valid_incident,
            diagnosis=self.valid_diagnosis,
            proposed_action=self.valid_action
        )
        passed, reason = evaluate_proposal(proposal, current_attempt_count=0)
        self.assertTrue(passed, reason)

    def test_invalid_namespace(self):
        incident = self.valid_incident.model_copy(update={"namespace": "kube-system"})
        proposal = RemediationProposal(
            incident=incident,
            diagnosis=self.valid_diagnosis,
            proposed_action=self.valid_action
        )
        passed, reason = evaluate_proposal(proposal, current_attempt_count=0)
        self.assertFalse(passed)
        self.assertIn("not in allowed_namespaces", reason)

    def test_invalid_operation(self):
        action = self.valid_action.model_copy(update={"operation": "delete_namespace"})
        proposal = RemediationProposal(
            incident=self.valid_incident,
            diagnosis=self.valid_diagnosis,
            proposed_action=action
        )
        passed, reason = evaluate_proposal(proposal, current_attempt_count=0)
        self.assertFalse(passed)
        self.assertIn("not in allowed_operations", reason)

    def test_excessive_memory_increase(self):
        action = self.valid_action.model_copy(update={"proposed_memory": "4Gi"})
        proposal = RemediationProposal(
            incident=self.valid_incident,
            diagnosis=self.valid_diagnosis,
            proposed_action=action
        )
        passed, reason = evaluate_proposal(proposal, current_attempt_count=0)
        self.assertFalse(passed)
        self.assertIn("exceeds allowed max_memory_multiplier", reason)
        
    def test_memory_decrease(self):
        action = self.valid_action.model_copy(update={"proposed_memory": "64Mi"})
        proposal = RemediationProposal(
            incident=self.valid_incident,
            diagnosis=self.valid_diagnosis,
            proposed_action=action
        )
        passed, reason = evaluate_proposal(proposal, current_attempt_count=0)
        self.assertFalse(passed)
        self.assertIn("strictly greater than current", reason)

    def test_attempt_limit_exceeded(self):
        proposal = RemediationProposal(
            incident=self.valid_incident,
            diagnosis=self.valid_diagnosis,
            proposed_action=self.valid_action
        )
        # Assuming max_attempts is 2
        passed, reason = evaluate_proposal(proposal, current_attempt_count=2)
        self.assertFalse(passed)
        self.assertIn("Max attempts", reason)
        
    def test_resource_mismatch(self):
        action = self.valid_action.model_copy(update={"resource": "other-app"})
        proposal = RemediationProposal(
            incident=self.valid_incident,
            diagnosis=self.valid_diagnosis,
            proposed_action=action
        )
        passed, reason = evaluate_proposal(proposal, current_attempt_count=0)
        self.assertFalse(passed)
        self.assertIn("not in allowed_resources", reason)

if __name__ == '__main__':
    unittest.main()

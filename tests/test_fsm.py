import unittest
from unittest.mock import patch

from src.agent.schemas import DiagnosisInfo, IncidentInfo, ProposedAction, RemediationProposal


class RecordingEventLogger:
    instances = []

    def __init__(self, run_id):
        self.events = []
        self.__class__.instances.append(self)

    def log_event(self, event_type, stage, status, message, metadata=None):
        self.events.append((event_type, stage, status, message, metadata))


def make_proposal(current_memory, proposed_memory):
    return RemediationProposal(
        incident=IncidentInfo(
            type="OOMKilled",
            namespace="safeheal-demo",
            workload="memory-hog",
        ),
        diagnosis=DiagnosisInfo(
            probable_cause="Memory exhaustion",
            confidence=0.9,
            evidence=["OOMKilled"],
        ),
        proposed_action=ProposedAction(
            operation="increase_memory_limit",
            resource="memory-hog",
            current_memory=current_memory,
            proposed_memory=proposed_memory,
            reason="Increase memory limit",
        ),
    )


class TestFSMIntegration(unittest.TestCase):

    def setUp(self):
        RecordingEventLogger.instances.clear()

    def _patch_common_fsm_dependencies(self):
        patches = [
            patch("main.EventLogger", RecordingEventLogger),
            patch("main.k8s_readonly.find_pods_for_deployment", return_value=["pod-1"]),
            patch("main.k8s_readonly.find_current_pods_for_deployment", return_value=["pod-1"]),
            patch(
                "main.k8s_readonly.get_pod_status",
                return_value={
                    "phase": "Running",
                    "container_statuses": [
                        {
                            "ready": True,
                            "state": {"type": "terminated", "reason": "OOMKilled"},
                            "last_state": {},
                        }
                    ],
                },
            ),
            patch("main.k8s_readonly.get_pod_logs", return_value="logs"),
            patch("main.k8s_readonly.get_pod_events", return_value=[]),
            patch("main.k8s_readonly.get_resource_limits", return_value={}),
            patch("main.get_sop_content", return_value="sop"),
            patch("main.request_approval", return_value=True),
        ]
        return patches

    def test_successful_path_reaches_resolved(self):
        import main

        patches = self._patch_common_fsm_dependencies()
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7], patches[8], \
                patch("main.analyze_incident", return_value=make_proposal("128Mi", "192Mi")), \
                patch("main.k8s_patch.apply_memory_patch", return_value=True), \
                patch("main.verification.verify_recovery", return_value=(True, "healthy")):
            main.run_fsm()

        stages = [event[1] for event in RecordingEventLogger.instances[0].events]
        self.assertIn("PROPOSE", stages)
        self.assertIn("POLICY_CHECK", stages)
        self.assertIn("RESOLVED", stages)
        self.assertLess(stages.index("PROPOSE"), stages.index("POLICY_CHECK"))

    def test_retry_exhaustion_reaches_escalated_without_third_diagnosis(self):
        import main

        patches = self._patch_common_fsm_dependencies()
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7], patches[8], \
                patch(
                    "main.analyze_incident",
                    side_effect=[
                        make_proposal("128Mi", "192Mi"),
                        make_proposal("192Mi", "256Mi"),
                    ],
                ) as mock_analyze, \
                patch("main.k8s_patch.apply_memory_patch", return_value=False), \
                patch("main.verification.verify_recovery") as mock_verify:
            main.run_fsm()

        stages = [event[1] for event in RecordingEventLogger.instances[0].events]
        self.assertIn("RETRY_BUDGET_EXHAUSTED", [event[0] for event in RecordingEventLogger.instances[0].events])
        self.assertIn("ESCALATED", stages)
        self.assertEqual(mock_analyze.call_count, 2)
        mock_verify.assert_not_called()


if __name__ == "__main__":
    unittest.main()
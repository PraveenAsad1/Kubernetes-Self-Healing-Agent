import unittest
from unittest.mock import patch
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from k8s.verification import verify_recovery

class TestVerification(unittest.TestCase):

    @patch('k8s.verification.get_deployment')
    @patch('k8s.verification.find_current_pods_for_deployment')
    @patch('k8s.verification.get_pod_status')
    @patch('time.sleep')
    @patch('k8s.verification.logger.info')
    def test_successful_recovery(self, mock_logger_info, mock_sleep, mock_pod_status, mock_find_pods, mock_get_deployment):
        # Mock deployment is ready
        mock_get_deployment.return_value = {
            "name": "memory-hog",
            "replicas": 1,
            "ready_replicas": 1,
            "updated_replicas": 1,
            "generation": 2,
            "observed_generation": 2,
        }
        
        # Mock pods found
        mock_find_pods.return_value = ["memory-hog-1234"]
        
        # Mock pod status is running and ready
        mock_pod_status.return_value = {
            "name": "memory-hog-1234",
            "phase": "Running",
            "container_statuses": [
                {
                    "name": "memory-hog",
                    "ready": True,
                    "state": {"type": "running"},
                    "last_state": {}
                }
            ]
        }
        
        # In the verification loop, we have a check `elapsed < 15`. Let's mock time to bypass the wait loop.
        with patch('time.time', side_effect=[0, 16, 17]):
            success, reason = verify_recovery("safeheal-demo", "memory-hog", timeout_seconds=20)
            
        self.assertTrue(success)
        self.assertIn("stable", reason)

    @patch('k8s.verification.get_deployment')
    @patch('k8s.verification.find_current_pods_for_deployment')
    @patch('k8s.verification.get_pod_status')
    @patch('time.sleep')
    @patch('k8s.verification.logger.info')
    def test_oomkilled_recurrence(self, mock_logger_info, mock_sleep, mock_pod_status, mock_find_pods, mock_get_deployment):
        mock_get_deployment.return_value = {
            "name": "memory-hog",
            "replicas": 1,
            "ready_replicas": 1,
            "updated_replicas": 1,
            "generation": 2,
            "observed_generation": 2,
        }
        mock_find_pods.return_value = ["memory-hog-1234"]
        
        # Mock pod status OOMKilled
        mock_pod_status.return_value = {
            "name": "memory-hog-1234",
            "phase": "Failed",
            "container_statuses": [
                {
                    "name": "memory-hog",
                    "ready": False,
                    "state": {
                        "type": "terminated",
                        "reason": "OOMKilled"
                    },
                    "last_state": {}
                }
            ]
        }
        
        with patch('time.time', side_effect=[0, 1, 2]):
            success, reason = verify_recovery("safeheal-demo", "memory-hog", timeout_seconds=10)
            
        self.assertFalse(success)
        self.assertIn("OOMKilled recurred", reason)

    @patch('k8s.verification.get_deployment')
    @patch('k8s.verification.find_current_pods_for_deployment')
    @patch('k8s.verification.get_pod_status')
    @patch('time.sleep')
    @patch('k8s.verification.logger.info')
    def test_historical_oom_on_superseded_pod_is_ignored(
        self, mock_logger_info, mock_sleep, mock_pod_status, mock_find_pods, mock_get_deployment
    ):
        mock_get_deployment.return_value = {
            "name": "memory-hog",
            "replicas": 1,
            "ready_replicas": 1,
            "updated_replicas": 1,
            "generation": 2,
            "observed_generation": 2,
        }
        mock_find_pods.return_value = ["memory-hog-current"]
        mock_pod_status.return_value = {
            "name": "memory-hog-current",
            "phase": "Running",
            "container_statuses": [
                {
                    "name": "memory-hog",
                    "ready": True,
                    "state": {"type": "running"},
                    "last_state": {},
                }
            ],
        }

        with patch('time.time', side_effect=[0, 16]):
            success, reason = verify_recovery(
                "safeheal-demo", "memory-hog", timeout_seconds=20
            )

        self.assertTrue(success)
        self.assertIn("stable", reason)

    @patch('k8s.verification.get_deployment')
    @patch('time.sleep')
    @patch('k8s.verification.logger.info')
    def test_timeout(self, mock_logger_info, mock_sleep, mock_get_deployment):
        # Deployment never ready
        mock_get_deployment.return_value = {
            "name": "memory-hog",
            "replicas": 1,
            "ready_replicas": 0,
            "updated_replicas": 0,
        }
        
        # Force timeout condition
        with patch('time.time', side_effect=[0, 11]):
            success, reason = verify_recovery("safeheal-demo", "memory-hog", timeout_seconds=10)
            
        self.assertFalse(success)
        self.assertIn("timeout", reason)

if __name__ == '__main__':
    unittest.main()

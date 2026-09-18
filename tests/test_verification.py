import unittest
from unittest.mock import patch
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from k8s.verification import verify_recovery

class TestVerification(unittest.TestCase):

    @patch('k8s.verification.get_deployment')
    @patch('k8s.verification.find_pods_for_deployment')
    @patch('k8s.verification.get_pod_status')
    @patch('time.sleep')
    def test_successful_recovery(self, mock_sleep, mock_pod_status, mock_find_pods, mock_get_deployment):
        # Mock deployment is ready
        mock_get_deployment.return_value = {
            "name": "memory-hog",
            "replicas": 1,
            "ready_replicas": 1
        }
        
        # Mock pods found
        mock_find_pods.return_value = ["memory-hog-1234"]
        
        # Mock pod status is running and ready
        mock_pod_status.return_value = {
            "name": "memory-hog-1234",
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
    @patch('k8s.verification.find_pods_for_deployment')
    @patch('k8s.verification.get_pod_status')
    @patch('time.sleep')
    def test_oomkilled_recurrence(self, mock_sleep, mock_pod_status, mock_find_pods, mock_get_deployment):
        mock_get_deployment.return_value = {
            "name": "memory-hog",
            "replicas": 1,
            "ready_replicas": 1
        }
        mock_find_pods.return_value = ["memory-hog-1234"]
        
        # Mock pod status OOMKilled
        mock_pod_status.return_value = {
            "name": "memory-hog-1234",
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
    @patch('time.sleep')
    def test_timeout(self, mock_sleep, mock_get_deployment):
        # Deployment never ready
        mock_get_deployment.return_value = {
            "name": "memory-hog",
            "replicas": 1,
            "ready_replicas": 0
        }
        
        # Force timeout condition
        with patch('time.time', side_effect=[0, 11]):
            success, reason = verify_recovery("safeheal-demo", "memory-hog", timeout_seconds=10)
            
        self.assertFalse(success)
        self.assertIn("timeout", reason)

if __name__ == '__main__':
    unittest.main()

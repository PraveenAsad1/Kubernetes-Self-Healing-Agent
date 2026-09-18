import sys
import os
import json
from pprint import pprint

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from k8s import k8s_readonly
from rag.retriever import get_sop_content
from agent.groq_client import analyze_incident

NAMESPACE = "safeheal-demo"
DEPLOYMENT = "memory-hog"

# Hardcoded mock evidence for testing without a real Kubernetes cluster
MOCK_LIMITS = {
    "memory-hog": {
        "limits": {"cpu": "500m", "memory": "128Mi"},
        "requests": {"cpu": "100m", "memory": "64Mi"}
    }
}

MOCK_STATUS = {
    "name": "memory-hog-5c9cd49b5c-8xgfz",
    "phase": "Running",
    "container_statuses": [
        {
            "name": "memory-hog",
            "ready": False,
            "restart_count": 3,
            "state": {
                "type": "waiting",
                "reason": "CrashLoopBackOff",
                "message": "back-off 1m20s restarting failed container=memory-hog pod=memory-hog-5c9cd49b5c-8xgfz"
            },
            "last_state": {
                "type": "terminated",
                "exit_code": 137,
                "reason": "OOMKilled",
                "message": None
            }
        }
    ]
}

MOCK_EVENTS = [
    {
        "type": "Warning",
        "reason": "BackOff",
        "message": "Back-off restarting failed container memory-hog in pod memory-hog-5c9cd49b5c-8xgfz_safeheal-demo(4231b14a-7b0f-4886-8a7e-4b67ab522ff6)",
        "count": 12,
        "last_timestamp": "2026-09-18 09:12:35+00:00"
    }
]

MOCK_LOGS = """Starting memory-hog workload on port 8080...
127.0.0.1 - - [18/Sep/2026 09:10:22] "GET /crash HTTP/1.1" 200 -
Starting rapid memory allocation...
Allocated 10 MB so far...
Allocated 20 MB so far...
Allocated 30 MB so far...
Allocated 40 MB so far...
Allocated 50 MB so far...
Allocated 60 MB so far...
Allocated 70 MB so far...
Allocated 80 MB so far...
Allocated 90 MB so far...
Allocated 100 MB so far...
Allocated 110 MB so far...
Allocated 120 MB so far...
Allocated 130 MB so far...
"""

def main():
    print(f"--- SafeHeal Stage 2: LLM Reasoning Test ---")
    
    # Try to get real data, fallback to mock data
    use_mock = False
    
    try:
        pods = k8s_readonly.find_pods_for_deployment(NAMESPACE, DEPLOYMENT)
        if not pods:
            print("No pods found. Falling back to mock data.")
            use_mock = True
        else:
            pod_name = pods[0]
            print(f"Using real data from pod: {pod_name}")
            status = k8s_readonly.get_pod_status(NAMESPACE, pod_name)
            logs = k8s_readonly.get_pod_logs(NAMESPACE, pod_name, previous=True, tail_lines=20)
            events = k8s_readonly.get_pod_events(NAMESPACE, pod_name)
            limits = k8s_readonly.get_resource_limits(NAMESPACE, DEPLOYMENT)
    except Exception as e:
        print(f"Error accessing Kubernetes: {e}")
        print("Falling back to mock data.")
        use_mock = True

    if use_mock:
        pod_name = "memory-hog-mock"
        status = MOCK_STATUS
        logs = MOCK_LOGS
        events = MOCK_EVENTS
        limits = MOCK_LIMITS
        
    print("\n1. Retrieving SOP for OOMKilled...")
    sop_content = get_sop_content("OOMKilled_SOP")
    
    print("\n2. Sending evidence to Groq for analysis...")
    try:
        proposal = analyze_incident(
            namespace=NAMESPACE,
            deployment=DEPLOYMENT,
            pod_name=pod_name,
            status=status,
            logs=logs,
            events=events,
            limits=limits,
            sop_content=sop_content
        )
        
        print("\n3. Received Structured Proposal:")
        print("="*40)
        print(proposal.model_dump_json(indent=2))
        print("="*40)
        
        print(f"\nDiagnosis: {proposal.diagnosis.probable_cause}")
        print(f"Action: {proposal.proposed_action.operation}")
        print(f"Reason: {proposal.proposed_action.reason}")
        
    except Exception as e:
        print(f"\nFailed to analyze incident: {e}")
        print("Make sure your GROQ_API_KEY is set in the environment or .env file.")

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    main()

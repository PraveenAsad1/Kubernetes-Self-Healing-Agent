import sys
import os
import json
from pprint import pprint

# Add src to Python path so we can import k8s module
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from k8s import k8s_readonly

NAMESPACE = "safeheal-demo"
DEPLOYMENT = "memory-hog"

def main():
    print(f"--- SafeHeal Stage 1: Perception Test ---")
    print(f"Targeting Deployment: {DEPLOYMENT} in Namespace: {NAMESPACE}")
    
    # 1. Identify the relevant pod
    print("\n1. Identifying pods...")
    pods = k8s_readonly.find_pods_for_deployment(NAMESPACE, DEPLOYMENT)
    
    if not pods:
        print("No pods found for deployment. Have you deployed Stage 0?")
        return
        
    pod_name = pods[0]
    print(f"Found pod: {pod_name}")
    
    # 2. Retrieve status
    print("\n2. Retrieving pod status...")
    status = k8s_readonly.get_pod_status(NAMESPACE, pod_name)
    print(json.dumps(status, indent=2))
    
    # 3. Detect OOMKilled
    print("\n3. Checking for OOMKilled...")
    is_oom_killed = False
    if "container_statuses" in status:
        for cs in status.get("container_statuses", []):
            last_state = cs.get("last_state", {})
            if last_state.get("type") == "terminated" and last_state.get("reason") == "OOMKilled":
                print(f"DETECTED: Container '{cs['name']}' was OOMKilled in a previous run! (Exit Code: {last_state.get('exit_code')})")
                is_oom_killed = True
            
            state = cs.get("state", {})
            if state.get("type") == "terminated" and state.get("reason") == "OOMKilled":
                print(f"DETECTED: Container '{cs['name']}' is currently OOMKilled! (Exit Code: {state.get('exit_code')})")
                is_oom_killed = True
                
    if not is_oom_killed:
        print("No OOMKilled detected. Try running `scripts/inject_crash.sh` first.")
    
    # 4. Retrieve logs
    print("\n4. Retrieving pod logs...")
    # If the pod is currently running but previously crashed, we might want previous=True logs
    logs = k8s_readonly.get_pod_logs(NAMESPACE, pod_name, previous=is_oom_killed, tail_lines=20)
    print(logs)
    
    # 5. Retrieve events
    print("\n5. Retrieving pod events...")
    events = k8s_readonly.get_pod_events(NAMESPACE, pod_name)
    print(json.dumps(events[:5], indent=2)) # Print only top 5 recent events
    
    # 6. Retrieve configured memory limit
    print("\n6. Retrieving configured memory limits...")
    limits = k8s_readonly.get_resource_limits(NAMESPACE, DEPLOYMENT)
    print(json.dumps(limits, indent=2))
    
    print("\n--- Perception Test Complete ---")

if __name__ == "__main__":
    main()

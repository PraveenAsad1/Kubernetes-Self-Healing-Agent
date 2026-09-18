import time
import logging
from typing import Tuple
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from .k8s_readonly import get_deployment, find_pods_for_deployment, get_pod_status

logger = logging.getLogger(__name__)

# Ensure config is loaded
try:
    config.load_incluster_config()
except config.ConfigException:
    try:
        config.load_kube_config()
    except config.ConfigException:
        pass

def verify_recovery(namespace: str, deployment_name: str, timeout_seconds: int = 120) -> Tuple[bool, str]:
    """
    Bounded verification loop.
    Checks:
    1. Deployment rollout finishes.
    2. Pods are Ready.
    3. No new OOMKilled events occur.
    Returns (is_recovered, reason).
    """
    start_time = time.time()
    logger.info(f"Starting verification for {namespace}/{deployment_name}...")
    
    while True:
        elapsed = time.time() - start_time
        if elapsed > timeout_seconds:
            return False, f"Verification timeout ({timeout_seconds}s) reached."
            
        try:
            # 1. Check deployment status
            deploy = get_deployment(namespace, deployment_name)
            if "error" in deploy:
                time.sleep(5)
                continue
                
            desired = deploy.get("replicas", 1)
            ready = deploy.get("ready_replicas", 0)
            
            if ready < desired:
                logger.info(f"Waiting for rollout: {ready}/{desired} replicas ready...")
                time.sleep(5)
                continue
                
            # 2. Check pod statuses for OOMKilled
            pods = find_pods_for_deployment(namespace, deployment_name)
            if not pods:
                logger.info("No pods found yet, waiting...")
                time.sleep(5)
                continue
                
            all_ready = True
            oom_recurred = False
            
            for pod_name in pods:
                status = get_pod_status(namespace, pod_name)
                if "error" in status:
                    continue
                    
                # Look for OOMKilled in current or last state
                for cs in status.get("container_statuses", []):
                    if not cs.get("ready"):
                        all_ready = False
                        
                    # Check current state
                    state = cs.get("state", {})
                    if state.get("type") == "terminated" and state.get("reason") == "OOMKilled":
                        oom_recurred = True
                        
                    # Check last state
                    last_state = cs.get("last_state", {})
                    if last_state.get("type") == "terminated" and last_state.get("reason") == "OOMKilled":
                        # If it just OOMKilled recently during this loop
                        oom_recurred = True
            
            if oom_recurred:
                return False, "OOMKilled recurred after applying patch."
                
            if all_ready and ready >= desired:
                # To be absolutely sure, wait a few more seconds to see if it crashes immediately
                if elapsed < 15:
                    logger.info("Rollout complete, waiting a few seconds to ensure stability...")
                    time.sleep(5)
                    continue
                    
                return True, "Deployment rolled out successfully and is stable."
                
        except Exception as e:
            logger.error(f"Error during verification loop: {e}")
            
        time.sleep(5)

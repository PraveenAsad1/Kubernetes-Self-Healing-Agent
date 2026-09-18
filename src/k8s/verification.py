import time
import logging
from typing import Tuple
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from .k8s_readonly import (
    get_deployment,
    find_current_pods_for_deployment,
    get_pod_status,
)

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
                
            desired = deploy.get("replicas") or 1
            ready = deploy.get("ready_replicas") or 0
            updated = deploy.get("updated_replicas") or 0

            if (
                deploy.get("generation") is not None
                and deploy.get("observed_generation") is not None
                and deploy["observed_generation"] < deploy["generation"]
            ):
                logger.info("Waiting for the Deployment controller to observe the rollout...")
                time.sleep(5)
                continue

            if updated < desired:
                logger.info(f"Waiting for updated replicas: {updated}/{desired}...")
                time.sleep(5)
                continue
            
            if ready < desired:
                logger.info(f"Waiting for rollout: {ready}/{desired} replicas ready...")
                time.sleep(5)
                continue
                
            # 2. Check pod statuses for OOMKilled
            pods = find_current_pods_for_deployment(namespace, deployment_name)
            if not pods:
                logger.info("No pods found yet, waiting...")
                time.sleep(5)
                continue
                
            healthy_pods = 0
            oom_recurred = False
            
            for pod_name in pods:
                status = get_pod_status(namespace, pod_name)
                if "error" in status:
                    continue
                    
                # Look for OOMKilled in current or last state
                container_statuses = status.get("container_statuses", [])
                if (
                    status.get("phase") == "Running"
                    and container_statuses
                    and all(
                        cs.get("ready")
                        and cs.get("state", {}).get("type") == "running"
                        for cs in container_statuses
                    )
                ):
                    healthy_pods += 1
                    continue

                for cs in container_statuses:
                    state = cs.get("state", {})
                    if state.get("type") == "terminated" and state.get("reason") == "OOMKilled":
                        oom_recurred = True
                    last_state = cs.get("last_state", {})
                    if last_state.get("type") == "terminated" and last_state.get("reason") == "OOMKilled":
                        oom_recurred = True
            
            if oom_recurred:
                return False, "OOMKilled recurred after applying patch."
                
            if healthy_pods >= desired and ready >= desired:
                # To be absolutely sure, wait a few more seconds to see if it crashes immediately
                if elapsed < 15:
                    logger.info("Rollout complete, waiting a few seconds to ensure stability...")
                    time.sleep(5)
                    continue
                    
                return True, "Deployment rolled out successfully and is stable."
                
        except Exception as e:
            logger.error(f"Error during verification loop: {e}")
            
        time.sleep(5)

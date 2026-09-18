import logging
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from ..agent.schemas import RemediationProposal
from ..safety.policy_engine import evaluate_proposal

logger = logging.getLogger(__name__)

# Ensure config is loaded
try:
    config.load_incluster_config()
except config.ConfigException:
    try:
        config.load_kube_config()
    except config.ConfigException:
        logger.warning("Could not load Kubernetes configuration in patch module.")

apps_v1 = client.AppsV1Api()

def apply_memory_patch(proposal: RemediationProposal) -> bool:
    """
    Safely applies a memory limit patch to a deployment.
    This is the ONLY function authorized to write to Kubernetes.
    """
    # 1. Double check policy approval right before execution
    is_safe, reason = evaluate_proposal(proposal)
    if not is_safe:
        logger.error(f"Execution rejected by safety policy: {reason}")
        return False
        
    action = proposal.proposed_action
    incident = proposal.incident
    
    if action.operation != "increase_memory_limit":
        logger.error(f"Unsupported operation for patching: {action.operation}")
        return False

    namespace = incident.namespace
    deployment_name = action.resource
    new_limit = action.proposed_memory
    
    if not new_limit:
        logger.error("No proposed memory limit provided.")
        return False

    logger.info(f"Applying patch to {namespace}/{deployment_name}: Memory Limit -> {new_limit}")
    
    # Construct the JSON patch for the Deployment
    # We patch the limits of the first container that matches the deployment name, 
    # or just assume the primary container is named identically to the deployment.
    patch = {
        "spec": {
            "template": {
                "spec": {
                    "containers": [
                        {
                            "name": deployment_name,
                            "resources": {
                                "limits": {
                                    "memory": new_limit
                                }
                            }
                        }
                    ]
                }
            }
        }
    }
    
    try:
        apps_v1.patch_namespaced_deployment(
            name=deployment_name,
            namespace=namespace,
            body=patch
        )
        logger.info(f"Successfully patched deployment {deployment_name}.")
        return True
    except ApiException as e:
        logger.error(f"Failed to patch deployment: {e}")
        return False

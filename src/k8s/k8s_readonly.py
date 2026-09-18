from kubernetes import client, config
from kubernetes.client.rest import ApiException
import logging

logger = logging.getLogger(__name__)

# Try to load incluster config first, fallback to kubeconfig
try:
    config.load_incluster_config()
except config.ConfigException:
    try:
        config.load_kube_config()
    except config.ConfigException:
        logger.warning("Could not load Kubernetes configuration.")

core_v1 = client.CoreV1Api()
apps_v1 = client.AppsV1Api()

def get_pod_status(namespace: str, pod_name: str) -> dict:
    """
    Retrieves the status of a specific pod.
    """
    try:
        pod = core_v1.read_namespaced_pod(name=pod_name, namespace=namespace)
        
        status_info = {
            "name": pod.metadata.name,
            "phase": pod.status.phase,
            "container_statuses": []
        }
        
        if pod.status.container_statuses:
            for cs in pod.status.container_statuses:
                state = {}
                if cs.state.running:
                    state = {"type": "running", "started_at": str(cs.state.running.started_at)}
                elif cs.state.terminated:
                    state = {
                        "type": "terminated", 
                        "exit_code": cs.state.terminated.exit_code, 
                        "reason": cs.state.terminated.reason,
                        "message": cs.state.terminated.message
                    }
                elif cs.state.waiting:
                    state = {
                        "type": "waiting",
                        "reason": cs.state.waiting.reason,
                        "message": cs.state.waiting.message
                    }
                    
                last_state = {}
                if cs.last_state.terminated:
                    last_state = {
                        "type": "terminated",
                        "exit_code": cs.last_state.terminated.exit_code,
                        "reason": cs.last_state.terminated.reason,
                        "message": cs.last_state.terminated.message
                    }
                
                status_info["container_statuses"].append({
                    "name": cs.name,
                    "ready": cs.ready,
                    "restart_count": cs.restart_count,
                    "state": state,
                    "last_state": last_state
                })
        
        return status_info
    except ApiException as e:
        logger.error(f"Error getting pod status: {e}")
        return {"error": str(e)}

def get_pod_logs(namespace: str, pod_name: str, previous: bool = False, tail_lines: int = 50) -> str:
    """
    Retrieves the logs of a specific pod.
    If previous is True, gets the logs of the previously terminated container instance.
    """
    try:
        logs = core_v1.read_namespaced_pod_log(
            name=pod_name, 
            namespace=namespace, 
            previous=previous,
            tail_lines=tail_lines
        )
        return logs
    except ApiException as e:
        logger.error(f"Error getting pod logs: {e}")
        return f"Error: {str(e)}"

def get_pod_events(namespace: str, pod_name: str) -> list:
    """
    Retrieves events associated with a specific pod.
    """
    try:
        events = core_v1.list_namespaced_event(
            namespace=namespace,
            field_selector=f"involvedObject.name={pod_name},involvedObject.kind=Pod"
        )
        
        events_list = []
        for event in events.items:
            events_list.append({
                "type": event.type,
                "reason": event.reason,
                "message": event.message,
                "count": event.count,
                "last_timestamp": str(event.last_timestamp) if event.last_timestamp else None
            })
            
        # Sort by timestamp descending
        events_list.sort(key=lambda x: x["last_timestamp"] or "", reverse=True)
        return events_list
    except ApiException as e:
        logger.error(f"Error getting pod events: {e}")
        return [{"error": str(e)}]

def get_deployment(namespace: str, deployment_name: str) -> dict:
    """
    Retrieves the details of a specific deployment.
    """
    try:
        deploy = apps_v1.read_namespaced_deployment(name=deployment_name, namespace=namespace)
        
        return {
            "name": deploy.metadata.name,
            "replicas": deploy.spec.replicas,
            "ready_replicas": deploy.status.ready_replicas,
            "available_replicas": deploy.status.available_replicas,
        }
    except ApiException as e:
        logger.error(f"Error getting deployment: {e}")
        return {"error": str(e)}

def get_resource_limits(namespace: str, deployment_name: str) -> dict:
    """
    Retrieves the configured resource limits and requests for a deployment.
    """
    try:
        deploy = apps_v1.read_namespaced_deployment(name=deployment_name, namespace=namespace)
        
        containers_resources = {}
        for container in deploy.spec.template.spec.containers:
            limits = container.resources.limits or {}
            requests = container.resources.requests or {}
            containers_resources[container.name] = {
                "limits": limits,
                "requests": requests
            }
            
        return containers_resources
    except ApiException as e:
        logger.error(f"Error getting resource limits: {e}")
        return {"error": str(e)}

def find_pods_for_deployment(namespace: str, deployment_name: str) -> list:
    """
    Helper function to find pods belonging to a deployment based on its selector.
    """
    try:
        deploy = apps_v1.read_namespaced_deployment(name=deployment_name, namespace=namespace)
        match_labels = deploy.spec.selector.match_labels
        
        if not match_labels:
            return []
            
        label_selector = ",".join([f"{k}={v}" for k, v in match_labels.items()])
        pods = core_v1.list_namespaced_pod(namespace=namespace, label_selector=label_selector)
        
        return [pod.metadata.name for pod in pods.items]
    except ApiException as e:
        logger.error(f"Error finding pods for deployment: {e}")
        return []

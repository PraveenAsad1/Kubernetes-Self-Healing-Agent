<<<<<<< HEAD
# Self-Heal Hackathon Prototype

Policy-Controlled AI Agent for Safe Kubernetes Self-Healing.

## Stage 0: Environment Setup

This stage provides the foundation for testing OOMKilled issues. We have a deliberately memory-hungry application that can be deployed into a local Minikube/kind cluster.

### Prerequisites

- Docker
- Minikube or kind
- kubectl

### 1. Build the Workload Image

Point your Docker client to Minikube's Docker daemon so the image is available locally without pushing to a registry:

```bash
eval $(minikube docker-env)
# Or for kind: you will need to build the image and load it using `kind load docker-image memory-hog:latest`

cd workload
docker build -t memory-hog:latest .
cd ..
```

### 2. Deploy to Kubernetes

Apply the Kubernetes manifests:

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/rbac.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
```

Check if the pod is running:

```bash
kubectl get pods -n safeheal-demo
```

### 3. Inject the Crash

Once the pod is `Running`, trigger the memory leak:

```bash
bash scripts/inject_crash.sh
```

### 4. Verify OOMKilled

Watch the pod status. It should eventually crash and report `OOMKilled`.

```bash
kubectl get pods -n safeheal-demo -w
```

After the crash, describe the pod to verify the exit code:

```bash
kubectl describe pod -n safeheal-demo -l app=memory-hog
```

You should see:
```text
Reason: OOMKilled
Exit Code: 137
```
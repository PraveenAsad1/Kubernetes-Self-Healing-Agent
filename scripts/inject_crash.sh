#!/bin/bash
set -e

NAMESPACE="safeheal-demo"
APP_LABEL="app=memory-hog"

echo "Looking for pod with label $APP_LABEL in namespace $NAMESPACE..."
POD_NAME=$(kubectl get pods -n $NAMESPACE -l $APP_LABEL -o jsonpath='{.items[0].metadata.name}')

if [ -z "$POD_NAME" ]; then
  echo "Error: Pod not found."
  exit 1
fi

echo "Found pod: $POD_NAME"
echo "Triggering memory allocation..."

# We execute curl inside the pod because the service is ClusterIP and we might not have ingress
kubectl exec -n $NAMESPACE $POD_NAME -- curl -s http://localhost:8080/crash

echo ""
echo "Crash initiated. The pod should run out of memory shortly."
echo "You can monitor it using: kubectl get pods -n $NAMESPACE -w"

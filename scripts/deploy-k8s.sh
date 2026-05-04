#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="${SCRIPT_DIR}/../deployments/helm"

ENVIRONMENT="${1:-staging}"
NAMESPACE="${2:-knowledge-platform}"
IMAGE_TAG="${3:-latest}"

echo "========================================="
echo "Deploying Knowledge Platform to Kubernetes"
echo "Environment: ${ENVIRONMENT}"
echo "Namespace:   ${NAMESPACE}"
echo "Image Tag:   ${IMAGE_TAG}"
echo "========================================="

# Ensure namespace exists
kubectl create namespace "${NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f -

# Deploy with Helm
helm upgrade --install knowledge-platform "${DEPLOY_DIR}" \
  --namespace "${NAMESPACE}" \
  --set backend.image.tag="${IMAGE_TAG}" \
  --set frontend.image.tag="${IMAGE_TAG}" \
  --values "${DEPLOY_DIR}/values.yaml" \
  --wait \
  --timeout 10m

# Wait for rollout
kubectl rollout status deployment/knowledge-platform-backend -n "${NAMESPACE}" --timeout=5m
kubectl rollout status deployment/knowledge-platform-frontend -n "${NAMESPACE}" --timeout=5m

echo "========================================="
echo "Deployment to ${ENVIRONMENT} completed!"
echo "========================================="

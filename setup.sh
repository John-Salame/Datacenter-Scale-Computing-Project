#!/usr/bin/env bash

# Start the cluster
if ! which minikube;
then
  echo "Please start up your cluster manually since you do not have minikube"
fi
minikube start || exit 1
# Allow Docker to push to Minikube local repository
eval $(minikube -p minikube docker-env)
# Start Minio
helm repo add bitnami https://charts.bitnami.com/bitnami
helm install -f minio/minio-config.yaml -n minio-ns --create-namespace minio-proj bitnami/minio
# Install the ingress controller
# https://kubernetes.io/docs/tasks/access-application-cluster/ingress-minikube/
# "To enable the NGINX Ingress controller, run the following command:"
if which minikube;
then
  minikube addons enable ingress
else
  kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.5.1/deploy/static/provider/cloud/deploy.yaml
fi

# bulid the Docker images locally
# Note: rest and worker use grpc built image as a base.
cd grpc
make build
cd ../rest
make build
cd ../worker
make build

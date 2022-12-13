#!/usr/bin/env bash

# Start the cluster
minikube start
# https://kubernetes.io/docs/tasks/access-application-cluster/ingress-minikube/
# "To enable the NGINX Ingress controller, run the following command:"
minikube addons enable ingress
# Allow Docker to push to Minikube local repository
eval $(minikube -p minikube docker-env)
# Start Minio
helm repo add bitnami https://charts.bitnami.com/bitnami
helm install -f minio/minio-config.yaml -n minio-ns --create-namespace minio-proj bitnami/minio
# Install the ingress controller
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.5.1/deploy/static/provider/cloud/deploy.yaml


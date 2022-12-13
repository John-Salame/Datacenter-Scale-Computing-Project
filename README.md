## Fixing local image pull:
https://medium.com/swlh/how-to-run-locally-built-docker-images-in-kubernetes-b28fbc32cc1d

## Directions
Starting the appliction is split into two scripts: setup.sh and deploy-local-dev.sh.
The combined contents are listed in the code block below:
```
# Start the cluster
minikube start
# https://kubernetes.io/docs/tasks/access-application-cluster/ingress-minikube/
# "To enable the NGINX Ingress controller, run the following command:"
minikube addons enable ingress
# Allow Docker to push to Minikube local repository (fix local image pull)
eval $(minikube -p minikube docker-env)
# Start Minio
helm repo add bitnami https://charts.bitnami.com/bitnami
helm install -f minio/minio-config.yaml -n minio-ns --create-namespace minio-proj bitnami/minio
# Install the ingress controller
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.5.1/deploy/static/provider/cloud/deploy.yaml
# Start the deployments, services, ingress, and port forwarding
./deploy-local-dev.sh
```

## Viewing MinIO Buckets
Go to the browser after port forwarding. Type in localhost:9001. Then, use rootuser and rootpass123.

## Debugging
Debug all logs from rest app:
`kubectl log -l app=rest`
Check if ingress is working (make sure it shows an IP address):
`kubectl describe ingress`

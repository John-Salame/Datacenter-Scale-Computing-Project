VERSION=v4
DOCKERUSER="gcr.io/csci-5253-datacenter-scale"

build:
	docker build -f Dockerfile-rest -t rest .

push:
	docker tag demucs-rest $(DOCKERUSER)/rest:$(VERSION)
	docker push $(DOCKERUSER)/rest:$(VERSION)
	docker tag demucs-rest $(DOCKERUSER)/rest:latest
	docker push $(DOCKERUSER)/rest:latest

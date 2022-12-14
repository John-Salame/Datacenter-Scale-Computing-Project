VERSION=protobuf
DOCKERUSER=""

build:
	docker build -f Dockerfile-rest -t rest .
	docker tag rest rest:$(VERSION)

push:
	docker tag rest $(DOCKERUSER)/rest:$(VERSION)
	docker push $(DOCKERUSER)/rest:$(VERSION)
	docker tag rest $(DOCKERUSER)/rest:latest
	docker push $(DOCKERUSER)/rest:latest

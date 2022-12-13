VERSION=v1
DOCKERUSER=""

build:
	docker build -f Dockerfile -t normal-map-protobuf .
	docker tag normal-map-protobuf normal-map-protobuf:$(VERSION)

push:
	docker tag normal-map-protobuf $(DOCKERUSER)/normal-map-protobuf:$(VERSION)
	docker push $(DOCKERUSER)/normal-map-protobuf:$(VERSION)
	docker tag normal-map-protobuf $(DOCKERUSER)/normal-map-protobuf:latest
	docker push $(DOCKERUSER)/normal-map-protobuf:latest

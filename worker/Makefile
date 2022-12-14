VERSION=protobuf
DOCKERUSER=""

build:
	docker build -f Dockerfile -t worker .
	docker tag worker worker:$(VERSION)

push:
	docker tag worker $(DOCKERUSER)/worker:$(VERSION)
	docker push $(DOCKERUSER)/worker:$(VERSION)
	docker tag worker $(DOCKERUSER)/worker:latest
	docker push $(DOCKERUSER)/worker:latest

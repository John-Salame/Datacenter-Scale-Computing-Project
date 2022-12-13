FROM python:3.8

WORKDIR /protobuf
COPY setup.sh .
COPY normalMap.proto .
RUN ./setup.sh
RUN rm setup.sh

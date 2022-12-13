# Dependency: Make sure you build the grpc Docker image first
FROM normal-map-protobuf:latest

# Install additional dependencies into virtual environment before copying to /rest
EXPOSE 5001
RUN venv/bin/pip3 install --upgrade matplotlib numpy minio
RUN mkdir /worker
RUN cp -r ./* /worker

WORKDIR /worker
COPY worker.py .
RUN ls

ENTRYPOINT ["/bin/bash", "--login", "-c"]
CMD ["venv/bin/python3 worker.py"]

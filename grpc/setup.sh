#!/usr/bin/env bash

# Author: John Salame
# Purpose: Download the dependencies required for Google Protobuf

# https://grpc.io/docs/languages/python/quickstart/

python3 -m venv ./venv

# If the virtual environment fails to activate, try installing python3.10-venv and try again.
if ! source venv/bin/activate
then
  echo "-------------------Installing Python virtual environment from apt---------------"
  sudo apt install python3.10-venv
  python3 -m venv ./venv
  source venv/bin/activate || exit 1
fi
echo "Installing grpcio-tools in order to compile the .proto file"
python3 -m pip install --upgrade pip
pip install grpcio
pip install grpcio-tools
# compile the protobuf into client and server code
echo "Compiling the .proto file"
python3 -m grpc_tools.protoc -I. --python_out=. --pyi_out=. --grpc_python_out=. ./normalMap.proto
# exit the Python virtual environment
deactivate

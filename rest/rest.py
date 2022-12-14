from flask import Flask, request, Response, send_file
from minio import Minio
import jsonpickle
import base64
import hashlib
import os
import sys
import io
import time

import grpc
import normalMap_pb2 as normalMap_proto
import normalMap_pb2_grpc as normalMap_gRPC

app = Flask(__name__)
minio_client = Minio("minio:9000", secure=False, access_key='rootuser', secret_key='rootpass123') # use minio as the hostname of the Minio server to talk with

# log the start of the program and log the hostname (should match pod name)
print("REST program starting")
os.system("hostname > hostname.txt")
with open("hostname.txt", "r") as f:
    hostname = f.read()
print(f"Hostname: {hostname}")

# helper function - print log that is visible to kubectl logs
def log(request_id, msg):
    print(f'{request_id} {msg}', file=sys.stderr)

# list the Minio buckets that exist
def list_buckets(request_id):
    try:
        log(request_id, 'list Minio buckets')
        buckets = buckets = minio_client.list_buckets()
        for bucket in buckets:
            log(request_id, f'* Found bucket: {bucket}')
    except Exception as e:
        log(request_id, f'Error listing Minio buckets: {e}')

# create an error response for error code 400 (client-side issue)
def create_bad_request(message):
    return f'<!doctype html><html lang=en><title>400 Bad Request</title>\n<h1>Bad Request</h1><p>{message}</p>'

def create_internal_error(message):
    return f'<!doctype html><html lang=en><title>500 Internal Server Error</title>\n<h1>Internal Server Error</h1><p>{message}</p>'

'''gRPC Client Implementation'''
def initiateWorkerFirstPassthrough(stub, workerInput):
    return stub.normalMapFirstPassthrough(workerInput)

def initiateWorkerFinalPassthrough(stub, workerInput):
    return stub.normalMapFinalPassthrough(workerInput)

'''Begin routing'''
# index page, which also has a form to upload image files
# resource for file uploads: https://www.smashingmagazine.com/2018/01/drag-drop-file-uploader-vanilla-js/
# another resource: https://developer.mozilla.org/en-US/docs/Web/HTML/Element/input/file
@app.route('/', methods=['GET'])
def index():
    return '''
    <form method="POST" enctype="multipart/form-data" action="/produceFirstPassthrough">
      <input type="file" id="fileUpload" name="file" accept="image/*" value=this.files>
      <input type="submit" value="Submit">
    </form>'''

@app.route('/produceFirstPassthrough', methods=['POST'])
def produceFirstPassthrough():
    start = time.perf_counter()
    r = request
    input_bucket = 'input'
    output_bucket = 'first-pass'
    '''
    What to look out for:
    Content-Type: multipart/form-data; boundary=---------------------------5926289141479646928502894430
    '''
    content_type = request.headers['Content-Type']
    if not 'multipart/form-data' in content_type:
        err_msg = create_bad_request('The form must send an image with multipart/form-data encoding.')
        return Response(response=err_msg, status=400, mimetype='text/html')
    # Easily dealing with multipart/form-data: https://www.techiediaries.com/python-requests-upload-file-post-multipart-form-data/
    my_file = r.files['file']
    img = my_file.read() # should be 'bytes object' binary data matching file contents
    in_filename = my_file.filename
    request_id = 'fp' + hashlib.md5((str(start) + in_filename).encode('utf-8')).hexdigest()
    log(request_id, f'/produceFirstPassthrough received file {in_filename}')

    # now, upload the image to Minio

    # First, create the bucket if it does not exist
    try:
        if not minio_client.bucket_exists(input_bucket):
            log(request_id, f'creating bucket "{input_bucket}"')
            minio_client.make_bucket(input_bucket)
            list_buckets(request_id)
    except Exception as e:
        log(request_id, f'error creating bucket {input_bucket} or checking if it exists: {e}')
        list_buckets(request_id)

    # Then, use BytesIO so we can upload the image without creating temporary files
    '''TO-DO: use protobuf to compress the image before sending to Minio'''
    img_stream = io.BytesIO(img)
    # https://stackoverflow.com/questions/26827055/python-how-to-get-bytesio-allocated-memory-length
    file_size = img_stream.getbuffer().nbytes
    log(request_id, f'Saving {in_filename}, file size {file_size} = {round(file_size / 1000, 2)} KB = {round(file_size / 1000000, 1)} MB')
    # https://stackoverflow.com/questions/55223401/minio-python-client-upload-bytes-directly
    minio_client.put_object(input_bucket, in_filename, img_stream, file_size)
    log(request_id, f'Upload input file compete! ({in_filename})')

    # Name the output (first passthrough) file based on the hash of the image
    # https://stackoverflow.com/questions/5297448/how-to-get-md5-sum-of-a-string-using-python
    extension = in_filename[in_filename.rindex('.'):]
    out_filename = hashlib.md5(img).hexdigest() + extension
    log(request_id, f'Signal firstPassthrough worker: {in_filename} -> {out_filename}')
    # Create a new gRPC channel for each request in case the old worker dies
    # later, maybe I can make a global permanent channel that tries to repair itself here if it dies
    with grpc.insecure_channel('worker-svc:5001') as channel:
        normalMapStub = normalMap_gRPC.normalMapStub(channel)
        workerInput = normalMap_proto.gRPCWorkerInput(inFile=in_filename, outFile=out_filename)
        response = initiateWorkerFirstPassthrough(normalMapStub, workerInput)

    end = time.perf_counter()
    delta = (end - start)*1000
    log(request_id, f"First Passthrough (REST) took {delta} ms")
    return Response(response=response.msg, status=response.status, mimetype='text/html')

# start flask app
app.run(host="0.0.0.0", port=5000)

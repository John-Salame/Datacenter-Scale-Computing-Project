from flask import Flask, request, Response, send_file
from minio import Minio
from minio import error as minio_error
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
os.system("hostname > hostname.txt")
with open("hostname.txt", "r") as f:
    hostname = f.read().replace('\n', '')

# https://developers.google.com/protocol-buffers/docs/pythontutorial
# choose the mode for encoding/marshalling data as it goes to/from Minio
protobuf_mode = True
minio_encoder = None
minio_decoder = None
if protobuf_mode:
    minio_encoder = lambda data: normalMap_proto.image(img=data).SerializeToString()
    minio_decoder = lambda data: normalMap_proto.image().FromString(data).img
else:
    minio_encoder = lambda data: data
    minio_decoder = lambda data: data

# helper function - print log that is visible to kubectl logs
def log(request_id, msg):
    print(f'{request_id} {msg}', file=sys.stderr)

# print how long the function took to run
def print_time(request_id, start):
    end = time.perf_counter()
    delta = (end - start)*1000
    log(request_id, f"First Passthrough (REST) took {delta} ms")
    log('-', "--------------------------------------------")

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

def create_not_found():
    return f'<!doctype html><html lang=en><title>404 Not Found</title>\n<h1>Not Found</h1><p>The requested URL was not found on the server. If you entered the URL manually please check your spelling and try again.</p>'

def rest_response(request_id, start, msg, status):
    html_constructor = {
        200: lambda msg: '<p>' + msg + '</p>',
        400: lambda msg: create_bad_request(msg),
        500: lambda msg: create_internal_error(msg)
    }
    log(request_id, msg)
    print_time(request_id, start)
    return Response(response=html_constructor[status](msg), status=status, mimetype='text/html')

def first_passthrough_html(request_id, start, input_bucket, in_filename, output_bucket, out_filename):
    # http://talkerscode.com/howto/how-to-divide-html-page-into-two-parts-horizontally.php
    img_el_input = f'<p>Input</p><image id="input" src="/image/{input_bucket}/{in_filename}">'
    img_el_normal = f'<p>First Passthrough</p><image id="firstPassthrough" src="/image/{output_bucket}/{out_filename}">'
    half_div = '<div style="width: 50%;">'
    page = f'<div>{half_div}{img_el_input}</div>{half_div}{img_el_normal}</div></div>'
    return page

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

@app.route('/image/<string:bucket>/<string:filename>')
def download_image(bucket, filename):
    log('download_image', f'/image/{bucket}/{filename}')
    try:
        response = minio_client.get_object(bucket, filename)
    except Exception as e:
        return create_not_found()
    img = minio_decoder(response.data)
    extension = filename[filename.rindex('.'):]
    return send_file(
        io.BytesIO(img),
        mimetype=f'image/{extension[1:]}'
    )

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
    content_type = r.headers['Content-Type']
    if not 'multipart/form-data' in content_type:
        err_msg = create_bad_request(f'The form must send an image with multipart/form-data encoding.\nForm: {r.data}')
        return rest_response(request_id=fp+str(start), start=start, msg=err_msg, status=400)
    # Easily dealing with multipart/form-data: https://www.techiediaries.com/python-requests-upload-file-post-multipart-form-data/
    my_file = r.files['file']
    img = my_file.read() # should be 'bytes object' binary data matching file contents
    in_filename = my_file.filename
    request_id = 'fp' + hashlib.md5((str(start) + in_filename).encode('utf-8')).hexdigest()
    log(request_id, f'/produceFirstPassthrough received file {in_filename}')
    # Name the output (first passthrough) file based on the hash of the image
    # https://stackoverflow.com/questions/5297448/how-to-get-md5-sum-of-a-string-using-python
    extension = in_filename[in_filename.rindex('.'):]
    out_filename = hashlib.md5(img).hexdigest() + extension

    # Create the Minio bucket if it does not exist
    try:
        if not minio_client.bucket_exists(input_bucket):
            log(request_id, f'creating bucket "{input_bucket}"')
            minio_client.make_bucket(input_bucket)
            list_buckets(request_id)
    except Exception as e:
        log(request_id, f'error creating bucket {input_bucket} or checking if it exists: {e}')
        list_buckets(request_id)

    # if the file already has a normal map. We do this instead of checking for the input file because we want to return error 400 from the worker if input is not an image.
    try:
        minio_client.stat_object(output_bucket, out_filename)
        log(request_id, f'{in_filename} already exists! Skipping upload.')
        page = first_passthrough_html(request_id, start, input_bucket, in_filename, output_bucket, out_filename)
        return rest_response(request_id, start, msg=page, status=200)
    except minio_error.S3Error as s3_err:
        if not (s3_err.code == 'NoSuchKey' or s3_err.code == 'NoSuchBucket'):
            err_msg = f'Exception listing Minio file {in_filename}: {s3_err}'
            return rest_response(request_id, start, msg=err_msg, status=500)
    except Exception as e:
        log(request_id, type(e))
        err_msg = f'Exception listing Minio file {in_filename}: {e}'
        return rest_response(request_id, start, msg=err_msg, status=500)

    # Upload the file to Minio
    # Use BytesIO so we can upload the image without creating temporary files
    img_stream = io.BytesIO(minio_encoder(img))
    # https://stackoverflow.com/questions/26827055/python-how-to-get-bytesio-allocated-memory-length
    file_size = img_stream.getbuffer().nbytes
    log(request_id, f'Saving {in_filename}, file size {file_size} = {round(file_size / 1000, 2)} KB = {round(file_size / 1000000, 1)} MB')
    # https://stackoverflow.com/questions/55223401/minio-python-client-upload-bytes-directly
    minio_client.put_object(input_bucket, in_filename, img_stream, file_size)
    log(request_id, f'Upload input file compete! ({in_filename})')
    log(request_id, f'Signal firstPassthrough worker: {in_filename} -> {out_filename}')
    # Create a new gRPC channel for each request in case the old worker dies
    # later, maybe I can make a global permanent channel that tries to repair itself here if it dies
    with grpc.insecure_channel('worker-svc:5001') as channel:
        normalMapStub = normalMap_gRPC.normalMapStub(channel)
        workerInput = normalMap_proto.gRPCWorkerInput(inFile=in_filename, outFile=out_filename)
        response = initiateWorkerFirstPassthrough(normalMapStub, workerInput)
    # If the worker succeeded, then return an HTML image
    if response.status == 200:
        page = first_passthrough_html(request_id, start, input_bucket, in_filename, output_bucket, out_filename)
        return rest_response(request_id, start, msg=page, status=200)

    # For status other than 200, return the error from the worker
    return rest_response(request_id, start, msg=response.msg, status=response.status)

# log the start of the program and log the hostname (should match pod name)
print("REST program starting")
print(f"Hostname: {hostname}")
log('worker', f"Protobuf encoding/decoding on Minio: {protobuf_mode}")
# start flask app
app.run(host="0.0.0.0", port=5000)

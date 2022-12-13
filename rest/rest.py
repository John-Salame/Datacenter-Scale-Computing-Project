from flask import Flask, request, Response, send_file
from minio import Minio
import jsonpickle
import base64
import hashlib
import os
import sys
import io
import time

app = Flask(__name__)
minio_client = Minio("minio:9000", secure=False, access_key='rootuser', secret_key='rootpass123') # use minio as the hostname of the Minio server to talk with

# log the start of the program
print("REST program starting")
os.system("hostname > hostname.txt")
with open("hostname.txt", "r") as f:
    hostname = f.read()
print(f"Hostname: {hostname}")

# helper function - print log that is visible to kubectl logs
def log(msg):
    print(msg, file=sys.stderr)

# list the Minio buckets that exist
def list_buckets():
    try:
        log('list Minio buckets')
        buckets = buckets = minio_client.list_buckets()
        for bucket in buckets:
            log(f'* Found bucket: {bucket}')
    except Exception as e:
        log(f'Error listing Minio buckets: {e}')

# create an error response
def create_bad_request(message):
    return f'<title>400 Bad Request</title>\n<h1>Bad Request</h1><p>{message}</p>'

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
    output_bucket = 'first_pass'
    '''
    What to look out for:
    Content-Type: multipart/form-data; boundary=---------------------------5926289141479646928502894430
    '''
    content_type = request.headers['Content-Type']
    if not 'multipart/form-data' in content_type:
        err_msg = create_bad_request('The form must send an image with multipart/form-data encoding.')
        return Response(response=err_msg, status=400, mimetype='text/plain')
    # Easily dealing with multipart/form-data: https://www.techiediaries.com/python-requests-upload-file-post-multipart-form-data/
    log('File is {}'.format(r.files['file']))
    my_file = r.files['file']
    img = my_file.read() # should be 'bytes object' binary data matching file contents
    in_filename = my_file.filename
    log(f'/produceFirstPassthrough received file {in_filename}')

    # now, upload the image to Minio

    # First, create the bucket if it does not exist
    try:
        if not minio_client.bucket_exists(input_bucket):
            log(f'creating bucket "{input_bucket}"')
            minio_client.make_bucket(input_bucket)
            list_buckets()
    except Exception as e:
        log(f'error creating bucket or checking if it exists: {e}')
        list_buckets()

    # Then, use BytesIO so we can upload the image without creating temporary files
    '''TO-DO: use protobuf to compress the image before sending to Minio'''
    img_stream = io.BytesIO(img)
    # https://stackoverflow.com/questions/26827055/python-how-to-get-bytesio-allocated-memory-length
    file_size = img_stream.getbuffer().nbytes
    log(f'Saving {in_filename}, file size {file_size} = {round(file_size / 1000, 2)} KB = {round(file_size / 1000000, 1)} MB')
    # https://stackoverflow.com/questions/55223401/minio-python-client-upload-bytes-directly
    minio_client.put_object(input_bucket, in_filename, img_stream, file_size)
    log(f'Upload input file compete! ({in_filename})')

    # Name the output (first passthrough) file based on the hash of the image
    # https://stackoverflow.com/questions/5297448/how-to-get-md5-sum-of-a-string-using-python
    extension = in_filename[in_filename.rindex('.'):]
    out_filename = hashlib.md5(img).hexdigest() + extension
    log(f'(TO-DO) Sending {in_filename} to worker to produce intermediate normal map {out_filename}')

    end = time.perf_counter()
    delta = (end - start)*1000
    log(f"First Passthrough took {delta} ms")
    return Response(response='OK', status=200, mimetype='text/plain')

# start flask app
app.run(host="0.0.0.0", port=5000)

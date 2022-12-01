from flask import Flask, request, Response, send_file
from minio import Minio
import jsonpickle
import base64
import os

app = Flask(__name__)
# minio_client = Minio("minio:9000", secure=False, access_key='rootuser', secret_key='rootpass123') # use minio as the hostname of the Minio server to talk with

# log the start of the program
print("REST program starting")

'''Begin routing'''
# resource for file uploads: https://www.smashingmagazine.com/2018/01/drag-drop-file-uploader-vanilla-js/
@app.route('/', methods=['GET'])
def health_check():
    return '''
    <form method="POST" action="/upload">
      <input type="file" id="fileUpload" name="file" multiple accept="image/*">
      <input type="submit" value="Submit">
    </form>'''

@app.route('/apiv1/separate', methods=['POST'])
def separate():
    bucket_name = 'demucs-bucket'
    r = request
    log_info("Handling a request /apiv1/separate")
    # song binary data
    req_data = jsonpickle.decode(r.data)
    print("Request data keys:", req_data.keys)
    song = base64.b64decode(req_data['mp3'])
    song_hash = hash(song)
    filename = str(song_hash) + '.mp3'
    # save the song to a temporary file so we can upload it to the bucket
    if not os.path.exists('./tmp'):
        os.mkdir('./tmp')
    tmpfile = f"tmp/{filename}"
    with open(tmpfile, 'wb') as f:
        f.write(song)
    print(f"Saved tmp file {tmpfile}")
    # create the bucket if necessary
    try:
        print('checking if bucket exists')
        if not minio_client.bucket_exists(bucket_name):
            log_info(f'creating bucket {bucket_name}')
            minio_client.make_bucket(bucket_name)
    except Exception as e:
        print(f'error creating bucket or checking if it exists: {e}')
    # debug the buckets
    try:
        print('debugging minio buckets')
        buckets = buckets = minio_client.list_buckets()
        for bucket in buckets:
            print(f'bucket {bucket}')
    except Exception as e:
        print(f'error listing minio buckets: {e}')
    # upload song to bucket
    print(f"Attempting to upload file {filename} to minio")
    try:
        minio_client.fput_object(bucket_name, filename, tmpfile)
        print(f"Uploaded file {filename} to minio")
    except Exception as e:
        print("Exception trying to upload file to minio: %s" % str(e))
    # upload the filename to redis toWorker queue
    redisClient.lpush('toWorker', filename)
    print(f"Pushed {filename} to Redis toWorker queue")
    # delte the temporary file
    os.unlink(tmpfile)
    print(f"Deleted tmp file {tmpfile}")
    # send the file hash to the requester
    response_pickled = jsonpickle.encode({'songhash': song_hash})
    return Response(response=response_pickled, status=200, mimetype="application/json")

@app.route('/apiv1/queue', methods=['GET'])
def queue():
    pass

@app.route('/apiv1/track/track', methods=['GET'])
def get_track():
    pass

@app.route('/apiv1/remove/track', methods=['GET'])
def remove_track():
    pass

# start flask app
app.run(host="0.0.0.0", port=5000)

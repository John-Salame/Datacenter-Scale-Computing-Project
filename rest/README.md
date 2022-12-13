# REST API and interface

## Links
* Using [sendfile to send binary response](https://stackoverflow.com/questions/11017466/flask-to-return-image-stored-in-database)
* Encoding data in [base64 form](https://docs.python.org/3/library/base64.html)

## REST API Endpoints
The REST routes are:
+ /produceFirstPassthrough[POST]: upload an image using a file input in an HTML form. The request has Content-Type 'multipart/form-data' and looks like the image 'Example produceFirstPassthrough Request.png.' The REST endpoint uploads the file to Minio and then passes the filename of the input file and the desired filename of the first passthrough normal map to the worker program. Make sure to encode the file using Google Protocol Buffer before uploading to Minio.

## Limitations
1. Saving two files with the same name will overwrite the first one. The Minio data store will still have all the normal maps because the names of the normal maps are based on image hashes. However, the input files will not be preserved if multiple files with the same name are uploaded. 
If I have time, maybe I could add a feature where the web server returns a bunch of images if the choice is ambigious and then lets you choose one to use as input. It would send a pairing of input image name (in an HTML image tag) and intermediate normal map name (as an image ID or attribute).
2. Another limitation is that the program will break if multiple files have the same hash, since I only use the hash and not the name of the original file when I am creating normal maps or looking for existing normal maps.

## Time and Space Case Studies
With only Minio file upload (no database/using cached results, no gRPC, no protobuf, no HTML content returned), these are the results:
* Total Request Time: 37.26 ms average over 5 iterations (according to the timers in rest.py), or 65.19 ms average using the `time_program.py` script.
* * Using `time python3 time_program.py` in the command line, we see that 45% of the time was taken by system and 55% of time was taken by the user, so the user took roughly 35.8 seconds per request.
* Time taken by REST server: 65.19 ms
* Time taken by worker: N/A
* Space (Minio): 192.1 KB (actual image size: 196.7 KB) for 256x256x24 byte RGB bitmap image.
Note: Minio is set to encrypt its contents. Perhaps this somehow shrunk the file size. Everything looks correct when I download it.

With firstPass (but no MongoDB, no protobuf in Minio, and no HTML content returned), these are the results:
* Total Request Time: 123.43 ms average using the `time_program.py` script.
* Time taken by REST server: 90.56 ms (averaging the last 5 results)
* Time taken by worker: 51.78 ms (averaging the last 5 results)
* This means REST server independently took 90.56-51.78 = 38.78 ms to run while not waiting for the worker to finish.


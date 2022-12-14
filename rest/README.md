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
2. Another limitation is that the program will break if multiple files have the same hash (of file contents), since I only use the hash and not the name of the original file when I am creating normal maps or looking for existing normal maps.

# CSCI 5253 Datacenter Scale Computing Final Project
Author: John Salame  
Code and report due Wed. 12/14/22

## Set Up and Run
Here is how to run the program. I use minikube to create my cluster, so if you do not, then modify setup.sh as appropriate.
```
source setup.sh
./deploy-local-dev.sh
```

## Debugging
Debug all logs from rest app:
`kubectl log -l app=rest`
Debug all logs from workers:
`kubectl log -l app=worker`
Check if ingress is working (make sure it shows an IP address):
`kubectl get ingress`
`kubectl describe ingress rest-ingress`
### Viewing MinIO Buckets
Go to the browser after port forwarding. Type in localhost:9001. Then, use rootuser and rootpass123.

## Limitations
Read [the REST README](./rest/README.md) about limitations of the program.

## Time and Space Case Studies
### Python Timing Script
Go to [the input images README](./input_images/README.md) to read more about the timing script.


### Results
#### Simple first passthrough on REST
With only Minio file upload from first passthrough on REST (no database/using cached results, no gRPC, no protobuf, no HTML content returned), these are the results:

*  Total Request Time: 37.26 ms average over 5 iterations (according to the timers in rest.py), or 65.19 ms average using the `time_program.py` script (100 iterations).
* * Using `time python3 time_program.py` in the command line, we see that 45% of the time was taken by system and 55% of time was taken by the user, so the user took roughly 35.8 seconds per request.
* Time taken by REST server: 65.19 ms
* Time taken by worker: N/A
* Space (Minio): 192.1 KB (actual image size: 196.7 KB) for 256x256x24 byte RGB bitmap image.
Note: Minio is set to encrypt its contents. Perhaps this somehow shrunk the file size. Everything looks correct when I download it.

#### Introduction of Worker
With partial first passthrough on REST + worker (no MongoDB, no protobuf in Minio, and no HTML content returned), these are the results:

* Total Request Time: 123.43 ms average using the `time_program.py` script, 100 iterations.
* Time taken by REST server: 90.56 ms (averaging the last 5 results)
* Time taken by worker: 51.78 ms (averaging the last 5 results)
* This means REST server independently took 90.56-51.78 = 38.78 ms to run while not waiting for the worker to finish.
* Space (Minio): 192.1 KB for 256x256x24 byte RGB bitmap image (same as before).

#### Variety of input files
##### Variety: Requests in Series
With the potential for failure (uploading files that are not images) and varying file sizes, these are the results:

* We have now introduced different file sizes, as well as non-images which make the worker return early.
* I have also introduced more error handling and more overhead to the worker and REST server due to logging, error handling, and packaging responses.
* I have also added a shortcut to detect if another thread is handling the same output file as you in case multiple concurrent requests are coming in.
* I also noticed that candyCane.bmp takes longer due to its special condition in the worker, and Grass Normal Map takes longer due to its .png file type; (for worker) candyCane.bmp takes 80-100 ms, while snow takes 30-50 ms and Grass Normal map takes more than 90 ms.
* Total Request Time using the `time_program.py` script (100 iterations):
* * 77.81 ms for all files
* * 99.32 ms for images
* * 34.63 ms for non-images
* Time taken by REST server: 
* * 106.50 ms for images (averaging the last 5 results)
* * 19.95 ms for non-images (averaging the last 5 results)
* Time taken by worker:
* * 71.62 seconds for images (averaging the last 5 results)
* * 4.57 ms for non-images (averaging the last 5 results)

##### Variety: Requests in Parallel
Now we run two timing scripts in parallel with 50 requests each.

* Total Request Time using the `time_program.py` script (100 iterations):
* * 107.48 ms for all files
* * 136.59 ms for images
* * 54.41 ms for non-images
* Time taken by REST server:
* * 126.54 ms for images (averaging the last 5 results)
* * 50.14 ms for non-images (averaging the last 5 results)
* Time taken by worker:
* * 104.16 seconds for images (averaging the last 5 results)
* * 8.64 ms for non-images (averaging the last 5 results)

With 4 scripts in parallel doing 25 requests each, the time per request jumps even higher. With 4 clients at once, the average request time is as follows:

* 170.75 ms for all files
* 222.39 ms for images
* 86.68 ms for non-images

#### Timing with Encoding and Decoding Minio Data
First, we will set up the infrastructure without encoding / decoding with protobuf. We simply use a lambda expression which returns the input (minio_encoder = minio_decoder = lambda data: data).  
The file size is still the same as before. In particular, the only file size which changes between the input file and the generated normal map is 'Grass Normal Map.png' since a png uses compression. The size of this file right now is 216.9 KiB (input) and 64.5 KiB (output).

With Google Protocol Buffer encoding and decoding Minio files, the file size does not change much or change at all. However, somehow the queries sped up again. I am not sure what could have caused this, since the network transfer time should be the same and the CPU overhead should be greater than before.

* 77.91 ms for all files
* 94.20 ms for images
* 38.60 ms for non-images




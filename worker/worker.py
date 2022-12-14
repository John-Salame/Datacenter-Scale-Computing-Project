from concurrent import futures
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.image
import sys
import os
from PIL import Image
import io
import time
import random
import hashlib

from minio import Minio
import grpc
import normalMap_pb2 as normalMap_proto
import normalMap_pb2_grpc as normalMap_gRPC

# Globals: put minio client and container hostname in the closure of all the functions
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

'''Helper functions'''
# helper function - print log that is visible to kubectl logs
def log(request_id, msg):
    print(f'{request_id} {msg}', file=sys.stderr)

# print how long the function took to run
def print_time(request_id, start):
    end = time.perf_counter()
    delta = (end - start)*1000
    log(request_id, f"First Passthrough (worker) took {delta} ms")
    log('-', "--------------------------------------------")
    sys.stderr.flush()

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

def rest_response(request_id, start, msg, status):
    html_constructor = {
        200: lambda msg: '<p>' + msg + '</p>',
        400: lambda msg: create_bad_request(msg),
        500: lambda msg: create_internal_error(msg)
    }
    log(request_id, msg)
    print_time(request_id, start)
    return normalMap_proto.restResponse(msg=html_constructor[status](msg), status=status)

'''Logic for creating normal maps'''

# Assumption is that gray areas are indented and white areas are just normal.
# This assumption works for snow and candy cane.

# white stripes take a value equal to the average of the area minus 20
def convert_white_stripes_to_indent(k, img):
    # k is the radius of kernel for average
    img = img.astype('double')
    shape = img.shape
    w = shape[1]
    h = shape[0]
    for i in range(k, h-k):
        for j in range(k, w-k):
            if img[i,j] > 200:
                img[i,j] = np.average(img[i-k:i+k,j-k:j+k]) - 20
    return img.astype('uint8')

# if the right side is brighter, normal is to left (negative red). Thus, we subtract pixel intensities on the right and add intensities on the left.
# the kernel is size k (radius)
def red_normal(k, img):
    # first, create the margins
    shape = img.shape
    w = shape[1]
    h = shape[0]
    img_pad = np.zeros((h+2*k, w+2*k), dtype=float)
    w = img_pad.shape[1]
    h = img_pad.shape[0]
    # duplicate image to center of padded image
    img_pad[k:(h-k), k:(w-k)] = img.astype('float')
    # duplicate first and last rows to padding
    for i in range(k):
        img_pad[i, :] = img_pad[k, :]
        img_pad[h-1-i, :] = img_pad[h-k-1, :]
    # duplicate first and last columns to padding
    for j in range(k):
        img_pad[:, j] = img_pad[:, k]
        img_pad[:, w-1-j] = img_pad[:, w-k-1]
    
    # Now that we have our padded image, normalize the image
    my_avg = np.average(img_pad)
    # normalize to [-1.0, 1.0] with the mean at 0
    img_pad = img_pad - my_avg
    my_max = np.amax(img_pad)
    my_min = np.amin(img_pad)
    my_range = my_max - my_min
    # img_pad[img_pad > 0] = img_pad[img_pad > 0] / my_max
    # img_pad[img_pad < 0] = -1.0 * img_pad[img_pad < 0] / my_min
    img_pad = img_pad / my_range
    print('max intensity %f' % np.amax(img_pad))
    print('min intensity %f' % np.amin(img_pad))
    print('avg intensity %f' % np.average(img_pad))

    # create the kernel
    # The kernel should be (k*2+1 by k*2+1), but I will make int only one row wide and use a trick
    # coef = 1 / (2*k+1)
    coef = 1/(2*k+1)
    kernel = np.zeros((1, 2*k+1))
    kernel[:, 0:k] = coef
    kernel[:, (k+1):] = -1 * coef
    print(kernel)

    # apply the kernel to columns of the padded matrix
    red_img = np.zeros(img_pad.shape)
    for j in range(w-2*k):
        cur_cols = img_pad[:, j:(j+1+2*k)]
        red_img[:, j+k] = np.sum(img_pad[:, j:(j+1+2*k)] * kernel, axis=1) # element-wise multiplication
    # now average over the vertical part of the kernel
    red_img_old = red_img
    vertical_convolution = np.abs(np.transpose(kernel))
    for i in range(h-2*k):
        red_img[i+k, :] = np.sum(red_img_old[i:(i+1+2*k), :] * vertical_convolution, axis=0) # add the rows belonging to the kernel, centered at i+k
    '''
    # now, smooth horizontally
    red_img_old = red_img
    smoothing = np.abs(kernel)
    for j in range(w-2*k):
        cur_cols = img_pad[:, j:(j+1+2*k)]
        red_img[:, j+k] = np.sum(red_img_old[:, j:(j+1+2*k)] * smoothing, axis=1) # element-wise multiplication
    '''
    # now, keep only the original image dimensions
    red_img = red_img[k:(h-k), k:(w-k)]
    print(red_img.shape)
    print('max red %f' % np.amax(red_img))
    print('min red %f' % np.amin(red_img))
    print('avg red %f' % np.average(red_img))
    # shift the mean over to 0.5 and call it a day. It should be fine as long as in and max do not exceet [-0.5, 0.5]
    my_avg = np.average(red_img)
    red_img = red_img + 0.5 - my_avg
    red_img = red_img * 255
    print('max red %f' % np.amax(red_img))
    print('min red %f' % np.amin(red_img))
    print('avg red %f' % np.average(red_img))
    return red_img.astype('uint8')

# request is of type gRPCWorkerInput
# request.inFile is the name of the original uploaded file (texture)
# request.outFile is the name of the first pass normal map that will be created (has the inFile image hash in the name)
class normalMapServicer(normalMap_gRPC.normalMapServicer):
    def normalMapFirstPassthrough(self, request, context):
        start = time.perf_counter()
        k = 3 # radius of kernel
        # pull the image from Minio
        input_bucket = 'input'
        output_bucket = 'first-pass'
        in_file = request.inFile
        out_file = request.outFile
        request_id = 'fp' + hashlib.md5((str(start) + out_file).encode('utf-8')).hexdigest()
        log(request_id, "handle first passthrough")
        if os.path.exists(out_file):
            # if the file already exists, then some other thread is working on uploading it.
            # skip the upload and just return 200 OK
            # the danger is that nobody will ever upload the file if one worker fails to unlink the local file
            # Therefore, later in the code, we try to unlink the file until is works.
            return rest_response(request_id, start, msg=f'Worker {hostname} creating normal map {out_file} for {in_file} in another thread', status=200)
        try:
            # response is a urllib3 response object; we get the file as response.data.
            response = minio_client.get_object(input_bucket, in_file)
            img_raw = minio_decoder(response.data) # img_raw is still in the file format as a bytes object, not a numpy array of RGB values
            img_stream = io.BytesIO(img_raw)
            file_size = img_stream.getbuffer().nbytes
            log(request_id, f'downloaded {in_file}, file size {file_size} = {round(file_size / 1000, 2)} KB = {round(file_size / 1000000, 1)} MB')
        except Exception as e:
            err_msg = f'error downloading {in_file} from Minio: {e}'
            return rest_response(request_id, start, msg=err_msg, status=500)
        try:
            # turn into numpy array of RGB values
            img = np.asarray(Image.open(img_stream))
            img_stream.close()
        except Exception as e:
            err_msg = f'File {in_file} is not an image!'
            return rest_response(request_id, start, msg=err_msg, status=400)
        
        # File is an image! Pre-emptively create the bucket
        try:
            if not minio_client.bucket_exists(output_bucket):
                log(request_id, f'creating bucket "{output_bucket}"')
                minio_client.make_bucket(output_bucket)
                list_buckets(request_id)
        except Exception as e:
            err_msg = f'error creating bucket {output_bucket} or checking if it exists: {e}'
            list_buckets(request_id)
            return rest_response(request_id, start, msg=err_msg, status=500)
        
        # let other threads know that you're servicing the request for the output normal map
        # make sure you delete/unlink this file in the "except" statement of any error-causing code.
        # Note: there is a race where multiple threads pass the early check for ./out_file before it is created.
        # I don't really have a good way to deal with the race condition. I'll just put try/catch around anything that requires the file out_file to exist
        with open(out_file, 'w') as f:
            f.write('busy')

        '''Normal map creation'''
        # keep intensities only (b here stands for brightness)
        img_b = np.zeros((img.shape[0], img.shape[1]), dtype=np.uint8)
        img_b = 0.33*img[:,:,0] + 0.33*img[:,:,1] + 0.33*img[:,:,2]
        # Special case for candy cane: create a depression where the white slash on the texture is
        if in_file == 'candyCane.bmp':
            img_b = convert_white_stripes_to_indent(k, img_b)
        reds = red_normal(k, img_b)
        # now, create the normal map
        normal_map = np.full(img.shape, 128, dtype=np.uint8)
        normal_map[:,:,0] = reds
        normal_map[:,:,2] = 255 # z should be fully out for all parts

        # use BytesIO to encode the image data and send it to Minio
        err_msg = ''
        im = Image.fromarray(normal_map)
        extension = out_file[out_file.rindex('.'):]
        # https://jdhao.github.io/2019/07/06/python_opencv_pil_image_to_bytes/
        # write image data into the BytesIO so we can encode it, then save it in the file we will upload.
        minio_data_pre_encoding = io.BytesIO()
        im.save(minio_data_pre_encoding, format=extension[1:])
        # minio_data = minio_encoder(minio_data_pre_encoding.getvalue())
        minio_data = io.BytesIO(minio_encoder(minio_data_pre_encoding.getvalue()))
        '''
        with open(out_file, 'wb') as f:
            f.write(minio_data)
        '''
        try:
            # file_size = os.path.getsize(out_file)
            file_size = minio_data.getbuffer().nbytes
        except Exception as e:
            err_msg = f'Error getting file size of file to upload (race condition area): {e}'
            return rest_response(request_id, start, msg=err_msg, status=500)
        # now, actually upload
        log(request_id, f'Saving {out_file}, file size {file_size} = {round(file_size / 1000, 2)} KB = {round(file_size / 1000000, 1)} MB')
        try:
            # minio_client.fput_object(output_bucket, out_file, out_file)
            minio_client.put_object(output_bucket, out_file, minio_data, file_size)
            minio_data_pre_encoding.close()
            minio_data.close()
        except Exception as e:
            err_msg = f'Worker firstPass: Error uploading to output bucket: {e}'
        # delete the image we saved
        while os.path.exists(out_file):
            try:
                os.unlink(out_file)
            except Exception as e:
                err_msg = f'Error deleting file (race condition area): {e}'
        if err_msg:
            return rest_response(request_id, start, msg=err_msg, status=500)

        # return success 200
        return rest_response(request_id, start, msg=f'Worker {hostname} created normal map {out_file} for {in_file}', status=200)


'''Now, bind the gRPC services to the server'''
# log the start of the program and log the hostname (should match pod name)
log('worker', "Worker program starting")
log('worker', f"Hostname: {hostname}")
log('worker', f"Protobuf encoding/decoding on Minio: {protobuf_mode}")
sys.stderr.flush()
# start the gRPC server and add the servicer to the server
server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
normalMap_gRPC.add_normalMapServicer_to_server(normalMapServicer(), server)
server.add_insecure_port('[::]:5001')
server.start()
server.wait_for_termination()

'''
def main():
    # plot the image and normal map side-by-side
    plt.subplot(1, 2, 1)
    plt.imshow(img)
    plt.title('Original texture')
    plt.subplot(1, 2, 2)
    # plt.imshow(img_b, cmap=plt.get_cmap('gray'))
    plt.imshow(normal_map)
    plt.colorbar()
    plt.title('Normal Map')
    plt.show()
    saveyn = input('save image? (y/n) ')
    if saveyn.upper() == 'Y':
        neutralRed = int(input('Decimal value for neutral red (enter 0 for no change): '))
        if neutralRed > 0:
            normal_map[:,:,0] += np.uint8(128 - neutralRed)
        extension_index = in_file.find('.bmp')
        out_file = in_file[:extension_index] + '_normal' + in_file[extension_index:]
        log("Saving normal map to file %s" % out_file)
        im = Image.fromarray(normal_map)
        im.save(out_file)
    return 0

if __name__ == "__main__":
    if len(sys.argv) < 1:
        raise Exception("Missing command line argument for input file name")
        sys.exit(1)
    in_file = sys.argv[1]
    if len(sys.argv) > 2:
        k = int(sys.argv[2])
    else:
        k = 3
    log("Kernel is %d" % k)
    exit_status = main()
    sys.exit(exit_status)
'''

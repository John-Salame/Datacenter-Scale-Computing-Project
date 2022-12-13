from concurrent import futures
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.image
import sys
import os
from PIL import Image
import io
import time

from minio import Minio
import grpc
import normalMap_pb2 as normalMap_proto
import normalMap_pb2_grpc as normalMap_gRPC

# Put minio client in the closure of all the functions
minio_client = Minio("minio:9000", secure=False, access_key='rootuser', secret_key='rootpass123') # use minio as the hostname of the Minio server to talk with

# log the start of the program and log the hostname (should match pod name)
print("Worker program starting")
os.system("hostname > hostname.txt")
with open("hostname.txt", "r") as f:
    hostname = f.read()
print(f"Hostname: {hostname}")


'''Helper functions'''
# helper function - print log that is visible to kubectl logs
def log(msg):
    print(msg)

# list the Minio buckets that exist
def list_buckets():
    try:
        log('list Minio buckets')
        buckets = buckets = minio_client.list_buckets()
        for bucket in buckets:
            log(f'* Found bucket: {bucket}')
    except Exception as e:
        log(f'Error listing Minio buckets: {e}')

# create an error response for error code 400 (client-side issue)
def create_bad_request(message):
    return f'<title>400 Bad Request</title>\n<h1>Bad Request</h1><p>{message}</p>'


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
        output_bucket = 'first_pass'
        in_file = request.inFile
        out_file = request.outFile
        response = minio_client.get_object(input_bucket, in_file)
        log(f'Minio get object data type: {type(response)}')
        sys.stdout.flush()
        img_raw = response.data # img_raw is still in the file format, not a numpy array
        img_stream = io.BytesIO(img_raw)
        log(f'Image data type: {type(response.data)}')
        sys.stdout.flush()
        try:
            img = np.asarray(Image.open(img_stream))
        except Exception as e:
            return normalMap_proto.restResponse(msg=create_bad_request(f'File {in_file} is not an image!'), status=400)
        log(f'After opening, image has type {type(img)}')
        sys.stdout.flush()
        log(img.shape)
        sys.stdout.flush()
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

        # now, upload the first passthrough normal map to Minio

        # First, create the bucket if it does not exist
        try:
            if not minio_client.bucket_exists(output_bucket):
                log(f'creating bucket "{output_bucket}"')
                minio_client.make_bucket(output_bucket)
                list_buckets()
        except Exception as e:
            log(f'error creating bucket or checking if it exists: {e}')
            list_buckets()

        # upload the image to Minio
        im = Image.fromarray(normal_map)
        log(f'image before saving has data type {type(im)}')
        sys.stdout.flush()
        # save to image stream instead of saving to a temp file
        with io.BytesIO() as img_stream:
            im.save(img_stream)
        file_size = img_stream.getbuffer().nbytes
        log(f'Saving {in_filename}, file size {file_size} = {round(file_size / 1000, 2)} KB = {round(file_size / 1000000, 1)} MB')
        minio_client.put_object(output_bucket, out_filename, img_stream, file_size)

        end = time.perf_counter()
        delta = (end - start)*1000
        log(f"First Passthrough (worker) took {delta} ms")
        # return success 200
        return normalMap_proto.restResponse(msg=f'Worker {hostname} created normal map {out_file} for {in_file}', status=200)


'''Now, bind the gRPC services to the server'''
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

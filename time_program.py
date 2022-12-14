import os
import sys
import random
import time

pid = os.getpid()
host = os.environ.get('INGRESS') or 'localhost:5000'
log_prefix = f'[{pid}] '

def log(msg):
    print(f'{log_prefix}{msg}')

def help():
    print("Usage: [number of reps] [image | non-image]")
    print("Defult behavior is 100 reps and a mix of images and non-images.")
    print("Each line of output is preceded by the pid of the process.")

# Do queries in series. Later, I may run two scripts at the same time or do a fork in this script to simulate simultaneous requests.
reps = 100
mode = ''
if len(sys.argv) > 1:
    arg = sys.argv[1]
    if arg == '-h' or 'help' in arg:
        help()
        sys.exit(0)
    reps = int(sys.argv[1])
if len(sys.argv) > 2:
    mode = sys.argv[2]
curlInputs = [] # list of file names to use in requests, in order
images = [] # file names of images in the input_images directory
non_images = [] # file names of non-images in the input_images directory
files = os.listdir('./input_images')
for file in files:
    if '.bmp' in file or '.jpg' in file or '.jpeg' in file or '.png' in file:
        images.append(file)
    else:
        non_images.append(file)
if mode == 'image' or mode == 'images':
    files = images
elif mode == 'non-image' or mode == 'non-images':
    files = non_images
num_files = len(files)
# create a list of 100 files to upload (the list is just file names)
for i in range(reps):
    curlInputs.append(files[random.randrange(num_files)])

# begin the timer and make the requests
start = time.perf_counter()
for i in range(reps):
    # do curl simulating a form upload with a file input
    filename = curlInputs[i]
    log(f'Input file {filename}')
    os.system(f'curl -F file=@\'input_images/{filename}\' http://{host}/produceFirstPassthrough')
    print('')
end = time.perf_counter()
delta = (end - start)/reps*1000
if mode:
    mode = '[' + mode + '] '
timing_log = f"{mode}Time taken for {reps} 'first passthrough' queries: {delta} ms each\n"
# log the time in stdout
log(timing_log)
os.system("date >> timing.txt")
with open('timing.txt', 'a') as f:
    f.write(f'{log_prefix}{timing_log}')

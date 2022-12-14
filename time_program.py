import os
import sys
import random
import time

pid = os.getpid()
host = os.environ.get('INGRESS') or 'localhost:5000'
log_prefix = f'[{pid}] '

def log(msg):
    print(f'{log_prefix}{msg}')

# Do queries in series. Later, I may run two scripts at the same time or do a fork in this script to simulate simultaneous requests.
print("Usage: command line argument for number of reps (default is 100)")
print("Each line of output is preceded by the pid of the process.")
reps = 100
if len(sys.argv) > 1:
    reps = int(sys.argv[1])
curlInputs = []
images = os.listdir('./input_images')
num_images = len(images)
# create a list of 100 files to upload (the list is just file names)
for i in range(reps):
    curlInputs.append(images[random.randrange(num_images)])

start = time.perf_counter()
for i in range(reps):
    # do curl simulating a form upload with a file input
    filename = curlInputs[i]
    log(f'Input file {filename}')
    os.system(f'curl -F file=@\'input_images/{filename}\' http://{host}/produceFirstPassthrough')
    print('')
end = time.perf_counter()
delta = (end - start)/reps*1000
timing_log = f"Time taken for {reps} 'first passthrough' queries: {delta} ms each\n"
# log the time in stdout
log(timing_log)
os.system("date >> timing.txt")
with open('timing.txt', 'a') as f:
    f.write(f'{log_prefix}{timing_log}')

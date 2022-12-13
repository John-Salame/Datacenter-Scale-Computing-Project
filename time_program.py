import os
import random
import time

# Do queries in series. Later, I may run two scripts at the same time or do a fork in this script to simulate simultaneous requests.
reps = 100
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
    os.system(f'curl -F file=@input_images/{filename} http://localhost:5000/produceFirstPassthrough')
end = time.perf_counter()
delta = (end - start)/reps*1000
print(f"Time taken for {reps} 'first passthrough' queries: {delta} ms each")

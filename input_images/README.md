## Input Images
This file has images we can feed into the normal map generator. It also has some red herrings to test error handling. The program `time_program.py` in the project root uploads these files at random, uploading <reps> files in series (not concurrently), where <reps> is 100 by default.
We can test concurrent execution by running two or more `time_program.py` scripts in the background at the same time.

## Use the timing program in project root
The timing program is called `time_program.py`. Command line argument 1 is the number of repetitions you want (number of files to feed into the program). If you use enough repetitions, some files will be uploaded multiple times. This can be used to check whether caching results actually speeds up the program.
For `time_program.py`, you need to export the ingress ip using `export INGRESS=$(minikube ip)` or note down the IP from `kubectl get ingress rest-ingress`.

## Results
Grass Normal Map is an image of what the normal map produced by this application looks like when used in my Compuer Graphics project.

# helpers.py

import sys

def checkError():
    haserror = hasattr(sys, 'last_value')
    if haserror:
        delattr(sys, 'last_value')
    print(haserror)
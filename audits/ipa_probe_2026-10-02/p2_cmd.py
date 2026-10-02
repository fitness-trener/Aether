import os, subprocess

def get_cmd(req):
    return req.args["c"]

def handler(req):
    c = get_cmd(req)
    os.system(c)                     # call-result via binding

def wrap(c):
    return c

def handler2(req):
    os.system(wrap(req.args["c"]))   # identity helper

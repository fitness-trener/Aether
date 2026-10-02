from flask import request, send_file

def user_path():
    return "/srv/files/" + request.args["f"]

def download():
    return open(user_path()).read()

def helper(p):
    with open(p) as fh:
        return fh.read()

def download2():
    return helper("/srv/files/" + request.args["f"])

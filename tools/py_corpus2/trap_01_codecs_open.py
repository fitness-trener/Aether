import codecs

def read_utf16(path):
    with codecs.open(path, "r", encoding="utf-16") as fh:
        return fh.read()

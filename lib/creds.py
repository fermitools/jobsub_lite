import ifdh

ih = None

def get_creds():
    """ get credentials -- Note this does not currently push to
        myproxy, nor does it yet deal with tokens, but those should
        be done here as needed.
    """
    global ih
    if not ih:
        ih = ifdh.ifdh()
    return ih.getProxy()


"""Summary

Attributes:
    CHECKSUM_PATTERN (str): Description
    MD5_MACHINE_TAG_PREFIX (TYPE): Description
    SHA1_MACHINE_TAG_PREFIX (TYPE): Description
"""

import os
import re
import hashlib
import unicodedata
from datetime import datetime


CHECKSUM_PATTERN = "[0-9a-f]{32,40}"
MD5_MACHINE_TAG_PREFIX = "checksum:md5="
SHA1_MACHINE_TAG_PREFIX = "checksum:sha1="


def datestr(date):
    """Return a flat string showing the datetaken from Flickr

    Requires the date input in the form 'Y-m-d H:M:S'
    """
    return '{:02d}{:02d}{:02d}{:02d}{:02d}{:02d}'.format(date.year,
                                                         date.month,
                                                         date.day,
                                                         date.hour,
                                                         date.minute,
                                                         date.second
                                                         )


def flickr_date_taken(photo):
    date_taken = datestr(datetime.strptime(photo.attrib['datetaken'], '%Y-%m-%d %H:%M:%S'))
    return date_taken


def md5sum(filename):
    """Wrapper for MD5 checksum calcuation for provided filename.

    Args:
        filename (string): filen to be checksummed.

    Returns:
        string: MD5 checksum
    """
    return checksum(filename, "md5")


def sha1sum(filename):
    """Wrapper for MD5 checksum calcuation for provided filename.

    Args:
        filename (string): filen to be checksummed.

    Returns:
        string: MD5 checksum
    """
    return checksum(filename, "sha1")


def checksum(filename, type, blocksize=65536):
    """Calculate the checksum of filename.

    Args:
        filename (string): filename to be checksummed
        type (string): type of checkusm (md5 or sha1)
        blocksize (int, optional): blocksize used for calculating the hash

    Returns:
        STRING: Checksum according type

    Raises:
        Exception: When provided checksum does not match the CHECKSUM_PATTERN.
    """
    if type == "md5":
        hash = hashlib.md5()
    elif type == "sha1":
        hash = hashlib.sha1()

    with open(filename, "rb") as f:
        for block in iter(lambda: f.read(blocksize), b""):
            hash.update(block)
        result = hash.hexdigest()

    m = re.search('^(' + CHECKSUM_PATTERN + ')', result.strip())
    if not m:
        raise Exception("Output from " + type + "sum was unexpected: " + result)
    return m.group(1)


def base58(n):
    """Wrapper for Flickr calls who need base58 encoding

    Returns:
        STRING: base58 encoded string

    Args:
        n (INT): integer; ref Flickr API for more info.
    """
    a = '123456789abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ'
    bc = len(a)
    enc = ''
    while n >= bc:
        div, mod = divmod(n, bc)
        enc = a[mod] + enc
        n = div
    enc = a[n] + enc
    return enc


def normalize(text):
    """Normalize a string to lowercase.

    Returns:
        STRING: normalized string (lowercase)

    Arg:
        text (STRING): text to normalize.
    """
    return unicodedata.normalize("NFKD", text.casefold())


class FileWithCallback(object):
    """Summary

    Attributes:
        callback (TYPE): Description
        file (TYPE): Description
        fileno (TYPE): Description
        len (TYPE): Description
        tell (TYPE): Description
    """

    def __init__(self, filename, callback):
        """Summary

        Args:
            filename (TYPE): Description
            callback (TYPE): Description
        """
        self.file = open(filename, 'rb')
        self.callback = callback
        # the following attributes and methods are required
        self.len = os.path.getsize(filename)
        self.fileno = self.file.fileno
        self.tell = self.file.tell

    def read(self, size):
        """Summary

        Args:
            size (TYPE): Description

        Returns:
            TYPE: Description
        """
        if self.callback:
            self.callback(self.tell() * 100 // self.len)
        return self.file.read(size)

    def __del__(self):
        """Destructor.

        Close the opened file in __init__
        """
        self.file.close()
        self.file = None


def short_url(photo_id):
    """Create short url to photo.

    Args:
        photo_id (int): Photo_id to create the link for

    Returns:
        STRINF: url to photo_id
    """
    encoded = base58(int(photo_id, 10))
    return "http://flic.kr/p/%s" % (encoded,)


def info_to_url(info_result, size=""):
    """Summary

    Args:
        info_result (TYPE): Description
        size (str, optional): Description

    Returns:
        TYPE: Description

    Raises:
        Exception: Description
    """
    a = info_result.getchildren()[0].attrib
    if size in ("", "-"):
        return 'http://farm%s.static.flickr.com/%s/%s_%s.jpg' % (a['farm'], a['server'], a['id'], a['secret'])
    elif size in ("s", "t", "m", "b"):
        return 'http://farm%s.static.flickr.com/%s/%s_%s_%s.jpg' % (a['farm'], a['server'], a['id'], a['secret'], size)
    elif size == "o":
        return 'http://farm%s.static.flickr.com/%s/%s_%s_o.%s' % (a['farm'], a['server'], a['id'], a['originalsecret'], a['originalformat'])
    else:
        raise Exception('Unknown size (' + size + ')passed to info_to_url()')

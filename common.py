# Copyright 2009 Mark Longair

#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.

import sys
import os
import re
import hashlib
from subprocess import Popen, PIPE

#flickr_api_filename = os.path.join(os.environ['HOME'],'flickr-api')
#if not os.path.exists(flickr_api_filename):
#    print("You must put your Flickr API key and secret in "+flickr_api_filename)

# configuration = {}
# for line in open(flickr_api_filename):
#     if len(line.strip()) == 0:
#         continue
#     m = re.search('\s*(\S+)\s*=\s*(\S+)\s*$',line)
#     if m:
#         configuration[m.group(1)] = m.group(2)
#     if not m:
#         print("Each line of "+flickr_api_filename+" must be either empty")
#         print("or of the form 'key = value'")
#         sys.exit(1)
#     continue
# 
# if not ('api_key' in configuration and 'api_secret' in configuration):
#     print("Both api_key and api_secret must be defined in "+flickr_api_filename)

class ProgressBar(object):
    DEFAULT_BAR_LENGTH = 65
    DEFAULT_CHAR_ON  = '='
    DEFAULT_CHAR_OFF = ' '
    fname = ''
    
    def __init__(self, end, start=0, screen=None):
        self.end    = end
        self.start  = start
        self._barLength = self.__class__.DEFAULT_BAR_LENGTH
        
        self.stdscr = screen
        self.stdscr.erase()

        self.setLevel(self.start)
        self._plotted = False

    def setLevel(self, level):
        self._level = level
        if level < self.start:  self._level = self.start
        if level > self.end:    self._level = self.end

        self._ratio = float(self._level - self.start) / float(self.end - self.start)
        self._levelChars = int(self._ratio * self._barLength)

    def plotProgress(self):
        self.stdscr.addstr(1, 0, "  %3i%% [%s%s]" %(
            int(self._ratio * 100.0),
            self.__class__.DEFAULT_CHAR_ON  * int(self._levelChars),
            self.__class__.DEFAULT_CHAR_OFF * int(self._barLength - self._levelChars),))
        self.stdscr.refresh()

    def set_label(self,label,number):
        self.stdscr.addstr(number, 0, '')
        self.stdscr.refresh()
        self.stdscr.addstr(number, 0, str(label))
        self.stdscr.refresh()

    def setAndPlot(self, level):
        oldChars = self._levelChars
        self.setLevel(level)
        if (not self._plotted) or (oldChars != self._levelChars):
            self.plotProgress()

    def __add__(self, other):
        assert type(other) in [float, int], "can only add a number"
        self.setAndPlot(self._level + other)
        return self
    def __sub__(self, other):
        return self.__add__(-other)
    def __iadd__(self, other):
        return self.__add__(other)
    def __isub__(self, other):
        return self.__add__(-other)

    def __del__(self):
        self.stdscr.erase()
        sys.stdout.write("\n")

def md5sum(filename):
    return checksum(filename,"md5")

def sha1sum(filename):
    return checksum(filename,"sha1")

def checksum(filename, type, blocksize=65536):
  if type == "md5":
    hash = hashlib.md5()
  elif type == "sha1":
    hash = hashlib.sha1()
    
  with open(filename, "rb") as f:
    for block in iter(lambda: f.read(blocksize), b""):
      hash.update(block)
    result = hash.hexdigest()
  
  m = re.search('^('+checksum_pattern+')',result.strip())
  if not m:
    raise Exception("Output from "+type+"sum was unexpected: "+result)
  return m.group(1)

checksum_pattern = "[0-9a-f]{32,40}"

md5_machine_tag_prefix = "checksum:md5="
sha1_machine_tag_prefix = "checksum:sha1="

def base58(n):
    a='123456789abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ'
    bc=len(a)
    enc=''
    while n >= bc:
        div, mod = divmod(n,bc)
        enc = a[mod]+enc
        n = div
    enc = a[n]+enc
    return enc

def short_url(photo_id):
    encoded = base58(int(photo_id,10))
    return "http://flic.kr/p/%s" % (encoded,)

def info_to_url(info_result,size=""):
    a = info_result.getchildren()[0].attrib
    if size in ( "", "-" ):
        return 'http://farm%s.static.flickr.com/%s/%s_%s.jpg' %  (a['farm'], a['server'], a['id'], a['secret'])
    elif size in ( "s", "t", "m", "b" ):
        return 'http://farm%s.static.flickr.com/%s/%s_%s_%s.jpg' %  (a['farm'], a['server'], a['id'], a['secret'], size)
    elif size == "o":
        return 'http://farm%s.static.flickr.com/%s/%s_%s_o.%s' %  (a['farm'], a['server'], a['id'], a['originalsecret'], a['originalformat'])
    else:
        raise Exception('Unknown size ('+size+')passed to info_to_url()')




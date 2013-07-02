#!/usr/bin/env python
#
# Created by: Simon Brunet 2013-06-17
#
# Abstract:
#   This is the hashing utilities
#
###############################################################################

import random
import string
import hashlib

from secret import SECRET

def GetSalt():
    return ''.join(random.choice(string.letters) for x in xrange(5))

def GetPwHash(pw):
    salt = GetSalt()
    h = hashlib.sha256(SECRET + pw + salt).hexdigest()
    return '%s|%s' % (h, salt)

def ValidPw(pw, h):
    pwHash = h.split('|')
    reH = hashlib.sha256(SECRET + pw + pwHash[1]).hexdigest()
    return reH == pwHash[0]

def GetHash(data):
    h = hashlib.sha256(SECRET + data).hexdigest()
    return '%s|%s' % (h, data)

def ValidHash(data):
    data = data.split('|')
    h = hashlib.sha256(SECRET + data[1]).hexdigest()
    return h == data[0]

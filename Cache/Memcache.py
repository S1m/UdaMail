#!/usr/bin/env python
#
# Created by: Simon Brunet 2013-06-30
#
# Notice: Do not in entirety or in part, copy, use, distribute, sell,
#         reproduce or publish any of that code without prior authorization
#         of the aforementionned author.
#
# Abstract:
#   Memcache abstraction
#
###############################################################################

from google.appengine.api import memcache

import Db
import logging
import collections

from Parameters import INBOX_PAGE_RESULTS
from Parameters import MAX_CAS_RETRY

##
class _Memcache(object):
    def __init__(self):
        super(_Memcache, self).__init__()
        self.cache = memcache.Client()
    
    # Set an element in memcache
    def _Set(self, key, data, **kwargs):
        self.cache.set(key, data, **kwargs)
    
    # Get an element in memcache, if not, execute the query functor specified
    #   Note: Watch out with Query.run() as it's returning an iterable not data
    def _Get(self, key, query, update = False, namespace=None, *args, **kwargs):
        data = self.cache.get(key, namespace=namespace)
        if data is None or update:
            data = query(*args, **kwargs)
            self._Set(key, data, namespace=namespace)
        return data

    def _Delete(self, key, **kwargs):
        self.cache.delete(key)
        
    def _DeleteMulti(self, keys, **kwargs):
        self.cache.delete_multi(keys)
        
##
class MemcacheMail(_Memcache):
    
    def __init__(self):
        super(MemcacheMail, self).__init__()
        
    def GetMail(self, mailId, update=False):
        query = Db.Model('Mail').GetMailById
        return self._Get(mailId, query, update, 'Mail', int(mailId))
    
    def SetMail(self, mailId, mail):
        self._Set(mailId, mail, namespace='Mail')
        
    def DeleteMails(self, user, ids):
        self._DeleteMulti(ids, namespace='Mail')
        # Refresh Inbox view
        self.GetUserMails(user, True)
        
    def GetUserMails(self, user, update = False):
        deque = self.cache.get(user, namespace='UserMails')
        if deque is None or update:
            data = Db.Model('Mail').GetRecentMail(user)
            # Store the recent mails in a circular queue so that
            # every new mail will simply refresh the queue
            deque = collections.deque(data, maxlen=INBOX_PAGE_RESULTS)
            self.cache.set(user, deque, namespace='UserMails')
        return deque
    
    def SetUserMails(self, user, mail):
        retry = 0
        # TODO brunets 2013-06-30 Handle case where max retry failed
        while retry < MAX_CAS_RETRY:
            deque = self.cache.gets(user, namespace='UserMails')
            if deque is None:
                # Why bother refreshing the cache if the user has
                # no mails or if he never viewed them.
                # It is not worth hitting the database or maintaining
                # the cache for a dead user.
                return
            deque.appendleft(mail)
            if self.cache.cas(user, deque, namespace='UserMails'):
                break
            retry += 1
            
    def SetUserMailViewed(self, user, mailId):
        retry = 0
        # TODO brunets 2013-06-30 Handle case where max retry failed
        while retry < MAX_CAS_RETRY:
            deque = self.cache.gets(user, namespace='UserMails')
            if deque is None:
                # Should never come here...
                logging.error('Trying to update something that is not...')
                return
            newDeque = collections.deque(maxlen=INBOX_PAGE_RESULTS)
            for mail in deque:
                if mail.key().id() == mailId:
                    mail.viewed = True
                newDeque.append(mail)
            if self.cache.cas(user, newDeque, namespace='UserMails'):
                break
            retry += 1
            
##
class MemcacheUser(_Memcache):
    
    def __init__(self):
        super(MemcacheUser, self).__init__()
        
    def SetUser(self, name, data):
        self._Set(name, data, namespace='User')
        
    def GetUser(self, name, update=False):
        query = Db.Model("User").GetUser
        return self._Get(name, query, update, 'User', name)
    
    def IsAdmin(self, name):
        user = self.GetUser(name)
        if user:
            return user.admin
        
    def ValidUser(self, name):
        user = self.cache.get(name, namespace='User')
        if user:
            return True
        user = Db.Model("User").GetUser(name)
        if user:
            # Update Memcache accordingly
            self.SetUser(name, user)
            return True
        return False
    
##
class MemcacheUdaUser(_Memcache):
    
    def __init__(self):
        super(MemcacheUdaUser, self).__init__()
        
    def SetUser(self, name, data):
        self._Set(name, data, namespace='UdaUser')
        
    def GetUser(self, name, update=False):
        query = Db.Model("UdaUser").GetUdaUser
        return self._Get(name, query, update, 'UdaUser', name)
    
    def UserTaken(self, name):
        user = self.cache.get(name, namespace='UdaUser')
        if user:
            return True
        user = Db.Model("UdaUser").GetUdaUser(name)
        if user:
            # Update Memcache accordingly
            self.SetUser(name, user)
            return True
        return False
    
##
class MemcacheGroup(_Memcache):
    
    def __init__(self):
        super(MemcacheGroup, self).__init__()
        
    def SetGroup(self, name, data):
        self._Set(name, data, namespace='Group')
        
    def GetGroup(self, name, update=False):
        query = Db.Model("Group").GetGroup
        return self._Get(name, query, update, 'Group', name)
    
    def GetUsers(self, name):
        group = self.GetGroup(name)
        if group:
            # WARNING! GAE stores element in a ListStringProperty in unicode.
            # Must convert back to string.
            return [str(user) for user in group.users]
    
    def ValidGroup(self, name):
        group = self.GetGroup(name)
        if group:
            return True
        return False
    
    

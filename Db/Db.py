#!/usr/bin/env python
#
# Created by: Simon Brunet 2013-06-29
#
# Notice: Do not in entirety or in part, copy, use, distribute, sell,
#         reproduce or publish any of that code without prior authorization
#         of the aforementionned author.
#
# Abstract:
#   Store the DB models and DB related functions
#
###############################################################################

from google.appengine.ext import db

import Memcache
import Hashing
import logging

from Parameters import INBOX_PAGE_RESULTS

# BaseModel
#    Generic interface used for all entities
class _BaseModel(db.Model):
    created = db.DateTimeProperty(auto_now_add = True, indexed=True)
    lastModified = db.DateTimeProperty(auto_now = True)
    
    @classmethod
    def _Put(cls, **kwargs):
        obj = cls(**kwargs)
        obj.put()
        # If needed, returns the object
        return obj
    
    def _delete(self):
        try:
            self.delete()
        except db.NotSavedError:
            logging.error('Trying to delete an object that is not')

# UdaUser
#    Stub entity used to simulate the Udacity User base.
#    This is just the most basic interface required.
#    Simply needs to replace this stub with the real database if this (UdaMail)
#    module is added.
class UdaUser(_BaseModel):
    name = db.StringProperty(required=True, indexed=True)
    password = db.StringProperty(required=True)
    
    @classmethod
    def GetUdaUser(cls, name):
        return Query("UdaUser").filter('name =', name).get()
    
    @classmethod
    def CreateUdaUser(cls, name, password, admin=False):
        # Automatically create a corresponding UdaMail user
        User.CreateUser(name, admin)
        user = cls._Put(name=name, password=Hashing.GetPwHash(password))
        # Refresh Memcache
        Memcache.MemcacheUdaUser().SetUser(name, user)

# User
#    User entity of UdaMail
class User(_BaseModel):
    name = db.StringProperty(required=True, indexed=True)
    groups = db.StringListProperty(required=True, default=["Udacity"])
    admin = db.BooleanProperty(required = True, default=False)
    
    @classmethod
    def GetUser(cls, name):
        return Query("User").filter('name =', name).get()
    
    @classmethod
    def CreateUser(cls, name, admin=False):
        user = cls._Put(name=name, admin=admin)
        # Refresh Memcache
        Memcache.MemcacheUser().SetUser(name, user)
        # Since he's part of Udacity group, add him to it
        Group.AddUserToUdacity(name)
        
    def UpdateUserGroups(self, groups):
        self.groups = groups
        self.put()
        # Refresh memcache
        Memcache.MemcacheUser().SetUser(self.name, self)
    
    
# Mail
#    Mail model. Mail entries must have the following infos
class Mail(_BaseModel):
    name = db.StringProperty(required=True, indexed=True)  # (To)
    sender = db.StringProperty(required=True, indexed=True) # (From)
    subject = db.StringProperty(required=True, default="(No Subject)")
    message = db.TextProperty(required=True, default="EOM")
    cc = db.StringListProperty(required=True, default=[]) # (CC)
    bcc = db.StringListProperty(required=True, default=[]) # (BCC)
    viewed = db.BooleanProperty(required = True, default=False)
    
    @classmethod
    def GetRecentMail(cls, name):
        return Query("Mail").order('-created').filter('name =', name)\
                    .fetch(INBOX_PAGE_RESULTS)
    
    @classmethod
    def GetMailById(cls, id):
        return cls.get_by_id(id)
    
    @classmethod
    def PutMail(cls, **kwargs):
        mail = cls._Put(**kwargs)
        # Refresh memcache
        memMail = Memcache.MemcacheMail()
        memMail.SetMail(str(mail.key().id()), mail)
        memMail.SetUserMails(kwargs['name'], mail)
        
    @classmethod
    def DeleteMails(cls, user, ids):
        # Delete all mails from Db before refreshing memcache so that the
        # database will only get hit once to refresh the deque.
        # This could be optimized by buffering extra mails in the deque in
        # memcache and then remove the deleted mails from the deque and
        # only refresh if len(deque) < INBOX_PAGE_RESULTS.
        # The deque is refilled anytime a mail is received.
        # That way, it could be possible to never have to hit the database
        # to refresh the cache.
        # However, I don't have stats to assess if this is really
        # optimizing the process or just adding some overhead.
        # Neither would I have a good value for the deque length.
        # Nevertheless, this would most likely be preferable as doing a
        # hit everytime a single mail is deleted.
        # TODO brunets 2013-07-01 Implement such logic
        memMail = Memcache.MemcacheMail()
        for id in ids:
            mail = memMail.GetMail(id)
            if mail:
                mail._delete()
        # Remove from memcache
        memMail.DeleteMails(user, ids)
        
    def SetViewed(self, user):
        self.viewed = True
        self.put()
        # Refresh memcache
        Memcache.MemcacheMail().SetUserMailViewed(user, self.key().id())
    
    
    
# Group
#    Group Model. Although the specs said that the group must be defined
#    inside the user definition, I feel like not having a centralized
#    group data would be cost prohibitive. If each user must be queried
#    to recompile the groups each time, at best this would be O(n**2).
#    Maintaining a group class would only cost O(n) to query. (if not indexed)
#    Since storing data is way less costly than query time (taking into
#    account user satisfaction), I think it's a safe bet to store those
#    in the DB.
#    Another approach could have been to "compile" the groups only once
#    and keep that in memcache or any other type of volatile memory.
#    But then if one of the server was to go down, recompiling the groups
#    would create a huge dent in the latency of the system. Which is
#    certainly not cool for the user.
#    Also, handling such failure using memcache or else is certainly
#    much more complicated as having Google doing all this hard work
#    for us on their DB side. Might as well use that to our advantage :)
#    Finally, groups are not expected to change frequently. Therefore,
#    write operations will not be performed too often so it should not
#    lead to extraordinary costs.
class Group(_BaseModel):
    name = db.StringProperty(required=True, indexed=True) # Group name
    users = db.StringListProperty(required=True, default=[])
    
    @classmethod
    def GetGroup(cls, name):
        return Query("Group").filter('name =', name).get()
    
    @classmethod
    def PutGroup(cls, name, users=[]):
        group = cls._Put(name=name, users=users)
        # Refresh Memcache
        Memcache.MemcacheGroup().SetGroup(name, group)
        
    @classmethod
    def AddUserToUdacity(cls, user):
        group = Memcache.MemcacheGroup().GetGroup("Udacity")
        if group is None:
            # Should happen once and only once
            cls.PutGroup("Udacity", [user])
        else:
            users = group.users
            users.append(user)
            users = list(set(users)) # Remove duplicates
            group.UpdateGroup(users)
        
    @classmethod
    def AddUser(cls, name, username):
        if name == "Udacity":
            # Just to make sure someone doesn't attempt that...
            # Which would lead to an infinite loop
            cls.AddUserToUdacity(username)
            return
        group = Memcache.MemcacheGroup().GetGroup(name)
        if group is None:
            cls.PutGroup(name, [username])
        else:
            users = group.users
            users.append(username)
            users = list(set(users)) # Remove duplicates
            group.UpdateGroup(users)
        # Maintain user
        user = Memcache.MemcacheUser().GetUser(username)
        if user:
            groups = user.groups
            groups.append(name)
            groups = list(set(groups))
            user.UpdateUserGroups(groups)
    
    @classmethod
    def RemoveUser(cls, name, username):
        group = Memcache.MemcacheGroup().GetGroup(name)
        if group is None:
            # Should not happen, but just in case, we want to know
            logging.error('Trying to remove user from non-existing group')
        else:
            users = group.users
            newUsers = []
            for u in users:
                if u != username:
                    newUsers.append(u)
            group.UpdateGroup(newUsers)
        # Maintain user
        user = Memcache.MemcacheUser().GetUser(username)
        if user:
            groups = user.groups
            newGroups = []
            for g in groups:
                if g != name:
                    newGroups.append(g)
            user.UpdateUserGroups(newGroups)
                    
    def UpdateGroup(self, users):
        self.users = users
        self.put()
        # Refresh memcache
        Memcache.MemcacheGroup().SetGroup(self.name, self)
    
    
    
###############################################################################
    
MODELS = {"UdaUser" : UdaUser,
          "User"    : User,
          "Mail"    : Mail,
          "Group"   : Group}
        
# Wrapper on Model to avoid explicit use of db model classes
# Kind of like a typedef... Can be handy for shortening long name or changing models
# name without breaking everything
def Model(model):
    return MODELS[model]

# Wrapper on Query to avoid explicit use of db model classes
class Query(db.Query):
    def __init__(self, model, **kwargs):
        super(Query, self).__init__(model_class = MODELS[model], **kwargs)


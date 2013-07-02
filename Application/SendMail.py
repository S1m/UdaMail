#!/usr/bin/env python
#
# Created by: Simon Brunet 2013-06-30
#
# Notice: Do not in entirety or in part, copy, use, distribute, sell,
#         reproduce or publish any of that code without prior authorization
#         of the aforementionned author.
#
# Abstract:
#   Functions related to sendind mails
#
###############################################################################

# Remap the paths for deferred
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'Application')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'Db')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'Cache')))

import Db
import Memcache

from google.appengine.ext import deferred

def ExpandGroups(memGroup, data):
    
    expand = []
    for d in data:
        users = memGroup.GetUsers(d)
        if users:
            for u in users:
                expand.append(u)
        else:
            expand.append(d)
    return list(set(expand))

# SendMail
#   Allright, time to have a semantical debate.
#   In the specs, it says that "[...]  a message should be received only by
#   the users who were members of the destination group at the time the
#   message was sent."
#   Now, theorically speaking, this is the time when the message is sent.
#   If it was intended to say that it was at the moment the user press "Send",
#   then it's a whole other game.
#   If such is the case, current technique to run mail dispatching
#   in the background (ie: deferred) would probably scream out of pain
#   if a snapshot of all the users in a group (say... Udacity)
#   are passed in parameter to the SendMail method.
#   So for now, the groups are evaluated only once the SendMail request
#   is being processed by deferred.
#   However! There is a known limitation at the moment.
#   There are no guarantee that for each GetUsers() call, it would
#   be done on the same Memcache or Db state...
#   Nevertheless, that shouldn't be too much of an issue
#   as the group or user management will eventually be consistent.
#   So a user can always re-attempt to send a mail.
#   So, this could be part of another semantical debate but...
#   TODO brunets 2013-07-01 Freeze groups at time of send
def SendMail(sender, to, cc, bcc, subject, message):

    # Just in case something bad happen, since this task is deferred,
    # I prefer to kill it rather than having a task that will retry
    # indefinitely. Raising the PermanentTaskFailure() will stop the task
    # TODO brunets 2013-07-01 Notify the user if the task failed
    try:
        memGroup = Memcache.MemcacheGroup()
        
        visible = to + ';' + cc  # All the visible recipients
        visible = visible.strip(';').split(';') # Make a list
        visible = list(set(visible)) # Remove duplicates
        # Expand groups
        expVisible = ExpandGroups(memGroup, visible)
                
        invisible = bcc.strip(';').split(';') # Make a list
        invisible = list(set(invisible)) # Remove duplicates
        # Expand groups
        expInvisible = ExpandGroups(memGroup, invisible)
        
        recipients = expVisible + expInvisible # All recipients
        recipients = list(set(recipients)) # Remove duplicates
        recipients = filter(len, recipients) # Remove empty strings
        
        # Send a mail to all the recipients
        for recipient in recipients:
            cc = list(set(visible) - set([recipient])) # Remove receiver from CC
            bcc = invisible # Pretty much kept for the records
            data = {}
            if subject:
                data['subject'] = subject
            if message:
                data['message'] = message
            Db.Model('Mail').PutMail(name=recipient, sender = sender, cc=cc, bcc = bcc, **data)
    except:
        # Could add some error handling stuff here
        raise deferred.PermanentTaskFailure()
#!/usr/bin/env python
#
# Created by: Simon Brunet 2013-06-29
#
# Notice: Do not in entirety or in part, copy, use, distribute, sell,
#         reproduce or publish any of that code without prior authorization
#         of the aforementionned author.
#
# Abstract:
#   Main
#
###############################################################################

import os, sys
# Setup the env
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'Utilities')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'Application')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'Db')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'Cache')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'markdown')))
# For unit tests
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'test')))
import gaeunit

import webapp2
import jinja2
import re

from google.appengine.ext import deferred

import Hashing
import Db
import Memcache
from SendMail import SendMail
import markdown

DEBUG = True
UNIT_TEST = False

# TODO brunets 2013-07-01 Have a little bit more flexibility than that
RE = re.compile(r"^[a-zA-Z0-9_-]{3,20}$")

jinjaEnv = jinja2.Environment(autoescape=True,
    loader=jinja2.FileSystemLoader(os.path.join(os.path.dirname(__file__), 'templates'))) 
jinjaEnv.filters['markdown'] = markdown.markdown

# Memcache instances
memMail = Memcache.MemcacheMail()
memUser = Memcache.MemcacheUser()
memUdaUser = Memcache.MemcacheUdaUser()
memGroup = Memcache.MemcacheGroup()

class PermissionException(Exception):
    def __init__(self):
         self.value = "Permission Denied."
    def __str__(self):
        return repr(self.value)

# Basic Handler
class Handler(webapp2.RequestHandler):
    def Write(self, *args, **kwargs):
        self.response.out.write(*args, **kwargs)

    def RenderStr(self, template, **params):
        t = jinjaEnv.get_template(template)
        return t.render(params)
    
    def Render(self, template, **kwargs):
        self.Write(self.RenderStr(template, **kwargs))
        
    def SetCookie(self, cookie):
        self.response.headers['Content-Type'] = 'text/plain'
        self.response.headers.add_header('Set-Cookie', cookie)
        
    def DeleteCookie(self, cookie):
        self.response.delete_cookie(cookie)
        
    def initialize(self, *a, **kw):
        webapp2.RequestHandler.initialize(self, *a, **kw)
        user = self.request.cookies.get('user', "")
        if user and Hashing.ValidHash(user):
            user = user.split('|')[1]
            self.user = user
            self.admin = memUser.IsAdmin(user)
        else:
            self.user = None
            self.admin = False
            path = self.request.path
            if path != '/' and path != '/signup' and path != '/login':
                # That's a pretty hardcore way to deal with the problem...
                # But simply modifying the header as with what a redirection
                # or an error would do would not prevent the page from loading
                # as the get request would overwrite the header, nullifying
                # the effect.
                # Hence, I needed something a little bit more... drastic
                # But that's the user's fault! He shouldn't be trying to
                # access URL he's not permitted. Good for him!
                raise PermissionException()
                
class Main(Handler):
    def get(self):
        self.Render("main.html", user = self.user, admin = self.admin)
        
class Signup(Handler):
    def renderSignup(self, **kwargs):
        self.Render("signup.html", **kwargs)

    def get(self):
        self.renderSignup()

    def post(self):
        user = self.request.get("username")
        password = self.request.get("password")
        verify = self.request.get("verify")
        admin = self.request.get("admin")
        
        if not user or not RE.match(user):
            self.renderSignup(errorUser = "That's not a valid username.", user=user)
            return 
        if not password or not RE.match(password):
            self.renderSignup(errorPass = "That's not a valid password.", user=user)
            return
        if not verify or password != verify:
            self.renderSignup(errorVerify = "Your passwords didn't match.", user=user)
            return
        if memUdaUser.UserTaken(user) or memGroup.ValidGroup(user):
            self.renderSignup(errorUser = "User already choosen.", user=user)
            return
        
        if admin:
            admin = True
        else:
            admin = False
            
        # Convert to string not unicode
        user = str(user)
        password = str(password)

        Db.Model('UdaUser').CreateUdaUser(user, password, admin)

        self.SetCookie('user=%s' % Hashing.GetHash(user))
        self.redirect('/')

class Login(Handler):
    def get(self):
        self.Render("login.html")

    def post(self):
        user = self.request.get("username")
        password = self.request.get("password")

        userData = memUdaUser.GetUser(user)
        if not userData:
            self.Render("login.html", error = 'This user does not exists', user=user)
            return
        # The matching here is to protect hashing against unicode characters
        if not RE.match(password) or not Hashing.ValidPw(password, userData.password):
            self.Render("login.html", error = 'Incorrect Password', user=user)
            return
        
        # Convert to string not unicode
        user = str(user)

        self.SetCookie('user=%s' % Hashing.GetHash(user))
        self.redirect('/inbox')

class Logout(Handler):
    def get(self):
        self.DeleteCookie("user")
        self.redirect('/')
        
class Group(Handler):
    def get(self):
        self.Render("group.html", user=self.user)
        
class Inbox(Handler):
    def get(self):
        mails = memMail.GetUserMails(self.user)
        self.Render("inbox.html", user = self.user, admin = self.admin, mails = list(mails))
        
    def post(self):
        toDel = self.request.arguments()
        ids = [str(id) for id in toDel]
        Db.Model('Mail').DeleteMails(self.user, ids)
        
        self.redirect('/inbox')
    
        
class Compose(Handler):
    def RenderCompose(self, **kwargs):
        self.Render("compose.html", user = self.user, admin = self.admin, **kwargs)
    
    def get(self):
        self.RenderCompose()
        
    def post(self):
        to = self.request.get("to").replace(" ", "").strip(';')
        cc = self.request.get("cc").replace(" ", "").strip(';')
        bcc = self.request.get("bcc").replace(" ", "").strip(';')
        subject = self.request.get("subject")
        message = self.request.get("message")
        kwargs = {'to':to, 'cc':cc, 'bcc':bcc, 'subject':subject, 'message':message}
        
        if to:
            for name in to.split(';'):
                if not memUser.ValidUser(name) and not memGroup.ValidGroup(name):
                    msg = "Invalid Recipient: " + name
                    self.RenderCompose(errorTo = msg, **kwargs)
                    return
        else:
            self.RenderCompose(errorTo = "To who?", **kwargs)
            return
        if cc:
            for name in cc.split(';'):
                if not memUser.ValidUser(name) and not memGroup.ValidGroup(name):
                    msg = "Invalid Recipient: " + name
                    self.RenderCompose(errorCc = msg, **kwargs)
                    return
        if bcc:
            for name in bcc.split(';'):
                if not memUser.ValidUser(name) and not memGroup.ValidGroup(name):
                    msg = "Invalid Recipient: " + name
                    self.RenderCompose(errorBcc = msg, **kwargs)
                    return
        if subject:
            if len(subject) > 500:
                msg = "Cannot have subject longer than 500 characters"
                self.RenderCompose(errorSubject = msg, **kwargs)
                return
        if message:
            if len(message) > 10000:
                msg = "Wow buddy! That's a huge mail, that much to say? Eh. " + \
                      "I can give you 10 000 chars... deal?"
                self.RenderCompose(errorMessage = msg, **kwargs)
                return

        # Defer processing, otherwise a user would wait a great while
        # if he's trying to reach all of Udacity users!
        deferred.defer(SendMail, self.user, **kwargs)

        self.redirect('/inbox')
    
class ViewMail(Handler):
    def get(self, id):
        mail = memMail.GetMail(id)
        if mail.name != self.user:
            self.error(403)   # For the sneaky ones...
            return
        mail.SetViewed(self.user)
        self.Render("view.html", mail=mail, user = self.user, admin = self.admin)
    
# If enabled, deploy unit tests
if UNIT_TEST:
    class MainTestPageHandler(gaeunit.MainTestPageHandler):
        def __init__(self, *args):
            super(MainTestPageHandler, self).__init__(*args)
    class JsonTestRunHandler(gaeunit.JsonTestRunHandler):
        def __init__(self, *args):
            super(JsonTestRunHandler, self).__init__(*args)
    class JsonTestListHandler(gaeunit.JsonTestListHandler):
        def __init__(self, *args):
            super(JsonTestListHandler, self).__init__(*args)
else:
    class MainTestPageHandler(webapp2.RequestHandler):
        def get(self):
            self.error(510)
    class JsonTestRunHandler(webapp2.RequestHandler):
        def get(self):
            self.error(510)
    class JsonTestListHandler(webapp2.RequestHandler):
        def get(self):
            self.error(510)

app = webapp2.WSGIApplication([('/', Main),
                               ('/signup', Signup),
                               ('/login', Login),
                               ('/logout', Logout),
                               ('/group', Group),
                               ('/inbox', Inbox),
                               ('/compose', Compose),
                               ('/(\d+)', ViewMail),
                               ('%s'      % gaeunit._WEB_TEST_DIR, MainTestPageHandler),
                               ('%s/run'  % gaeunit._WEB_TEST_DIR, JsonTestRunHandler),
                               ('%s/list' % gaeunit._WEB_TEST_DIR, JsonTestListHandler)
                               ],
                              debug=DEBUG)

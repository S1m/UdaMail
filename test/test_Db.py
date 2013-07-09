#!/usr/bin/env python
#
# Created by: Simon Brunet 2013-07-08
#
# Notice: Do not in entirety or in part, copy, use, distribute, sell,
#         reproduce or publish any of that code without prior authorization
#         of the aforementionned author.
#
# Abstract:
#   Unit tests for Db Models
#
###############################################################################

import unittest
from google.appengine.ext import testbed

import Db
import Memcache

################################# UNIT TESTS ##################################
###############################################################################


######## UdaUser #########
class UdaUserTest(unittest.TestCase):
    def setUp(self):
        # First, create an instance of the Testbed class.
        self.testbed = testbed.Testbed()
        # Then activate the testbed, which prepares the service stubs for use.
        self.testbed.activate()
        # Service stubs to use.
        self.testbed.init_datastore_v3_stub()
        self.testbed.init_memcache_stub()
        self.cache = Memcache.MemcacheUdaUser()

    def tearDown(self):
        self.testbed.deactivate()
        
    # Make sure UdaUser creation is properly done in DB and Memcache
    def test_CreateUser(self):
        name = 'Sim'
        Db.Model('UdaUser').CreateUdaUser(name, 'test')
        user = Db.Model('UdaUser').GetUdaUser(name)
        
        self.assertEqual(name, user.name)
        
        # Verify that it was properly put in memcache
        userMem = self.cache.GetUser(name)
        
        self.assertEqual(name, userMem.name)
        
        # Verify that user is taken
        self.assertTrue(self.cache.UserTaken(name))
        
    # Ensure that the password is not stored as is (!!)
    def test_PasswordEncrypted(self, ):
        name = 'Sim'
        password = 'test'
        Db.Model('UdaUser').CreateUdaUser(name, password, True)
        user = Db.Model('UdaUser').GetUdaUser(name)
        
        # Verify that the password is not saved in plain text
        self.assertNotEqual(user.password, password)
    
    # Test that the user is well maintained
    def test_UserMaintained(self, ):
        name = 'Sim'
        password = 'test'
        Db.Model('UdaUser').CreateUdaUser(name, password, True)
        
        # Get the user from the User Model
        user = Db.Model('User').GetUser(name)
        
        # Ensure it's the same
        self.assertEqual(name, user.name)
        
        # Ensure he's admin (propagated properly)
        self.assertTrue(user.admin)
        
######## User #########
class UserTest(unittest.TestCase):
    def setUp(self):
        # First, create an instance of the Testbed class.
        self.testbed = testbed.Testbed()
        # Then activate the testbed, which prepares the service stubs for use.
        self.testbed.activate()
        # Service stubs to use.
        self.testbed.init_datastore_v3_stub()
        self.testbed.init_memcache_stub()
        self.cache = Memcache.MemcacheUser()

    def tearDown(self):
        self.testbed.deactivate()
        
    # Make sure User creation is properly done in DB and Memcache
    def test_CreateUser(self):
        name = 'Sim'
        admin = True
        Db.Model('User').CreateUser(name, admin)
        user = Db.Model('User').GetUser(name)
        
        self.assertEqual(name, user.name)
        
        # Verify that it was properly put in memcache
        userMem = self.cache.GetUser(name)
        
        self.assertEqual(name, userMem.name)
        
        # Verify that user is admin
        self.assertTrue(userMem.admin)
        
        # Verify that user is member of Udacity
        self.assertIn('Udacity', userMem.groups)
        
        # Verify that the Udacity group was well maintained
        group = Db.Model('Group').GetGroup('Udacity')
        self.assertIn(userMem.name, group.users)
        
    # Test groups update
    def test_UpdateGroups(self, ):
        name = 'Sim'
        Db.Model('User').CreateUser(name)
        user = Db.Model('User').GetUser(name)
        
        groups = ['Udacity', 'PowerRangers']
        user.UpdateUserGroups(groups)
        
        # Verify that the groups were updated properly
        self.assertEqual(user.groups, groups)
        
        # Verify that the groups were updated in memcache
        userMem = self.cache.GetUser(name)
        self.assertEqual(userMem.groups, groups)

######## Group #########
class GroupTest(unittest.TestCase):
    def setUp(self):
        # First, create an instance of the Testbed class.
        self.testbed = testbed.Testbed()
        # Then activate the testbed, which prepares the service stubs for use.
        self.testbed.activate()
        # Service stubs to use.
        self.testbed.init_datastore_v3_stub()
        self.testbed.init_memcache_stub()
        self.cache = Memcache.MemcacheGroup()

    def tearDown(self):
        self.testbed.deactivate()
        
    # Make sure Group creation is properly done in DB and Memcache
    def test_CreateGroup(self):
        name = 'PowerRangers'
        users = ['Sim', 'Pink']
        Db.Model('Group').PutGroup(name, users)
        group = Db.Model('Group').GetGroup(name)
        
        self.assertEqual(name, group.name)
        
        # Verify that it was properly put in memcache
        groupMem = self.cache.GetGroup(name)
        
        self.assertEqual(name, groupMem.name)
        
        # Verify that users are the same
        self.assertEqual(groupMem.users, users)
        self.assertEqual(group.users, users)
        
    # Make sure Group creation is properly done in DB and Memcache
    def test_CreateGroup(self):
        name = 'PowerRangers'
        users = ['Sim', 'Pink']
        Db.Model('Group').PutGroup(name, users)
        group = Db.Model('Group').GetGroup(name)
        
        self.assertEqual(name, group.name)
        
        # Verify that it was properly put in memcache
        groupMem = self.cache.GetGroup(name)
        
        self.assertEqual(name, groupMem.name)
        
        # Verify that users are the same
        self.assertEqual(groupMem.users, users)
        self.assertEqual(group.users, users)
        
    # Ensure that you can maintain the Udacity group
    def test_MaintainUdacity(self, ):
        name = 'Udacity'
        users = ['Sim']
        
        Db.Model('Group').AddUserToUdacity(users[0])
        # Verify that Udacity group has been created
        group = self.cache.GetGroup(name)
        self.assertIn(users[0], group.users)
        
        newUser = 'Jessica'
        Db.Model('Group').AddUserToUdacity(newUser)
        users.append(newUser)
        # Verify that Udacity now contains 'Jessica' as well
        group = self.cache.GetGroup(name)
        self.assertListEqual(sorted(group.users), sorted(users))
        
        # Add a user to Udacity but through generic method
        newUser = 'Samantha'
        Db.Model('Group').AddUser(name, newUser)
        
        # Verify that Sim is now with Jessica and Samantha
        group = self.cache.GetGroup(name)
        users.append(newUser)
        self.assertEqual(sorted(group.users), sorted(users))
        
        # Ensure that you cannot put the same person multiple times
        Db.Model('Group').AddUserToUdacity('Sim')
        group = self.cache.GetGroup(name)
        self.assertEqual(len(users),3)
        self.assertEqual(sorted(group.users), sorted(users))
    
    # Ensure that you can maintain a group
    def test_MaintainGroup(self, ):
        name = 'PowerRangers'
        users = ['Sim']
        
        Db.Model('Group').AddUser(name, users[0])
        # Verify that group has been created
        group = self.cache.GetGroup(name)
        self.assertIn(users[0], group.users)
        groupMem = self.cache.GetGroup(name)
        self.assertIn(users[0], groupMem.users)
        
        newUser = 'Pink'
        Db.Model('User').CreateUser(newUser) # Create new User
        Db.Model('Group').AddUser(name, newUser)
        users.append(newUser)
        # Verify that PowerRangers now contains 'Pink' as well
        group = self.cache.GetGroup(name)
        self.assertListEqual(sorted(group.users), sorted(users))
        
        # Verify that 'Pink' considers herself as member of PowerRangers
        pink = Db.Model('User').GetUser(newUser)
        self.assertIn(name, pink.groups)
        
        # Try to add Pink again
        Db.Model('Group').AddUser(name, newUser)
        group = self.cache.GetGroup(name)
        self.assertEqual(len(users),2)
        self.assertListEqual(sorted(group.users), sorted(users))
        # Make sure she's in Udacity and PowerRangers
        pink = Db.Model('User').GetUser(newUser)
        self.assertIn('Udacity', pink.groups)
        self.assertIn(name, pink.groups)
        self.assertEqual(len(pink.groups),2)
        
        # Remove Pink from PowerRangers (poor her)
        Db.Model('Group').RemoveUser(name, newUser)
        users.remove(newUser)
        groupMem = self.cache.GetGroup(name)
        self.assertEqual(groupMem.users, users)
        group = Db.Model('Group').GetGroup(name)
        self.assertEqual(group.users, users)
        # Make sure she no longer considers herself part of PR (ouch..)
        pink = Db.Model('User').GetUser(newUser)
        self.assertNotIn(name, pink.groups)
        
if __name__ == '__main__':
    unittest.main()
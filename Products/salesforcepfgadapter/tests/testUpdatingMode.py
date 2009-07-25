# Integration tests specific to Salesforce adapter
#

import os, sys

if __name__ == '__main__':
    execfile(os.path.join(sys.path[0], 'framework.py'))

from zope.interface import providedBy
from zope.event import notify

from Products.Archetypes.event import ObjectEditedEvent
from Products.CMFCore.utils import getToolByName

from Products.Archetypes.public import DisplayList
from Products.ATContentTypes.tests.utils import FakeRequestSession
from Products.PloneFormGen.interfaces import IPloneFormGenField

from Products.salesforcebaseconnector.tests import sfconfig   # get login/pw

from Products.salesforcepfgadapter.tests import base
from Products.salesforcepfgadapter import config


class TestUpdateModes(base.SalesforcePFGAdapterTestCase):
    """ test alternate Salesforce adapter modes (update, upsert)"""
    
    def _createMember(self, id, pw, email, roles=('Member',)):
        pr = self.portal.portal_registration
        member = pr.addMember(id, pw, roles, properties={ 'username': id, 'email' : email })
        return member
    
    def afterSetUp(self):        
        super(TestUpdateModes, self).afterSetUp()
        self.folder.invokeFactory('FormFolder', 'ff1')
        self.ff1 = getattr(self.folder, 'ff1')
        
        # create our action adapter
        self.ff1.invokeFactory('SalesforcePFGAdapter', 'contact_adapter')
        
        # disable mailer adapter
        self.ff1.setActionAdapter(('contact_adapter',))
        
        # configure our action adapter to create a contact on submission
        # last name is the lone required field
        self.ff1.contact_adapter.setTitle('Salesforce Action Adapter')
        self.ff1.contact_adapter.setSFObjectType('Contact')
        self.ff1.contact_adapter.setFieldMap((
            {'field_path': 'replyto', 'form_field': 'Your E-Mail Address', 'sf_field': 'Email'},
            {'field_path': 'comments', 'form_field': 'Comments', 'sf_field': 'LastName'}))
        
    
    def beforeTearDown(self):
        """clean up SF data"""
        ids = self._todelete
        if ids:
            while len(ids) > 200:
                self.salesforce.delete(ids[:200])
                ids = ids[200:]
            self.salesforce.delete(ids)
    
    def testUpsertPrimaryKeyMatch(self):
        """Ensure that our Salesforce Adapter mapped objects
           find their way into the appropriate Salesforce.com
           instance.
        """
        
        # build the request and submit the form
        fields = self.ff1._getFieldObjects()
        request = base.FakeRequest(replyto = 'plonetestcase@plone.org', # mapped to Email (see above) 
                                   comments='PloneTestCase')            # mapped to LastName (see above)
        
        self.ff1.contact_adapter.onSuccess(fields, request)
        
        # direct query of Salesforce to get the id of the newly created contact
        res = self.salesforce.query(['Id',],self.ff1.contact_adapter.getSFObjectType(),
                                    "Email='plonetestcase@plone.org' and LastName='PloneTestCase'")
        self._todelete.append(res['records'][0]['Id'])
        
        # assert that our newly created Contact was found
        self.assertEqual(1, res['size'])
    
        # set mode to 'upsert' so we update rather than create
        self.ff1.contact_adapter.setCreationMode('upsert')
        self.ff1.contact_adapter.setPrimaryKeyField('Email')
        
        # submit again, after changing the non-key value
        request = base.FakeRequest(replyto = 'plonetestcase@plone.org', # this is the Primary key
                                   comments='PloneTestCaseChanged')     # mapped to LastName (see above)
        self.ff1.contact_adapter.onSuccess(fields, request)
        
        # we should only get on record, and the name should be changed
        res = self.salesforce.query(['Id','LastName'],self.ff1.contact_adapter.getSFObjectType(),
                                    "Email='plonetestcase@plone.org'")
        for item in res['records']:
            self._todelete.append(item['Id'])
        self.assertEqual(1, res['size'])
        self.assertEqual('PloneTestCaseChanged', res['records'][0]['LastName'])      

    def testUpsertWithNoMatchingRecord(self):
        """Ensure that our Salesforce Adapter mapped objects
           find their way into the appropriate Salesforce.com
           instance.
        """
        # set mode to 'upsert' so we update rather than create
        self.ff1.contact_adapter.setCreationMode('upsert')
        self.ff1.contact_adapter.setPrimaryKeyField('Email')
        
        # build the request and submit the form
        fields = self.ff1._getFieldObjects()
        request = base.FakeRequest(replyto = 'plonetestcase@plone.org', # mapped to Email (see above) 
                                   comments='PloneTestCase')            # mapped to LastName (see above)
        
        # we are in upsert mode, does it work?
        self.ff1.contact_adapter.onSuccess(fields, request)
        
        # direct query of Salesforce to get the id of the newly created contact
        res = self.salesforce.query(['Id',],self.ff1.contact_adapter.getSFObjectType(),
                                    "Email='plonetestcase@plone.org' and LastName='PloneTestCase'")
        self._todelete.append(res['records'][0]['Id'])
        
        # assert that our newly created Contact was found
        self.assertEqual(1, res['size'])
        
        # submit again, after changing the non-key value
        request = base.FakeRequest(replyto = 'plonetestcase2@plone.org', # this is the Primary key
                                   comments='PloneTestCaseChanged')     # mapped to LastName (see above)
        self.ff1.contact_adapter.onSuccess(fields, request)
        
        # we should get one record
        res = self.salesforce.query(['Id'],self.ff1.contact_adapter.getSFObjectType(),
                                    "Email='plonetestcase@plone.org'")
        for item in res['records']:
            self._todelete.append(item['Id'])
        self.assertEqual(1, res['size'])

        # we should get one record for the newest upsert.
        res = self.salesforce.query(['Id'],self.ff1.contact_adapter.getSFObjectType(),
                                    "Email='plonetestcase2@plone.org'")
        for item in res['records']:
            self._todelete.append(item['Id'])
        self.assertEqual(1, res['size'])
    
    def testUseUIDOnUpsert(self):
        self.app.REQUEST['SESSION'] = FakeRequestSession()
        import pdb; pdb.set_trace( )
        # set mode to 'upsert' so we update rather than create
        self.ff1.contact_adapter.setCreationMode('upsert')
        self.ff1.contact_adapter.setPrimaryKeyField('Email')
        self.ff1.contact_adapter.setPrepopulateFieldValues(True)
        # Make sure we set the SF prepopulators
        notify(ObjectEditedEvent(self.ff1.contact_adapter))
        
        # create a user with an email address
        id = 'ploney'
        pw = 'secret'
        email = 'original@plonetestcase.org'
        member = self._createMember(id, pw, email, roles=('Member',))
        # log in as this user
        self.login(member.id)
        # View form to trigger Salesforce lookup
        # XXX TODO This method of grabbing the form does not trigger the prepopulator, so things aren't
        # working like the do TTW
        # Perhaps try calling the view implemented with FieldValueRetriever on the first field?
        # PSUEDO CODE
        # form_obj = self.folder.ff1
        # first_field = form_obj.first_field
        # view = something to get view
        form = self.folder.restrictedTraverse('ff1')
        # Inspect SESSION to verify it's been set to something ID-like
        self.failUnless(config.SESSION_KEY in self.app.REQUEST.SESSION, "Failed to set session variable!")
        # Change primary key value 
        request = base.FakeRequest(replyto = 'changed@plonetestcase.org', # this is the Primary key
                                   comments='PloneTestCase')             # mapped to LastName (see above)        
        # Submit form
        self.ff1.contact_adapter.onSuccess(fields, request)
        
        # Verify there are no records returned when querying for the original email
        res = self.salesforce.query(['Id'],self.ff1.contact_adapter.getSFObjectType(),
                                    "Email='original@plonetestcase.org'")
        for item in res['records']:
            self._todelete.append(item['Id'])
        self.assertEqual(0, res['size'])
        
        # Verify that the record corresponding to the Session ID has been changed!
        res = self.salesforce.query(['Id'],self.ff1.contact_adapter.getSFObjectType(),
                                    "Email='changed@plonetestcase.org'")
        for item in res['records']:
            self._todelete.append(item['Id'])
        self.assertEqual(1, res['size'])
        self.assertEqual('changed@plonetestcase.org', res['records'][0]['Email'])
    

def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(TestUpdateModes))
    return suite

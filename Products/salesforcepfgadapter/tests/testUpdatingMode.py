# Integration tests specific to Salesforce adapter
#

import os, sys

if __name__ == '__main__':
    execfile(os.path.join(sys.path[0], 'framework.py'))

from zope.event import notify

from Products.Archetypes.event import ObjectEditedEvent

from Products.ATContentTypes.tests.utils import FakeRequestSession

from Products.Five.testbrowser import Browser
from Products.salesforcepfgadapter.tests import base

class TestUpdateModes(base.SalesforcePFGAdapterFunctionalTestCase):
    """ test alternate Salesforce adapter modes (update, upsert)"""
    
    def _createMember(self, id, pw, email, roles=('Member',)):
        pr = self.portal.portal_registration
        member = pr.addMember(id, pw, roles, properties={ 'username': id, 'email' : email })
        return member
    
    def _createTestContact(self, data):
        res = self.salesforce.create([data])
        self.objid = id = res[0]['id']
        self._todelete.append(id)
    
    def _assertNoExistingTestContact(self):
        res = self.salesforce.query(['Id',],self.ff1.contact_adapter.getSFObjectType(),
                                    "Email='plonetestcase@plone.org' and LastName='PloneTestCase'")
        self.assertEqual(0, res['size'], 'PloneTestCase contact already present in database.  Please '
                                         'remove it before running the tests.')

    def afterSetUp(self):
        super(TestUpdateModes, self).afterSetUp()
        self.setRoles(['Manager'])
        self.portal.invokeFactory('FormFolder', 'ff1')
        self.ff1 = getattr(self.portal, 'ff1')
        
        # create our action adapter
        self.ff1.invokeFactory('SalesforcePFGAdapter', 'contact_adapter')
        
        # disable mailer adapter
        self.ff1.setActionAdapter(('contact_adapter',))
        
        # remove the default replyto field default expression
        self.ff1.replyto.setFgTDefault('')
        self.ff1.replyto.setFgDefault('')
        
        # configure our action adapter to create a contact on submission
        # last name is the lone required field
        self.ff1.contact_adapter.setTitle('Salesforce Action Adapter')
        self.ff1.contact_adapter.setSFObjectType('Contact')
        self.ff1.contact_adapter.setFieldMap((
            {'field_path': 'replyto', 'form_field': 'Your E-Mail Address', 'sf_field': 'Email'},
            {'field_path': 'comments', 'form_field': 'Comments', 'sf_field': 'LastName'}))
        self.ff1.manage_delObjects(['topic'])
        
        self.portal.portal_workflow.doActionFor(self.ff1, 'publish')
        
        self.app.REQUEST['SESSION'] = FakeRequestSession()
    
    def beforeTearDown(self):
        """clean up SF data"""
        ids = self._todelete
        if ids:
            while len(ids) > 200:
                self.salesforce.delete(ids[:200])
                ids = ids[200:]
            self.salesforce.delete(ids)
    
    def testUpdateModeInitialLoadAndSubmission(self):
        """Ensure that our Salesforce Adapter mapped objects
           find their way into the appropriate Salesforce.com
           instance.
        """
        # first create a new contact - build the request and submit the form
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
    
        # set mode to 'update'
        self.ff1.contact_adapter.setCreationMode('update')
        self.ff1.contact_adapter.setUpdateMatchExpression("string:Email='plonetestcase@plone.org'")
        notify(ObjectEditedEvent(self.ff1.contact_adapter))
        
        # open a test browser on the initial form
        browser = Browser()
        browser.handleErrors = False
        browser.open('http://nohost/plone/ff1')
        
        # update the comments field
        self.assertEqual(browser.getControl(name='comments').value, 'PloneTestCase')
        browser.getControl(name='comments').value = 'PloneTestCaseChanged'
        
        # submit again
        browser.getControl('Submit').click()
        
        # we should only get one record, and the name should be changed
        res = self.salesforce.query(['Id','LastName'],self.ff1.contact_adapter.getSFObjectType(),
                                    "Email='plonetestcase@plone.org'")
        for item in res['records']:
            self._todelete.append(item['Id'])
        self.assertEqual(1, res['size'])
        self.assertEqual('PloneTestCaseChanged', res['records'][0]['LastName'])

    def testUpdateModeCreateIfNoMatch(self):
        self._assertNoExistingTestContact()

        # set mode to 'update', actionIfNoExistingObject to 'create'
        self.ff1.contact_adapter.setCreationMode('update')
        self.ff1.contact_adapter.setUpdateMatchExpression("string:Email='plonetestcase@plone.org'")
        self.ff1.contact_adapter.setActionIfNoExistingObject('create')
        notify(ObjectEditedEvent(self.ff1.contact_adapter))
        
        # open a test browser on the initial form
        browser = Browser()
        browser.handleErrors = False
        browser.open('http://nohost/plone/ff1')
        
        # confirm no existing values; set some new ones and submit
        self.assertEqual(browser.getControl(name='replyto').value, '')
        browser.getControl(name='replyto').value = 'plonetestcase@plone.org'
        self.assertEqual(browser.getControl(name='comments').value, '')
        browser.getControl(name='comments').value = 'PloneTestCase'
        browser.getControl('Submit').click()
        
        # now there should be one (new) record
        res = self.salesforce.query(['Id','LastName'],self.ff1.contact_adapter.getSFObjectType(),
                                    "Email='plonetestcase@plone.org'")
        for item in res['records']:
            self._todelete.append(item['Id'])
        self.assertEqual(1, res['size'])
        self.assertEqual('PloneTestCase', res['records'][0]['LastName'])

    def testUpdateModeAbortIfNoMatch(self):
        self._assertNoExistingTestContact()

        # set mode to 'update', actionIfNoExistingObject to 'abort'
        self.ff1.contact_adapter.setCreationMode('update')
        self.ff1.contact_adapter.setUpdateMatchExpression("string:Email='plonetestcase@plone.org'")
        self.ff1.contact_adapter.setActionIfNoExistingObject('abort')
        notify(ObjectEditedEvent(self.ff1.contact_adapter))
        
        # open a test browser on the initial form ... should get redirected
        # to the site root with a portal message.
        browser = Browser()
        browser.open('http://nohost/plone/ff1')
        self.assertEqual(browser.url, 'http://nohost/plone')
        self.failUnless('Could not find item to edit.' in browser.contents)

def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(TestUpdateModes))
    return suite

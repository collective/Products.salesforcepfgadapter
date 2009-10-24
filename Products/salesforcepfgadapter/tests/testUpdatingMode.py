# Integration tests specific to Salesforce adapter
#

import os, sys

if __name__ == '__main__':
    execfile(os.path.join(sys.path[0], 'framework.py'))

from Testing import ZopeTestCase as ztc
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
    
    def _createTestContact(self):
        # first create a new contact - build the request and submit the form
        self.ff1.contact_adapter.setCreationMode('create')
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
        
        self.ff1.contact_adapter.setCreationMode('update')
    
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
        self.ff1.contact_adapter.setCreationMode('update')
        self.ff1.contact_adapter.setUpdateMatchExpression("string:Email='plonetestcase@plone.org'")
        notify(ObjectEditedEvent(self.ff1.contact_adapter))
        
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
        self._createTestContact()

        # open a test browser on the initial form
        browser = Browser()
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

        # set actionIfNoExistingObject to 'create'
        self.ff1.contact_adapter.setActionIfNoExistingObject('create')
        notify(ObjectEditedEvent(self.ff1.contact_adapter))
        
        # open a test browser on the initial form
        browser = Browser()
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

        # set actionIfNoExistingObject to 'abort'
        self.ff1.contact_adapter.setActionIfNoExistingObject('abort')
        
        # open a test browser on the initial form ... should get redirected
        # to the site root with a portal message.
        browser = Browser()
        browser.open('http://nohost/plone/ff1')
        self.assertEqual(browser.url, 'http://nohost/plone')
        self.failUnless('Could not find item to edit.' in browser.contents)
    
    def testUpdateModeAbortIfNoMatchOnDirectSubmission(self):
        self._assertNoExistingTestContact()

        # make sure the 'abort' setting of actionIfNoExistingObject is
        # respected even if the check on the initial form load was bypassed.
        # To test, we'll first load the form with the setting on 'create'...
        self.ff1.contact_adapter.setActionIfNoExistingObject('create')
        browser = Browser()
        browser.open('http://nohost/plone/ff1')
        
        # then switch it to 'abort' and submit the form...
        self.ff1.contact_adapter.setActionIfNoExistingObject('abort')
        browser.getControl(name='replyto').value = 'plonetestcase@plone.org'
        browser.getControl(name='comments').value = 'PloneTestCase'
        browser.getControl('Submit').click()
        
        # should end up on the portal root, with an error message
        self.assertEqual(browser.url, 'http://nohost/plone')
        self.failUnless('Could not find item to edit.' in browser.contents)
    
    def testUpdateWhenObjectInitiallyFoundGoesMissing(self):
        # create a contact and load it into the form...
        self._createTestContact()
        browser = Browser()
        browser.open('http://nohost/plone/ff1')
        self.assertEqual(browser.getControl(name='comments').value, 'PloneTestCase')
        
        # now manually remove the new contact from Salesforce
        self.salesforce.delete(self._todelete[-1:])
        
        # on submission, the adapter will get a Id from the session and will try
        # to update the object with that Id, but we'll get an exception from SF
        # since the object no longer exists
        try:
            browser.getControl('Submit').click()
        except:
            self.assertEqual(self.portal.error_log.getLogEntries()[0]['value'],
                'Failed to update Contact in Salesforce: entity is deleted')

    def testNoUpdateIfInitialSessionWasDestroyed(self):
        # If the session is destroyed (e.g. if Zope restarts) or expires, then
        # we could get a submission that is supposed to be an update, but is
        # treated as a creation attempt.  Let's be sure to avoid that...
        self._createTestContact()
        self.ff1.contact_adapter.setActionIfNoExistingObject('create')
        browser = Browser()
        browser.open('http://nohost/plone/ff1')
        
        # reset the sessions
        self.app.temp_folder._delObject('session_data')
        ztc.utils.setupCoreSessions(self.app)

        # submit the form
        browser.getControl('Submit').click()

        # make sure we didn't create a new item in Salesforce
        res = self.salesforce.query("SELECT Id FROM Contact WHERE Email='plonetestcase@plone.org' and LastName='PloneTestCase'")
        self.failIf(res['size'] > 1, 'Known issue: Accidental creation following session destruction.')
    
    def testValuesFromRequestUsedAfterValidationFailure(self):
        self._createTestContact()
        browser = Browser()
        browser.open('http://nohost/plone/ff1')
        self.assertEqual(browser.getControl(name='replyto').value,
            'plonetestcase@plone.org')
        browser.getControl(name='replyto').value = ''
        browser.getControl('Submit').click()
        self.failUnless('Please correct the indicated errors.' in browser.contents)
        self.assertEqual(browser.getControl(name='replyto').value, '')

def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(TestUpdateModes))
    return suite

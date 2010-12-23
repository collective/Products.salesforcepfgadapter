# Integration tests specific to Salesforce adapter
#

import os, sys

if __name__ == '__main__':
    execfile(os.path.join(sys.path[0], 'framework.py'))

from Testing import ZopeTestCase as ztc
from zope.event import notify

from Products.ATContentTypes.tests.utils import FakeRequestSession

from Products.Five.testbrowser import Browser
from Products.salesforcepfgadapter.tests import base

try:
    from Products.Archetypes.event import ObjectEditedEvent as AdapterModifiedEvent
except ImportError:
    # BBB Zope 2.9 / AT 1.4
    from zope.app.event.objectevent import ObjectModifiedEvent as AdapterModifiedEvent


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
        request.SESSION = {}
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
        
        # Make topic optional so that we can test erasing values.
        self.ff1.topic.setRequired(False)
                
        # configure our action adapter to create a contact on submission
        # last name is the lone required field
        self.ff1.contact_adapter.setTitle('Salesforce Action Adapter')
        self.ff1.contact_adapter.setSFObjectType('Contact')
        self.ff1.contact_adapter.setFieldMap((
            {'field_path': 'replyto', 'form_field': 'Your E-Mail Address', 'sf_field': 'Email'},
            {'field_path': 'comments', 'form_field': 'Comments', 'sf_field': 'LastName'},
            {'field_path': 'topic', 'form_field': 'Subject', 'sf_field': 'Phone'},))
        self.ff1.contact_adapter.setCreationMode('update')
        self.ff1.contact_adapter.setUpdateMatchExpression("string:Email='plonetestcase@plone.org'")
        notify(AdapterModifiedEvent(self.ff1.contact_adapter))
        
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

    def testUpdateModeWithChainedUpdateAdapters(self):
        # add an Account and associated Contact in Salesforce.
        res = self.salesforce.create({
            'type': 'Account',
            'Name': 'Test Account',
            })
        account_id = res[0]['id']
        self._todelete.append(account_id)
        res = self.salesforce.create({
            'type': 'Contact',
            'LastName': 'McPloneson',
            'Email': 'plonetestcase@plone.org',
            'AccountId': account_id,
            })
        self._todelete.append(res[0]['id'])
        
        # add an Account adapter for updating the account we created,
        # and make the Contact adapter map its object id to AccountId
        self.ff1.invokeFactory('SalesforcePFGAdapter', 'account_adapter')
        self.ff1.invokeFactory('FormStringField', 'account_name')
        self.ff1.account_adapter.setSFObjectType('Account')
        self.ff1.account_adapter.setCreationMode('update')
        self.ff1.account_adapter.setUpdateMatchExpression("string:Id='%s'" % account_id)
        self.ff1.account_adapter.setFieldMap((
            {'field_path': 'account_name', 'form_field': '', 'sf_field': 'Name'},
            ))
        self.ff1.account_adapter.setPresetValueMap((
            {'value': 'ChangedDescription', 'sf_field': 'Description'},
            ))
        self.ff1.contact_adapter.setDependencyMap((
            {'adapter_id': 'account_adapter', 'adapter_name': '', 'sf_field': 'AccountId'},
            ))
        notify(AdapterModifiedEvent(self.ff1.account_adapter))
        
        browser = Browser()
        browser.open('http://nohost/plone/ff1')
        self.assertEqual(browser.getControl(name='account_name').value, 'Test Account')
        self.assertEqual(browser.getControl(name='comments').value, 'McPloneson')
        browser.getControl(name='account_name').value = 'Changed Test Account'
        browser.getControl(name='comments').value = 'PloneTestCaseChanged'
        browser.getControl('Submit').click()

        # we should only get one record, and the name should be changed
        res = self.salesforce.query(['Id','Description', 'Name'], 'Account',
                                    "Id='%s'" % account_id)
        self.assertEqual(1, res['size'])
        self.assertEqual('Changed Test Account', res[0].Name)
        self.assertEqual('ChangedDescription', res[0].Description)
        res = self.salesforce.query(['Id','LastName','AccountId'],self.ff1.contact_adapter.getSFObjectType(),
                                    "Email='plonetestcase@plone.org'")
        self.assertEqual(1, res['size'])
        self.assertEqual('PloneTestCaseChanged', res[0].LastName)
        self.assertEqual(account_id, res[0].AccountId)
        
        # now put the contact adapter in create mode, and make sure that works
        # too
        self.ff1.contact_adapter.setCreationMode('create')
        notify(AdapterModifiedEvent(self.ff1.contact_adapter))
        browser.open('http://nohost/plone/ff1')
        self.assertEqual(browser.getControl(name='account_name').value, 'Changed Test Account')
        self.assertEqual(browser.getControl(name='comments').value, '')
        self.assertEqual(browser.getControl(name='replyto').value, '')
        browser.getControl(name='account_name').value = 'Test Account'
        browser.getControl(name='comments').value = 'PloneTestCase'
        browser.getControl(name='replyto').value = 'plonetestcase2@plone.org'
        browser.getControl('Submit').click()
        res = self.salesforce.query(['Id', 'AccountId'], 'Contact',
                                    "LastName='PloneTestCase'")
        self._todelete.append(res[0].Id)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0].AccountId, account_id)
        self._todelete.append(res[0].Id)

    def testUpdateModeCreateIfNoMatch(self):
        self._assertNoExistingTestContact()

        # set actionIfNoExistingObject to 'create'
        self.ff1.contact_adapter.setActionIfNoExistingObject('create')
        notify(AdapterModifiedEvent(self.ff1.contact_adapter))
        
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
    
    def testUpdateModeQuietAbortIfNoMatch(self):
        self._assertNoExistingTestContact()

        self.ff1.contact_adapter.setActionIfNoExistingObject('quiet_abort')
        
        # open a test browser on the initial form; submit it.  Should work fine
        # without writing anything to salesforce.
        browser = Browser()
        browser.open('http://nohost/plone/ff1')
        self.assertEqual(browser.url, 'http://nohost/plone/ff1')
        self.assertEqual(browser.getControl(name='replyto').value, '')
        browser.getControl(name='replyto').value = 'plonetestcase@plone.org'
        self.assertEqual(browser.getControl(name='comments').value, '')
        browser.getControl(name='comments').value = 'PloneTestCase'
        browser.getControl('Submit').click()
        self.failUnless('Thank You' in browser.contents)

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
        browser.handleErrors = False
        browser.open('http://nohost/plone/ff1')
        self.assertEqual(browser.getControl(name='comments').value, 'PloneTestCase')
        
        # now manually remove the new contact from Salesforce
        self.salesforce.delete(self._todelete[-1:])
        
        # on submission, the adapter will get a Id from the session and will try
        # to update the object with that Id, but we'll get an exception from SF
        # since the object no longer exists
        try:
            browser.getControl('Submit').click()
        except Exception, e:
            self.assertEqual(e.message,
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

    def testUpdateModeCreateIfNoMatchResubmitAfterBrowserBackButton(self):
        # We have a form in update mode and configured to create a new
        # object if there is not matching object to update. Consider
        # the following scenario:
        #
        #  1. User gets to the form and submits it.
        #  2. A new record in Salesforce is created and user is taken
        #     to the thank you page.
        #  3. User hits the browser back button
        #
        # At that point we want to make sure that if the user re
        # submits the form, we don't create a new object in Salesforce.
        # Instead, the record created the first time that form was
        # submited must be updated. Let's test this scenario.
        self._assertNoExistingTestContact()

        # set actionIfNoExistingObject to 'create'
        self.ff1.contact_adapter.setActionIfNoExistingObject('create')
        notify(AdapterModifiedEvent(self.ff1.contact_adapter))

        # open a test browser and submit the form once
        browser = Browser()
        browser.open('http://nohost/plone/ff1')

        browser.getControl(name='replyto').value = 'plonetestcase@plone.org'
        browser.getControl(name='comments').value = 'PloneTestCase'
        browser.getControl('Submit').click()

        # now there should be one (new) record
        query_tuple = (['Id','LastName'],
            self.ff1.contact_adapter.getSFObjectType(),
            "Email='plonetestcase@plone.org'")
        res = self.salesforce.query(*query_tuple)

        for item in res['records']:
            self._todelete.append(item['Id'])
        self.assertEqual(1, res['size'])
        self.assertEqual('PloneTestCase', res['records'][0]['LastName'])

        # hit the back button
        browser.goBack()

        # change the comments and resubmit the form
        browser.getControl(name='replyto').value = 'plonetestcase@plone.org'
        browser.getControl(name='comments').value = 'New PloneTestCase'
        browser.getControl('Submit').click()

        # there should be still only one record and the comments field
        # should have changed
        res = self.salesforce.query(*query_tuple)

        for item in res['records']:
            self._todelete.append(item['Id'])
        self.assertEqual(1, res['size'])
        self.assertEqual('New PloneTestCase', res['records'][0]['LastName'])
        
    def testUpdateNullifiesEmptyFields(self):
        """
        Tests that, in update mode, empty fields overwrite existing data
        with a null value.
        """
        
        self._createTestContact()
        
        # Set actionIfNoExistingObject to 'abort.'
        self.ff1.contact_adapter.setActionIfNoExistingObject('abort')
        notify(AdapterModifiedEvent(self.ff1.contact_adapter))
        
        browser = Browser()
        browser.open('http://nohost/plone/ff1')
        
        browser.getControl(name='replyto').value = 'plonetestcase@plone.org'
        browser.getControl(name='comments').value = 'PloneTestCase'
        browser.getControl(name='topic').value = '(123) 456-7890'
        browser.getControl('Submit').click()
        
        # Now there should be one (new) record.
        query_tuple = (['Id','LastName','Phone'],
            self.ff1.contact_adapter.getSFObjectType(),
            "Email='plonetestcase@plone.org'")
        res = self.salesforce.query(*query_tuple)
        
        for item in res['records']:
            self._todelete.append(item['Id'])
        self.assertEqual(1, res['size'])
        self.assertEqual('PloneTestCase', res['records'][0]['LastName'])
        self.assertEqual('(123) 456-7890', res['records'][0]['Phone'])
        
        # We can now update the item by removing the phone number.
        browser.open('http://nohost/plone/ff1')
        self.assertEqual('(123) 456-7890', browser.getControl(name='topic').value)
        browser.getControl(name='topic').value = ''
        browser.getControl('Submit').click()
        
        # The record should now contain an empty phone number.
        query_tuple = (['Id','LastName','Phone'],
            self.ff1.contact_adapter.getSFObjectType(),
            "Email='plonetestcase@plone.org'")
        res = self.salesforce.query(*query_tuple)

        self.assertEqual(1, res['size'])
        self.assertEqual('PloneTestCase', res['records'][0]['LastName'])
        self.assertEqual('', res['records'][0]['Phone'])

def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(TestUpdateModes))
    return suite

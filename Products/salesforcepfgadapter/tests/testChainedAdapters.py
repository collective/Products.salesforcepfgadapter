# Integration tests specific to Salesforce adapter
#

import os, sys

if __name__ == '__main__':
    execfile(os.path.join(sys.path[0], 'framework.py'))

from Products.salesforcepfgadapter.tests import base
from Products.CMFCore.utils import getToolByName

from Products.salesforcebaseconnector.tests import sfconfig   # get login/pw

class TestChainedAdapters(base.SalesforcePFGAdapterTestCase):
    """ test adapters that create separate, related objects """
    
    def afterSetUp(self):
        super(TestChainedAdapters, self).afterSetUp()
        self.folder.invokeFactory('FormFolder', 'ff1')
        self.ff1 = getattr(self.folder, 'ff1')
    
    def beforeTearDown(self):
        """clean up SF data"""
        ids = self._todelete
        if ids:
            while len(ids) > 200:
                self.salesforce.delete(ids[:200])
                ids = ids[200:]
            self.salesforce.delete(ids)
    
    def testGetLocalSFAdapters(self):
        """getLocalSFAdapters is used just to populate the DataGridField with names of
        all other local adapters besides self"""
        # create two adapters
        for x in range(3):
            self.ff1.invokeFactory('SalesforcePFGAdapter', 'adapter%s' % x)
            item = getattr(self.ff1, 'adapter%s' % x)
            item.setTitle('Adapter #%s' % x)
        
        # we'll grab the first one -- calling getLocalSFAdapters should just return the other two
        # not the first one and not the by-default-created Mailer adapter
        first = getattr(self.ff1, 'adapter0')
        adapter_names = [mapping.initialData['adapter_name'] for mapping in first.getLocalSFAdapters()]
        adapter_ids = [mapping.initialData['adapter_id'] for mapping in first.getLocalSFAdapters()]
        for x in range(1,3):
            self.failUnless('Adapter #%s' % x in adapter_names)
            self.failUnless('adapter%s' % x in adapter_ids)
        self.failIf('Adapter #0' in adapter_names)
        # implicit test that the Mailer adapter isn't here: len should be 2
        self.failUnless(len(adapter_names)==2)
    
    def testChainedDependenciesInsertCorrectly(self):
        # create multiple action adapters
        self.ff1.invokeFactory('SalesforcePFGAdapter', 'contact_adapter')
        self.ff1.invokeFactory('SalesforcePFGAdapter', 'account_adapter')
        
        # disable mailer adapter
        self.ff1.setActionAdapter(('contact_adapter','account_adapter',))
        
        # configure our contact_adapter to create a contact on submission
        # last name is the lone required field
        self.ff1.contact_adapter.setTitle('Salesforce Contact Action Adapter')
        self.ff1.contact_adapter.setSFObjectType('Contact')
        self.ff1.contact_adapter.setFieldMap((
            {'field_path': 'replyto', 'form_field': 'Your E-Mail Address', 'sf_field': 'Email'},
            {'field_path': 'comments', 'form_field': 'Comments', 'sf_field': 'LastName'}))
        
        # configure our account_adapter to create a contact on submission
        # last name is the lone required field
        self.ff1.account_adapter.setTitle('Salesforce Account Action Adapter')
        self.ff1.account_adapter.setSFObjectType('Account')
        self.ff1.account_adapter.setFieldMap((
            {'field_path': 'topic', 'form_field': 'Subject', 'sf_field': 'Name'},))
        
        # set up dependencies
        self.ff1.contact_adapter.setDependencyMap(({'adapter_id': 'account_adapter',
                                                    'adapter_name': 'Salesforce Account Action Adapter',
                                                    'sf_field':'AccountId'},))
        request = base.FakeRequest(topic="testChainedDependenciesInsertCorrectly",
                              replyto = 'testChainedDependenciesInsertCorrectly@plone.org',
                              comments='testChainedDependenciesInsertCorrectly')
        request.SESSION = {}

        # call onSuccess on last SF adapter in form
        fields = self.ff1._getFieldObjects()
        self.ff1.account_adapter.onSuccess(fields, request)
        
        # salesforce queries and cleanup
        contact_res = self.salesforce.query(
            "SELECT Id, AccountId FROM Contact WHERE LastName='%s' AND Email='%s'" % (
                'testChainedDependenciesInsertCorrectly',
                'testChainedDependenciesInsertCorrectly@plone.org'
                )
            )
        self._todelete.append(contact_res['records'][0]['Id']) # for clean-up

        account_res = self.salesforce.query(
            "SELECT Id FROM Account WHERE Name = 'testChainedDependenciesInsertCorrectly'")
        account_id = account_res['records'][0]['Id']
        self._todelete.append(account_id) # for clean-up

        # assertions
        self.assertEqual(1, contact_res['size'])
        self.assertEqual(1, account_res['size'])
        self.assertEqual(account_id, contact_res['records'][0]['AccountId'])
    
    def testChainedAdaptersAccountsForDisabledAdapters(self):
        """We delegate the creation of all Salesforce objects for
           each adapter to the final adapter.  This final adapter,
           however, must be an adapter that's enabled (i.e. present
           in the getActionAdapter list). Here we ensure that all
           active adapters are successfully run (this would be done
           by the final active adapter -- but that is an unimportant
           implementation detail.)
        """
        # create multiple action adapters
        self.ff1.invokeFactory('SalesforcePFGAdapter', 'contact_adapter')
        self.ff1.invokeFactory('SalesforcePFGAdapter', 'account_adapter')
        
        # disable mailer adapter, and more importantly for our case,
        # we disable the account_adapter, which is the final Salesforce
        # Adapter within the form folder
        self.ff1.setActionAdapter(('contact_adapter',))
        
        # configure our contact_adapter to create a contact on submission
        # last name is the lone required field
        self.ff1.contact_adapter.setTitle('Salesforce Contact Action Adapter')
        self.ff1.contact_adapter.setSFObjectType('Contact')
        self.ff1.contact_adapter.setFieldMap((
            {'field_path': 'replyto', 'form_field': 'Your E-Mail Address', 'sf_field': 'Email'},
            {'field_path': 'comments', 'form_field': 'Comments', 'sf_field': 'LastName'}))
        
        # configure our account_adapter to create a contact on submission
        # last name is the lone required field
        self.ff1.account_adapter.setTitle('Salesforce Account Action Adapter')
        self.ff1.account_adapter.setSFObjectType('Account')
        self.ff1.account_adapter.setFieldMap((
            {'field_path': 'topic', 'form_field': 'Subject', 'sf_field': 'Name'},))
        
        # set up dependencies
        self.ff1.contact_adapter.setDependencyMap(({'adapter_id': 'account_adapter',
                                                    'adapter_name':'Salesforce Account Action Adapter',
                                                    'sf_field':'AccountId'},))
        request = base.FakeRequest(topic="testChainedRespectDisabledFinalAdapters",
                              replyto = 'testChainedRespectDisabledFinalAdapters@plone.org',
                              comments='testChainedRespectDisabledFinalAdapters')
        request.SESSION = {}
        fields = self.ff1._getFieldObjects()
        
        # call onSuccess on last *active* SF adapter in form
        self.ff1.contact_adapter.onSuccess(fields, request)
        
        # salesforce queries and cleanup
        contact_res = self.salesforce.query(
            "SELECT Id, AccountId FROM Contact WHERE LastName='%s' AND Email='%s'" % (
                'testChainedRespectDisabledFinalAdapters',
                'testChainedRespectDisabledFinalAdapters@plone.org'
                )
            )
        self._todelete.append(contact_res['records'][0]['Id']) # for clean-up
        
        account_res = self.salesforce.query(
            "SELECT Id FROM Account WHERE Name = 'testChainedRespectDisabledFinalAdapters'")
        
        # assertions
        self.assertEqual(1, contact_res['size'])
        self.assertEqual(0, account_res['size'])
        self.failIf(contact_res['records'][0]['AccountId'])
    
    def testChainedAdaptersAccountsForNonexecutingAdapters(self):
        """We delegate the creation of all Salesforce objects for
           each adapter to the final adapter.  This final adapter,
           however, must be an adapter that's enabled (i.e. present
           in the getActionAdapter list). Here we ensure that all
           active adapters are successfully run (this would be done
           by the final active adapter -- but that is an unimportant
           implementation detail.)
        """
        # create multiple action adapters
        self.ff1.invokeFactory('SalesforcePFGAdapter', 'contact_adapter')
        self.ff1.invokeFactory('SalesforcePFGAdapter', 'account_adapter')
        
        # disable mailer adapter
        self.ff1.setActionAdapter(('contact_adapter','account_adapter',))
        
        # configure our contact_adapter to create a contact on submission
        # last name is the lone required field
        self.ff1.contact_adapter.setTitle('Salesforce Contact Action Adapter')
        self.ff1.contact_adapter.setSFObjectType('Contact')
        # ... but configure a totally bogus execution
        # condition that could never be true
        self.ff1.contact_adapter.setFieldMap((
            {'field_path': 'replyto', 'form_field': 'Your E-Mail Address', 'sf_field': 'Email'},
            {'field_path': 'comments', 'form_field': 'Comments', 'sf_field': 'LastName'}))
        
        # configure our account_adapter to create a contact on submission
        # last name is the lone required field
        self.ff1.account_adapter.setTitle('Salesforce Account Action Adapter')
        self.ff1.account_adapter.setSFObjectType('Account')
        self.ff1.account_adapter.setExecCondition('python:1 == 0')
        self.ff1.account_adapter.setFieldMap((
            {'field_path': 'topic', 'form_field': 'Subject', 'sf_field': 'Name'},))
        
        # set up dependencies
        self.ff1.contact_adapter.setDependencyMap(({'adapter_id': 'account_adapter',
                                                    'adapter_name': 'Salesforce Account Action Adapter',
                                                    'sf_field':'AccountId'},))
        request = base.FakeRequest(topic="testChainedRespectNonexecutableFinalAdapters",
                              replyto = 'testChainedRespectNonexecutableFinalAdapters@plone.org',
                              comments='testChainedRespectNonexecutableFinalAdapters')
        request.SESSION = {}
        fields = self.ff1._getFieldObjects()
        
        # call onSuccess on last *executable* SF adapter in form
        self.ff1.contact_adapter.onSuccess(fields, request)
        
        # salesforce queries and cleanup
        contact_res = self.salesforce.query(
            "SELECT Id, AccountId FROM Contact WHERE LastName='%s' AND Email='%s'" % (
                'testChainedRespectNonexecutableFinalAdapters',
                'testChainedRespectNonexecutableFinalAdapters@plone.org'
                )
            )
        self._todelete.append(contact_res['records'][0]['Id']) # for clean-up
        
        account_res = self.salesforce.query(
            "SELECT Id FROM Account WHERE Name = 'testChainedRespectNonexecutableFinalAdapters'")
        
        # assertions
        self.assertEqual(1, contact_res['size'])
        self.assertEqual(0, account_res['size'])
        self.failIf(contact_res['records'][0]['AccountId'])
    
    def testRenamedAdapterCleanedFromStaticParentAdapterVocabs(self):
        """Prove that retitling of an adapter shows the new
           titling in the static parent adapter list.
        """
        for i in range(1,3):
            self.ff1.invokeFactory('SalesforcePFGAdapter', 'salesforce%s' % i)
            self.ff1['salesforce%s' % i].setTitle('Salesforce Adapter #%i' % i)
        
        # salesforce2 could be a parent adapter to salesforce1
        parentAdapterOptions = self.ff1.salesforce1.getLocalSFAdapters()
        adapter_titles_for_mapping = [mapping.initialData['adapter_name'] for mapping in parentAdapterOptions]
        
        # make sure the subject field exists
        self.failUnless('Salesforce Adapter #2' in adapter_titles_for_mapping)
        
        # map our soon to be retitled item
        fm = self.ff1.salesforce1.getDependencyMap()
        fm[0]['sf_field'] = 'some-bogus-field'
        self.ff1.salesforce1.setDependencyMap(fm)
        
        # rename the subject field
        self.ff1.salesforce2.setTitle('Renamed Salesforce Adapter #2')
        
        # call our mutator to ensure that our mapping gets cleaned out
        fm = self.ff1.salesforce1.getDependencyMap()
        self.ff1.salesforce1.setDependencyMap(fm)
        
        regeneratedAdapterRowFields = self.ff1.salesforce1.getDependencyMap()
        regenerated_adapter_titles_for_mapping = [mapping['adapter_name'] for mapping in regeneratedAdapterRowFields]
        
        # make sure the renamed item does exists, while the old title does not
        self.failIf('Salesforce Adapter #2' in regenerated_adapter_titles_for_mapping)
        self.failUnless('Renamed Salesforce Adapter #2' in regenerated_adapter_titles_for_mapping)
    
    def testRemovedAdapterCleanedFromStaticParentAdapterVocabs(self):
        """Prove that retitling of an adapter shows the new
           titling in the static parent adapter list.
        """
        for i in range(1,4):
            self.ff1.invokeFactory('SalesforcePFGAdapter', 'salesforce%s' % i)
            self.ff1['salesforce%s' % i].setTitle('Salesforce Adapter #%i' % i)
        
        # salesforce2 could be a parent adapter to salesforce1
        parentAdapterOptions = self.ff1.salesforce1.getLocalSFAdapters()
        adapter_titles_for_mapping = [mapping.initialData['adapter_name'] for mapping in parentAdapterOptions]
        
        # make sure the subject field exists
        self.failUnless('Salesforce Adapter #2' in adapter_titles_for_mapping)
        self.failUnless('Salesforce Adapter #3' in adapter_titles_for_mapping)
        
        # map our soon to be deleted item
        fm = self.ff1.salesforce1.getDependencyMap()
        fm[0]['sf_field'] = 'some-bogus-field'
        self.ff1.salesforce1.setDependencyMap(fm)
        
        # remove adapter #3 from contention
        self.ff1.manage_delObjects(ids=['salesforce2'])
        
        # call our mutator to ensure that our mapping gets cleaned out
        fm = self.ff1.salesforce1.getDependencyMap()
        self.ff1.salesforce1.setDependencyMap(fm)
        
        regeneratedAdapterRowFields = self.ff1.salesforce1.getDependencyMap()
        regenerated_adapter_titles_for_mapping = [mapping['adapter_name'] for mapping in regeneratedAdapterRowFields]
        
        # make sure the removed field no longer exists
        self.failIf('Salesforce Adapter #2' in regenerated_adapter_titles_for_mapping)
    


def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(TestChainedAdapters))
    return suite

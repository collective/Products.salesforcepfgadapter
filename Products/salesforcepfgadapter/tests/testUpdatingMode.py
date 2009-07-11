# Integration tests specific to Salesforce adapter
#

import os, sys

if __name__ == '__main__':
    execfile(os.path.join(sys.path[0], 'framework.py'))

from zope.interface import providedBy
from Products.CMFCore.utils import getToolByName

from Products.Archetypes.public import DisplayList

from Products.PloneFormGen.interfaces import IPloneFormGenField

from Products.salesforcebaseconnector.tests import sfconfig   # get login/pw

from Products.salesforcepfgadapter.tests import base
from Products.salesforcepfgadapter.config import REQUIRED_MARKER


class TestUpdateModes(base.SalesforcePFGAdapterTestCase):
    """ test alternate Salesforce adapter modes (update, upsert)"""
    
    def afterSetUp(self):        
        super(TestUpdateModes, self).afterSetUp()
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
    
    def testUpsert(self):
        """Ensure that our Salesforce Adapter mapped objects
           find their way into the appropriate Salesforce.com
           instance.
        """
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
    

def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(TestUpdateModes))
    return suite

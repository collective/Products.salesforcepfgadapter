# Integration tests specific to Salesforce adapter
#

import os, sys

if __name__ == '__main__':
    execfile(os.path.join(sys.path[0], 'framework.py'))

from Products.CMFCore.utils import getToolByName

from Products.Archetypes.interfaces.field import IField

from Products.salesforcebaseconnector.tests import sfconfig   # get login/pw

from Products.salesforcepfgadapter.tests import base


class TestSalesforceFormDateFieldInteraction(base.SalesforcePFGAdapterTestCase):
    """ test save data adapter """
    
    def afterSetUp(self):        
        self.portal.manage_addProduct['salesforcebaseconnector'].manage_addTool('Salesforce Base Connector', None)
        self.salesforce = getToolByName(self.portal, "portal_salesforcebaseconnector")
        self.salesforce.setCredentials(sfconfig.USERNAME, sfconfig.PASSWORD)
        self._todelete = list() # keep track of ephemeral test data to delete
        
        self.folder.invokeFactory('FormFolder', 'ff1')
        self.ff1 = getattr(self.folder, 'ff1')
        
        self.ff1.invokeFactory('FormDateField', 'date')
        self.ff1.date.setTitle('date')
    
        self.ff1.invokeFactory('SalesforcePFGAdapter', 'salesforce')
        self.ff1.setActionAdapter( ('salesforce',) )
        sf = self.ff1.salesforce
    
        fieldmap = sf.getFieldMap()
        fieldmap[-1]['sf_field'] = 'date'
        sf.setFieldMap(fieldmap)
        
    
    def beforeTearDown(self):
        """clean up SF data"""
        ids = self._todelete
        if ids:
            while len(ids) > 200:
                self.salesforce.delete(ids[:200])
                ids = ids[200:]
            self.salesforce.delete(ids)
    
    def testDateFieldConvertedToSalesforceFormat(self):
        """ Prove that DateField values get converted to the format
            expected by Salesforce (mm/dd/yyyy).
        """
        from DateTime import DateTime
        now = DateTime()
        now_plone = now.strftime('%m-%d-%Y %H:%M')
    
        request = base.FakeRequest(topic = 'test subject', replyto='test@test.org',
                              date = now_plone)
        fields = [fo for fo in self.ff1._getFieldObjects() if not IField.isImplementedBy(fo)]
        sObject = self.ff1.salesforce._buildSObjectFromForm(fields, REQUEST=request)
    
        from time import strptime
        try:
            res = strptime(sObject['date'], '%Y-%m-%dT%H:%M:%SZ')
        except ValueError:
            self.fail("Doesn't look like the date was converted to Salesforce format properly.")

    def testEmptyFormDateFieldDoesntFailDateTimeConversion(self):
        """We don't want to try and cast an empty FormDateField value
           to an appropriately formatted DateTime. See: 
           http://plone.org/products/salesforcepfgadapter/issues/5
        """
    
        # assuming there was a FormDateField that was not filled out, it would
        # look like the following in the request:
        request = base.FakeRequest(topic = 'test subject', replyto='test@test.org', date = '')
    
        fields = [fo for fo in self.ff1._getFieldObjects() if not IField.isImplementedBy(fo)]
    
        # attempt to build the object which would trigger
        # SyntaxError: Unable to parse (' GMT+0',), {}
        # if the date came through as '' and we tried to coerce to DateTime
        sObject = self.ff1.salesforce._buildSObjectFromForm(fields, REQUEST=request)
        self.failIf(sObject.has_key('date'))

    def testEmptyFormDateFieldIsntPushedUpstreamAsInvalidXSDDateTime(self):
        """Assuming we survive a test for issue (i.e. empty string isn't 
           cast to DateTime causing a syntax error): 
           http://plone.org/products/salesforcepfgadapter/issues/5
       
           We also want to make sure this isn't added to sObject and therefore
           failing upon an attempt to create the object in Salesforce due to
           a SoapFaultError of invalid value for the type xsd:dateTime. See:
           http://plone.org/products/salesforcepfgadapter/issues/6
        """
        # create a attachmetn action adapter
        self.ff1.invokeFactory('SalesforcePFGAdapter', 'contact_adapter')
        
        # disable mailer adapter
        self.ff1.setActionAdapter(('contact_adapter',))
        
        # configure our contact_adapter to create an Attachment on submission
        self.ff1.contact_adapter.setTitle('Salesforce Contact Action Adapter')
        self.ff1.contact_adapter.setSFObjectType('Contact')
        
        # bogus mapping to meet Contact creation reqs,
        # we optionally ask for the Birtdate in the form
        self.ff1.contact_adapter.setFieldMap((
            {'field_path': 'comments', 'form_field': 'Comments', 'sf_field': 'LastName'},
            {'field_path': 'date', 'form_field': 'date', 'sf_field': 'Birthdate'},
        ))
        
        # build the request and submit the form for both adapters
        fields = self.ff1._getFieldObjects()
        # assuming there was a FormDateField that was not filled out, it would
        # look like the following in the request:
        request = base.FakeRequest(comments = 'PloneTestCaseEmptyDateField', date = '')
        
        # call onSuccess 
        self.ff1.contact_adapter.onSuccess(fields, request)  
        
        # query for our attachment
        contact_res = self.salesforce.query(['Id','Birthdate'],
                                            'Contact',
                                            "LastName='PloneTestCaseEmptyDateField'")
        
        # in case we fail, stock up our to delete list for tear down
        self._todelete.append(contact_res['records'][0]['Id'])
        
        # make our assertions
        self.failIf(contact_res['records'][0]['Birthdate'])
    


def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(TestSalesforceFormDateFieldInteraction))
    return suite

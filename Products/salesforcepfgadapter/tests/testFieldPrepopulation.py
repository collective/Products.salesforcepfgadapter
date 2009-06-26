# Integration tests specific to Salesforce adapter
#

import os, sys, datetime

if __name__ == '__main__':
    execfile(os.path.join(sys.path[0], 'framework.py'))

from zope.event import notify
from Products.Archetypes.event import ObjectEditedEvent

from Products.salesforcepfgadapter.tests import base
from Products.salesforcepfgadapter.prepopulator import FieldValueRetriever

class TestFieldPrepopulationSetting(base.SalesforcePFGAdapterTestCase):
    """ test feature that can prepopulate the form from data in Salesforce """
    
    def afterSetUp(self):
        self.test_fieldmap = (dict(field_path= 'replyto',
            form_field='Your E-Mail Address', sf_field='Email'),)
        
        super(TestFieldPrepopulationSetting, self).afterSetUp()
        self.folder.invokeFactory('FormFolder', 'ff1')
        self.ff1 = getattr(self.folder, 'ff1')

        self.ff1.invokeFactory('SalesforcePFGAdapter', 'salesforce')
        self.sfa = getattr(self.ff1, 'salesforce')

    def beforeTearDown(self):
        """clean up SF data"""
        ids = self._todelete
        if ids:
            while len(ids) > 200:
                self.salesforce.delete(ids[:200])
                ids = ids[200:]
            self.salesforce.delete(ids)

    def testPrepopulateSettingAvailability(self):
        """
        The 'prepopulate fields' setting should only take effect if:
         - the creation mode is set to update or upsert
         - a primary key field is configured
        """
        self.sfa.setFieldMap(self.test_fieldmap)
        self.sfa.setCreationMode('creation')
        self.sfa.setPrepopulateFieldValues(True)
        notify(ObjectEditedEvent(self.sfa))
        
        self.assertEqual(self.ff1.replyto.getRawFgTDefault(), '')

    def testPrepopulateSettingSetsFieldDefaults(self):
        self.sfa.setSFObjectType('Contact')
        self.sfa.setFieldMap(self.test_fieldmap)
        self.sfa.setCreationMode('upsert')
        self.sfa.setPrimaryKeyField('ContactId')
        self.sfa.setPrepopulateFieldValues(True)
        notify(ObjectEditedEvent(self.sfa))
        
        default_expr = self.ff1.replyto.getRawFgTDefault()
        self.assertEqual(default_expr, 'context/@@sf_value')
    
    def testPrepopulateSettingSetsFieldDefaultsForFieldsInFieldsets(self):
        self.ff1.invokeFactory('FieldsetFolder', 'fieldset')
        fieldset = self.ff1.fieldset
        fieldset.invokeFactory('FormStringField', 'foo')
        fieldset_field = fieldset.foo
        
        self.sfa.setSFObjectType('Contact')
        self.sfa.setFieldMap((dict(field_path= 'fieldset/foo',
            form_field='', sf_field='Email'),))
        self.sfa.setCreationMode('upsert')
        self.sfa.setPrimaryKeyField('ContactId')
        self.sfa.setPrepopulateFieldValues(True)
        notify(ObjectEditedEvent(self.sfa))

        default_expr = self.ff1.fieldset.foo.getRawFgTDefault()
        self.assertEqual(default_expr, 'context/@@sf_value')

    def testClearingPrepopulateSettingClearsFieldDefaults(self):
        self.ff1.replyto.setFgTDefault('context/@@sf_value')
        self.sfa.setFieldMap((dict(field_path= 'replyto',
            form_field='Your E-Mail Address', sf_field='Email')))
        self.sfa.setCreationMode('upsert')
        self.sfa.setPrimaryKeyField('ContactId')
        self.sfa.setPrepopulateFieldValues(False)
        notify(ObjectEditedEvent(self.sfa))
        
        self.assertEqual(self.ff1.replyto.getRawFgTDefault(), '')
    
    def testPrepopulateSettingDoesntPurgeCustomizedFieldDefaults(self):
        self.ff1.replyto.setFgTDefault('foobar')
        self.sfa.setFieldMap(self.test_fieldmap)
        self.sfa.setCreationMode('upsert')
        self.sfa.setPrimaryKeyField('ContactId')
        self.sfa.setPrepopulateFieldValues(False)
        notify(ObjectEditedEvent(self.sfa))

        self.assertEqual(self.ff1.replyto.getRawFgTDefault(), 'foobar')

class TestFieldValueRetriever(base.SalesforcePFGAdapterTestCase):
    """ test feature that can prepopulate the form from data in Salesforce """

    def afterSetUp(self):
        super(TestFieldValueRetriever, self).afterSetUp()
        self.folder.invokeFactory('FormFolder', 'ff1')
        self.ff1 = getattr(self.folder, 'ff1')

        self.ff1.invokeFactory('SalesforcePFGAdapter', 'salesforce')
        self.sfa = getattr(self.ff1, 'salesforce')
        self.test_fieldmap = (dict(field_path= 'replyto',
            form_field='Your E-Mail Address', sf_field='Email'),)
        self.sfa.setFieldMap(self.test_fieldmap)
        self.sfa.setCreationMode('upsert')
        self.sfa.setPrimaryKeyField('Email')
        self.sfa.setPrepopulateFieldValues(True)
        notify(ObjectEditedEvent(self.sfa))
        
        self._todelete = []

    def _createTestContact(self):
        # create a test contact
        data = dict(type='Contact',
            LastName='Doe',
            FirstName='John',
            Phone='123-456-7890',
            Email='john@doe.com',
            Birthdate = datetime.date(1970, 1, 4)
            )
        res = self.salesforce.create([data])
        self.objid = id = res[0]['id']
        self._todelete.append(id)
    
    def testGetRelevantSFAdapter(self):
        retriever = FieldValueRetriever(self.ff1.replyto, self.app.REQUEST)
        sfa = retriever.getRelevantSFAdapter()
        self.failUnless(sfa is self.sfa)
    
    def testGetRelevantSFAdapterForFieldsetField(self):
        self.ff1.invokeFactory('FieldsetFolder', 'fieldset')
        fieldset = self.ff1.fieldset
        fieldset.invokeFactory('FormStringField', 'foo')
        fieldset_field = fieldset.foo
        
        retriever = FieldValueRetriever(fieldset_field, self.app.REQUEST)
        sfa = retriever.getRelevantSFAdapter()
        self.failUnless(sfa is self.sfa)

    def beforeTearDown(self):
        """clean up SF data"""
        ids = self._todelete
        if ids:
            while len(ids) > 200:
                self.salesforce.delete(ids[:200])
                ids = ids[200:]
            self.salesforce.delete(ids)


def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(TestFieldPrepopulationSetting))
    suite.addTest(makeSuite(TestFieldValueRetriever))
    return suite

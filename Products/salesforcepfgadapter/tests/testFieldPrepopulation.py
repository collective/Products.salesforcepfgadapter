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
        self.test_fieldmap = ({'field_path' : 'replyto',
                               'form_field' : 'Your E-Mail Address', 
                               'sf_field' : 'Email'},
                              {'field_path' : 'petname',
                               'form_field' : 'pet',
                               'sf_field' : 'Favorite_Pet__c'},)
        
        super(TestFieldPrepopulationSetting, self).afterSetUp()
        self.folder.invokeFactory('FormFolder', 'ff1')
        self.ff1 = getattr(self.folder, 'ff1')
        
        self.ff1.invokeFactory('FormStringField', 'pet')
        
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
        self.assertEqual(default_expr, 'object/@@sf_value')
    
    def testPrepopulateSettingSetsFieldDefaultsForFieldsInFieldsets(self):
        self.ff1.invokeFactory('FieldsetFolder', 'fieldset')
        fieldset = self.ff1.fieldset
        fieldset.invokeFactory('FormStringField', 'foo')
        fieldset_field = fieldset.foo
        
        self.sfa.setSFObjectType('Contact')
        self.sfa.setFieldMap(self.test_fieldmap)
        self.sfa.setCreationMode('upsert')
        self.sfa.setPrimaryKeyField('ContactId')
        self.sfa.setPrepopulateFieldValues(True)
        notify(ObjectEditedEvent(self.sfa))
        
        default_expr = self.ff1.fieldset.foo.getRawFgTDefault()
        self.assertEqual(default_expr, 'object/@@sf_value')
    
    def testClearingPrepopulateSettingClearsFieldDefaults(self):
        self.ff1.replyto.setFgTDefault('object/@@sf_value')
        self.ff1.pet.setFgTDefault('Mittens')
        self.sfa.setFieldMap(self.test_fieldmap)
        self.sfa.setCreationMode('upsert')
        self.sfa.setPrimaryKeyField('ContactId')
        self.sfa.setPrepopulateFieldValues(False)
        notify(ObjectEditedEvent(self.sfa))
        
        self.assertEqual(self.ff1.replyto.getRawFgTDefault(), '')
        self.assertEqual(self.ff1.pet.getRawFgTDefault(), 'Mittens')
    
    def testPrepopulateSettingDoesntPurgeCustomizedFieldDefaults(self):
        self.ff1.replyto.setFgTDefault('foobar')
        self.ff1.pet.setFgTDefault('Mittens')
        self.sfa.setFieldMap(self.test_fieldmap)
        self.sfa.setCreationMode('upsert')
        self.sfa.setPrimaryKeyField('ContactId')
        self.sfa.setPrepopulateFieldValues(False)
        notify(ObjectEditedEvent(self.sfa))
        
        self.assertEqual(self.ff1.replyto.getRawFgTDefault(), 'foobar')
        self.assertEqual(self.ff1.pet.getRawFgTDefault(), 'Mittens')
    

class TestFieldValueRetriever(base.SalesforcePFGAdapterTestCase):
    """ test feature that can prepopulate the form from data in Salesforce """

    def afterSetUp(self):
        super(TestFieldValueRetriever, self).afterSetUp()
        self.folder.invokeFactory('FormFolder', 'ff1')
        self.ff1 = getattr(self.folder, 'ff1')
        self.ff1.invokeFactory('FormStringField', 'lastname')
        self.lastname = self.ff1.lastname
        self.lastname.setTitle('Last Name')
        
        # this is the value we're going to key on for populating the fields
        self.ff1.replyto.setFgDefault('archimedes@doe.com')
        self.ff1.replyto.setFgTDefault('')

        self.ff1.invokeFactory('SalesforcePFGAdapter', 'salesforce')
        self.sfa = getattr(self.ff1, 'salesforce')
        self.test_fieldmap = (
            dict(field_path='lastname', form_field='Last Name', sf_field='LastName'),
            dict(field_path='replyto', form_field='Your E-Mail Address', sf_field='Email'),
            )
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
            Email='archimedes@doe.com',
            Birthdate = datetime.date(1970, 1, 4)
            )
        res = self.salesforce.create([data])
        self.objid = id = res[0]['id']
        self._todelete.append(id)
    
    def testGetRelevantSFAdapter(self):
        retriever = FieldValueRetriever(self.ff1.replyto, self.app.REQUEST)
        sfa = retriever.getRelevantSFAdapter()
        self.failUnless(sfa.aq_base is self.sfa.aq_base)
    
    def testGetRelevantSFAdapterForFieldsetField(self):
        self.ff1.invokeFactory('FieldsetFolder', 'fieldset')
        fieldset = self.ff1.fieldset
        fieldset.invokeFactory('FormStringField', 'foo')
        fieldset_field = fieldset.foo
        fieldset_field.setTitle('Foo')
        self.sfa.setFieldMap((
            dict(field_path= 'fieldset,foo', form_field='Foo', sf_field='Email'),
            ))

        retriever = FieldValueRetriever(fieldset_field, self.app.REQUEST)
        sfa = retriever.getRelevantSFAdapter()
        self.failUnless(sfa.aq_base is self.sfa.aq_base)
    
    def testRetrieveData(self):
        self._createTestContact()
        
        retriever = FieldValueRetriever(self.ff1.lastname, self.app.REQUEST)
        data = retriever.retrieveData()
        self.assertEqual(data, {
            'replyto': 'archimedes@doe.com',
            'lastname': 'Doe',
            })
    
    def testRetrieveDataNothingFound(self):
        self.ff1.replyto.setFgDefault('not-a-real-email')
        retriever = FieldValueRetriever(self.ff1.lastname, self.app.REQUEST)
        data = retriever.retrieveData()
        self.assertEqual(data, {})
    
    def testCallingMultipleRetrieversInARequestCaches(self):
        self._createTestContact()
        
        retriever = FieldValueRetriever(self.ff1.replyto, self.app.REQUEST)
        lastname = retriever()
        
        # swap in some mock data, get the retriever for another field, and make
        # sure it gives us the mock data
        self.app.REQUEST._sfpfg_adapter['lastname'] = 'Smith'
        retriever2 = FieldValueRetriever(self.ff1.lastname, self.app.REQUEST)
        lastname = retriever2()
        self.assertEqual(lastname, 'Smith')

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

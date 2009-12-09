# Integration tests specific to Salesforce adapter
#

import os, sys, datetime

if __name__ == '__main__':
    execfile(os.path.join(sys.path[0], 'framework.py'))

from Products.Five.testbrowser import Browser

from zope.event import notify
from Products.statusmessages.interfaces import IStatusMessage

from Products.salesforcepfgadapter.tests import base
from Products.salesforcepfgadapter.prepopulator import FieldValueRetriever
from Products.salesforcepfgadapter.config import SESSION_KEY

try:
    from Products.Archetypes.event import ObjectEditedEvent as AdapterModifiedEvent
except ImportError:
    # BBB Zope 2.9 / AT 1.4
    from zope.app.event.objectevent import ObjectModifiedEvent as AdapterModifiedEvent

class TestFieldPrepopulationSetting(base.SalesforcePFGAdapterFunctionalTestCase):
    """ test feature that can prepopulate the form from data in Salesforce """
    
    def afterSetUp(self):
        self.test_fieldmap = ({'field_path' : 'replyto',
                               'form_field' : 'Your E-Mail Address', 
                               'sf_field' : 'Email'},
                              {'field_path' : 'petname',
                               'form_field' : 'pet',
                               'sf_field' : 'Favorite_Pet__c'},)
        
        super(TestFieldPrepopulationSetting, self).afterSetUp()
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

    def testSavingAdapterSetsFieldDefaults(self):
        """
        A field should get its default override set to "object/@@sf_value" if
        and only if:
         - the creation mode is set to update
         - the update match expression is non-empty
        """
        # all three conditions are met
        self.sfa.setSFObjectType('Contact')
        self.sfa.setFieldMap(self.test_fieldmap)
        self.sfa.setCreationMode('update')
        self.sfa.setUpdateMatchExpression('string:foobar')
        notify(AdapterModifiedEvent(self.sfa))
        default_expr = self.ff1.replyto.getRawFgTDefault()
        self.assertEqual(default_expr, 'object/@@sf_value')
        # in the special case of the default 'replyto' field, make sure the
        # default value gets cleared too
        default = self.ff1.replyto.getFgDefault()
        self.assertEqual(default, '')
        
        # wrong creation mode
        self.sfa.setCreationMode('create')
        notify(AdapterModifiedEvent(self.sfa))
        default_expr = self.ff1.replyto.getRawFgTDefault()
        self.assertEqual(default_expr, '')
        
        # no update match expression
        self.sfa.setCreationMode('update')
        self.sfa.setUpdateMatchExpression('')
        notify(AdapterModifiedEvent(self.sfa))
        default_expr = self.ff1.replyto.getRawFgTDefault()
        self.assertEqual(default_expr, '')

    def testSavingAdapterSetsFieldDefaultsForFieldsInFieldsets(self):
        self.ff1.invokeFactory('FieldsetFolder', 'fieldset')
        fieldset = self.ff1.fieldset
        fieldset.invokeFactory('FormStringField', 'foo')
        
        self.sfa.setSFObjectType('Contact')
        fieldmap = list(self.test_fieldmap)
        fieldmap.append({
            'field_path': 'fieldset,foo', 'form_field': '', 'sf_field': 'Description'
            })
        self.sfa.setFieldMap(fieldmap)
        self.sfa.setCreationMode('update')
        self.sfa.setUpdateMatchExpression('string:foobar')
        notify(AdapterModifiedEvent(self.sfa))
        
        default_expr = self.ff1.fieldset.foo.getRawFgTDefault()
        self.assertEqual(default_expr, 'object/@@sf_value')
    
    def testLabelFieldsDoNotBreak(self):
        self.ff1.invokeFactory('FieldsetFolder', 'fieldset')
        fieldset = self.ff1.fieldset
        fieldset.invokeFactory('FormLabelField', 'foo')
        
        self.sfa.setSFObjectType('Contact')
        self.sfa.setFieldMap(self.test_fieldmap)
        self.sfa.setCreationMode('update')
        self.sfa.setUpdateMatchExpression('string:foobar')
        notify(AdapterModifiedEvent(self.sfa))
    
    def testRemovingDefaultExpressionDoesntPurgeCustomizedFieldDefaults(self):
        self.ff1.replyto.setFgTDefault('string:foobar')
        self.ff1.pet.setFgTDefault('Mittens')
        self.sfa.setFieldMap(self.test_fieldmap)
        self.sfa.setCreationMode('update')
        self.sfa.setUpdateMatchExpression('')
        notify(AdapterModifiedEvent(self.sfa))
        
        self.assertEqual(self.ff1.replyto.getRawFgTDefault(), 'string:foobar')
        self.assertEqual(self.ff1.pet.getRawFgTDefault(), 'Mittens')

class TestFieldValueRetriever(base.SalesforcePFGAdapterFunctionalTestCase):
    """ test feature that can prepopulate the form from data in Salesforce """

    def afterSetUp(self):
        super(TestFieldValueRetriever, self).afterSetUp()
        self.ff1.invokeFactory('FormStringField', 'lastname')
        self.lastname = self.ff1.lastname
        self.lastname.setTitle('Last Name')
        self.ff1.invokeFactory('FormDateField', 'birthday')
        self.ff1['birthday'].setTitle('Birthday')
        
        self.ff1.invokeFactory('SalesforcePFGAdapter', 'salesforce')
        self.sfa = getattr(self.ff1, 'salesforce')
        self.test_fieldmap = (
            dict(field_path='lastname', form_field='Last Name', sf_field='LastName'),
            dict(field_path='replyto', form_field='Your E-Mail Address', sf_field='Email'),
            dict(field_path='birthday', form_field='Birthday', sf_field='Birthdate'),
            )
        self.sfa.setFieldMap(self.test_fieldmap)
        self.sfa.setCreationMode('update')
        self.sfa.setUpdateMatchExpression("""python:"Email='" + sanitize_soql('archimedes@doe.com') + "'" """)
        notify(AdapterModifiedEvent(self.sfa))
        
        self.app.REQUEST.SESSION = {}
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
        self.assertEqual(data['replyto'], 'archimedes@doe.com')
        self.assertEqual(data['lastname'], 'Doe')
        self.failUnless('Id' in data)
        self.assertEqual(len(data.keys()), 4)
    
    def testRetrieveDataNothingFound(self):
        self.sfa.setUpdateMatchExpression("string:Email='not-a-real-email'")
        retriever = FieldValueRetriever(self.ff1.lastname, self.app.REQUEST)
        data = retriever.retrieveData()
        self.assertEqual(data, {})
    
    def testCallingMultipleRetrieversInARequestCaches(self):
        self._createTestContact()
        
        retriever = FieldValueRetriever(self.ff1.replyto, self.app.REQUEST)
        lastname = retriever()
        
        # swap in some mock data, get the retriever for another field, and make
        # sure it gives us the mock data
        self.app.REQUEST._sfpfg_adapter[self.sfa.UID()]['lastname'] = 'Smith'
        retriever2 = FieldValueRetriever(self.ff1.lastname, self.app.REQUEST)
        lastname = retriever2()
        self.assertEqual(lastname, 'Smith')

    def testRetrieveNonUniqueValueRaises(self):
        # Create two contacts that will have the same value for the key field
        self._createTestContact()
        self._createTestContact()
        # Since there is not a single record with this last name, we should
        # show an error message
        retriever = FieldValueRetriever(self.ff1.lastname, self.app.REQUEST)
        retriever.retrieveData()
        self.assertEqual(IStatusMessage(self.app.REQUEST).showStatusMessages()[0].message,
            u'Multiple items found; unable to determine which one to edit.')
    
    def testObjectIdFromSessionUsedIfAvailable(self):
        # if we've already started editing an object, use its ID rather than
        # doing a fresh query...to test this we manually store the desired UID
        # in the session, then create an additional matching contact record,
        # which would normally result in an error as per the previous test
        self._createTestContact()
        self._createTestContact()
        self.app.REQUEST.set('HTTP_REFERER', self.ff1.absolute_url())
        self.app.REQUEST.SESSION = {(SESSION_KEY, self.sfa.UID()): (self._todelete[-1], "Email='archimedes@doe.com'")}
        retriever = FieldValueRetriever(self.ff1.lastname, self.app.REQUEST)
        self.assertEqual(retriever(), 'Doe')
    
    def testDontUseObjectIdFromSessionIfExpressionChanged(self):
        # if the update match expression evaluates to something different than it did
        # when the object id was stored in the session, don't use the stored id
        self._createTestContact()
        self._createTestContact()
        self.app.REQUEST.set('HTTP_REFERER', self.ff1.absolute_url())
        self.app.REQUEST.SESSION = {(SESSION_KEY, self.sfa.UID()): (self._todelete[-1], "Email='archimedes@doe.com'")}
        retriever = FieldValueRetriever(self.ff1.lastname, self.app.REQUEST)
        # this one should not fail, because we're using the oid from the session
        self.assertEqual(retriever(), 'Doe')
        # now let's confirm that if a different expression is stored in the
        # session, then the populator will try a fresh match and fail due to
        # finding the multiple contacts we created
        self.app.REQUEST.SESSION = {(SESSION_KEY, self.sfa.UID()): (self._todelete[-1], "Email='socrates@doe.com'")}
        retriever.retrieveData()
        self.assertEqual(IStatusMessage(self.app.REQUEST).showStatusMessages()[0].message,
            u'Multiple items found; unable to determine which one to edit.')
    
    def testDateTimeWidgetRendersRetrievedDate(self):
        self._createTestContact()
        browser = Browser()
        browser.open('http://nohost' + '/'.join(self.ff1.getPhysicalPath()))
        self.assertEqual(browser.getControl(name='birthday_day').value, ['04'])
    
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

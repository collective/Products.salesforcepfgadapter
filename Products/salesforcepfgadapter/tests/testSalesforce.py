# Integration tests specific to Salesforce adapter
#

import os, sys, email

if __name__ == '__main__':
    execfile(os.path.join(sys.path[0], 'framework.py'))

from zope.interface import providedBy
from Products.PloneFormGen.interfaces import IPloneFormGenField
from Products.PloneFormGen.tests.testMailer import TestFunctions

from Products.salesforcepfgadapter.tests import base

from Products.CMFCore.utils import getToolByName

from Products.Archetypes.public import DisplayList

from Products.salesforcebaseconnector.tests import sfconfig   # get login/pw

from Products.salesforcepfgadapter.config import REQUIRED_MARKER
from Products.salesforcepfgadapter.config import SF_ADAPTER_TYPES

class FakeRequest(dict):
    
    def __init__(self, **kwargs):
        self.form = kwargs

class TestProductInstallation(base.SalesforcePFGAdapterTestCase):
    """ ensure that our product installs correctly """

    def afterSetUp(self):
        self.types      = self.portal.portal_types
        self.properties = self.portal.portal_properties
        self.factory    = self.portal.portal_factory
        self.skins      = self.portal.portal_skins
        self.workflow   = self.portal.portal_workflow
        self.metaTypes = SF_ADAPTER_TYPES
    
    def testDependenciesInstalled(self):
        DEPENDENCIES = ['PloneFormGen','DataGridField',]
        
        for depend in DEPENDENCIES:
            self.failUnless(self.portal.portal_quickinstaller.isProductInstalled(depend),
                "Dependency product %s is not already installed" % depend)
        
    def testAdapterTypeRegistered(self):
        for t in self.metaTypes:
            self.failUnless(t in self.types.objectIds())
    
    def testPortalFactorySetup(self):
        for t in self.metaTypes:
            self.failUnless(t in self.factory.getFactoryTypes(),
                "Type %s is not a factory types" % t)

    def testTypesNotSearched(self):
        types_not_searched = self.properties.site_properties.getProperty('types_not_searched')
        for t in self.metaTypes:
            self.failUnless(t in types_not_searched,
                "Type %s is searchable and shouldn't be" % t)

    def testTypesNotListed(self):
        metaTypesNotToList  = self.properties.navtree_properties.getProperty('metaTypesNotToList')
        for t in self.metaTypes:
            self.failUnless(t in metaTypesNotToList,
                "Type %s is will show up in the nav and shouldn't" % t)
    
    def testMetaTypesAllowedInFormFolder(self):
        allowedTypes = self.types.FormFolder.allowed_content_types
        for t in self.metaTypes:
            self.failUnless(t in allowedTypes,
                "Type %s is not addable to the Form Folder" % t)

        # make sure we haven't inadvertently removed other core field and adapter types
        
        # a random sampling of core fields
        coreFields = [
            'FormSelectionField',
            'FormMultiSelectionField',
            'FormLinesField',
            'FormIntegerField',
            'FormBooleanField',
            'FormStringField',
            'FormTextField',
        ]
        
        for t in coreFields:
            self.failUnless(t in allowedTypes,
                "Type %s was accidentally whacked from the Form Fields allowed_content_types" % t)
    
    def testNeededSkinsRegistered(self):
        """Our all important skin layer(s) should be registered with the site."""
        prodSkins = ('salesforcepfgadapter_images',)
        
        for prodSkin in prodSkins:
            self.failUnless(prodSkin in self.skins.objectIds(),
                "The skin %s was not registered with the skins tool" % prodSkin)
    
    def testSkinShowsUpInToolsLayers(self):
        """We need our product's skin directories to show up below custom as one of the called
           upon layers of our skin's properties
        """
        product_layers = ('salesforcepfgadapter_images',)

        for selection, layers in self.skins.getSkinPaths():
            for specific_layer in product_layers:
                self.failUnless(specific_layer in layers, "The %s layer \
                    does not appear in the layers of Plone's %s skin" % (specific_layer,selection))
        
    def testCorePloneLayersStillPresent(self):
        """As was known to happen with legacy versions of GS working with the skins tool,
           it was easy to inadvertently remove need layers for the selected skin.  Here 
           we make sure this hasn't happened.
        """
        core_layers = ('PloneFormGen','plone_templates',)
        
        for selection, layers in self.skins.getSkinPaths():
            for specific_layer in core_layers:
                self.failUnless(specific_layer in layers, "The %s layer \
                    does not appear in the layers of Plone's available skins" % specific_layer)
        
    

class TestSalesforcePFGAdapter(base.SalesforcePFGAdapterTestCase):
    """ test save data adapter """
    
    def afterSetUp(self):        
        self.portal.manage_addProduct['salesforcebaseconnector'].manage_addTool('Salesforce Base Connector', None)
        self.salesforce = getToolByName(self.portal, "portal_salesforcebaseconnector")
        self.salesforce.setCredentials(sfconfig.USERNAME, sfconfig.PASSWORD)
        self._todelete = list() # keep track of ephemeral test data to delete
        
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
    
    def testSetFFAdapterToSalesforce(self):
        """Proves that we can set our form's
           action adapter to a salesforce action adapter
        """
        # create an adapter
        self.ff1.invokeFactory('SalesforcePFGAdapter', 'salesforce')

        # make sure that our adapter is contained w/in the form
        self.failUnless('salesforce' in self.ff1.objectIds())
        salesforce = self.ff1.salesforce

        # set our action adapter and assert that it works
        self.ff1.setActionAdapter( ('salesforce',) )
        self.assertEqual(self.ff1.actionAdapter, ('salesforce',))
    
    def testDisplaySFObjectTypesVocabulary(self):
        # create an adapter
        self.ff1.invokeFactory('SalesforcePFGAdapter', 'salesforce')
        
        # ask salesforce for our display list of SFObject types
        staticListOfObjectTypes = self.ff1.salesforce.displaySFObjectTypes().values()
        
        # iterate through a list of must-haves to make sure they are options
        for sfobjecttype in ('Lead', 'Contact', 'Opportunity',):
            self.failUnless(sfobjecttype in staticListOfObjectTypes,
                "The object type %s is not an option in our display list" % sfobjecttype)
    
    def testSetGetSalesforcePFGAdapter(self):
        """Proves that we can add and edit the intended 
           fields of our salesforcepfgadapter content object.
        """
        # create an adapter
        self.ff1.invokeFactory('SalesforcePFGAdapter', 'salesforce')
        adapter = self.ff1.salesforce
        
        # try to validate the adapter
        errors = adapter.validate()      
        assert len(errors) == 0, "Had errors:" + str(errors)          
        
        # set fields on the adapter
        adapter.setTitle('Salesforce Action Adapter')
        adapter.setSFObjectType('Contact')
        adapter.setExecCondition('python:1')
        adapter.setFieldMap((
            {'field_path': 'replyto', 'form_field': 'Your E-Mail Address', 'sf_field': 'Email'},
            {'field_path': 'comments', 'form_field': 'Comments', 'sf_field': 'Description'}))
        adapter.setDependencyMap(({'adapter_name': 'Salesforce', 'sf_field': 'AccountId', 'adapter_id': 'salesforce'},))
        
        # test the values on the fields
        self.assertEquals('Salesforce Action Adapter',adapter.Title())
        self.assertEquals(1,adapter.getExecCondition())
        self.assertEquals('Contact',adapter.getSFObjectType())
        formToSalesforceMapperValues = adapter.getFieldMap()[0].values()
        for wanted in ('replyto', 'Your E-Mail Address', 'Email'):
            self.failUnless(wanted in formToSalesforceMapperValues,
                            "%s missing from %s" % (wanted, formToSalesforceMapperValues))
        formToSalesforceMapperValues = adapter.getFieldMap()[1].values()
        for wanted in ('comments', 'Comments', 'Description'):
            self.failUnless(wanted in formToSalesforceMapperValues,
                            "%s missing from %s" % (wanted, formToSalesforceMapperValues))
        adapterToSalesforceFieldValues = adapter.getDependencyMap()[0].values()
        for wanted in ('salesforce', 'AccountId', 'Salesforce'):
            self.failUnless(wanted in adapterToSalesforceFieldValues,
                            "%s missing from %s" % (wanted, adapterToSalesforceFieldValues))
    
    def testCantAddMappingsForNonExistentFieldTitles(self):
        # create an adapter
        self.ff1.invokeFactory('SalesforcePFGAdapter', 'salesforce')
        adapter = self.ff1.salesforce
        
        adapter.setFieldMap(({'field_path':'my-first-name', 'form_field':'My First Name','sf_field':'FirstName'},))
        formToSalesforceMapperValues = [mapping.values() for mapping in adapter.getFieldMap()]
        self.failIf(['my-first-name','My First Name','FirstName',] in formToSalesforceMapperValues)
    
    def testDataGridFieldStaticFormFieldVocabsContainsAllPFGFormFields(self):
        """Our SalesforcePFGAdapter depends on the DataGridField which among other 
          options allows for a Fixed Column that can be prepopulated using the fixed_rows
          attribute on the schema field.
        """
        # create an adapter
        self.ff1.invokeFactory('SalesforcePFGAdapter', 'salesforce')
        
        for formField in self.ff1.objectIds():
            fieldObj = getattr(self.ff1, formField)
            fixedRowFields = self.ff1.salesforce.generateFormFieldRows()
            static_titles_for_mapping = [(mapping.initialData['form_field'], mapping.initialData['field_path']) \
                for mapping in fixedRowFields]
            if IPloneFormGenField.providedBy(fieldObj):
                self.failUnless((fieldObj.Title(), fieldObj.getId()) in static_titles_for_mapping,
                    "Field %s is not listed as a possible field in the computed widget expression \
                    method." % fieldObj.Title())
        
        # let's add a new field to our form and immediately make sure it's 
        # available as a row in our FixedRow form fields for the mapping
        self.ff1.invokeFactory('FormTextField', 'formtextfield')
        self.ff1.formtextfield.setTitle('My Form Text Field')
        fixedRowFields = self.ff1.salesforce.generateFormFieldRows()
        static_titles_for_mapping = [(mapping.initialData['form_field'], mapping.initialData['field_path']) \
            for mapping in fixedRowFields]
        self.failUnless(('My Form Text Field', 'formtextfield') in static_titles_for_mapping,
            "Field formtextfield is not listed as a possible field in the computed widget expression method.")
    
    def testRequiredSalesforceFieldsMarkedInUI(self):
        """Our SalesforcePFGAdapter depends on the DataGridField which among other 
          options allows for a Select Column that can be populated using the vocabulary attribute
          on the field type.  Here we ensure that required fields for a given SFObject are
          marked appropriately in the UI.
        """
        # create an adapter
        self.ff1.invokeFactory('SalesforcePFGAdapter', 'salesforce')
        # manually call setObjectType, explain this
        chosenSObject = self.ff1.salesforce.getSFObjectType()
        self.ff1.salesforce.setSFObjectType(chosenSObject)
        
        # this generates a nice list of field options
        objectFieldOptions = self.ff1.salesforce.buildSFFieldOptionList()
        
        # live lookup to salesforce for the status of field on the chosen 
        # 
        fieldInfo = self.salesforce.describeSObjects(chosenSObject)[0].fields
        
        for k,v in fieldInfo.items():
            if v.nillable or v.defaultedOnCreate or not v.createable:
                self.failIf(REQUIRED_MARKER in objectFieldOptions.getValue(k), 
                    "Field %s is marked required and should not be for the %s SObject" % (k, chosenSObject))
            else:
                self.failUnless(REQUIRED_MARKER in objectFieldOptions.getValue(k), 
                    "Field %s is NOT marked required and should be for the %s SObject" % (k, chosenSObject))
    
    def testRequiredFieldsFloatToTopOfList(self):
        """As a convenience to the user, we put an 
           an empty display item first, then required items, followed
           by those that are optional.  This *hopefully* helps the user successfully
           create an adapter that won't fail on submit without as much trial and 
           error.  Our test proves that required fields come first.
        """
        # create an adapter
        self.ff1.invokeFactory('SalesforcePFGAdapter', 'salesforce')
        # manually call setObjectType, explain this
        chosenSObject = self.ff1.salesforce.getSFObjectType()
        self.ff1.salesforce.setSFObjectType(chosenSObject)
        
        # this generates a nice list of field options
        objectFieldOptions = self.ff1.salesforce.buildSFFieldOptionList()
        
        endOfRequiredItems = False
        for k,v in objectFieldOptions.items()[1:]: # Skip the first one, which is blank
            
            # set endOfRequiredItems terms on first non-required field
            if REQUIRED_MARKER not in v:
                # this must be our fist non-required field, 
                # if not, we have troubles...
                endOfRequiredItems = True
            
            if endOfRequiredItems:
                self.failIf(REQUIRED_MARKER in v, 
                    "Field %s is marked required and was sorted below non-required fields \
                        for the %s SObject" % (k, chosenSObject))
    
    def testSFPFGCanBeInstantiated(self):
        """This test is historically-motivated due to the transition
           from sf fields that didn't mark themselves as required, to 
           those that do.  In this transition, the data structure of the
           fields on the object needed to be changed, so that we can access
           which fields are actually required.  Due to the way in which we call 
           setSFObjectType and Python's dynamic typing (I think...), we 
           introduced an obvious TTW bug that didn't appear in tests.  
           
           You can't call items() on a list, which is what our instance var
           _fieldsForSFObjectType was being coerced from in our code.  D'oh.
        """
        self.ff1.invokeFactory('SalesforcePFGAdapter', 'salesforce')
        # at this point, setSFFieldObject has not been called
        # and though the default SFObject type is a contact,
        # our instance variable _fieldsForSFObjectType doesn't
        # yet have an actual listing of the fields.

        # call buildSFFieldOptionList, which constructs a
        # vocab for DGF and ensure it's an empty value and
        # does introduce a traceback
        self.assertEqual(type(DisplayList()), type(self.ff1.salesforce.buildSFFieldOptionList()))
    
    def testTitlesWithTrailingSpacesDontDuplicateThemselvesInTheFixedRowUserInterface(self):
        """Worked around issue where the DataGridField strips proceeding/trailing spaces for its FixedRow 
           values, but our generateFormFieldRows method did not, thus each save of the adapter produced duplicate
           mappings in the DataGridField UI
        """
        # create an adapter
        self.ff1.invokeFactory('SalesforcePFGAdapter', 'salesforce')
        
        self.ff1.invokeFactory('FormTextField', 'formtextfield')
        self.ff1.formtextfield.setTitle('My Form Text Field with Trailing Spaces   ')
        
        fixedRowFields = self.ff1.salesforce.generateFormFieldRows()
        static_titles_for_mapping = [mapping.initialData['form_field'] for mapping in fixedRowFields]
        self.failUnless('My Form Text Field with Trailing Spaces' in static_titles_for_mapping,
            "Field formtextfield's stripped title does not appear in the DataGridField.")
        
        self.failIf('My Form Text Field with Trailing Spaces   ' in static_titles_for_mapping,
            "Field formtextfield's unstripped title appears in the DataGridField.")
    
    def testRenamedFormFieldsRemovedFromStaticFormFieldVocabs(self):
        """Prove that retitling of the form field shows the new
           titling in the static field list.
        """
        self.ff1.invokeFactory('SalesforcePFGAdapter', 'salesforce')
        
        fixedRowFields = self.ff1.salesforce.generateFormFieldRows()
        static_titles_for_mapping = [mapping.initialData['form_field'] for mapping in fixedRowFields]
        
        # make sure the subject field exists
        self.failUnless('Subject' in static_titles_for_mapping)
        
        # rename the subject field
        self.ff1.topic.setTitle('Renamed Subject')
        
        # call our mutator to ensure that our mapping gets cleaned out
        fm = self.ff1.salesforce.getFieldMap()
        self.ff1.salesforce.setFieldMap(fm)
        
        regeneratedFixedRowFields = self.ff1.salesforce.generateFormFieldRows()
        regenerated_static_titles_for_mapping = [mapping.initialData['form_field'] for mapping in regeneratedFixedRowFields]
        
        # make sure the subject field exists
        self.failIf('Subject' in regenerated_static_titles_for_mapping, "This is a known issue in \
            intended for fix with the 1.0alpha2 release.")
        self.failUnless('Renamed Subject' in regenerated_static_titles_for_mapping)
    
    def testDateFieldConvertedToSalesforceFormat(self):
        """ Prove that DateField values get converted to the format
            expected by Salesforce (mm/dd/yyyy).
        """
        self.ff1.invokeFactory('FormDateField', 'date')
        self.ff1.date.setTitle('date')
        
        self.ff1.invokeFactory('SalesforcePFGAdapter', 'salesforce')
        self.ff1.setActionAdapter( ('salesforce',) )
        sf = self.ff1.salesforce
        
        fieldmap = sf.getFieldMap()
        fieldmap[-1]['sf_field'] = 'date'
        sf.setFieldMap(fieldmap)
        
        from DateTime import DateTime
        now = DateTime()
        now_plone = now.strftime('%m-%d-%Y %H:%M')
        
        request = FakeRequest(topic = 'test subject', replyto='test@test.org',
                              date = now_plone)
        from Products.Archetypes.interfaces.field import IField
        fields = [fo for fo in self.ff1._getFieldObjects() if not IField.isImplementedBy(fo)]
        sObject = self.ff1.salesforce._buildSObjectFromForm(fields, REQUEST=request)
        
        from time import strptime
        try:
            res = strptime(sObject['date'], '%Y-%m-%dT%H:%M:%SZ')
        except ValueError:
            self.fail("Doesn't look like the date was converted to Salesforce format properly.")
    
    def testImplementIMultiPageSchema(self):
        try:
            from Products.Archetypes.interfaces import IMultiPageSchema
            self.ff1.invokeFactory('SalesforcePFGAdapter', 'salesforce')
            sf = self.ff1.salesforce
            self.assertTrue(IMultiPageSchema.providedBy(sf))
        except ImportError:
            pass
    
    def testNoExtraneousSchemata(self):
        try:
            from Products.Archetypes.interfaces import IMultiPageSchema
            self.ff1.invokeFactory('SalesforcePFGAdapter', 'salesforce')
            sfSchema = self.ff1.salesforce.schema
            self.assertEquals(['default', 'field mapping', 'overrides'], sfSchema.getSchemataNames())
        except ImportError:
            pass
    
    def testSalesforceAdapterOnSuccess(self):
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
        request = FakeRequest(replyto = 'plonetestcase@plone.org', # mapped to Email (see above) 
                              comments='PloneTestCase')            # mapped to LastName (see above)
        
        self.ff1.contact_adapter.onSuccess(fields, request)
        
        # direct query of Salesforce to get the id of the newly created contact
        res = self.salesforce.query(['Id',],self.ff1.contact_adapter.getSFObjectType(),
                                    "Email='plonetestcase@plone.org' and LastName='PloneTestCase'")
        self._todelete.append(res['records'][0]['Id'])
        
        # assert that our newly created Contact was found
        self.assertEqual(1, res['size'])
    
    def testSalesforceAdapterOnSuccessFor1ToNObjects(self):
        """Ensure that 1:N -- well actually 2 here :) -- Salesforce Adapter mapped objects
           find their way into the appropriate Salesforce.com instance.  
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
        self.ff1.contact_adapter.setFieldMap((
            {'field_path': 'replyto', 'form_field': 'Your E-Mail Address', 'sf_field': 'Email'},
            {'field_path': 'comments', 'form_field': 'Comments', 'sf_field': 'LastName'}))
        
        # configure our account_adapter to create a contact on submission
        # last name is the lone required field
        self.ff1.account_adapter.setTitle('Salesforce Account Action Adapter')
        self.ff1.account_adapter.setSFObjectType('Account')
        self.ff1.account_adapter.setFieldMap((
            {'field_path':'comments', 'form_field': 'Comments', 'sf_field': 'Name'},))
        
        # build the request and submit the form for both adapters
        fields = self.ff1._getFieldObjects()
        request = FakeRequest(replyto = 'plonetestcase1ToN@plone.org', # mapped to Email (see above) 
                              comments='PloneTestCase1ToN')            # mapped to LastName (see above)
        
        
        # we only call onSuccess for our last SF adapter in the form
        # which calculates the need order and executes all SF adapters in 
        # the appropriate sequence
        self.ff1.account_adapter.onSuccess(fields, request)        
        
        # direct query of Salesforce to get the id of the newly created contact
        contact_res = self.salesforce.query(['Id',],
                                            self.ff1.contact_adapter.getSFObjectType(),
                                            "Email='plonetestcase1ToN@plone.org' and LastName='PloneTestCase1ToN'")
        # in case we fail, stock up our to delete list for tear down
        self._todelete.append(contact_res['records'][0]['Id'])
        
        # direct query of Salesforce to get the id of the newly created account
        account_res = self.salesforce.query(['Id',],self.ff1.account_adapter.getSFObjectType(),
                                    "Name='PloneTestCase1ToN'")
                                    
        # in case we fail, stock up our to delete list for tear down
        self._todelete.append(account_res['records'][0]['Id'])
        
        # assert that our newly created Contact was found
        self.assertEqual(1, contact_res['size'])
        self.assertEqual(1, account_res['size'])
    
    def testDataGridFieldAllowsMappingOfFieldsetContainedFields(self):
        """PloneFormGen has a concept of fieldsets, which architecturally
           are just folders within a form, where sectioned off fields can
           be added.  We ensure that these can be mapped despite their position
           nested 1 level under the top level.  
           See: http://plone.org/products/salesforcepfgadapter/issues/2
        """
        # create a new fieldset within the form
        self.ff1.invokeFactory('FieldsetFolder', 'subform')
        self.ff1.subform.setTitle("Subform Fieldset")
        # create a field local to the fieldset
        self.ff1.subform.invokeFactory('FormStringField', 'subformfield')
        self.ff1.subform.subformfield.setTitle("Subform Field")
        
        # create an adapter
        self.ff1.invokeFactory('SalesforcePFGAdapter', 'salesforce')
        
        # get the available mappable fields
        fixedRowFields = self.ff1.salesforce.generateFormFieldRows()
        static_titles_for_mapping = [(mapping.initialData['form_field'], mapping.initialData['field_path'], ) \
            for mapping in fixedRowFields]
        
        # make sure that our fieldset-based form field is present
        # and therefore can be mapped to a Salesforce field
        self.failUnless(("Subform Fieldset --> Subform Field", 'subform,subformfield',) in static_titles_for_mapping)
    
    def testFieldsetContainedFieldsCorrectlyPushedToSalesforceObject(self):
        """As a follow-up to ensuring our fieldset fields can be mapped,
           we ensure their values are appropriately pushed to Salesforce.com
           See: http://plone.org/products/salesforcepfgadapter/issues/2
        """
        # create a new fieldset within the form
        self.ff1.invokeFactory('FieldsetFolder', 'subform')
        self.ff1.subform.setTitle("Subform Fieldset")
        # create a field local to the fieldset
        self.ff1.subform.invokeFactory('FormStringField', 'subformfield')
        self.ff1.subform.subformfield.setTitle("Subform Field")
        
        # create a contact action adapters
        self.ff1.invokeFactory('SalesforcePFGAdapter', 'contact_adapter')
        
        # disable mailer adapter
        self.ff1.setActionAdapter(('contact_adapter',))
        
        # configure our contact_adapter to create a contact on submission
        # last name is the lone required field, but we map a few others 
        # and our fieldset field ...
        self.ff1.contact_adapter.setTitle('Salesforce Contact Action Adapter')
        self.ff1.contact_adapter.setSFObjectType('Contact')
        self.ff1.contact_adapter.setFieldMap((
            {'field_path': 'replyto', 'form_field': 'Your E-Mail Address', 'sf_field': 'Email'},
            {'field_path': 'comments', 'form_field': 'Comments', 'sf_field': 'LastName'},
            {'field_path': 'subform,subformfield', 'form_field': 'Subform Fieldset --> Subform Field', 'sf_field': 'FirstName'},
        ))
        
        # build the request and submit the form for both adapters
        fields = self.ff1._getFieldObjects()
        request = FakeRequest(replyto = 'plonetestcasefieldsetfields@plone.org', # mapped to Email (see above) 
                              comments='PloneTestCaseFieldsetFields',            # mapped to LastName (see above)
                              subformfield='PloneTestCaseFieldsetSubField',)     # mapped to FirstName (see above)
        
        
        # we only call onSuccess for our last SF adapter in the form
        # which calculates the need order and executes all SF adapters in 
        # the appropriate sequence
        self.ff1.contact_adapter.onSuccess(fields, request)        
        
        # direct query of Salesforce to get the id of the newly created contact
        contact_res = self.salesforce.query(['Id','FirstName'],
                                            self.ff1.contact_adapter.getSFObjectType(),
                                            "LastName='PloneTestCaseFieldsetFields'")
        # in case we fail, stock up our to delete list for tear down
        self._todelete.append(contact_res['records'][0]['Id'])
        
        # assert that our newly created Contact was found
        self.assertEqual(request.form['subformfield'], contact_res['records'][0]['FirstName'])
    
    def testFileFieldsSavedToSalesforce(self):
        """There may be other use cases, but the Attachment
           type in Salesforce can be associated with any other
           type and is where binary data, as stored on the Body
           field, is typically associated with a record. Here
           we confirm that a binary file can be mapped and
           is succesfully posted to Salesforce.com via PloneFormGen's
           FormFileField type.
        """
        def _createBinaryFile():
            from cgi import FieldStorage
            from ZPublisher.HTTPRequest import FileUpload
            from tempfile import TemporaryFile
            fp = TemporaryFile('w+b')
            fp.write('\x00' + 'x' * (1 << 19))
            fp.seek(0)
            env = {'REQUEST_METHOD':'PUT'}
            headers = {'content-type':'text/plain',
                       'content-length': 1 << 19,
                       'content-disposition':'attachment; filename=test.bin'}
            fs = FieldStorage(fp=fp, environ=env, headers=headers)
            return FileUpload(fs)
        
        # add a file field to our standard form
        self.ff1.invokeFactory('FormFileField','filefield')
        self.ff1.filefield.setTitle("File")
        
        # directly create a contact for association, since we need
        # a valid parent id and don't care about related objects here
        sObject = dict(type='Contact')
        sObject['LastName'] = 'testFileFieldsSavedToSalesforce'
        contact_create_res = self.salesforce.create(sObject)
        
        # get ready to cleanup regardless of test case success
        self._todelete.append(contact_create_res[0]['id'])
        
        # create a attachmetn action adapter
        self.ff1.invokeFactory('SalesforcePFGAdapter', 'attachment_adapter')
        
        # disable mailer adapter
        self.ff1.setActionAdapter(('attachment_adapter',))
        
        # configure our attachment_adapter to create an Attachment on submission
        self.ff1.attachment_adapter.setTitle('Salesforce Attachment Action Adapter')
        self.ff1.attachment_adapter.setSFObjectType('Attachment')
        
        # bogus mapping to meet Attachment reqs
        self.ff1.attachment_adapter.setFieldMap((
            {'field_path': 'replyto', 'form_field': 'Your E-Mail Address', 'sf_field': 'ParentId'},
            {'field_path': 'comments', 'form_field': 'Comments', 'sf_field': 'Name'},
            {'field_path': 'filefield', 'form_field': 'File', 'sf_field': 'Body'},
        ))
        
        # build the request and submit the form for both adapters
        fields = self.ff1._getFieldObjects()
        request = FakeRequest(replyto = contact_create_res[0]['id'], # mapped to ParentId (see above) 
                              comments='test.bin',                   # mapped to Name (see above)
                              filefield_file=_createBinaryFile())     # mapped to FirstName (see above)
        
        # call onSuccess 
        self.ff1.attachment_adapter.onSuccess(fields, request)  
        
        # query for our attachment
        attach_res = self.salesforce.query(['Id','Name','BodyLength',],
                                            'Attachment',
                                            "ParentId='%s'" % contact_create_res[0]['id'])
        # in case we fail, stock up our to delete list for tear down
        self._todelete.append(attach_res['records'][0]['Id'])
        
        # make our assertions
        self.assertEqual('test.bin', attach_res['records'][0]['Name'])
        self.failUnless(attach_res['records'][0]['BodyLength'] > 0)
    


def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(TestProductInstallation))
    suite.addTest(makeSuite(TestSalesforcePFGAdapter))
    return suite

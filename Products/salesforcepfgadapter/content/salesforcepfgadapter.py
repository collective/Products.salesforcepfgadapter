""" 
    
    An adapter for PloneFormGen that saves submitted form data
    to Salesforce.com
    
"""

__author__  = ''
__docformat__ = 'plaintext'

# Python imorts
import logging

# Zope imports
from zope.interface import implements
from AccessControl import ClassSecurityInfo
from Acquisition import aq_parent
from zope.interface import classImplements
from DateTime import DateTime
from ZPublisher.HTTPRequest import FileUpload
from zope.contenttype import guess_content_type

# CMFCore
from Products.CMFCore.Expression import getExprContext

# Plone imports
from Products.CMFPlone.utils import safe_hasattr
from Products.Archetypes.public import StringField, StringWidget, \
    SelectionWidget, BooleanField, BooleanWidget, DisplayList, Schema, \
    ManagedSchema

from Products.ATContentTypes.content.schemata import finalizeATCTSchema
from Products.ATContentTypes.content.base import registerATCT, ATCTContent
from Products.CMFCore.permissions import View, ModifyPortalContent
from Products.CMFCore.utils import getToolByName
from Products.validation.config import validation

# DataGridField
from Products.DataGridField import DataGridField, DataGridWidget
from Products.DataGridField.SelectColumn import SelectColumn
from Products.DataGridField.FixedColumn import FixedColumn
from Products.DataGridField.DataGridField import FixedRow

# Interfaces
from Products.PloneFormGen.interfaces import IPloneFormGenField

# PloneFormGen imports
from Products.PloneFormGen.content.actionAdapter import \
    FormActionAdapter, FormAdapterSchema

# Local imports
from Products.salesforcepfgadapter.config import PROJECTNAME, REQUIRED_MARKER, SF_ADAPTER_TYPES
from Products.salesforcepfgadapter import SalesforcePFGAdapterMessageFactory as _
from Products.salesforcepfgadapter import validators
from Products.salesforcepfgadapter import interfaces

logger = logging.getLogger("PloneFormGen")

validation.register(validators.CircularDependencyValidator('CircularDependencyValidator'))

schema = FormAdapterSchema.copy() + Schema((
    StringField('SFObjectType',
        searchable=0,
        required=1,
        read_permission=ModifyPortalContent,
        default=u'Contact',
        mutator='setSFObjectType',
        widget=SelectionWidget(
            label='Salesforce Object Type',
            i18n_domain = "salesforcepfgadapter",
            label_msgid = "label_salesforce_type_text",
            ),
        vocabulary='displaySFObjectTypes',
        ),
    DataGridField('fieldMap',
         searchable=0,
         required=1,
         read_permission=ModifyPortalContent,
         schemata='field mapping',
         columns=('field_path', 'form_field', 'sf_field'),
         fixed_rows = "generateFormFieldRows",
         allow_delete = False,
         allow_insert = False,
         allow_reorder = False,
         widget = DataGridWidget(
             label='Form fields to Salesforce fields mapping',
             label_msgid = "label_salesforce_field_map",
             description="""The following Form Fields are available\
                 within your Form Folder. Choose the appropriate \
                 Salesforce Field for each Form Field.""",
             description_msgid = 'help_salesforce_field_map',
             columns= {
                 "field_path" : FixedColumn("Form Fields (path)", visible=False),
                 "form_field" : FixedColumn("Form Fields"),
                 "sf_field" : SelectColumn("Salesforce Fields", 
                                           vocabulary="buildSFFieldOptionList")
             },
             i18n_domain = "salesforcepfgadapter",
             ),
        ),
    DataGridField('dependencyMap',
         searchable=0,
         required=0,
         read_permission=ModifyPortalContent,
         schemata='field mapping',
         columns=('adapter_name', 'adapter_id', 'sf_field'),
         fixed_rows = "getLocalSFAdapters",
         allow_delete = False,
         allow_insert = False,
         allow_reorder = False,
         widget = DataGridWidget(
             label='Configure Parent Adapters',
             label_msgid = "label_salesforce_dependency_map",
             description="""This form's other Salesforce Adapters are listed below. \
                To relate the current adapter's Saleforce record to the Salesforce \
                record created by another Salesforce Adapter, select the field that \
                relates both records. Note: relationships are made from children \
                back to parents.""",
             description_msgid = 'help_salesforce_dependency_map',
             columns= {
                 "adapter_name" : FixedColumn("Possible Parent Adapters"),
                 "adapter_id" : FixedColumn("Possible Parent Adapters (id)", visible=False),
                 "sf_field" : SelectColumn("Available Field IDs", 
                                           vocabulary="buildSFFieldOptionList")
             },
             i18n_domain = "salesforcepfgadapter",
             ),
         validators = ('CircularDependencyValidator',),
         ),
    StringField(
        'creationMode',
        schemata="mode",
        required=True,
        searchable=False,
        vocabulary=["create","upsert"],
        default="create",
        widget=SelectionWidget(
            label=_(u"Do update"),
            description=_(u"Do you want to create new objects or update existing?"),
            format="radio",
         ),
    ),
    
    StringField(
        'primaryKeyField',
        schemata="mode",
        required=False,
        searchable=False,
        vocabulary='getMappedSFFields',
        # default="contact_id",
        widget=SelectionWidget(
            label=_(u"Salesforce primary key field"),
            description=_(u"Salesforce field to be used to find and existing record"),
         ),
    ),    
    
    BooleanField(
        'prepopulateFieldValues',
        schemata="mode",
        required=False,
        default=False,
        widget=BooleanWidget(
            label=_(u"Prepopulate field values on form load"),
            description=_(u"You know... prepopulate.")
        ),
    ),

    StringField(
        'primaryKeyFieldDefaultExpression',
        schemata="mode",
        required=False,
        searchable=False,
        default="",
        widget=StringWidget(
            label=_(u"Primary key field default expression"),
            description=_(u"Placeholder for now. Will be a TALES expression."),
         ),
    ),    
    
))

# move 'field mapping' schemata before the inherited overrides schemata
schema = ManagedSchema(schema.copy().fields())
schema.moveSchemata('field mapping', -1)
schema.moveSchemata('mode', -1)

class SalesforcePFGAdapter(FormActionAdapter):
    """ An adapter for PloneFormGen that saves results to Salesforce.
    """
    implements(interfaces.ISalesforcePFGAdapter)
    
    schema = schema
    security = ClassSecurityInfo()
    
    meta_type = portal_type = 'SalesforcePFGAdapter'
    archetype_name = 'Salesforce Adapter'
    content_icon = 'salesforce.gif'
    
    def initializeArchetype(self, **kwargs):
        """Initialize Private instance variables
        """
        FormActionAdapter.initializeArchetype(self, **kwargs)
        
        # All Salesforce fields for the current Salesforce object type. Since
        # we need this for every row in our field mapping widget, it's better
        # to just set it on the object when we set the Salesforce object type. 
        # This way we don't query Salesforce for every field on our form.
        self._fieldsForSFObjectType = {}
    
    security.declareProtected(View, 'onSuccess')
    def onSuccess(self, fields, REQUEST=None):
        """ The essential method of a PloneFormGen Adapter:
        - collect the submitted form data
        - examine our field map to determine which Saleforce fields
          to populate
        - if there are any mappings, submit the data to Salesforce
          and check the result
        """
        logger.debug('Calling onSuccess()')
        # only execute if we're the last SF Adapter 
        # in the form; then sort and execute ALL
        execAdapters = self._listAllExecutableAdapters()
        if len(execAdapters) and self.getId() == execAdapters[-1].getId():
            uids = {}
            for adapter_id in self.getSortedSFAdapters():
                adapter = getattr(aq_parent(self), adapter_id)
                if not adapter._isExecutableAdapter():
                    logger.warn("""Adapter %s will not create a Salesforce object \
                                   either do to its execution condition or it has been \
                                   disabled on the parent form.""" % adapter.getId()) 
                    continue
                    
                sObject = adapter._buildSObjectFromForm(fields, REQUEST)
                if len(sObject.keys()) > 1:
                    salesforce = getToolByName(self, 'portal_salesforcebaseconnector')
                    
                    # flesh out sObject with data returned from previous creates
                    for (id,field) in [(adapter_map['adapter_id'], adapter_map['sf_field']) for adapter_map in adapter.getDependencyMap() \
                      if adapter_map['sf_field'] and getattr(aq_parent(self), adapter_map['adapter_id'])._isExecutableAdapter()]:
                        sObject[field] = uids[id]
                    
                    result = salesforce.create(sObject)[0]
                    if result['success']:
                        logger.debug("Successfully created new %s %s in Salesforce" % \
                                     (adapter.SFObjectType, result['id']))
                        uids[adapter.getId()] = result['id']
                    else:
                        errorStr = 'Failed to create new %s in Salesforce: %s' % \
                            (str(adapter.SFObjectType), result['errors'][0]['message'])
                        raise errorStr
                else:
                    logger.warn('No valid field mappings found. Not calling Salesforce.')
    
    def _buildSObjectFromForm(self, fields, REQUEST=None):
        """ Used by the onSuccess handler to convert the fields from the form
            into the fields to be stored in Salesforce.
            
            Also munges dates into the required (mm/dd/yyyy) format.
        """
        logger.debug('Calling _buildSObjectFromForm()')
        formPath = aq_parent(self).getPhysicalPath()
        sObject = dict(type=self.SFObjectType)
        for field in fields:
            formFieldPath = field.getPhysicalPath()
            formFieldValue = REQUEST.form.get(field.getFieldFormName())
            if field.meta_type == 'FormDateField':
                if formFieldValue:
                    formFieldValue = DateTime(formFieldValue + ' GMT+0').HTML4()
                else:
                    # we want to throw this value away rather than pass along 
                    # to salesforce, which would ultimately raise a SoapFaultError 
                    # due to invalid xsd:dateTime formatting
                    continue
            elif field.isFileField():
                file = formFieldValue
                if file and isinstance(file, FileUpload) and file.filename != '':
                    file.seek(0) # rewind
                    data = file.read()
                    filename = file.filename
                    mimetype, enc = guess_content_type(filename, data, None)
                    from base64 import encodestring
                    formFieldValue = encodestring(data)
            
            salesforceFieldName = self._getSFFieldForFormField(formFieldPath, formPath)
            if not salesforceFieldName or formFieldValue is None:
                # we either haven't found a mapping or the
                # the form field was left blank and we therefore
                # don't care about passing along that value, since
                # the Salesforce object field may have it's own ideas
                # about data types and or default values
                continue
            
            sObject[salesforceFieldName] = formFieldValue
        return sObject
    
    security.declareProtected(ModifyPortalContent, 'setFieldMap')
    def setFieldMap(self, currentFieldMap):
        """Accept a possible fieldMapping value ala the following:
        
            (
                  {'field_path': 'replyto', 'form_field': 'Your E-Mail Address', 'sf_field': 'Email'}, 
                  {'field_path': 'topic', 'form_field': 'Subject', 'sf_field': 'FirstName'},
                  {'field_path': 'fieldset,comments', 'form_field': 'Comments', 'sf_field': ''}
            )
            
           and iterate through each potential mapping to make certain that
           a field item at the path from the form still exists.  This is how
           we purge ineligible field mappings.
        """
        logger.debug('calling setFieldMap()')
        eligibleFieldPaths = [path for title, path in self._getIPloneFormGenFieldsPathTitlePair()]
        cleanMapping = []
        
        for mapping in currentFieldMap:
            if mapping.has_key('field_path') and mapping['field_path'] in eligibleFieldPaths:
                cleanMapping.append(mapping)
                
        self.fieldMap = tuple(cleanMapping)
    
    security.declareProtected(ModifyPortalContent, 'setDependencyMap')
    def setDependencyMap(self, currentDependencyMap):
        """Accept a possible dependencyMap value ala the following:
        
            (
                  {'adapter_id': 'replyto', 'adapter_name': 'Your E-Mail Address', 'sf_field': 'Email'}, 
                  {'adapter_id': 'topic', 'adapter_name': 'Subject', 'sf_field': 'FirstName'},
                  {'adapter_id': 'fieldset,comments', 'adapter_name': 'Comments', 'sf_field': ''}
            )
            
           and iterate through each potential mapping to make certain that
           an adapter from the form still exists.  This is how
           we purge ineligible adapter mappings.
           
           BBB - when we drop 2.5.x support after the 1.5 release cycle this should be 
           reimplemented in an event-driven nature.  This current implementation and 
           the setFieldMap implementation are insane.  Furthermore, an event driven 
           system could be made to retain the existing field mappings, rather than
           just clean them out.
        """
        logger.debug('calling setDependencyMap()')
        formFolder = aq_parent(self)
        eligibleAdapters = [(adapter.getId(),adapter.Title()) for adapter in formFolder.objectValues(SF_ADAPTER_TYPES)]
        cleanMapping = []
        
        for mapping in currentDependencyMap:
            # check for the presence of keys, which won't exist on content creation
            # then make sure it's an eligible mapping
            if mapping.has_key('adapter_id') and mapping.has_key('adapter_name') and \
              (mapping['adapter_id'], mapping['adapter_name']) in eligibleAdapters:
                cleanMapping.append(mapping)
                
        self.dependencyMap = tuple(cleanMapping)
    
    security.declareProtected(ModifyPortalContent, 'setSFObjectType')
    def setSFObjectType(self, newType):
        """When we set the Salesforce object type,
           we also need to reset all the possible fields
           for our mapping selection menus.
        """
        logger.debug('Calling setSFObjectType()')
        
        def _purgeInvalidMapping(fname):
            accessor = getattr(self, self.Schema().get(fname).accessor)
            mutator = getattr(self, self.Schema().get(fname).mutator)
            
            eligible_mappings = []
            for mapping in accessor():
                if mapping.has_key('sf_field') and not \
                  self._fieldsForSFObjectType.has_key(mapping['sf_field']):
                    continue
                
                eligible_mappings.append(mapping)
            
            mutator(tuple(eligible_mappings))
        
        # set the SFObjectType
        self.SFObjectType = newType
        
        # clear out the cached field info
        self._fieldsForSFObjectType = self._querySFFieldsForType()
        
        # purge mappings and dependencies that are no longer valid
        for fname in ('fieldMap', 'dependencyMap',):
            _purgeInvalidMapping(fname)
        
    
    security.declareProtected(ModifyPortalContent, 'displaySFObjectTypes')
    def displaySFObjectTypes(self):
        logger.debug('Calling displaySFObjectTypes()')        
        """ returns vocabulary for available Salesforce Object Types 
            we can create. 
        """
        types = self._querySFObjectTypes()
        typesDisplay = DisplayList()
        for type in types:
            typesDisplay.add(type, type)
        return typesDisplay
    
    def _requiredFieldSorter(self, a, b):
        """Custom sort function
        Any fields marked as required should appear first, and sorted, in the list, 
        followed by all non-required fields, also sorted. This:
            tuples = [
                        ('A', 'A'), 
                        ('B','B (required)'), 
                        ('E', 'E'), 
                        ('Z','Z (required)'), 
                    ]
                    
        would be sorted to:
            tuples = [
                        ('B','B (required)'), 
                        ('Z','Z (required)'), 
                        ('A', 'A'), 
                        ('E', 'E'), 
                    ]
        
        """
        if (a[1].endswith(REQUIRED_MARKER) and b[1].endswith(REQUIRED_MARKER)) or \
                (not a[1].endswith(REQUIRED_MARKER) and not b[1].endswith(REQUIRED_MARKER)):
            # both items are the same in their requiredness
            if a[0] > b[0]:
                return 1
            else:
                return -1
        else:
            if a[1].endswith(REQUIRED_MARKER):
                return -1
            else:
                return 1
    
    security.declareProtected(ModifyPortalContent, 'buildSFFieldOptionList')
    def buildSFFieldOptionList(self):
        """Returns a DisplayList of all the fields
           for the currently selected Salesforce object
           type.
        """
        sfFields = self._fieldsForSFObjectType
        
        fieldList = []
        for k, v in sfFields.items():
            # determine whether each field is required and mark appropriately
            
            if v.nillable or v.defaultedOnCreate or not v.createable:
                fieldList.append((k, k))
            else:
                fieldList.append((k, str("%s %s" % (k, REQUIRED_MARKER))))
        # We provide our own custom sort mechanism
        # rather than relying on DisplayList's because we
        # want all required fields to appear first in the
        # selection menu.
        fieldList.sort(self._requiredFieldSorter)
        fieldList.insert(0, ('', ''))
        dl = DisplayList(fieldList)
        
        return dl
    
    security.declareProtected(ModifyPortalContent, 'generateFormFieldRows')
    def generateFormFieldRows(self):
        """This method returns a list of rows for the field mapping
           ui. One row is returned for each field in the form folder.
        """
        fixedRows = []
        
        for formFieldTitle, formFieldPath in self._getIPloneFormGenFieldsPathTitlePair():
            logger.debug("creating mapper row for %s" % formFieldTitle)
            fixedRows.append(FixedRow(keyColumn="field_path",
                                      initialData={"form_field" : formFieldTitle, 
                                                   "field_path" : formFieldPath,
                                                   "sf_field" : ""}))
        return fixedRows
    
    security.declareProtected(ModifyPortalContent, 'getLocalSFAdapters')
    def getLocalSFAdapters(self):
        """This method returns a list of rows for the dependency mapping
           ui. One row is returned for each SF adapter in the current Form EXCEPT for self.
        """
        fixedRows = []
        formFolder = aq_parent(self)
        
        for item_name in formFolder.objectIds():
            adapterObj = getattr(formFolder, item_name)
            if adapterObj.meta_type == 'SalesforcePFGAdapter' and adapterObj.getId() != self.getId():
                fixedRows.append(FixedRow(keyColumn="adapter_name",
                                          initialData={"adapter_name" : adapterObj.Title().strip(),
                                                       "adapter_id" : adapterObj.getId(),
                                                       "sf_field" : ""}))
        return fixedRows
    
    def _getIPloneFormGenFieldsPathTitlePair(self):
        formFolder = aq_parent(self)
        formFolderPath = formFolder.getPhysicalPath()
        formFieldTitles = []
        
        for formField in formFolder.objectIds():
            fieldObj = getattr(formFolder, formField)
            if IPloneFormGenField.providedBy(fieldObj):
                formFieldTitles.append((fieldObj.Title().strip(),
                                        ",".join(fieldObj.getPhysicalPath()[len(formFolderPath):])))
        
            # can we also inspect further down the chain
            if fieldObj.isPrincipiaFolderish:
                # since nested folders only go 1 level deep
                # a non-recursive approach approach will work here
                for subFormField in fieldObj.objectIds():
                    subFieldObj = getattr(fieldObj, subFormField)
                    if IPloneFormGenField.providedBy(subFieldObj):
                        # we append a list in this case
                        formFieldTitles.append(("%s --> %s" % (fieldObj.Title().strip(),
                                                               subFieldObj.Title().strip()),
                                                ",".join(subFieldObj.getPhysicalPath()[len(formFolderPath):])))
        
        return formFieldTitles
    
    def _querySFFieldsForType(self):
        """Return a tuple of all the possible fields for the current
           Salesforce object type
        """
        salesforce = getToolByName(self, 'portal_salesforcebaseconnector')
        salesforceFields = salesforce.describeSObjects(self.SFObjectType)[0].fields
        return salesforceFields
    
    def _querySFObjectTypes(self):
        """Returns a tuple of all Salesforce object type names.
        """
        salesforce = getToolByName(self, 'portal_salesforcebaseconnector')
        types = salesforce.describeGlobal()['types']
        return types
    
    def _getSFFieldForFormField(self, full_field_path, full_form_path):
        """  Return the Salesforce field
             mapped to a given Form field. 
        """
        sfField = None
        for mapping in self.fieldMap:
            split_field_path = mapping['field_path'].split(',')
            relative_path = full_field_path[len(full_form_path):]
            if tuple(split_field_path) == tuple(relative_path) and mapping['sf_field']:
                sfField = mapping['sf_field'] 
                break
        
        return sfField
    
    def _isExecutableAdapter(self):
        """Check possible conditions for when an adapter 
           is disabled.  These include:
           
             1) non-true execCondition on the adapter
             2) not active within the parent form folder
        """
        formFolder = aq_parent(self)
        
        if safe_hasattr(self, 'execCondition') and \
          len(self.getRawExecCondition()):
            # evaluate the execCondition.
            # create a context for expression evaluation
            context = getExprContext(formFolder, self)
            return self.getExecCondition(expression_context=context)
        
        if self.getId() not in formFolder.getRawActionAdapter():
            return False
        
        return True
    
    def _listAllExecutableAdapters(self):
        """Ugh, we wake up all the Salesforce Adapters
           to determine which are executable as determined above
        """
        formFolder = aq_parent(self)
        adapters = formFolder.objectValues(SF_ADAPTER_TYPES)
        
        return [adapter for adapter in adapters if adapter._isExecutableAdapter()]
        
    
    security.declareProtected(View, 'getSortedSFAdapters')
    def getSortedSFAdapters(self):
        """This method inspects the parent form
          folder's available SalesforcePFGAdapter
          objects and returns an ordered list based
          on their interdependencies.
        """
        def _process(formFolder, id, sorted_):
            """Recursive helper method"""
            for depend in [adapter_map['adapter_id'] for adapter_map in getattr(formFolder, id).getDependencyMap() if adapter_map['sf_field']]:
                _process(formFolder, depend, sorted_)
            if id not in sorted_:
                sorted_.append(id)
            return sorted_
        
        formFolder = aq_parent(self)
        sorted_ = []
        for id in formFolder.objectIds(SF_ADAPTER_TYPES):
            # we manually call our validation code to ensure
            # we don't walk into an infinite loop.  this serves
            # as protection for adapters that may have been 
            # configured outside the context of Archetypes validation
            validator = validators.CircularDependencyValidator("validator")
            adapter = getattr(formFolder, id)
            if validator(adapter.getDependencyMap(), instance=adapter) is not True:
                raise validators.CircularChainException
            sorted_ = _process(formFolder, id, sorted_)
        
        return sorted_
    
    def processForm(self, data=1, metadata=0, REQUEST=None, values=None):
        ATCTContent.processForm(self, data, metadata, REQUEST, values)
    
    security.declareProtected(View, 'getMappedSFFields')
    def getMappedSFFields(self):
        return tuple([item['sf_field'] for item in self.fieldMap])
    

registerATCT(SalesforcePFGAdapter, PROJECTNAME)

from Products.Archetypes.interfaces import IMultiPageSchema
classImplements(SalesforcePFGAdapter, IMultiPageSchema)

""" 
    
    An adapter for PloneFormGen that saves submitted form data
    to Salesforce.com
    
"""

__author__  = ''
__docformat__ = 'plaintext'

# Python imports
from datetime import date
import logging
import traceback
import sys

# Zope imports
from zope.interface import implements
from AccessControl import ClassSecurityInfo
from ComputedAttribute import ComputedAttribute
from zExceptions import Redirect
from Acquisition import aq_parent
from zope.interface import classImplements
from DateTime import DateTime
from ZPublisher.HTTPRequest import FileUpload
try:
    # 3.0+
    from zope.contenttype import guess_content_type
except ImportError:
    # 2.5
    from zope.app.content_types import guess_content_type

# CMFCore
from Products.CMFCore.Expression import Expression

# Plone imports
from Products.CMFPlone.utils import safe_hasattr
from Products.CMFPlone.PloneBaseTool import getExprContext
from Products.Archetypes.public import StringField, StringWidget, \
    SelectionWidget, DisplayList, Schema, ManagedSchema

from Products.ATContentTypes.content.base import registerATCT, ATCTContent
from Products.ATContentTypes.content.schemata import finalizeATCTSchema
from Products.CMFCore.permissions import View, ModifyPortalContent
from Products.CMFCore.utils import getToolByName
from Products.validation.config import validation
from Products.statusmessages.interfaces import IStatusMessage

# DataGridField
from Products.DataGridField import DataGridField, DataGridWidget
from Products.DataGridField.SelectColumn import SelectColumn
from Products.DataGridField.FixedColumn import FixedColumn
from Products.DataGridField.Column import Column
from Products.DataGridField.DataGridField import FixedRow

# TALESField
from Products.TALESField import TALESString

# Interfaces
from Products.PloneFormGen.interfaces import IPloneFormGenField, IPloneFormGenActionAdapter

# PloneFormGen imports
from Products.PloneFormGen.content.actionAdapter import \
    FormActionAdapter, FormAdapterSchema
from Products.PloneFormGen.content.formMailerAdapter import FormMailerAdapter
from Products.PloneFormGen.content.saveDataAdapter import FormSaveDataAdapter
from Products.PloneFormGen.content.fields import FGFileField

# Local imports
from Products.salesforcepfgadapter.config import PROJECTNAME, REQUIRED_MARKER, SF_ADAPTER_TYPES
from Products.salesforcepfgadapter import SalesforcePFGAdapterMessageFactory as _
from Products.salesforcepfgadapter import HAS_PLONE25, HAS_PLONE30
from Products.salesforcepfgadapter import validators
from Products.salesforcepfgadapter import interfaces
from Products.salesforcepfgadapter import config
from Products.salesforcepfgadapter.prepopulator import ExpressionChanged, sanitize_soql

if HAS_PLONE25:
    import zope.i18n

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
                 "field_path" : FixedColumn("Form Field (path)", visible=False),
                 "form_field" : FixedColumn("Form Field"),
                 "sf_field" : SelectColumn("Salesforce Field", 
                                           vocabulary="buildSFFieldOptionList")
             },
             i18n_domain = "salesforcepfgadapter",
             ),
        ),
    DataGridField('presetValueMap',
        searchable=0,
        required=0,
        read_permission=ModifyPortalContent,
        schemata='field mapping',
        columns=('value', 'sf_field'),
        allow_delete = True,
        allow_insert = True,
        allow_reorder = False,
        widget = DataGridWidget(
            label=_(u'Preset field values'),
            description=_(u"You may optionally configure additional values that should be mapped "
                          u"to Salesforce fields.  The same value will be passed each time the form "
                          u"is submitted.  For example, this could be used to set the LeadSource for "
                          u"a new Lead to 'web'.  You may also use TALES path expressions (starting "
                          u"with 'path:') or Python expressions (starting with 'python:').  Use 'now' "
                          u"to submit the current time."),
            columns={
                'value': Column('Value'),
                'sf_field': SelectColumn('Salesforce Field',
                                         vocabulary='buildSFFieldOptionList')
                }
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
        schemata="create vs. update",
        required=True,
        searchable=False,
        read_permission=ModifyPortalContent,
        vocabulary=DisplayList((
            ('create', _(u'create - Always add a new object to Salesforce.')),
            ('update', _(u'update - Update an existing object in Salesforce.')),
            )),
        default='create',
        widget=SelectionWidget(
            label=_(u'Creation Mode'),
            description=_(u'Select which action should be performed when the form containing this adapter is submitted.'),
            format="radio",
            ),
         ),

    TALESString(
        'updateMatchExpression',
        schemata="create vs. update",
        required=False,
        searchable=False,
        default="",
        validators=('talesvalidator',),
        read_permission=ModifyPortalContent,
        widget=StringWidget(
            label=_(u"Expression to match existing object for update"),
            description=_(u"Enter a TALES expression which evaluates to a SOQL WHERE clause that returns the "
                          u"Salesforce.com object you want to update.  If you interpolate input from the request "
                          u"into single quotes in the SOQL statement, be sure to escape it using the sanitize_soql "
                          u"method. For example, python:\"Username__c='\" + sanitize_soql(request['username']) + \"'\""),
            visible={'view': 'invisible', 'edit': 'visible'},
            ),
        ),

    StringField(
        'actionIfNoExistingObject',
        schemata="create vs. update",
        required=True,
        searchable=False,
        read_permission=ModifyPortalContent,
        widget = SelectionWidget(
            label = _(u'Behavior if no existing object found'),
            description = _(u'If this adapter tries to update an existing object using the above expression, '
                            u'but no object is found, what should happen?'),
            ),
        vocabulary = DisplayList((
            ('create', _(u'Create a new object instead.')),
            ('abort', _(u'Fail with an error message.')),
            ('quiet_abort', _(u'Silently skip this and any subsequent Salesforce adapters.')),
            )),
        default = 'abort',
        ),

))

# move 'field mapping' schemata before the inherited overrides schemata
schema = ManagedSchema(schema.copy().fields())
schema.moveSchemata('field mapping', -1)
schema.moveSchemata('create vs. update', -1)


class SalesforcePFGAdapter(FormActionAdapter):
    """ An adapter for PloneFormGen that saves results to Salesforce.
    """
    implements(interfaces.ISalesforcePFGAdapter)
    
    schema = schema
    security = ClassSecurityInfo()
    
    if not HAS_PLONE30:
        finalizeATCTSchema(schema, folderish=True, moveDiscussion=False)
    
    meta_type = portal_type = 'SalesforcePFGAdapter'
    archetype_name = 'Salesforce Adapter'
    content_icon = 'salesforce.gif'
   
    security.declarePrivate('_evaluateExpression')
    def _evaluateExpression(self, expr):
        evaluate = False
        if expr.startswith('path:'):
            expr = expr[5:]
            evaluate = True
        if expr.startswith('python:'):
            evaluate = True
        if expr.startswith('string:'):
            evaluate = True
        
        if evaluate:
            econtext = getExprContext(self, self)
            econtext.setGlobal('now', DateTime().ISO8601())
            return Expression(expr)(econtext)
        return expr
    
    def _onSuccess(self, fields, REQUEST=None):
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
                                   either due to its execution condition or it has been \
                                   disabled on the parent form.""" % adapter.getId()) 
                    continue

                # start the object based on the form field mapping
                sObject = adapter._buildSObjectFromForm(fields, REQUEST)

                # flesh out sObject with data returned from previous creates
                for mapping in adapter.getDependencyMap():
                    if not mapping['sf_field']:
                        continue
                    if not getattr(aq_parent(self), mapping['adapter_id'])._isExecutableAdapter():
                        continue
                    sObject[mapping['sf_field']] = uids[mapping['adapter_id']]

                # add in the preset values
                for mapping in adapter.getPresetValueMap():
                    if len(mapping):
                        value = self._evaluateExpression(mapping['value'])
                        sObject[mapping['sf_field']] = value

                salesforce = getToolByName(self, 'portal_salesforcebaseconnector')
                
                if adapter.getCreationMode() == 'update':
                    # get the user's SF UID from the session
                    try:
                        uid = adapter._userIdToUpdate(sObject)
                    except KeyError:
                        error_msg = _(u'Session expired. Unable to process form. Please try again.')
                        IStatusMessage(REQUEST).addStatusMessage(error_msg)
                        raise Redirect(aq_parent(self).absolute_url())

                    if uid:
                        sObject['Id'] = uid
                        if len(sObject.keys()) > 2:
                            # only update if we are setting something beyond type and Id
                            result = salesforce.update(sObject)[0]
                        else:
                            result = {'success': True, 'id': uid}
                    else:
                        actionIfNoExistingObject = adapter.getActionIfNoExistingObject()
                        if actionIfNoExistingObject == 'quiet_abort':
                            return
                        
                        if len(sObject.keys()) <= 1:
                            logger.warn('No valid field mappings found. Not calling Salesforce.')
                            continue
                        
                        if actionIfNoExistingObject == 'create':
                            result = salesforce.create(sObject)[0]
                        else:
                            error_msg = _(u'Could not find item to edit.')
                            IStatusMessage(REQUEST).addStatusMessage(error_msg)
                            raise Redirect(aq_parent(self).absolute_url())
                else: # create
                    if len(sObject.keys()) <= 1:
                        logger.warn('No valid field mappings found. Not calling Salesforce.')
                        continue
                
                    result = salesforce.create(sObject)[0]

                if result['success']:
                    logger.debug("Successfully %sd %s %s in Salesforce" % \
                                 (adapter.getCreationMode(), adapter.SFObjectType, result['id']))
                    uids[adapter.getId()] = result['id']

                    REQUEST.SESSION[(config.SESSION_KEY, adapter.UID())] = (result['id'], 'CREATED')

                else:
                    errorStr = 'Failed to %s %s in Salesforce: %s' % \
                        (adapter.getCreationMode(), str(adapter.SFObjectType), result['errors'][0]['message'])
                    raise Exception(errorStr)
    
    security.declareProtected(View, 'onSuccess')
    def onSuccess(self, fields, REQUEST=None):
        # wrap _onSuccess so we can do fallback behavior when calls to Salesforce fail
        
        message = None
        try:
            self._onSuccess(fields, REQUEST)
        except:
            from Products.salesforcepfgadapter.tests import TESTING
            if TESTING:
                raise
            
            # swallow the exception, but log it
            t, v = sys.exc_info()[:2]
            logger.exception('Unable to save form data to Salesforce. (%s)' % '/'.join(self.getPhysicalPath()))
            
            formFolder = aq_parent(self)
            enabled_adapters = formFolder.getActionAdapter()
            adapters = [o for o in formFolder.objectValues() if IPloneFormGenActionAdapter.providedBy(o)]
            active_savedata = [o for o in adapters if isinstance(o, FormSaveDataAdapter)
                                                   and o in enabled_adapters]
            inactive_savedata = [o for o in adapters if isinstance(o, FormSaveDataAdapter)
                                                     and o not in enabled_adapters]
            
            # 1. If there's an enabled save data adapter, just suppress the exception
            #    so the data will still be saved.
            if active_savedata:
                message = """
Someone submitted this form, but the data couldn't be saved to Salesforce
due to an exception: %s The data was recorded in this Saved-data adapter instead: %s
""" % (formFolder.absolute_url(), active_savedata[0].absolute_url())
            
            # 2. If there's a *disabled* save data adapter, call it.
            #    (This can be used to record data locally *only* when recording to Salesforce fails.)
            elif inactive_savedata:
                message = """
Someone submitted this form, but the data couldn't be saved to Salesforce
due to an exception: %s The data was recorded in this Saved-data adapter instead: %s
""" % (formFolder.absolute_url(), inactive_savedata[0].absolute_url())
                inactive_savedata[0].onSuccess(fields, REQUEST)
            
            # 3. If there's no savedata adapter, send the data in an e-mail.
            else:
                message = """
Someone submitted this form, but the data couldn't be saved to Salesforce
due to an exception: %s
""" % formFolder.absolute_url()

            err_msg = 'Technical details on the exception: '
            err_msg += ''.join(traceback.format_exception_only(t, v))

            mailer = FormMailerAdapter('dummy').__of__(formFolder)
            mailer.msg_subject = 'Form submission to Salesforce failed'
            mailer.subject_field = None
            # we rely on the PFG mailer's logic to choose a good fallback recipient
            mailer.recipient_name = ''
            mailer.recipient_email = ''
            mailer.cc_recipients = []
            mailer.bcc_recipients = []
            mailer.additional_headers = []
            mailer.body_type = 'html'
            mailer.setBody_pre(message, mimetype='text/html')
            mailer.setBody_post(err_msg, mimetype='text/html')
            if 'credit_card' in REQUEST.form:
                REQUEST.form['credit_card'] = '(hidden)'
            mailer.send_form(fields, REQUEST)
    
    def _userIdToUpdate(self, sObject):
        if len(sObject.keys()) == 1:
            # only 'type' --> means no mapped fields, so do lookup now
            data = self.retrieveData()
            if not data:
                return
            return data['Id']
        return self.REQUEST.SESSION[(config.SESSION_KEY, self.UID())][0]
    
    security.declarePrivate('retrieveData')
    def retrieveData(self):
        request = self.REQUEST
        sfbc = getToolByName(self, 'portal_salesforcebaseconnector')
        sObjectType = self.getSFObjectType()
        econtext = getExprContext(self)
        econtext.setGlobal('sanitize_soql', sanitize_soql)
        updateMatchExpression = self.getUpdateMatchExpression(expression_context = econtext)
        mappings = self.getFieldMap()

        # determine which fields to retrieve
        fieldList = [m['sf_field'] for m in mappings if m['sf_field']]
        # we always want the ID
        fieldList.append('Id')

        try:
            (obj_id, oldUpdateMatchExpression) = request.SESSION[(config.SESSION_KEY, self.UID())]
            if obj_id is None:
                raise ExpressionChanged
            if oldUpdateMatchExpression != 'CREATED' and oldUpdateMatchExpression != updateMatchExpression:
                raise ExpressionChanged
        except (AttributeError, KeyError, ExpressionChanged):
            # find item using expression
            query = 'SELECT %s FROM %s WHERE %s' % (', '.join(fieldList), sObjectType, updateMatchExpression)
        else:
            if obj_id is not None:
                query = "SELECT %s FROM %s WHERE Id='%s'" % (', '.join(fieldList), sObjectType, obj_id)
            else:
                request.SESSION[(config.SESSION_KEY, self.UID())] = (None, updateMatchExpression)
                return {}

        res = sfbc.query(query)
        error_msg = ''
        if not len(res['records']):
            if self.getActionIfNoExistingObject() == 'abort':
                error_msg = _(u'Could not find item to edit.')
            else:
                request.SESSION[(config.SESSION_KEY, self.UID())] = (None, updateMatchExpression)
                return {}
        if len(res['records']) > 1:
            error_msg = _(u'Multiple items found; unable to determine which one to edit.')

        # if we have an error condition, report it
        if error_msg:
            IStatusMessage(request).addStatusMessage(error_msg)
            mtool = getToolByName(self, 'portal_membership')
            if mtool.checkPermission('Modify portal content', self.aq_parent):
                # user needs to be able to edit form
                request.SESSION[(config.SESSION_KEY, self.UID())] = (None, updateMatchExpression)
                return {}
            else:
                # user shouldn't see form
                portal_url = getToolByName(self, 'portal_url')()
                raise Redirect(portal_url)

        data = {'Id':res['records'][0]['Id']}
        for m in mappings:
            if not m['sf_field']:
                continue
            value = res['records'][0][m['sf_field']]
            if isinstance(value, date):
                # make sure that the date gets interpreted as UTC
                value = str(value) + ' +00:00'
            data[m['field_path']] = value
        
        obj_id = None
        if 'Id' in data:
            obj_id = data['Id']
        request.SESSION[(config.SESSION_KEY, self.UID())] = (obj_id, updateMatchExpression)

        return data
    
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
                    filenameFieldName = self._getSFFieldForFormField(list(formFieldPath) + ['filename'], formPath)
                    if filenameFieldName:
                        sObject[filenameFieldName] = filename
                    mimetypeFieldName = self._getSFFieldForFormField(list(formFieldPath) + ['mimetype'], formPath)
                    if mimetypeFieldName:
                        sObject[mimetypeFieldName] = mimetype

            salesforceFieldName = self._getSFFieldForFormField(formFieldPath, formPath)
            
            if not salesforceFieldName:
                # We haven't found a mapping to a Salesforce field.
                continue
            
            if 'creationMode' in self.Schema() and self.getCreationMode() == 'update' and formFieldValue == '':
                # The adapter is in update mode and one of the fields has a value
                # of an empty string. If that field is nillable in Salesforce, we
                # should set its value to None so that it gets cleared.
                salesforceField = self._querySFFieldsForType()[salesforceFieldName]
                if getattr(salesforceField, 'nillable', False):
                    formFieldValue = None
            elif formFieldValue is None:
                # The form field was left blank and we therefore
                # don't care about passing along that value, since
                # the Salesforce object field may have it's own ideas
                # about data types and or default values.
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
                  self._querySFFieldsForType().has_key(mapping['sf_field']):
                    continue
                
                eligible_mappings.append(mapping)
            
            mutator(tuple(eligible_mappings))
        
        # set the SFObjectType
        self.SFObjectType = newType
        
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
        sfFields = self._querySFFieldsForType()
        
        fieldList = []
        for k, v in sfFields.items():
            # determine whether each field is required and mark appropriately
            
            if v.updateable or v.createable:
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
            title = fieldObj.Title().strip()
            path = ",".join(fieldObj.getPhysicalPath()[len(formFolderPath):])
            if IPloneFormGenField.providedBy(fieldObj):
                formFieldTitles.append((title, path))
            # also allow mapping the filename and mimetype for file uploads
            if isinstance(fieldObj, FGFileField):
                formFieldTitles.append((title + ' Filename', path + ',filename'))
                formFieldTitles.append((title + ' Mimetype', path + ',mimetype'))
            
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
        """Return a mapping of all the possible fields for the current
           Salesforce object type
        """
        sfbc = getToolByName(self, 'portal_salesforcebaseconnector')
        if self.SFObjectType not in sfbc.client.typeDescs:
            sfbc.client.typeDescs[self.SFObjectType] = sfbc.describeSObjects(self.SFObjectType)[0]
        return sfbc.client.typeDescs[self.SFObjectType].fields

    # for backwards-compatibility
    _fieldsForSFObjectType = ComputedAttribute(_querySFFieldsForType, 1)

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

registerATCT(SalesforcePFGAdapter, PROJECTNAME)

try:
    from Products.Archetypes.interfaces import IMultiPageSchema
    classImplements(SalesforcePFGAdapter, IMultiPageSchema)
except ImportError:
    pass

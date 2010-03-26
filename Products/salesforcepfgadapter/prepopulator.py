from DateTime import DateTime
from datetime import date
from zExceptions import Redirect
from Acquisition import aq_inner, aq_parent
from Products.PloneFormGen.interfaces import IPloneFormGenForm
from Products.Five import BrowserView
from Products.CMFCore.Expression import getExprContext
from Products.CMFCore.utils import getToolByName
from Products.statusmessages.interfaces import IStatusMessage
from Products.salesforcepfgadapter import config
from Products.salesforcepfgadapter import SalesforcePFGAdapterMessageFactory as _

def sanitize_soql(s):
    """ Sanitizes a string that will be interpolated into single quotes
        in a SOQL expression.
    """
    return s.replace("'", "\\'")

class ExpressionChanged(Exception):
    pass

class FieldValueRetriever(BrowserView):
    """
    Retrieves a default field value by querying Salesforce.
    All the fields mapped by the SF adapter are retrieved at once,
    and then cached on the request for use by other instances of
    this view.
    """

    def __init__(self, context, request):
        self.context = context
        self.request = request
        self.form = self.getForm()
        if not hasattr(request, config.REQUEST_KEY) and not request.get('HTTP_REFERER', '').startswith(self.form.absolute_url()):
            # clear session if first load
            sf_adapters = self._getSFAdapters()
            for sfa in sf_adapters:
                try:
                    del request.SESSION[(config.SESSION_KEY, sfa.UID())]
                except (AttributeError, KeyError):
                    pass
    
    def __call__(self, field_path=None):
        all_data = getattr(self.request, config.REQUEST_KEY, {})
        sfa = self.getRelevantSFAdapter()
        if sfa is None:
            return
        if sfa.UID() not in all_data:
            data = self.retrieveData()
            all_data[sfa.UID()] = data
            setattr(self.request, config.REQUEST_KEY, all_data)
        else:
            data = all_data[sfa.UID()]

        if field_path is None:
            field_path = self.getFieldPath()
        return data.get(field_path, None)

    def retrieveData(self):
        sfbc = getToolByName(self.context, 'portal_salesforcebaseconnector')
        sfa = self.getRelevantSFAdapter()
        if sfa is None:
            return {}
        
        sObjectType = sfa.getSFObjectType()
        econtext = getExprContext(sfa)
        econtext.setGlobal('sanitize_soql', sanitize_soql)
        updateMatchExpression = sfa.getUpdateMatchExpression(expression_context = econtext)
        mappings = sfa.getFieldMap()

        # determine which fields to retrieve
        fieldList = [m['sf_field'] for m in mappings if m['sf_field']]
        # we always want the ID
        fieldList.append('Id')

        try:
            (obj_id, oldUpdateMatchExpression) = self.request.SESSION[(config.SESSION_KEY, sfa.UID())]
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
                self.request.SESSION[(config.SESSION_KEY, sfa.UID())] = (None, updateMatchExpression)
                return {}

        res = sfbc.query(query)
        error_msg = ''
        if not len(res['records']):
            if sfa.getActionIfNoExistingObject() == 'abort':
                error_msg = _(u'Could not find item to edit.')
            else:
                self.request.SESSION[(config.SESSION_KEY, sfa.UID())] = (None, updateMatchExpression)
                return {}
        if len(res['records']) > 1:
            error_msg = _(u'Multiple items found; unable to determine which one to edit.')

        # if we have an error condition, report it
        if error_msg:
            IStatusMessage(self.request).addStatusMessage(error_msg)
            mtool = getToolByName(self.context, 'portal_membership')
            if mtool.checkPermission('Modify portal content', self.form):
                # user needs to be able to edit form
                self.request.SESSION[(config.SESSION_KEY, sfa.UID())] = (None, updateMatchExpression)
                return {}
            else:
                # user shouldn't see form
                portal_url = getToolByName(self.context, 'portal_url')()
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
        self.request.SESSION[(config.SESSION_KEY, sfa.UID())] = (obj_id, updateMatchExpression)

        return data

    def getForm(self):
        if IPloneFormGenForm.providedBy(self.context):
            return self.context
        parent = aq_parent(aq_inner(self.context))
        if not IPloneFormGenForm.providedBy(parent):
            # might be in a fieldset
            parent = aq_parent(parent)
        return parent
    
    def getFieldPath(self):
        return ','.join(self.context.getPhysicalPath()[len(self.form.getPhysicalPath()):])

    def _getSFAdapters(self):
        return [o for o in self.form.objectValues() if o.portal_type == 'SalesforcePFGAdapter']

    def getRelevantSFAdapter(self):
        """
        Returns the SF adapter that is already in use for this request,
        or else looks for one that maps this field
        """
        field_path = self.getFieldPath()
        
        # find a Salesforce adapter in this form that maps this field
        for sfa in self._getSFAdapters():
            if sfa.getCreationMode() != 'update':
                continue
            field_map = sfa.getFieldMap()
            if field_path in [f['field_path'] for f in field_map if f.get('sf_field', None)]:
                return sfa

    def redirectUnlessMatches(self, request_value, message, target):
        """ Helper for use in a PFG form's "Form Setup Script" override.
            Checks whether a value matches the database value of a given
            field, and if not, redirects to a given target.
        """
        db_value = self()
        if request_value != db_value:
            IStatusMessage(self.request).addStatusMessage(message)
            raise Redirect(target)

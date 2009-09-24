from Acquisition import aq_inner, aq_parent
from zope.component import adapts
from Products.PloneFormGen.interfaces import IPloneFormGenForm, IPloneFormGenField
from Products.Five import BrowserView
from Products.CMFCore.utils import getToolByName
from Products.salesforcepfgadapter import config

class FieldValueRetriever(BrowserView):
    """
    Retrieves a default field value by querying Salesforce.
    All the fields mapped by the SF adapter are retrieved at once,
    and then cached on the request for use by other instances of
    this view.
    """

    adapts(IPloneFormGenField)

    def __init__(self, context, request):
        self.context = context
        self.request = request
        self.form = self.getForm()
    
    def __call__(self):
        data = getattr(self.request, config.REQUEST_KEY, None)
        if data is None:
            data = self.retrieveData()
            setattr(self.request, config.REQUEST_KEY, data)
            if 'Id' in data:
                formkey = self.form.UID()
                self.request.SESSION[(config.SESSION_KEY, formkey)] = data['Id']
            
        field_path = self.getFieldPath()
        return data.get(field_path, None)
    
    def retrieveData(self):
        sfa = self.getRelevantSFAdapter()
        if sfa is None:
            return {}
        
        sObjectType = sfa.getSFObjectType()
        updateMatchExpression = sfa.getUpdateMatchExpression()
        mappings = sfa.getFieldMap()

        # determine which fields to retrieve
        fieldList = [m['sf_field'] for m in mappings if m['sf_field']]
        # we always want the ID
        fieldList.append('Id')

        sfbc = getToolByName(self.context, 'portal_salesforcebaseconnector')
        query = 'SELECT %s FROM %s WHERE %s' % (', '.join(fieldList), sObjectType, updateMatchExpression)
        res = sfbc.query(query)
        if not len(res['records']):
            return {}
        if len(res['records']) > 1:
            raise Exception('Multiple records found; you must use a unique key.')

        data = {'Id':res['records'][0]['Id']}
        for m in mappings:
            if not m['sf_field']:
                continue
            data[m['field_path']] = res['records'][0][m['sf_field']]
        return data

    def getForm(self):
        parent = aq_parent(aq_inner(self.context))
        if not IPloneFormGenForm.providedBy(parent):
            # might be in a fieldset
            parent = aq_parent(parent)
        return parent
    
    def getFieldPath(self):
        return ','.join(self.context.getPhysicalPath()[len(self.form.getPhysicalPath()):])

    def getRelevantSFAdapter(self):
        """
        Returns the SF adapter that is already in use for this request,
        or else looks for one that maps this field
        """
        pfg = self.form
        field_path = self.getFieldPath()
        
        # find a Salesforce adapter in this form that maps this field
        for sfa in [o for o in pfg.objectValues() if o.portal_type == 'SalesforcePFGAdapter']:
            field_map = sfa.getFieldMap()
            if field_path in [f['field_path'] for f in field_map]:
                return sfa

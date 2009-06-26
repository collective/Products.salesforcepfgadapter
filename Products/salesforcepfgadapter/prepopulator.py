from Acquisition import aq_inner, aq_parent
from zope.component import adapts
from Products.PloneFormGen.interfaces import IPloneFormGenForm, IPloneFormGenField
from Products.Five import BrowserView
from Products.CMFCore.utils import getToolByName

REQUEST_KEY = '_sfpfg_adapter'

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
        data = getattr(self.request, REQUEST_KEY, None)
        if data is None:
            data = self.retrieveData()
            setattr(self.request, REQUEST_KEY, data)

        field_path = self.getFieldPath()
        return data.get(field_path, None)

    def retrieveData(self):
        sfa = self.getRelevantSFAdapter()
        if sfa is None:
            return {}
        
        sObjectType = sfa.getSObjectType()
        sf_key_field = sfa.getPrimaryKeyField()
        mappings = sfa.getFieldMap()

        # determine the key value
        key_field_path = None
        for m in mappings:
            if m['sf_field'] == sf_key_field:
                key_field_path = m['field_path']
        if key_field_path is None:
            return {}
        key_field = self.form.restrictedTraverse(key_field_path)
        key_value = key_field.getFgTDefault()

        # determine which fields to retrieve
        fieldList = [m['sf_field'] for m in mappings if m['sf_field']]
        
        sfbc = getToolByName(self.context, 'portal_salesforcebaseconnector')
        res = sfbc.query(fieldList, sObjectType, "%s='%s'" % (sf_key_field, key_value))
        if not len(res):
            return {}
        
        data = {}
        for m in mappings:
            data[m['field_path']] = res[0][m['sf_field']]
        return data

    def getForm(self):
        parent = aq_parent(aq_inner(self.context))
        if not IPloneFormGenForm.providedBy(parent):
            # might be in a fieldset
            parent = aq_parent(parent)
        return parent
    
    def getFieldPath(self):
        return self.context.getPhysicalPath()[len(self.form.getPhysicalPath()):]

    def getRelevantSFAdapter(self):
        """
        Returns the SF adapter that is already in use for this request,
        or else looks for one that maps this field
        """
        data = self.getData()
        if 'sf_adapter' in data:
            return data['sf_adapter']
        
        pfg = self.getForm()
        field_path = self.context.getPhysicalPath()[len(pfg.getPhysicalPath()):]
        
        # find a Salesforce adapter in this form that maps this field
        data['sf_adapter'] = None
        for sfa in [o for o in pfg.objectValues() if o.portal_type == 'SalesforcePFGAdapter']:
            field_map = sfa.getFieldMap()
            if field_path in [f['field_path'] for f in field_map]:
                # now cache the found adapter for the rest of this request
                data['sf_adapter'] = sfa
                return sfa

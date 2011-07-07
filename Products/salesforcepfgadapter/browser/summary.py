from Products.Five import BrowserView
from Products.CMFCore.utils import getToolByName
from Products.PloneFormGen.interfaces import IPloneFormGenField

from Products.salesforcepfgadapter.config import SF_ADAPTER_TYPES


class AdapterSummary(BrowserView):
    
    def __call__(self):
        self.adapters = self._sf_adapters()
        self.fields = self._form_fields()
        
        return self.index()
    
    def has_sf_adapters(self):
        """ Does this form have any Salesforce adapters?
        """
        return bool(self._sf_adapters())
    
    def map_for_field(self, field_id, adapter_id):
        """ For a given PFG field Id and a Salesforce adapter Id, return the 
            Salesforce field the form field will be mapped to, or None.
        """
        field = self._field_by_id(field_id)
        adapter = self._adapter_by_id(adapter_id)
        if field is None or adapter is None:
            return None
        fieldmap = adapter.getFieldMap()
        for m in fieldmap:
            # Check for fields inside old-style fieldsets, where the fieldset
            # name is added to the field_path:
            if ',' in m['field_path']:
                id_from_map = m['field_path'].split(',')[-1]
            else:
                id_from_map = m['field_path']
            if id_from_map == field_id and m['sf_field']:
                return m['sf_field']
        return None
    
    def _sf_adapters(self):
        """ Return a tuple of dicts describing all the Salesforce adapters
            associated with this form.
        """
        info = []
        adapters = self.context.objectValues(SF_ADAPTER_TYPES)
        for a in adapters:
            presets = self._adapter_presets(a)
            parents = self._adapter_parents(a)
            data = {'id':a.getId(),
                    'title':a.Title(),
                    'sf_type':a.getSFObjectType(),
                    'presets':presets,
                    'parents':parents,
                    'condition':a.getRawExecCondition(),
                    'status':self._adapter_status(a)}
            info.append(data)
        return tuple(info)
    
    def _form_fields(self):
        """ Return the Id and Title for every field in this form, as a tuple 
            of dicts.
        """
        info = []
        cat = getToolByName(self.context, 'portal_catalog')
        form_path = '/'.join(self.context.getPhysicalPath())
        brains = cat(object_provides = IPloneFormGenField.__identifier__,
                     path=form_path)
        
        for brain in brains:
            data = {'id':brain.getId,
                    'title':brain.Title,}
            info.append(data)
        return tuple(info)
    
    def _adapter_status(self, adapter):
        if adapter.getId() in self.context.getRawActionAdapter():
            return u'enabled'
        return u'disabled'
    
    def _adapter_by_id(self, id):
        """ This assumes that adapters can only live in the root of a 
            FormFolder.
        """
        return self.context.get(id, None)
    
    def _adapter_parents(self, adapter):
        """ Return a tuple of tuples where the first value is the target
            Salesforce field, and the second is the "parent" adapter that will
            be providing the Id to use in setting the value.
        """
        parents = []
        for mapping in adapter.getDependencyMap():
            if mapping['sf_field']:
                parents.append((mapping['sf_field'],mapping['adapter_name']))
        return tuple(parents)
    
    def _adapter_presets(self, adapter):
        """ Return a tuple of tuples where the first value is the target 
            Salesforce field, and the second is the expression that will
            generate the value.
        """
        presets = []
        for mapping in adapter.getPresetValueMap():
            if mapping:
                presets.append((mapping['sf_field'],mapping['value']))
                
        return tuple(presets)
    
    def _field_by_id(self, id):
        """ Return a Form Field for a given id/shortname.
        """
        cat = getToolByName(self.context, 'portal_catalog')
        form_path = '/'.join(self.context.getPhysicalPath())
        brains = cat(object_provides = IPloneFormGenField.__identifier__,
                     path=form_path,
                     id=id)
        if len(brains) > 1:
            raise RuntimeError("Found multiple fields with id %s in this form!"
                                    % id)
        if brains:
            return brains[0].getObject()
        return None
    

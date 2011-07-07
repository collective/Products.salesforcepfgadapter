from Products.Five import BrowserView
from Products.PloneFormGen.interfaces import IPloneFormGenField
from Products.salesforcepfgadapter.config import SF_ADAPTER_TYPES


class AdapterOverview(BrowserView):
    
    def __call__(self):
        self.adapters = self._sf_adapters()
        self.fields = self._form_fields()
        
        return self.index()
    
    def is_active(self):
        return bool(self._sf_adapters())
    
    def map_for_field(self, field_id, adapter_id):
        field = self._field_by_id(field_id)
        adapter = self._adapter_by_id(adapter_id)
        if field is None or adapter is None:
            return None
        fieldmap = adapter.getFieldMap()
        for m in fieldmap:
            if m['field_path'] == field_id and m['sf_field']:
                return m['sf_field']
        return None
    
    def _sf_adapters(self):
        info = []
        adapters = self.context.objectValues(SF_ADAPTER_TYPES)
        for a in adapters:
            presets = []
            for mapping in a.getPresetValueMap():
                if mapping:
                    presets.append((mapping['sf_field'],mapping['value']))
            parents = []
            for mapping in a.getDependencyMap():
                if mapping['sf_field']:
                    parents.append((mapping['sf_field'],mapping['adapter_name']))
            data = {'id':a.getId(),
                    'title':a.Title(),
                    'sf_type':a.getSFObjectType(),
                    'presets':presets,
                    'parents':parents,
                    'status':self._adapter_status(a)}
            info.append(data)
        return info
    
    def _form_fields(self):
        info = []
        contents = self.context.objectValues()
        fields = [f for f in contents if IPloneFormGenField.providedBy(f)]
        for field in fields:
            data = {'id':field.getId(),
                    'title':field.Title(),}
            info.append(data)
        return info
    
    def _adapter_status(self, adapter):
        if adapter.getId() in self.context.getRawActionAdapter():
            return u'enabled'
        return u'disabled'
    
    def _adapter_by_id(self, id):
        # TODO: Currently does not support fieldsets
        return self.context.get(id, None)
    
    def _field_by_id(self, id):
        # TODO: Currently does not support fieldsets
        return self.context.get(id, None)
    

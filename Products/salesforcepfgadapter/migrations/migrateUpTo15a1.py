from Acquisition import aq_parent

# CMF imports
from Products.CMFCore.utils import getToolByName

class Migration(object):
    """Migrate from version prior to 1.5a1
    """
    adapterMetaType = "SalesforcePFGAdapter"
    
    def __init__(self, site, out):
        self.site = site
        self.out = out
        self.catalog = getToolByName(self.site, 'portal_catalog')
    
    def _rebuildFieldMapWithFieldPath(self):
        """We need to rebuild the list of fields for the chosen
           SFObject type, so that we can correctly mark required
           fields in the UI.
        """
        results = self.catalog.searchResults(meta_type = 'SalesforcePFGAdapter')
        
        for result in results:
            # get info about the adapter
            obj = result.getObject()
            fieldMappings = obj.getFieldMap()
            
            # get the form folder
            formFolder = aq_parent(obj)
            form_path = formFolder.getPhysicalPath()
            fields = formFolder._getFieldObjects()
            
            migratedFieldMapping = []
            for mapping in fieldMappings:
                # coerce mapping into a dictionary, since on real
                # content objects this is really a record instance
                # with no __setitem__ callable
                mapping_dict = dict(mapping)
                
                if not mapping_dict.has_key('field_path') and mapping_dict.has_key('form_field'):
                    # we need to add the field_path key with a 
                    # value the rest can stay the same
                    for field in fields:
                        if field.Title().strip() == mapping_dict['form_field']:
                            relative_field_path = field.getPhysicalPath()[len(form_path):]
                            # instances of content, we're talking about 
                            mapping_dict['field_path'] = ",".join(relative_field_path)
                            
                            # found the match, jump from field iteration
                            break
                
                migratedFieldMapping.append(mapping_dict)
            
            obj.setFieldMap(migratedFieldMapping)
    
    def migrate(self):
        """Run migration on site object passed to __init__.
        """
        print >> self.out, "Migrating from SalesforcePFGAdapter versions \
            prior 1.5a1"
        
        # run our catalog rebuild, which also 
        # calls the _rebuildFieldsForSFObjectType
        self._rebuildFieldMapWithFieldPath()
    


from Acquisition import aq_parent
from zope.component import adapter
from Products.Archetypes.interfaces import IObjectEditedEvent

from Products.salesforcepfgadapter import interfaces

UPSERT_MODE = 'upsert'
SF_VIEW = 'object/@@sf_value'
PFG_EMAIL_DEFAULT = 'here/memberEmail'

def _safe_to_override(field):
    if field.getRawFgTDefault() == PFG_EMAIL_DEFAULT:
        return True
    return not field.getRawFgTDefault() or \
        field.getRawFgTDefault() == SF_VIEW

def _set_default(sf_adapter, new_default):
    form_folder = aq_parent(sf_adapter)
    sf_key_field = sf_adapter.getPrimaryKeyField()
    mappings = sf_adapter.getFieldMap()
    for m in mappings:
        if 'sf_field' in m and m['sf_field'] != sf_key_field:
            field_path = m['field_path'].replace(',', '/')
            field = form_folder.restrictedTraverse(field_path)
            if _safe_to_override(field):
                field.setFgTDefault(new_default)

def _sf_defaults_activated(sf_adapter):
    # if we're upserting and prepopulating, we're active
    # TODO: simplify to just return  sf_adapter.getPrepopulateFieldValues()
    return sf_adapter.getCreationMode() == UPSERT_MODE and \
                sf_adapter.getPrepopulateFieldValues()


@adapter(interfaces.ISalesforcePFGAdapter, IObjectEditedEvent)
def handle_adapter_saved(sf_adapter, event):
    """On save, check if fields should be prepopulated from Salesforce.
       If so, set the default TAL expression to our custom browser view.
    """
    if _sf_defaults_activated(sf_adapter):
        _set_default(sf_adapter, SF_VIEW)
        return
    
    _set_default(sf_adapter, '')
    return


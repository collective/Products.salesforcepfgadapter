from Acquisition import aq_parent
from zope.component import adapter
from Products.Archetypes.interfaces import IObjectEditedEvent

from Products.salesforcepfgadapter import interfaces

SF_VIEW = 'object/@@sf_value'
PFG_EMAIL_DEFAULT = 'here/memberEmail'

def _safe_to_override(field):
    if field.getRawFgTDefault() == PFG_EMAIL_DEFAULT:
        return True
    return not field.getRawFgTDefault() or \
        field.getRawFgTDefault() == SF_VIEW

def _set_default(sf_adapter, new_default):
    form_folder = aq_parent(sf_adapter)
    mappings = sf_adapter.getFieldMap()
    for m in mappings:
        if 'sf_field' in m:
            field_path = m['field_path'].replace(',', '/')
            field = form_folder.restrictedTraverse(field_path)
            if _safe_to_override(field):
                field.setFgTDefault(new_default)

def _sf_defaults_activated(sf_adapter):
    # if we're upserting and prepopulating, we're active
    # TODO: simplify to just return  sf_adapter.getPrepopulateFieldValues()
    return sf_adapter.getCreationMode() == 'update' and \
        sf_adapter.getRawUpdateMatchExpression()

@adapter(interfaces.ISalesforcePFGAdapter, IObjectEditedEvent)
def handle_adapter_saved(sf_adapter, event):
    """On save, check if fields should be prepopulated from Salesforce.
       If so, set the default TAL expression to our custom browser view.
    """
    if _sf_defaults_activated(sf_adapter):
        _set_default(sf_adapter, SF_VIEW)
    else:
        _set_default(sf_adapter, '')

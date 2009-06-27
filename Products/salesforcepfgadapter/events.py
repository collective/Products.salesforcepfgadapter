import logging
from Acquisition import aq_parent
from zope.component import adapter, queryUtility
from zope.app.component.hooks import getSite
from Products.statusmessages.interfaces import IStatusMessage
from Products.Archetypes.interfaces import IObjectEditedEvent, IObjectInitializedEvent

from Products.salesforcepfgadapter import interfaces

logger = logging.getLogger("Products.salesforcepfgadapter")

DO_UPSERT_FLAG = 'upsert'
VIEW_NAME = 'context/@@sf_value'
PFG_EMAIL_DEFAULT = 'here/memberEmail'

def _safe_to_override(field):
    if field.getRawFgTDefault() == PFG_EMAIL_DEFAULT:
        return True
    return not field.getRawFgTDefault() or \
        field.getRawFgTDefault() == VIEW_NAME

def set_default(sf_adapter, new_default):
    form_folder = aq_parent(sf_adapter)
    sf_key_field = sf_adapter.getPrimaryKeyField()
    mappings = sf_adapter.getFieldMap()
    for m in mappings:
        if m['sf_field'] != sf_key_field:
            field_path = m['field_path'].replace(',', '/')
            field = form_folder.restrictedTraverse(field_path)
            if _safe_to_override(field):
                field.setFgTDefault(new_default)

@adapter(interfaces.ISalesforcePFGAdapter, IObjectEditedEvent)
def handle_adapter_saved(sf_adapter, event):
    logger.info("We hit our handler!")
    
    # if we're not upserting, make sure all our defaults are removed
    if sf_adapter.getCreationMode() != DO_UPSERT_FLAG:
        set_default(sf_adapter, '')
        return
    # if prepopulate is off, make sure all our defaults are removed
    if not sf_adapter.getPrepopulateFieldValues():
        set_default(sf_adapter, '')
        return
    # otherwise, set default to the browser view 'context/@@sf_value'
    # for each field that is mapped
    set_default(sf_adapter, VIEW_NAME)


import logging
from zope.component import adapter, queryUtility
from zope.app.component.hooks import getSite
from Products.statusmessages.interfaces import IStatusMessage
from Products.Archetypes.interfaces import IObjectEditedEvent, IObjectInitializedEvent

from Products.salesforcepfgadapter import interfaces

logger = logging.getLogger("Products.salesforcepfgadapter")

@adapter(interfaces.ISalesforcePFGAdapter, IObjectEditedEvent)
def handle_adapter_saved(sf_adapter, event):
    logger.info("We hit our handler!")
    import pdb; pdb.set_trace( )
    
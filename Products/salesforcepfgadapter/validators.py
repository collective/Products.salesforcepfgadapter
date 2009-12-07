from zope.interface import implements
from Acquisition import aq_parent
from Products.validation.interfaces.IValidator import IValidator

try: 
    # Plone 4 and higher
    import plone.app.upgrade
    USE_BBB_VALIDATORS = False
except ImportError:
    # BBB Plone 3
    USE_BBB_VALIDATORS = True

CIRCULAR_FAILURE_MSG = """You've created a circular chain of dependencies."""

class CircularChainException(Exception):
    """Exception for circular adapter chains"""
    pass

def _validateChain(current, me, adapter_ids=None):
    """Recursive function to establish chains"""
    # on the first run through this, the mapping hasn't been set, so we use the value coming
    # into the validator
    if adapter_ids is None:
        adapter_ids = [m['adapter_id'] for m in current.getDependencyMap() if m['sf_field'] != '']
    for adapter in adapter_ids:
        if adapter == me:
            raise CircularChainException
        else:
            _validateChain(getattr(aq_parent(current), adapter), me)

class CircularDependencyValidator(object):
    """"Chained adapters" are a series of adapters for SF objects in the same form
    that are related to each other, and thus depend on UIDs.  (ie creating a
    Contact and an Account where the Contact has a lookup field on a newly created Account)
    
    This validator insures that a newly added adapter's dependencies don't create a circular
    chain of dependencies.  This couldn't happen for real in SF, but could in the form's configuration
    through normal user error."""
    
    if USE_BBB_VALIDATORS:
        __implements__ = (IValidator,)
    else:
        implements(IValidator)

    def __init__(self, name, title='', description='', fail_message=CIRCULAR_FAILURE_MSG):
        self.name = name
        self.title = title or name
        self.description = description
        self.fail_message = fail_message
    
    def __call__(self, value, *args, **kwargs):
        current = kwargs['instance']
        me = current.getId()
        adapter_ids = [m['adapter_id'] for m in value if m['sf_field'] != '']
        try:
            _validateChain(current, me, adapter_ids=adapter_ids)
        except CircularChainException:
            return self.fail_message
        return True

    
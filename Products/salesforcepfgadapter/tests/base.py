# Import the base test case classes
from Testing import ZopeTestCase as ztc
from Products.CMFPlone.tests import PloneTestCase as ptc
from Products.Five import zcml
from Products.Five import fiveconfigure
from Products.PloneTestCase.layer import onsetup

from Products.salesforcebaseconnector.tests.layer import SalesforcePloneLayer

# These must install cleanly, ZopeTestCase will take care of the others
ztc.installProduct('PloneFormGen')
ztc.installProduct('DataGridField')
ztc.installProduct('salesforcebaseconnector')
ztc.installProduct('salesforcepfgadapter')

# Set up the Plone site used for the test fixture. The PRODUCTS are the products
# to install in the Plone site (as opposed to the products defined above, which
# are all products available to Zope in the test fixture)
PRODUCTS = ['salesforcepfgadapter']

@onsetup
def load_zcml():
    # load our zcml
    fiveconfigure.debug_mode = True
    import Products.salesforcepfgadapter
    zcml.load_config('configure.zcml', Products.salesforcepfgadapter)
    fiveconfigure.debug_mode = False
    
    import Products.salesforcepfgadapter.tests
    Products.salesforcepfgadapter.tests.TESTING = True

load_zcml()
ptc.setupPloneSite(products=PRODUCTS)

class SalesforcePFGAdapterTestCase(ptc.PloneTestCase):
    """Base class for integration tests for the 'salesforcepfgadapter' product. This may
    provide specific set-up and tear-down operations, or provide convenience
    methods.
    """
    layer = SalesforcePloneLayer
    
    def afterSetUp(self):
        self.salesforce = self.portal.portal_salesforcebaseconnector
        self._todelete = list() # keep track of ephemeral test data to delete
    

class SalesforcePFGAdapterFunctionalTestCase(ptc.FunctionalTestCase):
    """Base class for functional doctests
    """
    layer = SalesforcePloneLayer
    
    def afterSetUp(self):
        ztc.utils.setupCoreSessions(self.app)
        
        self.salesforce = self.portal.portal_salesforcebaseconnector
        self._todelete = list() # keep track of ephemeral test data to delete
        self.folder.invokeFactory('FormFolder', 'ff1')
        self.ff1 = getattr(self.folder, 'ff1')


class FakeRequest(dict):

    def __init__(self, **kwargs):
        self.form = kwargs

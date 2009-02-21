import transaction

# Import the base test case classes
from Testing import ZopeTestCase as ztc
from Products.CMFPlone.tests import PloneTestCase as ptc
from Products.PloneTestCase.layer import onsetup
from Products.CMFCore.utils import getToolByName

from Products.salesforcebaseconnector.tests import sfconfig   # get login/pw

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
def setup_salesforce_base_connector():
    """Install, Add, and Configure Salesforce Base Connector
       on a layer, so that we don't need to repetitively do 
       this prior to each test case run.
    """
    # aware of salesforcebaseconnector
    ztc.installProduct('salesforcebaseconnector')
    
    # get our plone site
    app = ztc.app()
    plone = app.plone
    
    # setup base connector
    plone.manage_addProduct['salesforcebaseconnector'].manage_addTool('Salesforce Base Connector', None)
    toolbox = getToolByName(plone, "portal_salesforcebaseconnector")
    toolbox.setCredentials(sfconfig.USERNAME, sfconfig.PASSWORD)
    
    # commit transaction, close connection to app ZODB
    transaction.commit()
    ztc.close(app)

ptc.setupPloneSite(products=PRODUCTS)
setup_salesforce_base_connector()

class SalesforcePFGAdapterTestCase(ptc.PloneTestCase):
    """Base class for integration tests for the 'salesforcepfgadapter' product. This may
    provide specific set-up and tear-down operations, or provide convenience
    methods.
    """
    def afterSetUp(self):
        self.salesforce = self.portal.portal_salesforcebaseconnector
        self._todelete = list() # keep track of ephemeral test data to delete
    

class BaseSalesforcePFGAdapterFunctionalTestCase(ptc.FunctionalTestCase):
    """Base class for functional doctests
    """
    def afterSetUp(self):
        self._todelete = list() # keep track of ephemeral test data to delete
        self.folder.invokeFactory('FormFolder', 'ff1')
        self.ff1 = getattr(self.folder, 'ff1')
    

class FakeRequest(dict):

    def __init__(self, **kwargs):
        self.form = kwargs

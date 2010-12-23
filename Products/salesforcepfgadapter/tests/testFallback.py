# Make sure something reasonable happens when the connection to Salesforce
# breaks.

from Products.Five.testbrowser import Browser
from Products.CMFPlone.tests.utils import MockMailHost
from Products.salesforcepfgadapter.tests import base

def always_fail(fields, REQUEST):
    assert False

class FallbackBehaviorTestCase(base.SalesforcePFGAdapterFunctionalTestCase):
    
    def afterSetUp(self):
        super(FallbackBehaviorTestCase, self).afterSetUp()

        # create form
        self.setRoles(['Manager'])
        self.portal.invokeFactory('FormFolder', 'ff1')
        self.ff1 = getattr(self.portal, 'ff1')
        
        # Create Salesforce adapter.
        # Replace its _onSuccess with one that always raises an exception.
        self.ff1.invokeFactory('SalesforcePFGAdapter', 'contact_adapter')
        self.ff1.contact_adapter._onSuccess = always_fail
        
        # disable mailer adapter, and set up mock mail host
        self.ff1.setActionAdapter(('contact_adapter',))
        self.portal._original_MailHost = self.portal.MailHost
        self.portal.MailHost = MockMailHost('MailHost')
        self.portal.email_from_address = 'test@example.com'

        self.portal.portal_workflow.doActionFor(self.ff1, 'publish')
        
        # make sure we actually use the fallback code even though we're testing
        import Products.salesforcepfgadapter.tests
        Products.salesforcepfgadapter.tests.TESTING = False

    def beforeTearDown(self):
        import Products.salesforcepfgadapter.tests
        Products.salesforcepfgadapter.tests.TESTING = True
        self.portal.MailHost = self.portal._original_MailHost
        super(FallbackBehaviorTestCase, self).beforeTearDown()
    
    def test_fallback_with_no_savedata(self):
        # if there's an exception and no savedata adapter, send an e-mail
        browser = Browser()
        browser.open('http://nohost/plone/ff1')
        browser.getControl(name='replyto').value = 'test@example.com'
        browser.getControl(name='topic').value = 'foo'
        browser.getControl(name='comments').value = 'bar'
        browser.getControl('Submit').click()

        self.failUnless('Thank You' in browser.contents)
        self.assertEqual(1, len(self.portal.MailHost.messages))
        self.failUnless('Someone submitted this form, but the data couldn\'t be saved to Salesforce'
                        in self.portal.MailHost.messages[0])

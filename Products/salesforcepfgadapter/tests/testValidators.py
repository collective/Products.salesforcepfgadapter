import os, sys
from unittest import TestCase
from Products.CMFCore.utils import getToolByName
from Products.salesforcebaseconnector.tests import sfconfig   # get login/pw
from Products.salesforcepfgadapter.validators import CircularDependencyValidator
from Products.salesforcepfgadapter.tests import base


if __name__ == '__main__':
    execfile(os.path.join(sys.path[0], 'framework.py'))

class TestCircularAdapters(base.SalesforcePFGAdapterTestCase):
    
    def afterSetUp(self):
        super(TestCircularAdapters, self).afterSetUp()
        self.validator = CircularDependencyValidator('validator')
        self.folder.invokeFactory('FormFolder', 'ff1')
        self.ff1 = getattr(self.folder, 'ff1')

    def testTwoWayCircle(self):
        """Create a pair of adapters that point to each other.  Should fail."""
        self.ff1.invokeFactory('SalesforcePFGAdapter', 'a')
        a = getattr(self.ff1, 'a')
        a.setTitle('a')
        
        self.ff1.invokeFactory('SalesforcePFGAdapter', 'b')
        b = getattr(self.ff1, 'b')
        b.setTitle('b')
        
        a.setDependencyMap(({'adapter_id': 'b', 'adapter_name': 'b', 'sf_field': '1'},))
        b.setDependencyMap(({'adapter_id': 'a', 'adapter_name': 'a', 'sf_field': '1'},))
        
        self.failIf(self.validator(({'adapter_id':'a', 'sf_field': '1'},), **{'instance':b})==True)
    
    def testThreeWayCircle(self):
        """Create a trio of adapters that point to each other.  Should fail."""
        self.ff1.invokeFactory('SalesforcePFGAdapter', 'a')
        a = getattr(self.ff1, 'a')
        a.setTitle('a')
        
        self.ff1.invokeFactory('SalesforcePFGAdapter', 'b')
        b = getattr(self.ff1, 'b')
        b.setTitle('b')
        
        self.ff1.invokeFactory('SalesforcePFGAdapter', 'c')
        c = getattr(self.ff1, 'c')
        c.setTitle('c')
        
        c.setDependencyMap(({'adapter_id': 'a', 'adapter_name': 'a', 'sf_field': '1'},))
        a.setDependencyMap(({'adapter_id': 'b', 'adapter_name': 'b', 'sf_field': '1'},))
        b.setDependencyMap(({'adapter_id': 'c', 'adapter_name': 'c', 'sf_field': '1'},))
        
        self.failIf(self.validator(({'adapter_id':'a', 'sf_field': '1'},), **{'instance':c})==True)
    
    def testThreeWayLine(self):
        """Create a trio of adapters that form a line.  Should validate."""

        # Line: a, b->c, c->a; validate c's setting of a
        self.ff1.invokeFactory('SalesforcePFGAdapter', 'a')

        self.ff1.invokeFactory('SalesforcePFGAdapter', 'b')
        b = getattr(self.ff1, 'b')
        b.setDependencyMap(({'adapter_id': 'c', 'adapter_name': 'c', 'sf_field': '1'},))

        self.ff1.invokeFactory('SalesforcePFGAdapter', 'c')
        c = getattr(self.ff1, 'c')
        c.setDependencyMap(({'adapter_id': 'a', 'adapter_name': 'a', 'sf_field': '1'},))

        self.failUnless(self.validator(({'adapter_id':'a', 'sf_field': '1'},), **{'instance':c})==True)


def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(TestCircularAdapters))
    return suite

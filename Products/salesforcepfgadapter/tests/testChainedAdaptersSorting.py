# Integration tests specific to Salesforce adapter
#

import os, sys

if __name__ == '__main__':
    execfile(os.path.join(sys.path[0], 'framework.py'))

from Products.salesforcepfgadapter.tests import base
from Products.CMFCore.utils import getToolByName

from Products.salesforcebaseconnector.tests import sfconfig   # get login/pw

from Products.salesforcepfgadapter.validators import CircularChainException

class TestChainedAdaptersSorting(base.SalesforcePFGAdapterTestCase):
    """ test order of adapters' processing so that dependencies are taken care of"""
    
    def afterSetUp(self):        
        super(TestChainedAdaptersSorting, self).afterSetUp()
        self.folder.invokeFactory('FormFolder', 'ff1')
        self.ff1 = getattr(self.folder, 'ff1')
    
    def beforeTearDown(self):
        """clean up SF data"""
        ids = self._todelete
        if ids:
            while len(ids) > 200:
                self.salesforce.delete(ids[:200])
                ids = ids[200:]
            self.salesforce.delete(ids)
    
    def testGetSortedSFAdaptersOnlyReturnsSFAdapters(self):
        """docstring for testGetSortedSFAdaptersOnlyReturnsSFAdapters"""
        # create several adapters
        self.createContent(('a','b','c','d'))
        
        # as a base case, we ensure that our getSortedSFAdapters
        # method on our adapter returns itself in the list, but
        # no other objects (i.e. validators or form folders) that
        # exist within the directory in question.
        self.assertEqual(4, len(self.ff1.a.getSortedSFAdapters()))
    
    def createContent(self, order):
        """Create len(orders) adapters in ff1, in the order specified by order
        The logic for these items is as follows:
            adapters a,b,c,d
            b depends on a
            d depends on b & c
            Assertions about order of execution:
              - a precedes b
              - b precedes d
              - c precedes d
        """
        for item in order:
            self.ff1.invokeFactory('SalesforcePFGAdapter', item)
            self.ff1[item].setTitle(item)
        
        # set the logic
        b = getattr(self.ff1, 'b')
        b.setDependencyMap(({'adapter_id': 'a', 'adapter_name': 'a', 'sf_field': '1',},))
        d = getattr(self.ff1, 'd')
        d.setDependencyMap(({'adapter_id': 'b', 'adapter_name': 'b', 'sf_field': '1',},
                            {'adapter_id': 'c', 'adapter_name': 'c', 'sf_field': '1',},))
        
    
    def verifyOrder(self, sorted_):
        """Verify the business logic for this list of sorted adapter ids.
           Once again, the logic was:
              - a precedes b
              - b precedes d
              - c precedes d
        """
        self.failUnless(sorted_.index('a') < sorted_.index('b'))
        self.failUnless(sorted_.index('b') < sorted_.index('d'))
        self.failUnless(sorted_.index('c') < sorted_.index('d'))
        self.failUnless('e' in sorted_)
    
    def testGetSortedSFAdapters1(self):
        """Ensure that our getSortedSFAdapters method returns appropriate
          ordering
        """
        # create several adapters
        self.createContent(('a','b','c','d','e'))
        sorted_adapters = self.ff1.a.getSortedSFAdapters()
        self.verifyOrder(sorted_adapters)
    
    def testGetSortedSFAdapters2(self):
        """Same as above, but with a different folder contents order
        """
        # create several adapters
        self.createContent(('e','d','c','b','a'))
        sorted_adapters = self.ff1.a.getSortedSFAdapters()
        self.verifyOrder(sorted_adapters)
    
    def testCircularAdaptersDontRaiseInfiniteLoop1(self):
        """While we currently protect circular adapters from
           being configured via archetypes validation, we also
           want to protect at the code level, since that's another
           mechanism from which the getSortedSFAdapters may be used.
        """
        self.ff1.invokeFactory('SalesforcePFGAdapter', 'a')
        a = getattr(self.ff1, 'a')
        a.setTitle('a')
        
        self.ff1.invokeFactory('SalesforcePFGAdapter', 'b')
        b = getattr(self.ff1, 'b')
        b.setTitle('b')
        
        self.ff1.invokeFactory('SalesforcePFGAdapter', 'c')
        c = getattr(self.ff1, 'c')
        c.setTitle('c')
        
        a.setDependencyMap(({'adapter_id': 'b', 'adapter_name': 'b', 'sf_field': '1'},))
        b.setDependencyMap(({'adapter_id': 'c', 'adapter_name': 'c', 'sf_field': '1'},))
        c.setDependencyMap(({'adapter_id': 'a', 'adapter_name': 'a', 'sf_field': '1'},))
        
        self.assertRaises(CircularChainException, getattr(a, 'getSortedSFAdapters'))
        self.assertRaises(CircularChainException, getattr(b, 'getSortedSFAdapters'))
        self.assertRaises(CircularChainException, getattr(c, 'getSortedSFAdapters'))
        
        # and just to make sure, we add a independent adapter to the mix, which
        # should still respect the CircularChainException seen above
        self.ff1.invokeFactory('SalesforcePFGAdapter', 'd')
        d = getattr(self.ff1, 'd')
        self.assertRaises(CircularChainException, getattr(d, 'getSortedSFAdapters'))
        
    
    def testCircularAdaptersDontRaiseInfiniteLoop2(self):
        """While we currently protect circular adapters from
           being configured via archetypes validation, we also
           want to protect at the code level, since that's another
           mechanism from which the getSortedSFAdapters may be used.
        """
        self.ff1.invokeFactory('SalesforcePFGAdapter', 'a')
        a = getattr(self.ff1, 'a')
        a.setTitle('a')
        
        self.ff1.invokeFactory('SalesforcePFGAdapter', 'b')
        b = getattr(self.ff1, 'b')
        b.setTitle('b')
        
        a.setDependencyMap(({'adapter_id': 'b', 'adapter_name': 'b', 'sf_field': '1'},))
        b.setDependencyMap(({'adapter_id': 'a', 'adapter_name': 'a', 'sf_field': '1'},))
        
        self.assertRaises(CircularChainException, getattr(a, 'getSortedSFAdapters'))
        self.assertRaises(CircularChainException, getattr(b, 'getSortedSFAdapters'))
    


def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(TestChainedAdaptersSorting))
    return suite

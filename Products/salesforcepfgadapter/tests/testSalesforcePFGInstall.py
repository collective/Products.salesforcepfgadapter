# Integration tests specific to Salesforce adapter
#

import os, sys

if __name__ == '__main__':
    execfile(os.path.join(sys.path[0], 'framework.py'))

from Products.salesforcepfgadapter.tests import base
from Products.salesforcepfgadapter.config import SF_ADAPTER_TYPES

class TestProductInstallation(base.SalesforcePFGAdapterTestCase):
    """ ensure that our product installs correctly """

    def afterSetUp(self):
        self.types      = self.portal.portal_types
        self.properties = self.portal.portal_properties
        self.factory    = self.portal.portal_factory
        self.skins      = self.portal.portal_skins
        self.workflow   = self.portal.portal_workflow
        self.metaTypes = SF_ADAPTER_TYPES
    
    def testDependenciesInstalled(self):
        DEPENDENCIES = ['PloneFormGen','DataGridField',]
        
        for depend in DEPENDENCIES:
            self.failUnless(self.portal.portal_quickinstaller.isProductInstalled(depend),
                "Dependency product %s is not already installed" % depend)
        
    def testAdapterTypeRegistered(self):
        for t in self.metaTypes:
            self.failUnless(t in self.types.objectIds())
    
    def testPortalFactorySetup(self):
        for t in self.metaTypes:
            self.failUnless(t in self.factory.getFactoryTypes(),
                "Type %s is not a factory types" % t)

    def testTypesNotSearched(self):
        types_not_searched = self.properties.site_properties.getProperty('types_not_searched')
        for t in self.metaTypes:
            self.failUnless(t in types_not_searched,
                "Type %s is searchable and shouldn't be" % t)
    
    def testTypesNotSearchedListNotPurged(self):
        types_not_searched = self.properties.site_properties.getProperty('types_not_searched')
        self.failUnless(len(types_not_searched) > 1,
            "There are plenty of stock types that are excluded from "
            "search, but we presumably just have our own due to a purge "
            "on installation.")
    
    def testMetaTypesNotListed(self):
        metaTypesNotToList  = self.properties.navtree_properties.getProperty('metaTypesNotToList')
        for t in self.metaTypes:
            self.failUnless(t in metaTypesNotToList,
                "Type %s is will show up in the nav and shouldn't" % t)
    
    def testMetaTypesNotListedNotPurged(self):
        metaTypesNotToList = self.properties.navtree_properties.getProperty('metaTypesNotToList')
        self.failUnless(len(metaTypesNotToList) > 1,
            "There are plenty of stock types that are excluded from "
            "search, but we presumably just have our own due to a purge "
            "on installation.")
    
    def testMetaTypesAllowedInFormFolder(self):
        allowedTypes = self.types.FormFolder.allowed_content_types
        for t in self.metaTypes:
            self.failUnless(t in allowedTypes,
                "Type %s is not addable to the Form Folder" % t)

        # make sure we haven't inadvertently removed other core field and adapter types
        
        # a random sampling of core fields
        coreFields = [
            'FormSelectionField',
            'FormMultiSelectionField',
            'FormLinesField',
            'FormIntegerField',
            'FormBooleanField',
            'FormStringField',
            'FormTextField',
        ]
        
        for t in coreFields:
            self.failUnless(t in allowedTypes,
                "Type %s was accidentally whacked from the Form Fields allowed_content_types" % t)
    
    def testNeededSkinsRegistered(self):
        """Our all important skin layer(s) should be registered with the site."""
        prodSkins = ('salesforcepfgadapter_images',)
        
        for prodSkin in prodSkins:
            self.failUnless(prodSkin in self.skins.objectIds(),
                "The skin %s was not registered with the skins tool" % prodSkin)
    
    def testSkinShowsUpInToolsLayers(self):
        """We need our product's skin directories to show up below custom as one of the called
           upon layers of our skin's properties
        """
        product_layers = ('salesforcepfgadapter_images',)

        for selection, layers in self.skins.getSkinPaths():
            for specific_layer in product_layers:
                self.failUnless(specific_layer in layers, "The %s layer \
                    does not appear in the layers of Plone's %s skin" % (specific_layer,selection))
        
    def testCorePloneLayersStillPresent(self):
        """As was known to happen with legacy versions of GS working with the skins tool,
           it was easy to inadvertently remove need layers for the selected skin.  Here 
           we make sure this hasn't happened.
        """
        core_layers = ('PloneFormGen','plone_templates',)
        
        for selection, layers in self.skins.getSkinPaths():
            for specific_layer in core_layers:
                self.failUnless(specific_layer in layers, "The %s layer \
                    does not appear in the layers of Plone's available skins" % specific_layer)
        
    
def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(TestProductInstallation))
    return suite


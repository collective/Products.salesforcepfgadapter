# Migration tests specific to Salesforce adapter
#

import os, sys, email
import transaction
from Products.salesforcebaseconnector.tests import sfconfig   # get login/pw
from Products.salesforcepfgadapter.migrations.migrateUpTo10rc1 import Migration as Migration_10rc1
from Products.salesforcepfgadapter.migrations.migrateUpTo15a1 import Migration as Migration_15a1
from Products.salesforcepfgadapter.Extensions.Install import _productNeedsMigrationTo10RC1, \
    _productNeedsMigrationTo15a1

if __name__ == '__main__':
    execfile(os.path.join(sys.path[0], 'framework.py'))

from Products.CMFCore.utils import getToolByName

from Products.salesforcepfgadapter.tests import base

class Test10rc1ProductMigration(base.SalesforcePFGAdapterTestCase):
    """ ensure that our product migrates correctly from version to version 
        with thanks to CMFPlone/tests/testMigrations.py for numerous examples.
    """
    
    def afterSetUp(self):
        super(Test10rc1ProductMigration, self).afterSetUp()
        self.types   = getToolByName(self.portal, 'portal_types')
        self.catalog = getToolByName(self.portal, 'portal_catalog')
        self.qi      = getToolByName(self.portal, 'portal_quickinstaller')
        
        self.migration = Migration_10rc1(self.portal, [])
    
    def testTypeIndexRebuiltViaReinstallationTestsMigrationTo10rc1(self):
        # make a form folder
        self.folder.invokeFactory('FormFolder', 'ff1')
        self.ff1 = getattr(self.folder, 'ff1')
        
        # force set the portal's version
        self.qi.salesforcepfgadapter.installedversion = '1.0alpha1'
        
        # change the type name, so an outdated version gets created
        adapter = self.types.get('SalesforcePFGAdapter')
        adapter.title = 'Unmigrated'
        
        # make an adapter
        self.ff1.invokeFactory('SalesforcePFGAdapter', 'salesforceadapter')
        self.ff1.salesforceadapter.reindexObject()
        
        # assert that misnamed type exists in Type index, and the 
        # meta/portal type remains as expected
        self.failUnless("SalesforcePFGAdapter" in self.catalog.uniqueValuesFor('portal_type'))
        self.failUnless("SalesforcePFGAdapter" in self.catalog.uniqueValuesFor('meta_type'))
        self.failUnless("Unmigrated" in self.catalog.uniqueValuesFor('Type'))
        
        # quickinstall
        self.qi.reinstallProducts(['salesforcepfgadapter',])
        
        # our migration is happen
        self.failUnless("SalesforcePFGAdapter" in self.catalog.uniqueValuesFor('portal_type'))
        self.failUnless("SalesforcePFGAdapter" in self.catalog.uniqueValuesFor('meta_type'))
        self.failUnless("Salesforce Adapter" in self.catalog.uniqueValuesFor('Type'))
    
    def testDataTypeForOnInstanceFieldsForSFObjectTypeMigratedTo10rc1(self):
        """prior to version 1.0rc1, we were instantiating the adapter with 
           a private attribute, _fieldsForSFObjectType, as a list.  In a nutshell,
           we were populating this with a list of the fields for the chosen SFObject
           and threw away a bunch of extra field information provided by Salesforce.
           In order to mark certain fields as required in the UI, we needed to change
           the data structure and store more information locally.  This caused breakage
           in pre-modification adapter instances and our migration regenerates the value stored.
        """
        
        # make a form folder
        self.folder.invokeFactory('FormFolder', 'ff1')
        self.ff1 = getattr(self.folder, 'ff1')
        
        # force set the portal's version
        self.qi.salesforcepfgadapter.installedversion = '1.0alpha1'
        
        # create an adapter
        self.ff1.invokeFactory('SalesforcePFGAdapter', 'salesforce')
        
        # we brute force our attribute to the previous data structure
        self.ff1.salesforce.__dict__['_fieldsForSFObjectType'] = []
        
        # quickinstall
        self.qi.reinstallProducts(['salesforcepfgadapter',])
        
        # make sure our migration has resolved the situation
        self.assertEqual(type(dict()), type(self.ff1.salesforce._fieldsForSFObjectType))
    
    def testMigrationTo10rc1RequiredForVersions(self):
        versionMigrationNeededMapping = {
            '1.0alpha1':True,
            '1.0alpha2':True,
            '1.0alpha3':True,
            '1.0a3':True,
            '1.0b1':True,
            '1.0beta3':True,
            '1.0alpha1 (svn/unreleased)':True,
            '1.0alpha1 (SVN/UNRELEASED)':True,
            'Some Bogus Version':False,
            '1.0rc1':False,
            '1.0rc2':False,
            '5.0':False,
        }
        
        for k,v in versionMigrationNeededMapping.items():
            self.qi.salesforcepfgadapter.installedversion = k
            
            self.assertEqual(v, _productNeedsMigrationTo10RC1(self.qi),
                "Version %s received an incorrect version migration status response" % k)
    
class Test15a1ProductMigration(base.SalesforcePFGAdapterTestCase):
    """ ensure that our product migrates correctly from version to version 
        with thanks to CMFPlone/tests/testMigrations.py for numerous examples.
    """
    def afterSetUp(self):
        super(Test15a1ProductMigration, self).afterSetUp()
        self.catalog = getToolByName(self.portal, 'portal_catalog')
        self.qi      = getToolByName(self.portal, 'portal_quickinstaller')
        self.migration = Migration_15a1(self.portal, [])
    
    def testMigrationTo15a1RequiredForVersions(self):
        versionMigrationNeededMapping = {
            '1.0alpha1':True,
            '1.0a3':True,
            '1.0b1':True,
            '1.0beta3':True,
            '1.0alpha1 (svn/unreleased)':True,
            '1.0alpha1 (SVN/UNRELEASED)':True,
            'Some Bogus Version':False,
            '1.0rc1':True,
            '1.0rc2':True,
            '1.0':True,
            '1.4.9':True,
            '1.5a1':False,
            '5.0':False,
        }

        for k,v in versionMigrationNeededMapping.items():
            self.qi.salesforcepfgadapter.installedversion = k

            self.assertEqual(v, _productNeedsMigrationTo15a1(self.qi),
                "Version %s received an incorrect version migration status response" % k)
    
    def testFieldPathAddedToFieldMapUponMigrationTo15a1(self):
        # make a form folder
        self.folder.invokeFactory('FormFolder', 'ff1')
        self.ff1 = getattr(self.folder, 'ff1')
        
        # force set the portal's version to an older version
        self.qi.salesforcepfgadapter.installedversion = '1.0b1'
        
        # create an adapter
        self.ff1.invokeFactory('SalesforcePFGAdapter', 'salesforce')
        
        # we brute force our fieldMap to the pre-field path format
        # notice no field_path key for each mapping, we bypass the
        # setter, which would clean this up for us automatically
        self.ff1.salesforce.fieldMap = (
            {'form_field': 'Your E-Mail Address', 'sf_field': 'Email'},
            {'form_field': 'Comments', 'sf_field': 'Description'})
        
        # a list has no call for items, thus the attribute error
        self.failIf(self.ff1.salesforce.getFieldMap()[0].has_key('field_path'))
        
        # reinstall the product, which should recongnize our
        # pre-1.5a1-ness and force the 1.5a1 migration
        self.qi.reinstallProducts(['salesforcepfgadapter',])
        
        # make sure our migration has added a field_path to the mapping and
        # has retained our previously configure destination field
         
        # for the first mapping
        self.assertEqual('replyto', self.ff1.salesforce.getFieldMap()[0]['field_path'])
        self.assertEqual('Email', self.ff1.salesforce.getFieldMap()[0]['sf_field'])
        
        # and the second
        self.assertEqual('comments', self.ff1.salesforce.getFieldMap()[1]['field_path'])
        self.assertEqual('Description', self.ff1.salesforce.getFieldMap()[1]['sf_field'])
    




def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(Test10rc1ProductMigration))
    suite.addTest(makeSuite(Test15a1ProductMigration))
    return suite

from Products.salesforcepfgadapter.config import PROJECTNAME
from Products.salesforcepfgadapter import HAS_PLONE25, HAS_PLONE30

from Products.CMFCore.utils import getToolByName
from Products.CMFCore.permissions import ManagePortal
from Products.CMFPlone.utils import versionTupleFromString

from Products.salesforcepfgadapter.migrations.migrateUpTo10rc1 import Migration as Migration_10rc1
from Products.salesforcepfgadapter.migrations.migrateUpTo15a1 import Migration as Migration_15a1


from StringIO import StringIO

ALLTYPES = ('SalesforcePFGAdapter',)
DEPENDENCIES = ('PloneFormGen','DataGridField',)

def _productNeedsMigrationTo10RC1(qi_tool):
    # was the product ever installed?
    if hasattr(qi_tool, PROJECTNAME):
        # get needed info about the version that was intalled
        installedProduct = getattr(qi_tool, PROJECTNAME)
        installedVersion = installedProduct.getInstalledVersion()
        
        # convert toInstallVersion into a tuple via Plone's migration infrastructure
        installedVersionTuple = versionTupleFromString(installedVersion)
    
        # if we're in the 1.0 branch and we're less mature than a release candidate
        return bool(installedVersionTuple and installedVersionTuple[0:2] == (1,0) and installedVersionTuple[3] in ('alpha', 'beta',))
    else:
        # never installed, no migration needed
        return False

def _productNeedsMigrationTo15a1(qi_tool):
    # was the product ever installed?
    if hasattr(qi_tool, PROJECTNAME):
        # get needed info about the version that was intalled
        installedProduct = getattr(qi_tool, PROJECTNAME)
        installedVersion = installedProduct.getInstalledVersion()
    
        # convert toInstallVersion into a tuple via Plone's migration infrastructure
        installedVersionTuple = versionTupleFromString(installedVersion)
    
        # if we're in the 1.0 branch and we're less mature than a release candidate
        return bool(installedVersionTuple and installedVersionTuple[0] == 1 and installedVersionTuple[1] < 5)
    else:
        # never installed, no migration needed
        return False
    

def install(self):
    out = StringIO()
    
    print >> out, "Installing dependency products"
    portal_qi = getToolByName(self, 'portal_quickinstaller')
    for depend in DEPENDENCIES:
        if portal_qi.isProductInstallable(depend) and not portal_qi.isProductInstalled(depend):
            portal_qi.installProduct(depend)
    
    # we determine here, if we need to run a migration to 1.0rc1
    # this is because running the steps from profile in Plone 3.1.x
    # will jump the version number immediately up to the installing version
    # and we'll no longer have access to what was originally installed
    # NOTE: the migration needs to be run later in the process is below
    # and this allows us to support both a jump to the latest 
    # salesforcepfgadapter version and Plone 3.1.x in the same jump
    needs10rc1Migration = _productNeedsMigrationTo10RC1(portal_qi)
    needs15a1Migration = _productNeedsMigrationTo15a1(portal_qi)
    
    # We install our product by running a GS profile.  We use the old-style Install.py module 
    # so that our product works w/ the Quick Installer in Plone 2.5.x
    print >> out, "Installing salesforcepfgadapter"
    setup_tool = getToolByName(self, 'portal_setup')
    if HAS_PLONE30:
        setup_tool.runAllImportStepsFromProfile(
                "profile-Products.salesforcepfgadapter:default",
                purge_old=False)
    else:
        old_context = setup_tool.getImportContextID()
        setup_tool.setImportContext('profile-Products.salesforcepfgadapter:default')
        setup_tool.runAllImportSteps()
        setup_tool.setImportContext(old_context)
    print >> out, "Installed types and added to portal_factory via portal_setup"
    
    propsTool = getToolByName(self, 'portal_properties')
    siteProperties = getattr(propsTool, 'site_properties')
    navtreeProperties = getattr(propsTool, 'navtree_properties')

    # Add the field, fieldset, thanks and adapter types to types_not_searched
    # This is not desirable to do with GS because we don't want to maintain a list of 
    # the Portal's types_not_searched and we don't want to overwrite existing settings
    typesNotSearched = list(siteProperties.getProperty('types_not_searched'))
    for f in ALLTYPES:
        if f not in typesNotSearched:
            typesNotSearched.append(f)
    siteProperties.manage_changeProperties(types_not_searched = typesNotSearched)
    print >> out, "Added form fields & adapters to types_not_searched"
    
    # Add the field, fieldset, thanks and adapter types to types excluded from navigation
    # This is not desirable to do with GS because we don't want to maintain a list of 
    # the Portal's metaTypesNotToList and we don't want to overwrite existing settings
    typesNotListed = list(navtreeProperties.getProperty('metaTypesNotToList'))
    for f in ALLTYPES:
        if f not in typesNotListed:
            typesNotListed.append(f)
    navtreeProperties.manage_changeProperties(metaTypesNotToList = typesNotListed)
    print >> out, "Added form fields & adapters to metaTypesNotToList"
    
    # run the 1.0rc1 migration if deemed necessary
    if needs10rc1Migration:
        portal_url = getToolByName(self, 'portal_url')
        portal     = portal_url.getPortalObject()
        migration = Migration_10rc1(portal, out).migrate()
        print >> out, migration
    
    # run the 1.5a1 migration if deemed necessary
    if needs15a1Migration:
        portal_url = getToolByName(self, 'portal_url')
        portal     = portal_url.getPortalObject()
        migration = Migration_15a1(portal, out).migrate()
        print >> out, migration
    
    print >> out, "Successfully installed %s." % PROJECTNAME
    return out.getvalue()


def uninstall(self):
    out = StringIO()
    
    portal_factory = getToolByName(self,'portal_factory')
    propsTool = getToolByName(self, 'portal_properties')
    siteProperties = getattr(propsTool, 'site_properties')
    navtreeProperties = getattr(propsTool, 'navtree_properties')
    types_tool = getToolByName(self, 'portal_types')
    
    # remove salesforce adapter as a factory type
    factory_types = portal_factory.getFactoryTypes().keys()
    for t in ALLTYPES:
        if t in factory_types:
            factory_types.remove(t)
    portal_factory.manage_setPortalFactoryTypes(listOfTypeIds=factory_types)
    print >> out, "Removed form adapters from portal_factory tool"
    
    # remove salesforce adapter from Form Folder's list of addable types
    if 'FormFolder' in types_tool.objectIds():
        allowedTypes = types_tool.FormFolder.allowed_content_types
        
        if 'SalesforcePFGAdapter' in allowedTypes:
            allowedTypes = list(allowedTypes)
            allowedTypes.remove('SalesforcePFGAdapter')
            types_tool.FormFolder.allowed_content_types = allowedTypes
            print >> out, "Removed SalesforcePFGAdapter from FormFolder's allowedTypes"
    
    # remove our types from the portal's list of types excluded from navigation
    typesNotListed = list(navtreeProperties.getProperty('metaTypesNotToList'))
    for f in ALLTYPES:
        if f in typesNotListed:
            typesNotListed.remove(f)
    navtreeProperties.manage_changeProperties(metaTypesNotToList = typesNotListed)
    print >> out, "Removed form adapters from metaTypesNotToList"

    # remove our types from the portal's list of types_not_searched
    typesNotSearched = list(siteProperties.getProperty('types_not_searched'))
    for f in ALLTYPES:
        if f in typesNotSearched:
            typesNotSearched.remove(f)
    siteProperties.manage_changeProperties(types_not_searched = typesNotSearched)
    print >> out, "Removed form adapters from types_not_searched"
    
    # Remove skin directory from skin selections
    skinstool = getToolByName(self, 'portal_skins')
    for skinName in skinstool.getSkinSelections():
        path = skinstool.getSkinPath(skinName)
        path = [i.strip() for i in  path.split(',')]
        if 'salesforcepfgadapter_images' in path:
            path.remove('salesforcepfgadapter_images')
            path = ','.join(path)
            skinstool.addSkinSelection(skinName, path)
    print >> out, "Removed salesforcepfgadapter_images layer from all skin selections"
    
    print >> out, "\nSuccessfully uninstalled %s." % PROJECTNAME
    return out.getvalue()


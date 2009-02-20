from AccessControl import ModuleSecurityInfo
from Products.Archetypes.public import process_types, listTypes
from Products.CMFCore import utils
from Products.CMFCore.DirectoryView import registerDirectory

from Products.salesforcepfgadapter.config import PROJECTNAME, GLOBALS, \
    SFA_ADD_CONTENT_PERMISSION
from Products.PloneFormGen.config import ADD_CONTENT_PERMISSION, SKINS_DIR

from zope.i18nmessageid import MessageFactory
SalesforcePFGAdapterMessageFactory = MessageFactory('salesforcepfgadapter')

registerDirectory(SKINS_DIR + '/salesforcepfgadapter_images', GLOBALS)

def initialize(context):    

    import content

    ##########
    # Add our content types
    # A little different from the average Archetype product
    # due to the need to individualize some add permissions.
    #
    # This approach borrowed from ATContentTypes
    #
    listOfTypes = listTypes(PROJECTNAME)

    content_types, constructors, ftis = process_types(
        listOfTypes,
        PROJECTNAME)
    allTypes = zip(content_types, constructors)
    for atype, constructor in allTypes:
        kind = "%s: %s" % (PROJECTNAME, atype.archetype_name)
        
        if atype.portal_type == 'SalesforcePFGAdapter':
            permission = SFA_ADD_CONTENT_PERMISSION
        else:
            permission = ADD_CONTENT_PERMISSION
        
        utils.ContentInit(
            kind,
            content_types      = (atype,),
            permission         = permission,
            extra_constructors = (constructor,),
            fti                = ftis,
            ).initialize(context)

    ModuleSecurityInfo('Products.PloneFormGen').declarePublic('SalesforcePFGAdapterMessageFactory')



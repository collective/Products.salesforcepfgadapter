from Products.CMFCore.permissions import setDefaultRoles

## The Project Name
PROJECTNAME = "salesforcepfgadapter"

## The skins dir
SKINS_DIR = 'skins'

## Globals variable
GLOBALS = globals()

## Permission for creating a SalesforcePFGAdapter
SFA_ADD_CONTENT_PERMISSION = 'PloneFormGen: Add Salesforce PFG Adapter'
setDefaultRoles(SFA_ADD_CONTENT_PERMISSION, ('Manager','Owner',))

## Required field marker
REQUIRED_MARKER = "(required)"

SF_ADAPTER_TYPES = ['SalesforcePFGAdapter',]

REQUEST_KEY = '_sfpfg_adapter'
SESSION_KEY = '_pfgadapter_session'
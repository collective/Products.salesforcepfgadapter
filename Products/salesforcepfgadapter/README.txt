Salesforce PFG Adapter (PloneFormGen Add-On)
============================================
Product home is http://plone.org/products/salesforcepfgadapter. A 
`documentation area`_ and `issue tracker`_ are available at the linked 
locations.

.. _documentation area: http://plone.org/documentation/manual/integrating-plone-with-salesforce.com
.. _issue tracker: http://plone.org/products/salesforcepfgadapter/issues

A Google Group, called `Plone Salesforce Integration`_ exists with the sole 
aim of discussing and developing tools to make Plone integrate well with
Salesforce.com.  If you have a question, joining this group and posting to the 
mailing list is the likely best way to get support.

.. _Plone Salesforce Integration: http://groups.google.com/group/plonesf

Failing that, please try using the Plone users' mailing list or the #plone irc 
channel for support requests. If you are unable to get your questions answered 
there, or are interested in helping develop the product, see the credits below 
for individuals you might contact.

Overview
========

This product builds on top of the foundation for through the web form 
creation provided by `PloneFormGen`_.
If you are unfamiliar with PloneFormGen's capabilities and the problem
space it intends to serve, we encourage you to start by downloading that
and reading the README.txt file in the root of the product. In particular,
the "Overview" and "Rationale For This Product" sections are recommended.

.. _PloneFormGen: http://plone.org/products/ploneformgen

Once you've setup a suitable PloneFormGen form folder (and correctly
installed and configured the Salesforce PFG Adapter and its dependencies), 
you'll have the option of adding a new action adapter called a
"Salesforce Adapter".

Once you've added a Salesforce PFG Adapter to your form, you're presented with 
both "default" and "field mapping" (in addition to the standard "overrides") 
management screens for editing the adapter. The default screen consists of a 
drop-down menu populated with all the sObject types (i.e. Salesforce Objects) 
found in the Salesforce.com instance that corresponds to the credentials
entered when creating a Salesforce Base Connector in the ZMI. This should 
include both standard and custom sObjects. 
 
Once you've chosen your sObject type, moving through to the "field mapping"
management screen will display a two-column form for setting which Salesforce 
field will be populated by each field on your form. Each field on your form is
represented by a single row, with the form field name in the left column, and a
drop-down selection menu of all available Salesforce fields on the right. 
Select the desired Salesforce field for each form field and click "Save". 
 
NB: While it is not required to map every form field to a Salesforce field,
you will want to make sure that all the sObject fields defined as required
fields in your Salesforce configuration *do* have a mapping.  Otherwise, the
sObject will not be succesfully created on submission of the form.  All required
fields for your chosen sObject should be marked accordingly and appear at the
top of the list of options.

Should you go back and switch to a different sObject type after having provided
a  mapping at any time, you'll want to recreate your desired mapping.  This is
intended behavior, since the update would fail (or worse, produce very
confusing results) if the previously selected sObject type's mapping were
maintained.

If you are using a version of Salesforce PFG Adapter that is >= version 1.5.x 
and you configure a form that contains multiple "Salesforce Adapters", you 
also have the ability to relate the resulting Salesforce.com provided unique 
"Id" for each adapter to a field of your choosing on later executed adapters. 
This is how one can create related Salesforce.com (via a lookup field, which 
is conceptually similar to a foreign key) records from a single form.  Take 
the following scenario as a visual example with to sObjects and their inherent
schemas::

 -----------                -------------
 | Account |                | Contact   |
 -----------                -------------
 | Id      | -------------> | AccountId |
 | Name    |                | LastName  |
 -----------                -------------
 
In the above scenario, the "Account" adapter will be run before the "Contact" 
adapter regardless of ordering within the PloneFormGen form.  In this sense, 
the "Contact" adapter is *dependent upon* the result from the "Account" 
adapter. Upon creation of the "Account" within Salesforce.com an Id like 
"01r600123009QiJ", will be returned along with the API response.  This will 
then be saved and can be configured to be inserted into the "AccountId" field 
for the "Contact" record that is next created. Care is taken via validation to
ensure that "circularly dependent" adapters can not be accidentally 
configured.


Rationale For This Product
==========================

Using the wonderful foundation that is provided by PloneFormGen (and Plone for
that  matter), the task of creating a form that collects and validates some
desired information is no longer a task that requires developer intervention,
but can be done by the content editor with a decent grasp of the Plone user
interface.  Having this data inside the CMS or emailed is only of limited use
however. 

Salesforce.com provides an extensible, powerful platform from which
to do Customer Relationship Management (CRM) tasks ranging from sales,
marketing, nonprofit constituent organizing, and customer service. The
Salesforce PFG Adapter symbolizes the pragmatic joining of a best of breed CMS
and CRM so that each can focus on its own strengths in a way that is easy for
non-developers to use.

Salesforce.com offers functionality called web-to-lead, but aside from 
PloneFormGen's many strengths over the web-to-lead form builder this software 
offers the following additional features:

- Configurable validation of individual form fields
- Ability to create as many different records as you'd like from the results 
  of one form
- Ability to create custom sObject records with your form
- Ability to create whichever type of sObject records, whereas web-to-lead
  creates a Lead record, which can only be converted to a Contact, Account, or
  Opportunity record. Want to directly create a Campaign record from a form?  
  That's fine.
- Ability to create multiple records that are related to each other (i.e. 
  create an Account record, then create a Contact record with the previously 
  created Account's Id filling the Contact's AccountId field.) 


Dependencies
============

Depends upon the beatbox library >= 0.9.1.1, which is a Python wrapper to the
Salesforce.com API (version 7.0).  You must have a Salesforce.com account
that provides API access.

To download and install beatbox, please visit::

 http://code.google.com/p/salesforce-beatbox/

Tested with Plone 2.5.x, 3.0.x, or 3.1.x and all relevant dependencies.

See dependencies for PloneFormGen 1.2.x+.  As a pre-requisite, all of these must be 
met in order to use the Salesforce PFG Adapter.

SalesforceBaseConnector >= 1.0a3. See 
http://plone.org/products/salesforcebaseconnector

DataGridField >= 1.6.x.  Earlier versions didn't properly disable 
DataGridField's add row feature, which is important in our case because the 
user can't add new possible form fields for mapping from within the Salesforce
Adapter.  Those need to be added to the form itself.
 
Installation
============

Typical for a Zope/Plone product:

* Install and *configure* dependencies (includes beatbox setup and creation of
  Salesforce Base Connector with credentials in the root of the Plone site.)

* Unpack the product package into the Products folder of the Zope/Plone 
  instance. Check your ownership and permissions.

* Restart Zope.

* Go to the Site Setup page in the Plone interface and click on the Add/Remove
  Products link. Choose salesforcepfgadapter (check its checkbox) and click the 
  Install button. If not done already, this will install PloneFormGen in 
  addition to the salesforcepfgadapter.  If PloneFormGen is not available on the 
  Add/Remove Products list, it usually means that the product did not load due 
  to missing prerequisites.

Permissions
===========

See Permissions section of README.txt within PloneFormGen.

Security
========

See Security section of README.txt within PloneFormGen.

Known Problems
==============

See Known Problems section of README.txt within PloneFormGen. In addition:

- Beatbox, the underlying Python wrapper library to the Salesforce.com API 
  does not raise a custom exception in the scenario of the API being 
  unavailable due to scheduled maintenance as is evident within the following 
  response: SoapFaultError: 'UNKNOWN_EXCEPTION' 'UNKNOWN_EXCEPTION: Server 
  unavailable due to scheduled maintenance'

This is left unfixed in all branches <=1.5.x of the Salesforce PFG Adapter, 
due to the modifications that would be required to adequately handle the case 
with technologies lower in the stack, such as Salesforce Base Connector and 
beatbox. This will be addressed in a future release.

Another known problem arises when using versions of DataGridField (DGF), a 
dependency to this product, < 1.6 final. DGF shipped with two versions
of a css stylesheet called datagridwidget.css (one a .dtml file and the other 
a .css file).  If the incorrect version was active, the PloneFormGen to 
Salesforce "field mapping" user interface appeared as though additional fields
were addable directly from the Salesforce Adapter editing screen.  In 
addition, the hidden column containing the relative path to the field appeared
to the user.  This is easily resolved by upgrading to DGF versions >= 1.6.

Credits
=======

The Plone & Salesforce crew in Seattle and Portland:

- Jon Baldivieso <jonb --AT-- onenw --DOT-- org>
- Andrew Burkhalter <andrewb --AT-- onenw --DOT-- org>
- Brian Gershon <briang --AT-- webcollective --DOT-- coop>
- David Glick <davidglick --AT-- onenw --DOT-- org> 
- Jesse Snyder <jesses --AT-- npowerseattle --DOT-- org>

With special PloneFormGen guest star:

- Steve McMahon <steve@dcn.org> 

Jesse Snyder and NPower Seattle for the foundation of code that has become
Salesforce Base Connector
 
Simon Fell for providing the beatbox Python wrapper to the Salesforce.com API
 
Salesforce.com Foundation and Enfold Systems for their gift and work on 
beatbox (see: 
http://gokubi.com/archives/onenorthwest-gets-grant-from-salesforcecom-to-integrate-with-plone)

See the CHANGES.txt file for the growing list of people who helped
with particular features or bugs.


License
=======

Distributed under the GPL.

See LICENSE.txt and LICENSE.GPL for details.


Overview
========

The Salesforce-PloneFormGen adapter provides the ability to create, read and
update in a Salesforce.com database via a PloneFormGen form.

Using the wonderful foundation that is provided by `PloneFormGen`_ (and Plone for
that matter), the task of creating a form that collects and validates some
desired information is no longer a task that requires developer intervention,
but can be done by the content editor with a decent grasp of the Plone user
interface.  Having this data inside the CMS or emailed is only of limited use
however.

.. _PloneFormGen: http://plone.org/products/ploneformgen

Salesforce.com provides an extensible, powerful platform from which
to do Customer Relationship Management (CRM) tasks ranging from sales,
marketing, nonprofit constituent organizing, and customer service. The
Salesforce PFG Adapter allows the pragmatic joining of a best of breed CMS
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

Usage
=====

Connecting a PloneFormGen form to Salesforce is accomplished by adding a
"Salesforce Adapter" to a PloneFormGen form folder.  Typically the site editor
responsible setting up the form will:

 1. Create a PloneFormGen form with the necessary fields.
 2. Add a Salesforce Adapter to the form via Plone's add menu.
 3. Configure the adapter by selecting:

   * the type of Salesforce.com object the adapter should create or update
   * the "field mapping" that specifies the correspondence between fields in
     the form and fields in Salesforce.
   * whether the adapter should create a new object, or edit an existing one
     found by matching some expression.


Mapping Form Fields
-------------------

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


Preset Values
-------------

Sometimes you want every object created by a particular form to have the same
value for a particular field.  For instance, you might want to set the "Lead
Source" field of a Lead to "Web".  This can be accomplished using the "Preset
Field Values" setting.

In the left column, enter the value you want to store in the field.  (e.g. "Web")

In the right column, select the field in which the value should be stored. (e.g.
Lead Source)

If you need a more complicated expression in order to determine the value, you
could instead create a hidden form field, edit its default value override
expression, and map it using the form field mapping setting.


Chained Adapters
----------------

Salesforce-PloneFormGen adapters can be used to create multiple related
objects from a single form.  e.g. creating a Contact linked to an Account::

 -----------                -------------
 | Account |                | Contact   |
 -----------                -------------
 | Id      | -------------> | AccountId |
 | Name    |                | LastName  |
 -----------                -------------

To create this link, the 'AccountId' external key of the Contact object needs
to be set to the Id of the Account it should be associated with.  This can be
accomplished with Salesforce-PloneFormGen by creating one Salesforce Adapter
for the Account and one Salesforce adapter for the Contact, and then setting
the "Configure Parent Adapters" setting of the contact adapter so that it maps
the Id from the account adapter to the AccountId field of the Contact.

In this setup, the Account adapter will be run before the Contact adapter
regardless of ordering within the PloneFormGen form.  In this sense, 
the "Contact" adapter is *dependent upon* the result from the "Account" 
adapter. Upon creation of the "Account" within Salesforce.com an Id like 
"01r600123009QiJ", will be returned along with the API response.  This will 
then be saved and used by the Contact record which is created subsequently.
Care is taken via validation that "circularly dependent" adapters can not be
accidentally configured.


Updating Existing Objects
-------------------------

By default a Salesforce Adapter will always create new objects in Salesforce.
It is also possible to use them in an "update" mode in which the form will
find an object in Salesforce matching a given expression, load the form with
values from that object, and then save changes to the object when the form
is submitted.

This can be set up using the following settings on the "create vs. update"
section of the Salesforce Adapter configuration:

 Creation Mode
   Set to 'create' to always create a new object (default).  Set to 'update'
   to try to find and update an existing object.
 
 Expression to match existing object for update
   Enter a TALES expression which evaluates to a SOQL WHERE clause that returns
   the Salesforce.com object you want to update.  If you interpolate input from
   the request into single quotes in the SOQL statement, be sure to escape it
   using the sanitize_soql method. For example, the following could be used to
   match objects whose Username__c field equals a value passed in the 'username'
   parameter of the request::
    
    python:"Username__c='" + sanitize_soql(request.form.get('username', '')) + "'"

 Behavior if no existing object found
   Determines the desired behavior in case no object was found matching the
   given expression.  If set to 'Fail with an error message.', an error will be
   displayed (default).  If set to 'create', a new object will be created instead.

NB: The adapters accomplish prepopulation of form fields by modifying the
default value override for all mapped fields.  Default value overrides that
have already been customized will be left intact.

NB: Salesforce is queried using the match expression only when the form is
first loaded; at which point the Salesforce Id of the object that was found
is stored in a Zope session.  This ensures that changes are always saved to
the same object that was loaded, even if other changes happened to the database
in the meantime.  However, it does mean that if the user's session is destroyed
(such as during a Zope restart), then submitting the form will fail.

When using chained adapters, some adapters could be used in update mode while
others are used in create mode.  For example, this could be used to add a new
Opportunity associated with an existing Account.  Currently this requires
setting up at least one form field mapping for each adapter to work properly.
In addition, the behavior if a single field is mapped by multiple adapters is
not yet defined.

When Things Break
-----------------

Sometimes temporary errors may occur when trying to write to Salesforce (for
example, if Salesforce is undergoing maintenance).  If this occurs when trying
to process an adapter whose "creation mode" is set to "create," a fallback
mechanism will try to record the information in an alternate way.

If any savedata adapter is present (whether or not it is enabled),
the data will be saved using it.  In addition, regardless of whether a savedata
adapter is present, an e-mail will be sent to the e-mail address configured in
the Plone site's e-mail settings, to report that saving to Salesforce failed.
A site administrator can then take action based on this e-mail as necessary.
The end user is directed to the normal form thank you page, so that they are
not inconvenienced by the error writing to Salesforce.

There is no fallback mechanism for adapters in update mode, since this mode
requires reading from Salesforce as well.


Dependencies
============

Tested with Plone 2.5.x, 3.x, and 4.0a2.

Depends upon the beatbox library >= 16.0, which is a Python wrapper to the
Salesforce.com API.  You must have a Salesforce.com account that provides API
access.

SalesforceBaseConnector >= 1.2b1. See 
http://plone.org/products/salesforcebaseconnector

PloneFormGen and related dependencies.

DataGridField >= 1.6.x.

 
Installation
============

Typical for a Zope/Plone product:

* Add the Products.salesforcepfgadapter egg to your buildout.  (Or on a
  non-buildout installation, install the product and dependencies as
  appropriate.)

* Rerun buildout and restart Zope.

* If you don't have a Salesforce Base Connector (portal_salesforcebaseconnector)
  in the root of your site yet, add one via the ZMI add menu, and configure its
  login credentials.

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


Further Information
===================

Product home is http://plone.org/products/salesforcepfgadapter. A 
`documentation area`_ and `issue tracker`_ are available at the linked 
locations.

.. _documentation area: http://plone.org/documentation/kb/integrating-plone-with-salesforce
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


Credits
=======

The Plone & Salesforce crew in Seattle and Portland:

- Jon Baldivieso <jonb --AT-- groundwire --DOT-- org>
- Andrew Burkhalter <andrewburkhalter --AT-- gmail --DOT-- com>
- Brian Gershon <briang --AT-- webcollective --DOT-- coop>
- David Glick <davidglick --AT-- groundwire --DOT-- org> 
- Jesse Snyder <jesses --AT-- npowerseattle --DOT-- org>
- Alex Tokar <alext --AT-- webcollective --DOT-- coop>

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


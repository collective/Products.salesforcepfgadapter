from setuptools import setup, find_packages
import os

version = open(os.path.join("Products", "salesforcepfgadapter", "version.txt")).read().strip()

setup(name='Products.salesforcepfgadapter',
      version=version,
      description="PloneFormGen adapter allowing for creation of arbitrary Salesforce.com \
        records based on data collected from a web form",
      long_description=open(os.path.join("Products", "salesforcepfgadapter", "README.txt")).read(),
      # Get more strings from http://www.python.org/pypi?%3Aaction=list_classifiers
      classifiers=[
        "Programming Language :: Python",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Framework :: Zope2",
        "Framework :: Plone",
        ],
      keywords='Zope CMF Plone Salesforce.com CRM PloneFormGen forms integration',
      author='Plone/Salesforce Integration Group',
      author_email='plonesf@googlegroups.com',
      url='http://groups.google.com/group/plonesf',
      license='GPL',
      packages=find_packages(exclude=['ez_setup']),
      namespace_packages=['Products'],
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          'setuptools',
          'beatbox>=0.9,<=1.0dev',
          'Products.salesforcebaseconnector',
          'Products.TALESField',
          'Products.TemplateFields',
          'Products.PythonField',
          'Products.PloneFormGen',
          'Products.DataGridField',
          # -*- Extra requirements: -*-
      ],
      entry_points="""
      # -*- Entry points: -*-
      """,
      )

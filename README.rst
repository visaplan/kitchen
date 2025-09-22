.. image:: https://travis-ci.org/visaplan/kitchen.svg?branch=master
       :target: https://travis-ci.org/visaplan/kitchen
.. This README is meant for consumption by humans and pypi. Pypi can render rst files so please do not use Sphinx features.
   If you want to learn more about writing documentation, please check out: http://docs.plone.org/about/documentation_styleguide.html
   This text does not appear on pypi or github. It is a comment.

================
visaplan.kitchen
================

This package tackles "soup", i.e. trees which are created by the well-known
beautifulsoup4_ package from parsed HTML or XML sources.
It might be possible to accomplish the same by using lxml_ directly,
but it might have been more difficult, and thus it is left to another
package.

Features
========

- ``spoons`` module, for tackling "soup", e.g.

  - ``has_any_class`` (a filter function to check for one of the given classes)

- ``forks`` module
  (named mainly for historical reasons; for poking around in the soup), e.g.
  ``extract_linktext``, ``convert_dimension_styles``

- ``ids`` module, for creation of new ids for HTML elements

  - ``id_factory``::

        new_id = id_factory(...)
        id = new_id(prefix)


Tests remark
============

The modules are documented and tested by doctests.
However, they currently don't fully work because of import problems;
see the `issue tracker`_.

Help is appreciated.

Examples
========

This add-on can be seen in action at the following sites:

- https://www.unitracc.de
- https://www.unitracc.com


Documentation
=============

For now, the functions are documented by doctests.


Installation
============

Install visaplan.kitchen by adding it to your buildout::

    [buildout]

    ...

    eggs =
        visaplan.kitchen


and then running ``bin/buildout``


Contribute
==========

- Issue Tracker: https://github.com/visaplan/kitchen/issues
- Source Code: https://github.com/visaplan/kitchen


Support
=======

If you are having issues, please let us know;
please use the `issue tracker`_ mentioned above.


License
=======

The project is licensed under the GPLv2.

.. _`issue tracker`: https://github.com/visaplan/kitchen/issues
.. _`beautifulsoup4`: https://pypi.org/project/beautifulsoup4

.. vim: tw=79 cc=+1 sw=4 sts=4 si et

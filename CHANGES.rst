Changelog
=========


1.1.0 (unreleased)
------------------

Improvements:

- Improved Python 3 compatibility

New Features:

- `.spoons.swap_classes`, supporting both `add` and `remove` options,
  and by default removing an empty `class` attribute

Requirements:

- Support *(but don't require yet)* visaplan.tools_ v1.4+

Miscellaneous:

- Zope/Plone entry point and ``configure.zcml`` removed,
  which didn't do anything interesting

[tobiasherp]


1.0.5 (2024-04-09)
------------------

New Features:

- .extract.head supports the `verbose` option to
  aid processing of multiple fields; code example included.

Improvements:

- Added a doctest for .extract.head: yes, we accept text/plain as well.

Miscellaneous:

- .extract._head_kwargs: when injecting the fuzz default value, we ignore
  a words restriction now, which may be given additionally;
  only the chars restriction is needed.

[tobiasherp]


1.0.4 (2023-12-21)
------------------

Bugfixes:

- .spoons.stripped_soup raises an IndexError when called with empty content.

[tobiasherp]


1.0.3 (2022-09-20)
------------------

New Features:

- New function .spoons.generate_image_infos

[tobiasherp]


1.0.2 (2021-10-27)
------------------

Improvements:

- Imports sorted by isort_

New Features:

- New ``extract`` module to create extracts of HTML text
  (e.g. a `head`, containing the first NN visible characters)

Requirements:

- lxml_ v3.7.0+ (`collect_ids` argument)
- six_ explicitly required
- visaplan.tools_ v1.3.7+

[tobiasherp]


1.0.1 (2020-02-25)
------------------

- Python_ 3 compatibility (``python-modernize``)
  [tobiasherp]


1.0 (2018-09-17)
----------------

- Initial release.
  [tobiasherp]

.. _isort: https://pypi.org/project/isort
.. _lxml: https://lxml.de
.. _Python: https://www.python.org
.. _six: https://pypi.org/project/six
.. _visaplan.tools: https://pypi.org/project/visaplan.tools

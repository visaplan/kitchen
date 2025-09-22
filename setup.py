# -*- coding: utf-8 -*- vim: et ts=8 sw=4 sts=4 si tw=79 cc=+1
"""Installer for the visaplan.kitchen package."""
# Python compatibility:
from __future__ import absolute_import, print_function

# Setup tools:
from setuptools import find_packages, setup

# Standard library:
from os.path import isfile
from sys import version_info, argv

package_name = 'visaplan.kitchen'

# -------------------------------------------- [ get the version ... [
def read_version(fn, sfn):
    main = open(fn).read().strip()
    if sfn is not None and isfile(sfn):
        suffix = valid_suffix(open(sfn).read().strip())
    else:
        suffix = ''
    return main + suffix
    # ... get the version ...
def valid_suffix(suffix):
    """
    Enforce our suffix convention
    """
    suffix = suffix.strip()
    if not suffix:
        return suffix
    allowed = set('edv.0123456789rcpost')
    disallowed = set(suffix).difference(allowed)
    if disallowed:
        disallowed = ''.join(sorted(disallowed))
        raise ValueError('Version suffix contains disallowed characters'
                         ' (%(disallowed)s)'
                         % locals())
    chunks = suffix.split('.')
    chunk = chunks.pop(0)
    if chunk and not chunk.startswith('rc') and not chunk.startswith('post'):
        raise ValueError('Version suffix must start with "."'
                         ' (%(suffix)r)'
                         % locals())
    if not chunks:
        raise ValueError('Version suffix is too short'
                         ' (%(suffix)r)'
                         % locals())
    for chunk in chunks:
        if not chunk:
            raise ValueError('Empty chunk %(chunk)r in '
                             'version suffix %(suffix)r'
                             % locals())
        char = chunk[0]
        if char in '0123456789':
            raise ValueError('Chunk %(chunk)r of version suffix %(suffix)r'
                             ' starts with a digit'
                             % locals())
        char = chunk[-1]
        if char not in '0123456789':
            raise ValueError('Chunk %(chunk)r of version suffix %(suffix)r'
                             ' doesn\'t end with a digit'
                             ' (normalization would append a "0")'
                             % locals())
    return suffix  # ... valid_suffix
    # ... get the version ...
    # ... get the version ...
VERSION = read_version('VERSION',
                       'VERSION_SUFFIX')
# -------------------------------------------- ] ... get the version ]


# ------------------------------------------- [ for setup_kwargs ... [
long_description = '\n\n'.join([
    open('README.rst').read(),
    open('TODO.rst').read(),
    open('CHANGES.rst').read(),
])

# see as well --> src/visaplan/kitchen/configure.zcml:
exclude_subpackages = (
        )
exclude_packages = []
for subp in exclude_subpackages:
    exclude_packages.extend([package_name + '.' + subp,
                             package_name + '.' + subp + '.*',
                             ])
packages = find_packages(
            'src',
            exclude=exclude_packages)

def github_urls(package, **kwargs):
    pop = kwargs.pop
    pkg_list = package.split('.')
    res = {}
    readthedocs = pop('readthedocs', False)
    if readthedocs:
        if readthedocs in (1, True):
            readthedocs = ''.join(pkg_list)
        res['Documentation'] = \
            'https://%(readthedocs)s.readthedocs.io' % locals()
        assert 'docs' not in kwargs
    else:
        docs = pop('docs', None)
        if docs is None:
            res['Documentation'] = 'https://pypi.org/project/%(package)s' \
                                   % locals()
        elif docs:
            res['Documentation'] = docs
    if not pop('github', 1):
        assert not kwargs
        return res
    pop_user = pop('pop_user', False)
    if pop_user:
        assert 'pick_user' not in kwargs
        assert 'user' not in kwargs
        user = pkg_list.pop(0)
        package = '.'.join(pkg_list)
    else:
        pick_user = pop('pick_user', 'user' not in kwargs)
        given_user = pop('user', None)
        if pick_user:
            user = pkg_list[0]
            if given_user is not None and given_user != user:
                raise ValueError('given user %(given_user)r mismatches '
                                 'user picked from package %(user)r!'
                                 % locals())
        elif given_user is not None:
            user = given_user
        else:
            raise ValueError('no user given nor picked!')
    if pop('travis', False):  # reqires github to be trueish
        res.update({  # CHECKME: is there a de-facto standard key for this?
            'Tests': 'https://travis-ci.org/%(user)s/%(package)s' % locals()
            })
    base = 'https://github.com/%(user)s/%(package)s' % locals()
    res.update({
        'Source': base,
        'Tracker': base + '/issues',
        })
    return res
project_urls = github_urls(package_name,
                           travis=True,
                           pop_user=1)  # or pick_user=1, or github=0
# ------------------------------------------- ] ... for setup_kwargs ]

def at_most_installing(args):
    """
    No non-installing command here

    We don't recommend to combine installing and non-installing commands;
    however, if the setup is called with some installing command *only*,
    we can be more picky about what to accept.
    """
    if not args:
        return True
    for a in args:
        if a.startswith('-'):
            continue
        if a not in ('install', 'develop'):
            return False
    return True

setup_kwargs = dict(
    name=package_name,
    version=VERSION,
    description="A kitchen for (beautiful) soup",
    long_description=long_description,
    long_description_content_type='text/x-rst',
    # Get more from https://pypi.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        "Environment :: Web Environment",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Intended Audience :: Developers",
        "Natural Language :: German",
        "Operating System :: OS Independent",
        "License :: OSI Approved :: GNU General Public License v2 (GPLv2)",
        "Topic :: Text Processing :: Markup :: HTML",
    ],
    # keywords='Python Plone',
    author='Tobias Herp',
    author_email='tobias.herp@visaplan.com',
    project_urls=project_urls,
    license='GPL version 2',
    packages=packages,
    namespace_packages=[
        'visaplan',
        ],
    package_dir={'': 'src'},
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        'setuptools',
        'six',
        # -*- Extra requirements: -*-
        'beautifulsoup4 >=4.3.2; python_version >="3"',  # KGS of Plone 4.3.3
        # the last bs4 version known to support Python 2.7 is 4.9.3:
        'beautifulsoup4 >=4.3.2, <4.10; python_version <"3"',
        'lxml >=3.7.0',  # 2.1: parser argument; 3.7.0: collect_ids
        'visaplan.tools >=1.3.7',  # .words.head(..., return_tuple)
    ],
    extras_require={
        'test': [
            'plone.app.testing',
            # plone.app.robotframework 1.2.0 requires plone.testing 4.0.11; 
            # plone.app.robotframework 1.3+ drops Plone 4.3 compatibility:
            'plone.testing',
            'plone.app.robotframework[debug]',
        ],
    },
)
if 0:
    from pprint import pprint
    del setup_kwargs['long_description']
    pprint(setup_kwargs)
    raise SystemExit(1)
setup(**setup_kwargs)

#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
from setuptools.command.test import test as TestCommand

try:
    from setuptools import setup, find_packages
except ImportError:
    from distutils.core import setup, find_packages

# To prevent importing about and thereby breaking the coverage info we use this
# exec hack
about = {}
with open('mt940/__about__.py') as fp:
    exec(fp.read(), about)


class PyTest(TestCommand):
    user_options = [('pytest-args=', 'a', 'Arguments to pass to pytest')]

    def initialize_options(self):
        TestCommand.initialize_options(self)
        self.pytest_args = ''

    def run_tests(self):
        import shlex
        # import here, cause outside the eggs aren't loaded
        import pytest
        errno = pytest.main(shlex.split(self.pytest_args))
        sys.exit(errno)


tests_require = [
    'pyyaml',
    'pytest',
    'pytest-cache',
    'pytest-cover',
    'pytest-flake8',
    'flake8',
]


if sys.argv[-1] == 'info':
    for k, v in about.items():
        print('%s: %s' % (k, v))
    sys.exit()

if __name__ == '__main__':
    with open('README.rst') as fh:
        try:
            import sphinx2rst
            readme = sphinx2rst.sphinx_to_rst(fh)
        except ImportError:
            readme = fh.read()

    try:
        import git
        try:
            repo = git.Repo('.')
        except git.exc.InvalidGitRepositoryError:
            raise ImportError()

        if repo.bare:
            raise ImportError()

        tags = [tag.tag for tag in repo.tags if tag.tag]
        tags = sorted(tags, key=lambda tag: tag.tagged_date, reverse=True)
        changes = [
            '',
            '',
            'Changelog',
            '---------',
        ]

        for tag in tags:
            version = tag.tag
            if version[0] != 'v':
                version = 'v' + version

            message = tag.message.split('\n')[0]
            changes.append(' * **%s** %s' % (version, message))

        changes = '\n'.join(changes)
    except ImportError:
        changes = ''

    setup(
        name=about['__package_name__'],
        version=about['__version__'],
        author=about['__author__'],
        author_email=about['__email__'],
        description=about['__description__'],
        url=about['__url__'],
        license=about['__license__'],
        keywords=about['__title__'],
        packages=find_packages(exclude=['docs']),
        long_description=readme + changes,
        include_package_data=True,
        tests_require=tests_require,
        setup_requires=[
            'setuptools>=39.1.0',
        ],
        zip_safe=False,
        cmdclass={'test': PyTest},
        extras_require={
            'docs': [
                'sphinx>=1.7.2',
                'GitPython>=2.1.9',
                'sphinx2rst',
            ],
            'tests': tests_require,
        },
        classifiers=[
            'Development Status :: 6 - Mature',
            'Intended Audience :: Developers',
            'License :: OSI Approved :: BSD License',
            'Natural Language :: English',
            'Programming Language :: Python :: 3',
            'Programming Language :: Python :: 3.7',
            'Programming Language :: Python :: 3.8',
            'Programming Language :: Python :: 3.9',
            'Programming Language :: Python :: 3.10',
            'Programming Language :: Python :: Implementation :: PyPy',
        ],
    )

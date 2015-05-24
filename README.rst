MT940 library for Python
==============================================================================

Introduction
------------------------------------------------------------------------------

.. image:: https://travis-ci.org/WoLpH/mt940.png?branch=master
    :alt: Test Status
    :target: https://travis-ci.org/WoLpH/mt940

.. image:: https://coveralls.io/repos/WoLpH/mt940/badge.png?branch=master
    :alt: Coverage Status
    :target: https://coveralls.io/r/WoLpH/mt940?branch=master

.. image:: https://landscape.io/github/WoLpH/mt940/master/landscape.png
   :target: https://landscape.io/github/WoLpH/mt940/master
   :alt: Code Health

A library to parse MT940 files and returns smart Python collections for
statistics and manipulation.

Links
-----

* Documentation
    - http://mt940.readthedocs.org/en/latest/
* Source
    - https://github.com/WoLpH/mt940
* Bug reports 
    - https://github.com/WoLpH/mt940/issues
* Package homepage
    - https://pypi.python.org/pypi/mt-940
* My blog
    - http://w.wol.ph/

Install
------------------------------------------------------------------------------

To install simply run:

::
       
    pip install mt-940

Example usage
------------------------------------------------------------------------------

::

    import mt940
    import pprint

    transactions = mt940.parse('tests/jejik/abnamro.sta')

    print 'Transactions:'
    print transactions
    pprint.pprint(transactions.data)

    print
    for transaction in transactions:
        print 'Transaction: ', transaction
        pprint.pprint(transaction.data)


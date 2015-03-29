MT940 library for Python
==============================================================================

Introduction
------------------------------------------------------------------------------

.. image:: https://travis-ci.org/WoLpH/mt940.png?branch=master
    :alt: Test Status
    :target: https://travis-ci.org/WoLpH/mt940

.. image:: https://landscape.io/github/WoLpH/django-statsd/master/landscape.png
   :target: https://landscape.io/github/WoLpH/django-statsd/master
   :alt: Code Health

A library to parse MT940 files and returns smart Python collections for
statistics and manipulation.

Install
------------------------------------------------------------------------------

To install simply run `pip install mt-940`.

Example usage
------------------------------------------------------------------------------

::

    import mt940
    with open('your_mt940_file.sta') as fh:
        transactions = mt940.parse(fh)
        for transaction in transactions:
            print 'transaction', transaction


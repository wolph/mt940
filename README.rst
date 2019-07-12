=====
MT940
=====


.. image:: https://travis-ci.org/WoLpH/mt940.svg?branch=master
    :alt: MT940 test status
    :target: https://travis-ci.org/WoLpH/mt940

.. image:: https://badge.fury.io/py/mt-940.svg
    :alt: MT940 Pypi version
    :target: https://pypi.python.org/pypi/mt-940

.. image:: https://coveralls.io/repos/WoLpH/mt940/badge.svg?branch=master
    :alt: MT940 code coverage
    :target: https://coveralls.io/r/WoLpH/mt940?branch=master

.. image:: https://img.shields.io/pypi/pyversions/mt-940.svg

``mt940`` - A library to parse MT940 files and returns smart Python collections
for statistics and manipulation.

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
    - http://wol.ph/

Install
-------

To install the latest release:

.. code-block:: bash

    pip install mt-940

Or if `pip` is not available:
    
.. code-block:: bash

    easy_install mt-940
   
To install the latest development release:

.. code-block:: bash

    git clone --branch develop https://github.com/WoLpH/mt940.git mt940
    cd ./mt940
    virtualenv .env
    source .env/bin/activate
    pip install -e .

To run the tests you can use the `py.test` command or just run `tox` to test
everything in all supported python versions.

Usage
-----

Basic parsing:

.. code-block:: python

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

Set opening / closing balance information on each transaction:

.. code-block:: python

   import mt940
   import pprint

   mt940.tags.BalanceBase.scope = mt940.models.Transaction

   # The currency has to be set manually when setting the BalanceBase scope to Transaction.
   transactions = mt940.models.Transactions(processors=dict(
       pre_statement=[
           mt940.processors.add_currency_pre_processor('EUR'),
       ],
   ))

   with open('tests/jejik/abnamro.sta') as f:
       data = f.read()

   transactions.parse(data)

   for transaction in transactions:
       print 'Transaction: ', transaction
       pprint.pprint(transaction.data)

Simple json encoding:

.. code-block:: python

    import json
    import mt940


    transactions = mt940.parse('tests/jejik/abnamro.sta')

    print(json.dumps(transactions, indent=4, cls=mt940.JSONEncoder))

Contributing
------------

Help is greatly appreciated, just please remember to clone the **development**
branch and to run `tox` before creating pull requests.

Travis tests for `flake8` support and test coverage so it's always good to
check those before creating a pull request.

Development branch: https://github.com/WoLpH/mt940/tree/develop

To run the tests:

.. code-block:: shell

    pip install -r tests/requirements.txt
    py.test
    
Or to run the tests on all available Python versions:

.. code-block:: shell

    pip install tox
    tox

Info
----

==============  ==========================================================
Python support  Python 2.7, >= 3.3
Blog            http://wol.ph/
Source          https://github.com/WoLpH/mt940
Documentation   http://mt940.rtfd.org
Changelog       http://mt940.readthedocs.org/en/latest/history.html
API             http://mt940.readthedocs.org/en/latest/modules.html
Issues/roadmap  https://github.com/WoLpH/mt940/issues
Travis          http://travis-ci.org/WoLpH/mt940
Test coverage   https://coveralls.io/r/WoLpH/mt940
Pypi            https://pypi.python.org/pypi/mt-940
Ohloh           https://www.ohloh.net/p/mt-940
License         `BSD`_.
git repo        .. code-block:: bash

                    $ git clone https://github.com/WoLpH/mt940.git
install dev     .. code-block:: bash

                    $ git clone https://github.com/WoLpH/mt940.git mt940
                    $ cd ./mt940
                    $ virtualenv .env
                    $ source .env/bin/activate
                    $ pip install -e .
tests           .. code-block:: bash

                    $ py.test
==============  ==========================================================

MT940 standard description:
==============================================================================

https://www.db-bankline.deutsche-bank.com/download/MT940_Deutschland_Structure2002.pdf

Standards used/tested
==============================================================================

============== =========================================================
TEST OK        Credit Agricole weak :86: structure, https://firmabank.credit-ag ricole.pl/mt-front/help/en/10527.html
TEST OK        Millenium, https://www.bankmillennium.pl/documents/10184/112009/Opis__formatu__pliku_wyciagow__MT940v20120309_1216885.pdf
TEST OK        BNP PariBas, https://www.bgzbnpparibas.pl/_fileserver/item/1504995 (PL) https://www.bgzbnpparibas.pl/_fileserver/item/1504996 (EN)
TEST OK        PKO BP, http://www.pkobp.pl/media_files/26455bd3-6edb-417f-9c03-647e27cdc9c5.pdf/ http://www.pkobp.pl/media_files/9ee49e34-754d-451d-83fc-b8a8051f7e33.pdf
TEST OK        PEKAO SA, ftp://ftp.kamsoft.pl/pub/KS-FKW/Pomoce/MT940/PekaoBIZNES24.pdf
TEST OK        FORTIS, ftp://ftp.kamsoft.pl/pub/KS-FKW/Pomoce/MT940/Fortis.pdf
TEST OK        Santander (encoding!), (transaction_code 4n)
               https://static3.santander.pl/asset/P/r/z/Przewodnik-iBiznes24---Formaty-Plikow_91267.pdf
OK, NOT TESTED Alior, ftp://ftp.kamsoft.pl/pub/KS-FKW/Pomoce/MT940/Alior.pdf
OK, NOT TESTED BPH, ftp://ftp.kamsoft.pl/pub/KS-FKW/Pomoce/MT940/BPH_SAM2.pdf
OK, NOT TESTED BPH, ftp://ftp.kamsoft.pl/pub/KS-FKW/Pomoce/MT940/BPH_SAT.pdf
OK, NOT TESTED BPS (Bank Polskiej Spółdzielczości) ftp://ftp.kamsoft.pl/pub/KS-FKW/Pomoce/MT940/BPS_MC.pdf
OK, NOT TESTED ING, ftp://ftp.kamsoft.pl/pub/KS-FKW/Pomoce/MT940/ING.pdf
OK, NOT TESTED Krakowski Bank Spółdzielczy, ftp://ftp.kamsoft.pl/pub/KS-FKW/Pomoce/MT940/KBS.pdf
OK, NOT TESTED https://www.mbank.pl/pdf/firmy/inne/mt940-wyciagi-dzienne-i-miesieczne-w-czesci-detalicznej-mbanku.pdf

NOT TESTED:    DeutscheBank weak :86: structure ftp://ftp.kamsoft.pl/pub/KS-FKW /Pomoce/MT940/DeutscheBank.pdf
NOT TESTED:    weak :86: structure ftp://ftp.kamsoft.pl/pub/KS-FKW/Pomoce/MT940/GetinNobleBank.PDF
NOT TESTED:    weak :86: structure ftp://ftp.kamsoft.pl/pub/KS-FKW/Pomoce/MT940/BG%C5%BB.pdf
============== =========================================================

.. _BSD: http://opensource.org/licenses/BSD-3-Clause
.. _Documentation: http://mt940.readthedocs.org/en/latest/
.. _API: http://mt940.readthedocs.org/en/latest/modules.html

Choose compatibility options
============================

Some parsing corrections change the output of previously accepted input.
:class:`mt940.Options` keeps all ten switches ``False`` by default. Choose
individual switches after comparing your source files, or use
:meth:`mt940.options.Options.all` to enable every declared field.

Compare a reversal
------------------

Run ``uv run python -m examples.compatibility`` from the checkout:

.. literalinclude:: ../examples/compatibility.py
   :language: python

Its recorded output is:

.. literalinclude:: ../examples/output/compatibility.txt
   :language: text

The default amount for ``RC`` remains positive. Enabling ``reversal_sign``
makes it negative. ``Options.all()`` includes that switch, so the amount agrees
in this example. Agreement for one input does not establish that the other
switches have no effect on your bank's exports.

All ten switches
----------------

.. list-table:: Defaults and enabled effects
   :header-rows: 1
   :widths: 32 33 35

   * - Option
     - ``False`` behaviour
     - ``True`` effect and limit
   * - ``applicant_iban``
     - Structured ``?31`` contributes to ``applicant_name``.
     - Stores ``?31`` in ``applicant_iban``. ``?32`` and ``?33`` remain name
       fragments. The source can be an ordinary account number, not an IBAN.
   * - ``merge_keeps_values``
     - Incoming ``None`` can overwrite an existing transaction field.
     - Keeps existing transaction values when a later result supplies
       ``None``. Missing keys can still be added as ``None``. Statement
       metadata merging is unaffected.
   * - ``reversal_sign``
     - Only exact ``D`` negates an amount. ``RC`` remains positive for a
       positive input.
     - ``RC`` also negates. ``RD`` remains unchanged. Lowercase needs the
       separate case option.
   * - ``case_insensitive_marks``
     - Lowercase debit/reversal marks do not trigger sign handling.
     - Uses uppercase marks for signing. Source ``status`` is unchanged.
       Lowercase ``rc`` needs ``reversal_sign`` too.
   * - ``timezone_offset``
     - ``:13D:`` offset digits are treated as a minute count. ``+0100`` gives
       100 minutes.
     - Reads hours and minutes. ``+0100`` gives 60 minutes. This is a fixed
       offset, not a named timezone or daylight-saving rule.
   * - ``unbounded_details``
     - ``:86:`` capture is limited to nine chunks of at most 65 characters.
     - Captures details without that length cap. Structured post-processing
       can still transform or discard fields.
   * - ``non_swift_free_text``
     - Some unnumbered ``:NS:`` lines after content become paragraph separators.
     - Preserves non-blank free-text lines in ``non_swift_text``. Raw
       ``non_swift`` is retained in both modes.
   * - ``floor_limit_blank_mark``
     - A space mark on ``:34F:`` creates ``' _floor_limit'``, which is not a
       recognised collection currency source.
     - Treats the space as absent and creates debit and credit floor limits.
       Their currency becomes eligible for collection currency lookup.
   * - ``strip_bom``
     - A leading U+FEFF prevents the following initial ``:20:`` from matching.
     - Removes one leading U+FEFF in the high-level source reader. Direct
       ``Transactions.parse`` does not apply it.
   * - ``gvc_leading_text``
     - A ``+`` in the first four purpose characters can act as an empty-key
       terminator and discard early text.
     - Disables that early terminator interpretation. Free text before a
       genuine GVC keyword is still discarded.

Configuration is immutable
--------------------------

An options object is a frozen, slotted dataclass. Share it between collections,
and use ``dataclasses.replace`` when a copy needs one changed field:

.. doctest::

   >>> from dataclasses import replace
   >>> import mt940
   >>> selected: mt940.Options = mt940.Options(reversal_sign=True)
   >>> extended: mt940.Options = replace(selected, case_insensitive_marks=True)
   >>> selected.case_insensitive_marks, extended.case_insensitive_marks
   (False, True)
   >>> len(mt940.Options.names())
   10
   >>> all(getattr(mt940.Options.all(), name) for name in mt940.Options.names())
   True

``Options.names()`` returns dataclass field names in declaration order.
``Options.all()`` passes every name to the called class's constructor with
value ``True``. A dataclass subclass works only if its constructor accepts all
declared fields. An added ``init=False`` field can therefore make ``all()``
raise ``TypeError``.

Migration checks
----------------

Parse representative fixtures with the selected settings and compare metadata,
transaction counts, amounts, references and purpose text. Keep default-mode
expectations when supporting existing integrations. The suite's ``.all.yml``
files record changed output under ``Options.all()``. See :doc:`testing`.

These switches do not repair every format issue. They do not split ``:28C:``
pages, retain every intermediate balance, validate reconciliation, give bare
``:90:`` a status, or guarantee one transaction per ``:61:`` with a missing ID.
They also do not change the active decimal context used during debit negation.

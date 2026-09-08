Trace the parser pipeline
=========================

When a field differs from the source, follow the value through each parser
stage. The high-level functions handle source reading first. The collection
then recognises tags, runs transformations and stores their results.

.. container:: pipeline

   1. **Decode**: load a path, handle, descriptor, text or bytes. Decode bytes
      and optionally remove the leading BOM.
   2. **Recognise**: normalise lines and find registered tag markers.
   3. **Preprocess**: match a tag's named groups and run ordered pre-processors.
   4. **Convert**: call the tag to construct dates, amounts, balances or fields.
   5. **Postprocess**: run ordered callbacks over the converted result.
   6. **Route**: merge into statement metadata or a transaction according to
      tag class, configured boundaries and scope.

Source reading and recognition
------------------------------

:func:`mt940.parser._load` dispatches sources, while
:func:`mt940.parser._decode` tries the preferred encoding, UTF-8 and CP852.
:func:`mt940.parser._read` combines them and applies ``strip_bom``.
:func:`mt940.parser._new_transactions` constructs the collection. When options
are omitted, it omits that keyword to preserve compatibility with older
collection subclasses lacking an ``options`` parameter.

:meth:`mt940.models.Transactions.parse` removes trailing whitespace, carriage
returns, empty lines and standalone ``-`` lines. Registered markers at line
starts delimit values. :meth:`mt940.models.Transactions.normalize_tag_id`
turns numeric IDs into integers. The sanitiser
:meth:`mt940.models.Transactions.sanitize_tag_id_matches` filters recognised
matches before values are sliced.

An unknown marker is not a delimiter. Its text can remain part of the previous
known tag's value, where it may be retained, ignored by a permissive pattern or
cause a parse error. Register a custom tag when its presence should delimit
other fields. Regex matching is not whole-file format validation.

Conversion and storage
----------------------

:meth:`mt940.models.Transactions._process_match` selects a full suffixed ID
before its numeric base. :meth:`mt940.tags.Tag.parse` captures named groups.
Each pre-processor replaces the dictionary passed to the next callback.
Calling the tag creates model values, then each post-processor replaces the
result passed onward. The current result is stored only after these callbacks.
See :class:`mt940._types.PreProcessor` and
:class:`mt940._types.PostProcessor` for their protocols.

Storage precedence is statement-tag grouping, extra transaction boundaries,
transaction scope when a current transaction exists, then statement scope.
:meth:`mt940.models.Transactions._process_statement_tag` fills a trailing
transaction whose ``id`` is missing or false, otherwise appending a new one.
Dual scope routes to one location as explained in :doc:`customising`.

Statement metadata uses dictionary update, so the last value under a key wins.
:meth:`mt940.models.Transactions._update_transaction` handles later transaction
fields differently. If both values expose ``strip``, it appends the stripped
incoming value after a newline. Other values replace the old value, except
that ``merge_keeps_values`` preserves existing fields against incoming
``None``. This preservation does not apply to statement metadata.

The details processor uses :func:`mt940.processors._parse_segments`,
:func:`mt940.processors._process_segments` and
:func:`mt940.processors._join_result` to collect and join structured fields.
:func:`mt940.processors._parse_mt940_gvcodes` handles purpose keywords.
These private helpers are documented for diagnosis, but application extensions
should normally use the public tags and processor slots.

Currency and time order
-----------------------

``Transactions.currency`` checks the first non-``None`` eligible metadata
value in this order: final opening, opening, intermediate opening, available,
forward available, final closing, closing and intermediate closing balances,
then credit and debit floor limits. It uses that value's ``currency`` or its
nested ``amount.currency``. An unusable earlier value can give ``None`` without
falling through to a later balance.

A ``:61:`` amount uses currency available when that tag runs. A closing balance
encountered later does not backfill earlier transactions. An explicitly
supplied ``currency=None`` also prevents the statement tag's missing-key
fallback. Supply currency with
:func:`mt940.processors.add_currency_pre_processor` when a bank's tag order
requires it.

State, sharing and pickle
-------------------------

Repeated ``Transactions.parse`` calls reuse the existing dictionaries and
transaction list. Parsing is not atomic: a later exception leaves earlier
results and callback mutations in place. Construct a fresh collection for an
unrelated input or when retrying after failure.

Collection constructors copy tag and processor mappings shallowly. Tag
instances and callback lists remain shared. ``parse_statements`` constructs
fresh collections, but supplied tag objects and processor lists are still
shared across those collections. Build new lists and local tag subclasses for
isolated configuration. Options can be shared because they are immutable.

:meth:`mt940.models.Transactions.__getstate__` drops the processor mapping from
pickle state. :meth:`mt940.models.Transactions.__setstate__` restores default
processor slots and supplies disabled options and empty transaction boundaries
when absent from older state. Saved tags, data and transactions are retained.
Custom callback closures therefore do not survive a pickle round trip.
Reapply custom processor configuration after loading trusted state. Never load
pickle data from an untrusted source.

For portable data exchange, :doc:`json` explains the encoder's ordinary JSON
shape and its lack of model reconstruction.

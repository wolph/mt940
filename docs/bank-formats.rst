Bank formats and field reference
================================

A bank's MT940 export can depart from another bank's format even when both use
the same tag IDs. Begin with the default parser and compare the resulting
fields with the source. Add a tag override or processor for the specific
variant you can reproduce.

What the fixtures establish
---------------------------

The regression suite organises fixtures under ``mt940_tests/ASNB``,
``betterplace``, ``citi``, ``cmxl``, ``jejik``, ``mBank``, ``sberbank`` and
``self-provided``, with targeted cases under ``test_issues``. Their expected
outputs establish behaviour for those files in default and enabled-option
modes. Directory names are provenance, not a guarantee covering a bank's
current products, accounts or export settings.

:class:`mt940.tags.StatementASNB` adapts ASN's statement-line format.
:class:`mt940.tags.StatementGLS` permits longer customer references used by
GLS/Atruvia variants. They are explicit replacements for tag ``61``, not
automatically selected by the account identifier. Register them as described
in :doc:`customising`.

The examples in these guides use synthetic data. For a new bank report, reduce
the failure to a synthetic fixture that preserves tag order, separators,
encoding and relevant lengths. Remove customer data before sharing it.
:doc:`testing` explains how fixture expectations are checked.

Built-in tag IDs, slugs and output
----------------------------------

A full suffixed ID is tried before its numeric base ID. This is why ``13D``,
``28C`` and ``34F`` use parsers registered under ``13``, ``28`` and ``34``.
Slugs determine processor slot names. In this table, *statement* means the
collection's ``data``, and *transaction* means the current transaction's
``data``.

.. list-table:: Built-in tag routing
   :header-rows: 1
   :widths: 14 30 16 40

   * - Input ID
     - Slug
     - Scope
     - Output fields
   * - ``13``, ``13D``
     - ``date_time_indication``
     - statement
     - ``date`` as ``DateTime``
   * - ``20``
     - ``transaction_reference_number``
     - statement
     - ``transaction_reference``
   * - ``21``
     - ``related_reference``
     - statement
     - ``related_reference``
   * - ``25``
     - ``account_identification``
     - statement
     - ``account_identification``
   * - ``28``, ``28C``
     - ``statement_number``
     - statement
     - ``statement_number``, ``sequence_number``
   * - ``34``, ``34F``
     - ``floor_limit_indicator``
     - statement
     - ``d_floor_limit`` and/or ``c_floor_limit`` as ``Amount``. A legacy space
       mark produces ``' _floor_limit'``.
   * - ``60``
     - ``opening_balance``
     - statement
     - ``opening_balance`` as ``Balance``
   * - ``60F``
     - ``final_opening_balance``
     - statement
     - ``final_opening_balance``
   * - ``60M``
     - ``intermediate_opening_balance``
     - statement
     - ``intermediate_opening_balance``
   * - ``61``
     - ``statement``
     - transaction
     - Amount, dates, status, type ID and references. See :doc:`data-model`.
   * - ``62``
     - ``closing_balance``
     - statement
     - ``closing_balance`` as ``Balance``
   * - ``62F``
     - ``final_closing_balance``
     - statement
     - ``final_closing_balance``
   * - ``62M``
     - ``intermediate_closing_balance``
     - statement
     - ``intermediate_closing_balance``
   * - ``64``
     - ``available_balance``
     - statement
     - ``available_balance``
   * - ``65``
     - ``forward_available_balance``
     - statement
     - ``forward_available_balance``
   * - ``86``
     - ``transaction_details``
     - transaction
     - ``transaction_details`` for plain text, mapped fields for structured
       text after the default post-processor.
   * - ``NS``
     - ``non_swift``
     - dual
     - ``non_swift``, ``non_swift_text``, ``non_swift_<two-digit ID>``.
       Routes to the current transaction, otherwise the statement.
   * - ``90D``
     - ``sum_debit_entries``
     - statement
     - ``sum_debit_entries`` as ``SumAmount``
   * - ``90C``
     - ``sum_credit_entries``
     - statement
     - ``sum_credit_entries`` as ``SumAmount``
   * - ``90``
     - ``sum_entries``
     - statement
     - The registered base class lacks ``status`` and raises ``AttributeError``
       on conversion. Use ``90D`` or ``90C``.

For debit and credit summaries, ``SumAmount.number`` remains the captured
string, including an empty string when omitted. Convert and validate the count
in your application if you require an integer. Its historical annotation does
not change that runtime behaviour.

Structured ``:86:`` fields
--------------------------

The default post-processor recognises structured text only when the joined
details begin with three digits, ``?`` and two digits, for example
``105?00TRANSFER?20Invoice``. It removes the raw ``transaction_details`` key
and emits the mapped fields. Missing mapped content becomes ``None``.

.. list-table:: Structured subfields
   :header-rows: 1
   :widths: 25 35 40

   * - Subfield
     - Output key
     - Joining and compatibility
   * - Initial three digits
     - ``transaction_code``
     - Retained as text.
   * - ``?00``
     - ``posting_text``
     - Booking description.
   * - ``?10``
     - ``prima_nota``
     - Source reference.
   * - ``?20`` through ``?29``
     - ``purpose``
     - Purpose fragments are joined. Continuations remove a dangling
       `` BIC`` or `` IBAN`` label.
   * - ``?30``
     - ``applicant_bin``
     - Historical field spelling is retained.
   * - ``?31``
     - ``applicant_name`` by default
     - ``applicant_iban`` with ``Options.applicant_iban=True``.
   * - ``?32``, ``?33``
     - ``applicant_name``
     - Name fragments are joined.
   * - ``?34``
     - ``return_debit_notes``
     - Source text.
   * - ``?35``
     - ``recipient_name``
     - Source text.
   * - ``?60`` through ``?65``
     - ``additional_purpose``
     - Additional purpose fragments are joined.

Unknown subfields are ignored. Fragments join without inserted spaces by
default. Use
:data:`mt940.processors.transaction_details_post_processor_with_space`
when the bank's fragments need a separator. See
:data:`mt940.processors.DETAIL_KEYS` and
:data:`mt940.processors.DETAIL_KEYS_APPLICANT_IBAN` for the exact mappings.

GVC keywords inside purpose text
--------------------------------

Recognised GVC keywords are case-sensitive four-character codes followed by
``+``. The BIC keyword includes a trailing space (``"BIC "``). The default details processor also
decodes purpose content when it detects one of its configured keywords.

.. list-table:: GVC output keys
   :header-rows: 1
   :widths: 25 75

   * - Keyword
     - Output key
   * - Empty fallback or ``SVWZ``
     - ``purpose``
   * - ``IBAN``
     - ``gvc_applicant_iban``
   * - ``"BIC "``
     - ``gvc_applicant_bin``
   * - ``EREF``
     - ``end_to_end_reference``
   * - ``MREF``
     - ``additional_position_reference``
   * - ``CRED``
     - ``applicant_creditor_id``
   * - ``PURP``
     - ``purpose_code``
   * - ``MDAT``
     - ``additional_position_date``
   * - ``ABWA``
     - ``deviate_applicant``
   * - ``ABWE``
     - ``deviate_recipient``
   * - ``SQTP``
     - ``FRST_ONE_OFF_RECC``
   * - ``ORCR``
     - ``old_SEPA_CI``
   * - ``ORMR``
     - ``old_SEPA_additional_position_reference``
   * - ``DDAT``
     - ``settlement_tag``
   * - ``KREF``
     - ``customer_reference``
   * - ``DEBT``
     - ``debitor_identifier``
   * - ``COAM``
     - ``compensation_amount``
   * - ``OAMT``
     - ``original_amount``

These names reproduce :data:`mt940.processors.GVC_KEYS`, including historical
spelling and capitalisation. The parser emits all mapped GVC keys, using
``None`` for missing values. Values remain text even for names that contain
``amount`` or ``date``. The ``gvc_leading_text`` switch fixes an early ``+``
interpretation but still drops free text before a genuine keyword. Retain the
source if that text matters to your import.

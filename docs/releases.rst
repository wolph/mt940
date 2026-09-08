Verify a release
================

A release is more than a successful upload. It includes the version and release
notes, a pushed tag, registry distributions, a GitHub release and a stable
``master`` branch containing the tagged commit. This guide describes the checks
for an authorised release. Building the documentation does not publish one.

Prepare the tagged source
-------------------------

Start from a clean, reviewed development commit. Update the version metadata
and changelog or release notes for the new version together. Run the complete
test, type, lint, documentation, security and build checks. Confirm every Python
3.10 through 3.15 environment ran, and inspect the documentation exports.

Before tagging, build and validate the distributions locally:

.. code-block:: console

   uv run tox
   uv build
   uvx twine check --strict dist/*

Inspect the wheel and source archive contents. Confirm that version metadata,
licence, README rendering and ``py.typed`` are present, and that development
caches and planning documents are excluded. Install the built wheel into a
fresh environment and execute the self-contained README example there.

Use the project's release tag convention ``vX.Y.Z`` and verify the tag points
to the reviewed commit. Where signing is configured, verify its signature too.
The command examples below use ``vX.Y.Z`` as a placeholder for the actual tag.

What the publish workflow does
------------------------------

``.github/workflows/publish.yml`` runs on pushed ``v*`` tags. Its test job calls
the reusable CI workflow. The supported ``$/`` same-repository workflow syntax
keeps that reference attached to the same repository. The build job runs
``uv build`` and ``twine check --strict`` and uploads the distributions as a
workflow artefact.

The publish job requires both test and build jobs. It uses the ``pypi``
environment with an OIDC identity for PyPI Trusted Publishing and requests
attestations. Workflow defaults are read-only, and only the publish job gets
``id-token: write``. Release concurrency does not cancel a running publication.

That workflow publishes registry distributions. It does not create the GitHub
release or synchronise ``master``. Verify those steps separately.

Five-part verification
----------------------

.. list-table:: Required release checks
   :header-rows: 1
   :widths: 28 72

   * - Part
     - Verification
   * - Version and notes
     - The source, built metadata and release notes identify the same version.
       Notes describe the released change and compatibility effects.
   * - Pushed tag
     - The remote tag exists and resolves to the reviewed release commit.
       Verify the signature when signed.
   * - Registry publish
     - PyPI exposes the expected version, wheel and source archive. Check
       uploaded metadata, hashes and attestations against the build artefacts.
   * - GitHub release
     - A release exists for the already-pushed tag, with the intended notes,
       and is marked Latest when it is the new stable release.
   * - Stable branch
     - ``master`` contains the tagged commit and has been fast-forwarded as
       required by the release process.

Inspect current remote state before declaring the release complete:

.. code-block:: console

   git fetch origin --tags
   git tag --sort=-creatordate
   gh release list
   git rev-list --count origin/master..vX.Y.Z

The final command prints ``0`` when no tagged commits are missing from
``origin/master``. Also compare commit IDs when ``master`` is expected to equal
the tag exactly. A local tag list or a green upload job alone does not establish
remote branch and release state.

Complete missing release metadata
---------------------------------

For an authorised release whose tag is already pushed, extract that version's
notes to a file and create the missing GitHub release with:

.. code-block:: console

   gh release create vX.Y.Z --title vX.Y.Z --notes-file release-notes.txt --verify-tag

``--verify-tag`` refuses to invent a new tag. Match the established release
body format, then confirm the release appears in ``gh release list`` and has
the expected Latest status.

If ``master`` is stale and can fast-forward to the release, the authorised
update is:

.. code-block:: console

   git push origin 'vX.Y.Z^{commit}:master'

A normal push refuses a non-fast-forward update. Investigate divergence instead
of forcing it. If automating this step, use credentials allowed to update any
workflow files in the released commits. ``GITHUB_TOKEN`` cannot perform that
workflow-changing push. Keep credentials in the CI secret mechanism and grant
only the permissions required by the release operation.

Finally recheck the remote tag, published package, GitHub release, ``master``
commit and local working tree. Record the actual verification results in the
release handoff, including any external step still pending.

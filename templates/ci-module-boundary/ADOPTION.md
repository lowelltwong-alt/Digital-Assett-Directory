# CI Module Boundary Adoption

This template is a reviewed-patch input, not an installer. A repository owner
must declare stable module IDs, roots, owners, typed path edges, dependencies,
suites, workflow events, and temporary exceptions. DAD does not mutate enrolled
repositories from an audit or recommendation.

Keep the provider-neutral manifest authoritative. Provider workflow files are
adapters. Required checks must use an always-starting selector/aggregator so a
path-filtered skipped workflow cannot deadlock a pull request.

For a multi-repo Law Firm OS family, keep the reviewed cross-repo map in the
family authority repository and keep a local manifest and adoption decision in
every child repository.

## Exact reviewed-patch procedure

1. Copy `monorepo/module-boundaries.yaml` to `.ci/module-boundaries.yaml`, the
   schema to `schemas/ci-module-boundary.schema.json`, and only the applicable
   provider adapter. Law Firm OS families also copy and review
   `multi-repo-law-firm-os/family-module-boundaries.yaml` in the family
   authority repository.
2. Replace every placeholder with source-owner-reviewed IDs, owners, roots,
   typed paths, direct-dependent edges, suites, and provider workflow paths.
3. Make the DAD Python package available as a pinned CI development dependency,
   or invoke the reviewed central DAD checkout with its `src` directory on
   `PYTHONPATH`. Do not silently vendor or auto-update it.
4. Validate the head against the base manifest and then evaluate the exact
   merge-base name-status diff:

   ```powershell
   $env:PYTHONPATH='<DAD_ROOT>\src'
   python '<DAD_ROOT>\scripts\validate_ci_module_boundaries.py' --repo '<TARGET_REPO>' validate --provider github-actions --manifest .ci/module-boundaries.yaml --base-manifest '<BASE_MANIFEST>'
   python '<DAD_ROOT>\scripts\validate_ci_module_boundaries.py' --repo '<TARGET_REPO>' evaluate --manifest .ci/module-boundaries.yaml --changes-file '<NAME_STATUS_DIFF>'
   ```

5. Replay the DAD fixtures, inspect selected suite IDs, and make one
   always-starting aggregate status the required check. Keep conditional module
   jobs below it and keep full-system regression scheduled or manually
   dispatched.
6. Submit the manifest, provider adapter, required-check change, and dependency
   evidence as a human-reviewed patch. A DAD metadata audit never authorizes or
   applies this patch.

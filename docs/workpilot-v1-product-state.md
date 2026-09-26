# Block 12: explicit post-hire state

Product mode is workflow state, never Candidate evidence. Accepted outcomes alone
do not create or change mode. Legacy candidates default to SEARCH on reads without
creating a row. Existing application history/outcome repositories remain unchanged.

The authorized caller supplies the active candidate to HiredTransitionService.
An owned accepted outcome is required for post-hire choices. CAREER requires an
explicit return to SEARCH before searching. End subscription records intent and
its timestamp, retaining the current mode and all history. Changing search/career
mode does not implicitly withdraw a pending subscription-end request.

ConfirmedProductAccessService is a separate trusted server boundary, not a public
endpoint. It requires an authoritative access-decision reference. There is no
billing adapter/caller yet: do not connect the End subscription button to this
boundary and do not describe requests as billing cancellations. READ_ONLY cannot
be overridden by user mode choices. Future access restoration requires its own
authoritative integration, not a user-selectable mode bypass.

The additive create_product_state_schema initializer creates current state plus
append-only before/after events. Parent candidate locking serializes transitions
including initial creation on PostgreSQL and SQLite. Repeated identical actions
do not create extra events. PostgreSQL tables are server-only with RLS and role
revocation. No backfill, deletion, or mutation of historical evidence is performed.

KEEP existing history/outcome repositories; use this contract for product-mode
authority. Production UI wiring and enforcement across paid mutation entry points
are integration work: this block does not pretend a subscription/access provider
exists. Browser and real PostgreSQL validation remain required before activation.

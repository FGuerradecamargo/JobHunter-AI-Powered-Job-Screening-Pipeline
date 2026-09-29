# Membership V1 Foundation

Membership is the user-scoped commercial-access authority.

It is separate from:

- Candidate Product State
- Entitlements
- Usage
- prices
- billing providers
- UI

Existing users without a persisted Membership row resolve
to an implicit active Free membership.

Membership stores a current projection plus append-only
transition history.

CandidateProductState still contains legacy subscription
intent from the pre-Free architecture. That coupling is
left untouched until Membership and Entitlements are ready
to replace it safely.

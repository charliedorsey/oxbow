# Known seams

The v0.1 release candidate intentionally leaves these boundaries visible:

- no artifact can guarantee that a receiving model will interpret a handoff correctly;
- integrity and conformance do not establish factual truth;
- a detached signature establishes key possession, not identity unless the public key is trusted independently;
- a `.oxb.py` is executable source; trusted CLI inspection validates the embedded payload without authenticating arbitrary wrapper code;
- Witness validates structure/provenance declarations, not the truth of the account;
- Witness third-party handling is an explicit operator/drafter note, not an automated privacy/compliance system;
- FirstLight is an optional integration and is not required by Oxbow core;
- historical RSB1/Rosetta compatibility is reference evidence and has a larger attack surface than the locked public reader;
- the final v0.1 product gate is an outside-user trial, not another internal selftest.

The absence of hosted services, encryption, databases, dashboards, model APIs, and specialist codec competitions is deliberate for v0.1.

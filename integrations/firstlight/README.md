# Optional FirstLight integration seam

Oxbow core does not require FirstLight and does not ship a Room library.

A routing system may optionally inspect an Oxbow handoff and recommend which subset of context or tool should receive attention first. That recommendation remains advisory: Oxbow verification, reading, extraction, and wrapper generation must work with no router installed.

If a FirstLight integration is added later, it should declare which routing path produced a result. An embedding-backed path and a lexical fallback are different capabilities and must not be reported as equivalent.

No historical operator Rooms, user state, or personal routing fixtures belong in canonical Oxbow.

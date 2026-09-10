# Continuity boundary

Oxbow is designed for **continuity of work**, not continuity of model instance.

A fresh model may receive a highly coherent account of earlier work. That does not make it the model that performed the work, and it does not give it hidden state or memories it does not possess.

## What can travel

An Oxbow handoff can carry:

- source documents and artifacts;
- operator-authored working state;
- prior decisions and their provenance;
- open questions and unresolved overhang;
- tools or runnable artifacts chosen by the operator;
- Witness records from prior sessions;
- orientation and reading paths.

## What cannot travel

Oxbow does not carry:

- model identity;
- internal activations or hidden state;
- subjective experience;
- private memory unavailable in the files;
- certainty that the receiver will interpret the corpus correctly.

Useful shorthand:

> **The corpus is source. It is not memory.**

> **You may have the frame without the trajectory.**

A receiver should therefore say “the handoff records X” or “the prior record says Y” rather than “I remember X” when X exists only in the carried corpus.

## Why this is a product boundary

Counterfeit continuity creates practical errors. A receiver that treats a compact handoff as memory may:

- overstate confidence in old decisions;
- silently fill gaps in the historical trajectory;
- treat a prior model's inference as its own observation;
- blur operator-authored facts with later summaries;
- resist correction because the corpus feels familiar.

Oxbow's front doors deliberately name the boundary before the reader encounters the larger corpus.

## Verification does not erase the boundary

A perfect manifest can prove that the packaged bytes arrived intact. A valid signature can prove that those bytes were signed by the holder of a trusted key. Neither proves that the contents are true or that the receiving model lived the work.

**Carry the work, not the model.**

## Witness v2 lineage is still source, not memory

Witness v2 may declare basis and lineage relationships to earlier packets. Those links improve navigation and make cross-session interpretations catchable, but they do not change the continuity boundary.

A receiver may say:

- "this read cites packet `pkt_x`";
- "this packet declares that it corrects `pkt_y`";
- "the stream records a promoted working conclusion."

It should not turn those declarations into "I remember deciding this" or "I was the model that made that judgment."

Packet IDs establish addresses. The actual carried packet content is the source. A lineage edge is a declared relationship between records, not hidden trajectory.

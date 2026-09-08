# Oxbow history

This public history records the product lineage without carrying the private corpus or operator-specific material that produced it.

## The original job

The practical problem was simple: useful AI work often became most coherent near the end of a context window, exactly when the next conversation would have to start cold.

The first response was to ask the late-session model for a summary and hand that summary to the next instance.

That worked until the summary itself became a growing object.

## Plain text

The earliest durable handoff was essentially a text file containing successive summaries.

Plain text was easy to create and easy to paste. It also had weak structure. As it grew, readers could technically receive the whole file without reliably locating the few pieces that mattered for the current task.

## Compression

Compression reduced size but exposed a different failure: a shorter summary could be cleaner while being less faithful. The most important loss was often not a headline fact but a decision boundary, unresolved tension, caveat, or reason a prior path had been abandoned.

The job was not simply “make the previous conversation shorter.”

## Markdown and structured state

Markdown added navigable structure. Later experiments represented working state explicitly in structured data so durable facts, volatile state, decisions, and open questions did not have to be recovered from transcript prose every time.

That was the first important abstraction shift:

> Stop representing only what the previous conversation said; represent what the next reader needs in order to work.

## Purpose-built work environments

The next step was to specify environments for different classes of work rather than produce one universal summary. Those environments described intended user, governing purpose, source rules, transformation contracts, quality gates, and failure modes.

A second correction followed: **more structure is not automatically better.** Some exploratory work performed better with less framing. Structure had to earn its place against an observed failure.

## Routing

Once multiple environments existed, the system needed a way to decide what deserved attention first. Routing and advisory context-selection experiments followed.

The important product principle survived even when individual routing methods did not:

> What exists in the corpus is not the same as what deserves immediate attention.

## Rosetta

Rosetta became a large personal inheritance environment: corpus, orientation, verification, work environments, routing, tools, guided entry paths, and records of prior receiving failures.

Many local additions were sensible. Collectively, they also accumulated the history of the failures that caused them.

Rosetta was useful precisely because it grew through use. It was also difficult to generalize because some of its infrastructure was scar tissue from one long-running environment.

## Oxbow

Oxbow is the redesign after those lessons became legible.

The generalized product keeps the bones that repeatedly proved useful:

- orient before volume;
- verify before trust;
- carry source and working state without claiming memory;
- keep integrity separate from truth;
- route deeper only when useful;
- preserve append-only provenance where work is written back;
- let optional machinery remain optional;
- make the receiving interface inspectable;
- keep executable and inert artifacts visibly distinct.

It removes the requirement that a new user inherit the private corpus, personal operating environment, or historical research machinery that happened to produce those lessons.

> **Rosetta grew. Oxbow was designed.**

That sentence is not a claim that design means more machinery. Several of the most important improvements removed machinery, weakened a rule, or made “do not force a structure here” a valid outcome.

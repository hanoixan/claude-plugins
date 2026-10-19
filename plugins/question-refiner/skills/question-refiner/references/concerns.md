# Interview concern tags

The starting concerns for `skel/.interview-weights.md`. `interview.py` copies everything from the first `## C`
heading down when it creates that file. Annotators tag each choice with these tags; when none fits, they write
`NEW:<tag>` (lower case, digits and hyphens), and the agent maps it to a concern with `interview.py tag`.

Two pairs of the eighteen tags start merged, because they are close: `security` with `isolation`, and
`maintainability` with `ops-complexity`.

## C1 security
meaning: attackers cannot get in, and parts are kept apart so a breach stays contained.
tags: security, isolation

## C2 open source
meaning: the design can be published and built on, with no closed part.
tags: open-source

## C3 owner control
meaning: the owner decides, configures and can leave; no outside party holds the keys.
tags: owner-control

## C4 privacy
meaning: data about people stays with them and is shared only on purpose.
tags: privacy

## C5 user friction
meaning: how many steps, prompts or surprises a user meets.
tags: user-friction

## C6 platform reach
meaning: how many operating systems, devices and environments it runs on.
tags: platform-reach

## C7 maintenance and operations
meaning: the work of keeping it running, upgraded and understood over time.
tags: maintainability, ops-complexity

## C8 effort
meaning: how much work and time the choice takes to build.
tags: impl-effort

## C9 performance
meaning: speed, latency and resource use.
tags: performance

## C10 reliability
meaning: it keeps working, and keeps its data, when something fails.
tags: reliability

## C11 scalability
meaning: it holds up as users, data or load grow.
tags: scalability

## C12 interoperability
meaning: it works with the standards and tools around it.
tags: interoperability

## C13 flexibility
meaning: it can change direction later without a rewrite.
tags: flexibility

## C14 cost
meaning: the money spent to build and run it.
tags: cost

## C15 third-party dependency
meaning: how much it relies on outside services, libraries or vendors.
tags: third-party-dependency

## C16 testability
meaning: its behaviour can be checked automatically and in isolation.
tags: testability

# Concern catalog

The concerns `refiner.py domains add` copies into `.question-refiner/weights.md`: every concern any named domain
lists, once each, in this order. Annotators tag each choice with these tags; when none fits, they write `NEW:<tag>`
(lower case, digits and hyphens), and the agent maps it with `refiner.py tag`: to a concern already in the weights,
to a catalog concern with `--catalog`, or to a new one with `--new`.

Domains: software, infrastructure, product, fiction, nonfiction, research, planning.

## security
meaning: attackers cannot get in, and parts are kept apart so a breach stays contained.
tags: security, isolation
domains: software, infrastructure, product

## open source
meaning: the design can be published and built on, with no closed part.
tags: open-source
domains: software

## owner control
meaning: the owner decides, configures and can leave; no outside party holds the keys.
tags: owner-control
domains: software, infrastructure, product

## privacy
meaning: data about people stays with them and is shared only on purpose.
tags: privacy
domains: software, product, research

## user friction
meaning: how many steps, prompts or surprises a user meets.
tags: user-friction
domains: software, product

## platform reach
meaning: how many operating systems, devices and environments it runs on.
tags: platform-reach
domains: software, product

## maintenance and operations
meaning: the work of keeping it running, upgraded and understood over time.
tags: maintainability, ops-complexity
domains: software, infrastructure

## effort
meaning: how much work and time the choice takes to build.
tags: impl-effort
domains: software, infrastructure, product, fiction, nonfiction, research, planning

## performance
meaning: speed, latency and resource use.
tags: performance
domains: software, infrastructure

## reliability
meaning: it keeps working, and keeps its data, when something fails.
tags: reliability
domains: software, infrastructure

## scalability
meaning: it holds up as users, data or load grow.
tags: scalability
domains: software, infrastructure

## interoperability
meaning: it works with the standards and tools around it.
tags: interoperability
domains: software, infrastructure, research

## flexibility
meaning: it can change direction later without a rewrite.
tags: flexibility
domains: software, product, fiction, nonfiction, planning

## cost
meaning: the money spent to build and run it.
tags: cost
domains: software, infrastructure, product, research, planning

## third-party dependency
meaning: how much it relies on outside services, libraries or vendors.
tags: third-party-dependency
domains: software, infrastructure, planning

## testability
meaning: its behaviour can be checked automatically and in isolation.
tags: testability
domains: software

## clarity
meaning: the reader understands it the first time.
tags: clarity
domains: fiction, nonfiction, product

## engagement
meaning: the reader wants to keep going.
tags: engagement
domains: fiction, nonfiction

## consistency
meaning: tone, style and established facts hold throughout.
tags: consistency
domains: fiction, nonfiction

## pacing
meaning: the time spent on each part matches its weight.
tags: pacing
domains: fiction, nonfiction

## emotional impact
meaning: the reader feels what the work intends.
tags: emotional-impact
domains: fiction

## originality
meaning: it avoids the familiar and the predictable.
tags: originality
domains: fiction, product, research

## audience fit
meaning: it suits its readers' or users' level and expectations.
tags: audience-fit
domains: fiction, nonfiction, product

## accuracy
meaning: its claims are correct and can be sourced.
tags: accuracy
domains: nonfiction, research

## rigor
meaning: its methods support its conclusions.
tags: rigor
domains: research

## reproducibility
meaning: others can repeat it and get the same result.
tags: reproducibility
domains: research

## accessibility
meaning: people with disabilities can use it.
tags: accessibility
domains: software, product, nonfiction

## scope
meaning: how much it tries to cover.
tags: scope
domains: product, nonfiction, research, planning

## risk
meaning: the chance it goes wrong, and how badly.
tags: risk
domains: infrastructure, product, research, planning

## stakeholder support
meaning: the people it depends on back it.
tags: stakeholder-support
domains: product, planning

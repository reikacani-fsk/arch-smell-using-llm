# Architecture smell knowledge base (starter)

Starter notes for the RAG knowledge collection. Replace/extend them with content you can cite
(e.g. Azadi et al. 2019 catalogue, Arcan/Designite documentation, Sharma's smell catalogue).
Each "## " section becomes one retrievable chunk. Never put tool output or benchmark labels here.

## Cyclic dependency: why it matters
Packages in a cycle cannot be understood, tested, released or reused independently; a change in
one package can ripple around the whole cycle. Cycles often appear when a general-purpose package
starts calling back into a more specific package that was built on top of it.

## Cyclic dependency: refactorings
Move the class that causes the back-reference into the package where it is actually used; extract
an interface into the lower-level package and let the higher-level package implement it
(dependency inversion); extract the shared code into a new package both can depend on; or merge
packages that are in fact one component.

## Unstable dependency: why it matters
A package that many others rely on should be stable (hard to change). If it depends on packages
that change more easily than itself, their changes propagate to everything that uses it.
Instability I = Ce / (Ca + Ce); dependencies should point towards lower I.

## Unstable dependency: refactorings
Invert the dependency through an abstraction owned by the stable package; move the volatile
functionality out of the stable package; or stabilise the target by splitting off its volatile part.

## God component: why it matters
A very large package mixes many concerns, attracts dependencies from everywhere, and becomes a
bottleneck for comprehension and change. Size alone is a signal, not proof: check cohesion.

## God component: refactorings
Split the package along cohesive groups of classes (classes that change together and call each
other); move utility code that serves one client into that client's package; remove duplication.

## Feature concentration: why it matters
A package that realises several unrelated features forces unrelated changes into the same place and
couples their release cycles. Typical sign: groups of classes inside the package that never
reference each other and are used by different clients.

## Feature concentration: refactorings
Split the package so that each new package realises one feature; group by the clients that use the
classes; keep shared abstractions in a small, stable package.

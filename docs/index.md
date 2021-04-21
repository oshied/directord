# Welcome to Director

Director was created to solve several deployment specific problems which are
unique to heterogeneous large scale environments. While this application was
built for scale, easily scaling to thousands of targets, it is also perfectly
suited for single system environments which can gain the benifits of a simple,
fast, stable, and unique deployment engine.

> Direct your deployment instead of being driven insane by elements,
  ingredients, and attestations.

## First Principles

* Director uses well defined interfaces with clear documentation and
  boundaries.

* Director implements a fingerprinting system which ensures a deployment is
  predictable, reproducible, and idempotent at any level.

* Director is platform agnostic and depends on well defined libraries which
  are generally available on most operating systems.

* Director is an easily debuggable framework with coherent logging and the
  ability to expose exact job definitions, target operations, and runtime
  statistics.

* Director is stateless and natively runs within a container management
  ecosystem or within a traditional operating system.

* Director is light, and has been designed to use a few resources as possible,
  optimizing for consistency, stability, and performance; this means Director can
  be co-located within a cluster's deliverables or external to the environment.

### Getting Started

Getting started is simple, here's the documentation needed to be successful
with Director.

* [Tutorials](tutorials.md)

* [Overview](overview.md)
* [Installation](installation.md)
* [Service Setup](service-setup.md)
* [Containerization](containerization.md)
* [Authentication](authentication.md)
* [Management](management.md)
* [Syntax](syntax.md)
* [Orchestrations](orchestrations.md)
* [Testing](testing.md)

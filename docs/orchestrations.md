# Orchestration file specification

* TOC
{:toc}

Orchestration files allow directord to run any number of jobs against a given
set of targets. The specification file is simple and made to be easy. Each
file is loaded as an array and can contain many jobs.

### Structure

The values available within an orchestration file are `targets` and `jobs`.

* `async` **Optional** is a boolean. Enabling this option allows all tasks
  within a given orchestration to run asynchronously.

> Asynchronous orchestrations allow operators to run many orchestrations at
  the same time while following the defined task ordering.

* `jobs` is an array of hashes.

* `name` is a String. An orchestration can be named. This is done through
  the use of the `name` key. When orchestrations are named, both the job
  list and fingerprint output will use the defined `name` in the returned
  information.

* `targets` is an array of strings.

  * `assign` is an array which allows operators to define given set of
    targets. This is useful when defining node assignments outside of
    the typical targets consruct.

##### Example Orchestrations

This is the basic, syntax.

``` yaml
---
- targets: []
  jobs: []
  async: False
```

Within orchestration file the "targets" key is optional. If this key is
undefined, Directord will run against all available targets.

``` yaml
---
- jobs: []
```

Running jobs requires each item be a key=value pair. The key is a VERB used for
the given command and the value is the execution.

``` yaml
---
- jobs:
  - RUN: "echo hello world"
```

Each job can use either inline or YAML arguments. In the following example the
orchestration is using a YAML argument to instruct the command to skip the
cache.

``` yaml
---
- jobs:
  - RUN: "echo hello world"
    vars:
      skip_cache: true
```

> Several CLI options are available when orchestrating a deployment, such as
  `--restrict` and `--ignore-cache`. These option provide for the ability to
  replay specific tasks or forcefully ignore the client side cache.

#### Example Orchestration file

This example orchestration file will copy the local client ssh keys from the
directory `/home/centos/.ssh` to all nodes within the clister. Then, on the
three noted targets, `wget` will be installed.

``` yaml
---
- jobs:
  - WORKDIR: /home/centos/.ssh
  - RUN: chmod 600 /home/centos/.ssh/* && chmod 700 /home/centos/.ssh
  - ADD: /home/centos/.ssh/* /home/centos/.ssh/
    vars:
      chown: "centos:centos"
  - RUN: --skip-cache echo hello world
- targets:
  - df.next-c1.localdomain-client-1
  - df.next-c2.localdomain-client-1
  - df.next-c3.localdomain-client-1
  jobs:
  - RUN: dnf install -y wget
```

Upon the execution of each job, a new UUID will be presented to you for
tracking purposes. This information can be used with the manage commands.

Running an orchestration is simple and follows the same pattern as running an
adhoc execution.

``` shell
$ directord orchestrate ${ORCHESTRATION_FILE_NAME} [<switches> ...]
```

#### Jobs breakdown

Each **job** within the `jobs` list is a dictionary item with the fist key
ALWAYS representing the verb used within the given job. This verb corresponds
to a known component.

All jobs can make use extra options to enhance the user experience. This
options are useful when defining complex variables, which may be difficult
to express inline or within a "string" format.

* `assign` is a list object which allows operators to override the
  given set of targets for a particular job.

* `name` is a string object which provides a human friendly name
  for a job definition. This name can be used for an improved UX when
  looking into job debug information.

* `vars` is a dictionary of arguments that will be passed back into the
  execution options for a given job

# Orchestration file specification

* TOC
{:toc}

Orchestration files allow directord to run any number of jobs against a given
set of targets. The specification file is simple and made to be easy. Each
file is loaded as an array and can contain many jobs.

### Structure

The values available within an orchestration file are `targets` and `jobs`.

* `targets` is an array of strings.

* `jobs` is an array of hashes.

``` yaml
---
- targets: []
  jobs: []
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

### Example Orchestration file

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

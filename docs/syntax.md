# User facing DSL

* TOC
{:toc}

Directord uses a DSL inspired by the `Containerfile` specification. The AIM of
Directord isn't to create a new programing language, it is to get things done,
and then get out of the way.

## Components

To access component specific help information the `--exec-help` flag can be
used.

* Example

``` shell
$ directord exec --verb ${COMPONENT} '--exec-help true'
```

## Extra options

Every job has the ability to skip a cache hit should one be present on the
client node. To instruct the system to ignore all forms of cache, add the
`--skip-cache` to the job definition.

``` shell
$ directord exec --verb RUN '--skip-cache echo -e "hello world"'
```

Every job can be executed only one time. This is useful when orchestrating
a complex deployment where service setup only needs to be performed once. Use
the `--run-once` flag in your command to ensure it's only executed one time.

``` shell
$ directord exec --verb RUN '--run-once echo -e "hello world"'
```

Every job has the ability to define am execution timeout. The default timeout
is 600 seconds (5 minutes) however, each job can set a timeout to suit it's
specific need. Setting a timeout in the job is does with the `--timeout` switch
which takes a single integer as an argument.

``` shell
$ directord exec --verb RUN '--timeout 1 sleep 10'
```

> The above example with trigger the timeout signal after 1 second of
  execution time.

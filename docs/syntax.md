# User facing DSL

* TOC
{:toc}

When interacting with the **User** CLI utility executive and orchestration
operations follow a simple DSL inspired by the `Containerfile` specification.

> The AIM of Director isn't to create a new programing language, it is to get
  things done, and then get out of the way.

### Verbs

This is a short list of the available verbs. While this list includes all known
options at the time of this writing, the actual verb and switches all provide
help information regarding their usage. To access verb specific help information
the `--exec-help` flag can be used.

* Example

``` shell
$ director exec --verb ${VERB} '--exec-help true'
```

##### `RUN`

Syntax: `STRING`

Execute a command. The client terminal will execute using `/bin/sh`.

Extra arguments available to the `RUN` verb.

`--stdout-arg STRING` - Sets the stdout of a given command to defined cached
argument.

##### `ARG`

Syntax: `KEY VALUE`

Sets a cached item within the argument system, which allows for the brace
expansion of items within a command or through the blueprint interface.

> Argument values are cached for 12 hours.

##### `ENV`

Syntax: `KEY VALUE`

Sets a cached item within the environment system used to augment command
line execution.

> Environmental values are cached for 12 hours.

##### `ADD`

syntax: `SOURCE DESTINATION`

Copy a file or glob of files to a remote system. This method allows
operators to define multiple files on the CLI using the specific file, or a
glob of files within a given path.

> When copying multiple files, ensure that the destination path ends with an
  operating system separator.

Extra arguments available to the `ADD` verb.

`--chown user[:group]` - Sets the ownership of a recently transferred file to
a defined user and group (optionally).

`--blueprint` - The blueprint option instructs the client to read and render
a copied file. The file will be rendered using cached arguments.

> When a copy command has a brace expanded path, the value must be quoted:
  `example/path "/example/{{ target }}/path"`. The quotes around the brace
  exampled target path ensure that the string is preserved by the parser and
  is passed, as is, to the execution engine.

##### `COPY`

The same as `ADD`.

##### `WORKDIR`

Syntax: `STRING`

Create a directory on the client system.

##### `CACHEFILE`

Syntax: `STRING`

Read a **JSON** or **YAML** file on the client side and load the contents into
argument cache. While cached arguments can easily be defined using the `ARG` or
`ENV` verb, the `CACHEFILE` verb provides a way to load thousands of arguments
using a single action.

##### `CACHEEVICT`

Syntax: `STRING`

Evicts all cached items from a given tag. Built-in tags are: **jobs**,
**parents**, **args**, **envs**, **query**, **all**.

While all cached items have a TTL of 12 hours, this method is useful to purge
items on demand.

> The "all" keyword will evict all items from the cache.

##### `QUERY`

Syntax: `STRING`

> Scan the environment for a given cached argument and store the resultant on
  the target. The resultant is set in dictionary format:
  `"query": {query_identity: {query_arg: query_value}}`

Note that the key `query` stores all of the queried values for a given item
from across the cluster. This provides the ability to store multiple items
and intelligently parse/blueprint data based on node memberships.

## Extra options

Every job has the ability to skip a cache hit should one be present on the
client node. To instruct the system to ignore all forms of cache, add the
`--skip-cache` to the job definition.

``` shell
$ director exec --verb RUN '--skip-cache echo -e "hello world"'
```

Every job can be executed only one time. This is useful when orchestrating
a complex deployment where service setup only needs to be performed once. Use
the `--run-once` flag in your command to ensure it's only executed one time.

``` shell
$ director exec --verb RUN '--run-once echo -e "hello world"'
```

Every job has the ability to define am execution timeout. The default timeout
is 600 seconds (5 minutes) however, each job can set a timeout to suit it's
specific need. Setting a timeout in the job is does with the `--timeout` switch
which takes a single integer as an argument.

``` shell
$ director exec --verb RUN '--timeout 1 sleep 10'
```

> The above example with trigger the timeout signal after 1 second of
  execution time.

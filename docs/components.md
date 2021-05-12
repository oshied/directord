# Components

* TOC
{:toc}

Components power Directord and provide well documented interfaces.

### Built-in Components

The following section covers all of the built-in components Directord ships with.

##### `RUN`

Syntax: `STRING`

Execute a command. The client terminal will execute using `/bin/sh`.

Extra arguments available to the `RUN` component.

* `--stdout-arg` **STRING** Sets the stdout of a given command to defined cached
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

Extra arguments available to the `ADD` component.

* `--chown` **user[:group]** - Sets the ownership of a recently transferred file to
  a defined user and group (optionally).

* `--blueprint` The blueprint option instructs the client to read and render
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
`ENV` component, the `CACHEFILE` component provides a way to load thousands of
arguments using a single action.

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

##### `POD`

This features allows operators to run, manage, or manipulate pods across a
Directord cluster.

> At this time pod management requires **podman**.

* `--env` **KEY=VALUE** Comma separated environment variables. KEY=VALUE,...
* `--command` **COMMAND** Run a command in an exec container.
* `--privileged` Access a container with privleges.
* `--tls-verify` Verify certificates when pulling container images.
* `--force` When running removal operations, Enable or Disable force.
* `--kill-signal`  **SIGNAL** Set the kill signal. Default: SIGKILL
* `--start` **POD_NAME** Start a pod.
* `--stop` **POD_NAME** Stop a pod.
* `--rm` **POD_NAME** Remove a pod.
* `--kill` **POD_NAME** Kill a pod.
* `--inspect` **POD_NAME** Inspect a pod.
* `--play` **POD_FILE** Play a pod from a structured file.
* `--exec-run` **CONTAINER_NAME** Container name or ID to use for an execution container.

> When installing Directord with `pip`, the dev optional packages are
  needed on the client side to manage pods; `pip install directord[dev]`.

> Client side **podman** needs to be setup to enable the socket API. The
  orchestration [podman.yaml](https://github.com/cloudnull/directord/blob/main/orchestrations/podman.yaml)
  can be used to automate the **podman** installation and setup process.

### User defined Components

User defined components are expected to be in the
 `/etc/directord/components`, or within the package maintained share
path `share/directord/components`. When running user defined components,
Directord will ship them to target nodes when needed and ensure
remote nodes are up-to-date with the latest version. Because Directord
will automatically handle the transport, developing new components is
simple.

#### Complete User Defined Component Example

An example user defined component is available within the **components**
directory of Directord; [echo component](https://github.com/cloudnull/directord/blob/main/components/echo.py).

##### Minified Example

``` python
from directord import components


class Component(components.ComponentBase):
    def __init__(self):
        super().__init__(desc="Process echo commands")

    def args(self):
        super().args()
        self.parser.add_argument(
            "echo",
            help=("add echo statement for tests and example."),
        )

    def server(self, exec_string, data, arg_vars):
        super().server(exec_string=exec_string, data=data, arg_vars=arg_vars)
        data["echo"] = self.known_args.echo
        return data

    def client(self, conn, cache, job):
        super().client(conn=conn)
        print(job["echo"])
        return job["echo"], None, True
```

To build a component, only three methods are required. `args`, `server`, `client`.

| Method   | Description                                          |
| ---------| ---------------------------------------------------- |
| `args`   | Defines arguments used within a component            |
| `server` | Encompasses everything that must be done server side |
| `client` | Encompasses everything that will be done client side |

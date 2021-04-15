# Director

A deployment framework built to manage the data center life cycle.

Director is a messaging based asynchronous deployment and operations platform
with the aim to better enable faster time to delivery and consistency.

## Why

Director was created to solve several deployment specific problems which are
unique to heterogeneous large scale environments. While this application was
built for scale, easily scaling to thousands of targets, it is also perfectly
suited for single system environments.

#### First Principles

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

### Makeup

Director is a single application which consists of three parts:

* **Server** - The server is the centralized manager of all communication and
  application delivery.

* **Client** - The client is the minimal application required for enrolling a
  node into a given cluster.

* **User** - CLI utility which interfaces with the server over a local socket
  connect.

Director allows for the user to configure the application using environment
variables, a configurations file, or command line switches.

> NOTE: Because the user interface communicates with the server over a UNIX
  socket, the User and Server components are assumed to exist on the same
  machine.

![Director](assets/Director.png)

### Messaging

The cluster messaging uses a router format which ensures it has bi-directional
communication to and from the nodes. The router allows us to create a low
latency mesh which monitors node health and ensures is highly responsive
instruction delivery network.

![Director-Data-flow](assets/Director-Data-flow.png)

### User facing DSL

When interacting with the **User** CLI utility executive and orchestration
operations follow a simple DSL inspired by the `Containerfile` specification.

> The AIM of Director isn't to create a new programing language, it is to get
  things done, and then get out of the way.

#### Verbs

This is a short list of the available verbs.

##### `RUN`

Syntax: `STRING`

Execute a command. The client terminal will execute using `/bin/sh`.

Extra arguments available to the `RUN` verb.

`--stdout-arg STRING` - Sets the stdout of a given command to defined cached
argument.

##### `ARG`

Syntax: `KEY VALUE`

Sets a cached item within the environment.

##### `ENV`

The same as `ARG`.

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

#### Extra options

Every job has the ability to skip a cache hit should one be present on the
client node. To instruct the system to ignore all forms of cache, add the
`--skip-cache` to the job definition.

``` shell
$ director exec --verb RUN '--skip-cache echo -e "hello world"'
```

Every job can also be executed only one time. This is useful when orchestrating
a complex deployment where service setup only needs to be performed once. Use
the `--run-once` flag in your command to ensure it's only executed one time.

``` shell
$ director exec --verb RUN '--run-once echo -e "hello world"'
```

### Management

The **User** CLI provides for cluster management and insight into operations.
These functions allow operators to see and manipulate job and node status within
the cluster.

## UI

The server component of director provides for a minimal read-only UI which
provides insight into job executions and nodes within the cluster. To start
the UI component use the `--run-ui` flag when starting the server.

![Director-UI](assets/Director-UI.png)

## Orchestration file specification

Orchestration files allow director to run any number of jobs against a given
set of targets. The specification file is simple and made to be easy. Each
file is loaded as an array and can contain many jobs.

The values available within an orchestration file are `targets` and `jobs`.

* `targets` is an array of strings.

* `jobs` is an array of hashes.

``` yaml
---
- targets: []
  jobs: []
```

Within the orchestration file the "target" key is optional. If this key is
undefined, Director will run against all available targets.

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

> Several CLI options are available when orchestrating a deployment, such as
  `--restrict` and `--ignore-cache`. These option provide for the ability to
  replay specific tasks or forcefully ignore the client side cache.

##### Example Orchestration file

This example orchestration file will copy the local client ssh keys from the
directory `/home/centos/.ssh` to all nodes within the clister. Then, on the
three noted targets, `wget` will be installed.

``` yaml
---
- jobs:
  - WORKDIR: /home/centos/.ssh
  - RUN: chmod 600 /home/centos/.ssh/* && chmod 700 /home/centos/.ssh
  - ADD: --chown=centos:centos /home/centos/.ssh/* /home/centos/.ssh/
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
$ director orchestrate ${ORCHESTRATION_FILE_NAME} [<switches> ...]
```

## Service setup

Director comes with the ability to pre-create systemd service unit files when
required. When director is installed two additional entrypoints are created for
`director-server-systemd` and `director-client-systemd`. These utilities will
create relevant service unit files and ensure the execution path is set
correctly. This allows operators to easily install and run Director, even when
executing from a virtual-environment.

The service unit, for both server and client, assumes that all configuration
will be performed through the `/etc/director/config.yaml` file. This
configuration file maps all arguments that can be defined on the CLI to is a
simple key=value pair.

##### Example configuration file

``` yaml
---
heartbeat_interval: 1
debug: true
```

### Authentication

Director supports two forms of authentication, **Shared Key** and
**Curve25519**. Both of these authentication methods enhance the security of an
environment however both methods have some pros and cons.

| Method      | Overview    |
| ----------- | ----------- |
| Shared Key  | Plain Text  |
| Curve25519  | Encryption  |

##### Shared Key

**Shared Key** is the easiest method to setup and only requires a shared token
be generated on all client and server nodes. **Shared Key** is only an
authentication method and does not provide any encryption. While **Shared Key**
is a simple method to setup, it is not recommended to use this method when
dealing with deployments that extend out of a single data center.

**Shared Key** requires only a simple string to be defined within the Director
configuration file or on the CLI.

Server setup

``` shell
$ director --shared-key ${SECRET_TOKEN} server
```

Client Setup

``` shell
$ director --shared-key ${SECRET_TOKEN} client
```

##### Curve

**Curve25519** is a more complicated method to setup as keys have to be
generated and synchronized to all client and server nodes. While generating
keys is simple with the `director manage --generate-keys` command, the
**Curve25519** method is called out as more complex due to the requirement of
file transfers. **Curve25519** will encrypt the traffic within the cluster
making it suitable for deployments that extend beyond a single data center.

> When starting Director, both on the server and client, if a keys are directed
  and no other authentication method is provided **Curve25519** will be enabled
  automatically.

Example key generation, and synchronization to client nodes.

The following command will generate the encryption keys required to enable
**Curve25519**.

``` shell
$ director manage --generate-keys
```

> If the `--generate-keys` command is run more than once it will backup old key
  files before creating new ones. This is important for rollback capabilities
  should that be needed.

This example shows what needs to be created on remote (client) nodes and which
files need to be synchronized to client hosts.

``` shell
$ ssh root@${REMOTE_NODE} "mkdir -p /etc/director/private_keys /etc/director/public_keys"
$ rsync -avz /etc/director/private_keys/client.key_secret root@${REMOTE_NODE}:/etc/director/private_keys/
$ rsync -avz /etc/director/public_keys/*.key root@${REMOTE_NODE}:/etc/director/public_keys/
```

Once the keys are all in place the server can be started using the following command.

``` shell
$ director --curve-encryption server
```

It is also possible to upgrade an existing, un-encrypted, deployment to an
encrypted one using the provided orchestration file, `sync-curve-keys.yaml`.
This orchestration file assumes keys have been generated on the server.

``` shell
$ director orchestrate sync-curve-keys.yaml
```

> This orchestration file will push key files to all nodes within the cluster.
  This can be restricted by setting targets within the orchestration file or
  defining a restriction on the CLI. Once files are synchronized the client
  will need to be configured and restarted.

## Installation

Director can be installed and used on systems or in containers. If installing
on a system, the `toos/dev-setup.sh` script can be used to install Director
into a virtual environment.

#### Bootstrap natively

Director provides a bootstrap method which uses a **catalog** file to run the
operations. The catalog file uses a subset of the **orchestration** syntax,
with slight modifications to the target layout which is done to support extra
`SSH` information.

You can see an example [**catalog** file here](tools/director-catalog.yaml).

Once the catalog file is setup, running a cluster wide bootstrap is simple.

``` shell
$ director bootstrap --catalog ${CATALOG_FILE_NAME}
```

This method will bootstrap any defined servers in serial and all clients in
parallel with a maximum default thread count of 10; the thread count can be
modified using the `--thread` switch in the *bootstrap* mode.

#### Bootstrap with Ansible

It is possible to bootstrap Director with ansible. The following example is
a minimal inventory which could be used to bootstrap a cluster with Director.

``` yaml
all:
  vars:
    ansible_user: centos
  children:
    director_server:
      hosts:
        server0:
          ansible_host: 172.16.27.120
    director_clients:
      hosts:
        client0:
          ansible_host: 172.16.27.53
        client1:
          ansible_host: 172.16.27.58
        client2:
          ansible_host: 172.16.27.113
        client3:
          ansible_host: 172.16.27.120
```

With the inventory created, run the bootstrap playbook from the **tools** directory.

``` shell
$ ansible-playbook --inventory ~/director-inventory.yaml tools/ansible-bootstap.yaml
```

> The bootstrap playbook will assume the installation is from source.

##### Package based Installations

At this time Director doesn't have a pre-built package for the purpose of
installation. However all of the director dependencies can be installed
via packaging leaving only director running in a thin virtual environment.

Before installing Director appropriate repositories need to be setup within the
environment. On enterprise Linux environments repositories can be setup using
EPEL or RDO.

> On fedora based systems, running Fedora 33 or later, all of the packages are
  available without additional repositories.

Installing EPEL repositories

``` shell
$ dnf -y install epel-release
```

Installing RDO repositories

``` shell
$ dnf -y install https://www.rdoproject.org/repos/rdo-release.el8.rpm
```

Once appropriate repositories are setup, install the required packages.

``` shell
dnf -y install git python3 python3-tabulate python3-zmq python3-pyyaml python3-jinja2
```

If you intend to run the Director server web UI install the one UI dependency.

``` shell
dnf -y install python3-flask
```

Now install the core dependencies.

``` shell
dnf -y install zeromq libsodium
```

As mentioned, Director doesn't have an a package to install at this time. To
get director installed create a virtual environment and install director from a
given checkout into the virtual environment.

``` shell
python3 -m venv --system-site-packages /opt/director
/opt/director/bin/pip install git+https://github.com/cloudnull/director
```

> Once Installed further installation customizations can be made within the
  /etc/director path. Additionally, systemd unit files can be installed using
  the `director-server-systemd` or `director-client-systemd` entry points
  accordingly. See [the Service Setup Section](#service-setup) for more on these
  options.

The script `prod-setup.sh`, within the tools directory, can be used to automate
the setup of Director using a package based installation.

### Containerization

A Containerfile and image has been provided allowing operators to run the
Server and Client components within a container. While containerization
functions and is a great tool for development and test, it is recommended
to only run the **Server** component within a container in production scenarios.

#### Pre-built containers are available

Pre-built Director images are available on my the major public registries.

##### Github Package

``` shell
$ podman login https://docker.pkg.github.com -u $USERNAME
$ podman pull docker.pkg.github.com/cloudnull/director/director:main
```

##### Quay.io

``` shell
$ podman pull quay.io/cloudnull/director
```

##### Dockerhub

``` shell
$ docker pull cloudnull/director
```

#### Building the container

``` shell
$ podman build -t director -f Containerfile
```

#### Running the container in Server mode

When running Director in server mode two things need to happen.

1. Create a volume for the container to access local artifacts.

2. Create a volume for the client to access the server socket.

``` shell
mkdir -p ~/director

$ podman run --hostname director \
             --name director-server \
             --net=host \
             --env DIRECTOR_MODE=server \
             --env DIRECTOR_SHARED_KEY=secrete \
             --volume /tmp:/tmp \
             --volume ${HOME}/director:${HOME}/director \
             --detach \
             director director
```

> NOTE: the volume `--volume ${HOME}/director:${HOME}/director` is specifically
  using the full path so that the file system structure within the server mirrors
  that of the local file system. This is important when working with artifacts
  that are not native to the container.

When using this example you can move content into the `~/director` home folder
and access the server socket via `~/director/tmp`.

> Operators following this example will need to copy content on the local
  system into `~/director` before running jobs that assume read access to
  artifacts; such as exec `COPY` or `ADD` jobs and all orchestrations.

Example local client action using a containerized server.

``` shell
$ director --socket-path /tmp/director.sock manage --list-nodes
```

#### Running the container in Client mode

``` shell
$ podman run --hostname $(hostname)-client \
             --name director-client \
             --net=host \
             --env DIRECTOR_SERVER_ADDRESS=172.16.27.120 \
             --env DIRECTOR_SHARED_KEY=secrete \
             --user 0 \
             --detach \
             director director
```

> NOTE: the DIRECTOR_SERVER_ADDRESS environment variable needs to point to the
  IP address or Domain name of the Director server.

#### Touchless Operations

Because the server can be containerized it is possible to run Director on any
container servicing environment without having to officially install the
application on the local system using conventional packages. Interfacing with a
container can be done in an almost endless number of ways. In the following
example a shell function is used to exec into a running `director-server`
container and interface with the client.

``` shell
function director() {
  podman exec -ti director-server /director/bin/director --socket-path /tmp/director.sock $@;
}
```

> Running *Touchless* with the above container invocations still assumes that
  the working path, where artifacts can be read or written, is `~/director`.

## Testing Interactions

Lots of client containers can be created to test full scale interactions. This
simple example shows how that could be done on a single machine.

``` shell
# Pull the director container from quay
$ podman pull quay.io/cloudnull/director

# Start the server
$ director --debug --shared-key secrete server --bind-address 127.0.0.1 &

# Run 40 client containers
$ for i in {1..40}; do
  podman run --hostname $(hostname)-client-${i} \
             --name $(hostname)-client-${i} \
             --net=host \
             --env DIRECTOR_SERVER_ADDRESS=127.0.0.1 \
             --env DIRECTOR_SHARED_KEY=secrete \
             --user 0 \
             --detach \
             director director
done
```

Once running the clients will connect to the server which will stream log
output.

#### Running the functional tests

With Director running, with at least one client, the functional test
orchestration file can be used to exercise the entire suit of tooling. For the
functional tests to work the will need to be executed from the "orchestrations"
directory within the local checkout of this repository.

``` shell
$ director orchestrate functional-tests.yaml --ignore-cache
```

This will run the functional tests and ignore all caching all client nodes when
executing. The reason all caching is ignored is to ensure that the application
is executing what we expect on successive test runs.

Once the test execution is complete, the following oneliner can be used to
check for failure and then dump the jobs data to further diagnose problems.

``` shell
$ (director manage --list-jobs | grep False) && director manage --export-jobs jobs-failure-information.yaml
```

Run the `--purge-jobs` management command to easily clear the job information
before testing again.

``` shell
director manage --purge-jobs
```

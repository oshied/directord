# Installation

* TOC
{:toc}

Directord can be installed and used on systems or in containers. If installing
on a system, the `toos/dev-setup.sh` script can be used to install Directord
into a virtual environment.

### Bootstrap natively

Directord provides a bootstrap method which uses a **catalog** file to run the
operations. The catalog file uses a subset of the **orchestration** syntax,
with slight modifications to the target layout which is done to support extra
`SSH` information.

This is a **catalog** example

``` yaml
directord_server:
  targets:
  - host: 172.16.27.120
    port: 22
    username: centos

directord_clients:
  args:
    port: 22
    username: centos
  targets:
  - host: 172.16.27.53
```

> An example inventory catalog can be found under
  `tools/directord-inventory-catalog.yaml`.

Once the catalog file is setup, running a cluster wide bootstrap is simple.
In this example the first catalog option is referencing the unique inputs
that represent a given data center. The second catalog file is referencing
built-in file maintained by Directord to deploy Directord.

``` shell
$ directord bootstrap --catalog ${CATALOG_FILE_NAME} --catalog tools/directord-bootstrap-catalog.yaml
```

> The catalog input can be used more than once and can be totally user
  defined. While a built-in has been provided as an example, users are
  free to do whatever they see fit to achieve their bootstrap goals.

> All values within a set of catalog files can be used as blueprinted options
  with commands. This makes it possible to set any key and value within a catalog
  file and use that option as an argument. This is specifically used in the
  default bootstrap catalog file to dynamically source the server address for
  clients; blueprinting is basic jinja and for the purpose of the bootstrap
  example is used like so `"{{ directord_server['targets'][0]['host'] }}"`.

> In a [touchless](containerization.md#touchless-operations) operations
  scenario only the `directord_clients` would need to be defined for a bootstrap
  operation as the server would be provided for using the container image.

This method will bootstrap any defined servers in serial and all clients in
parallel with a maximum default thread count of 10; the thread count can be
modified using the `--thread` switch in the *bootstrap* mode.

###### Encryption Key Rotation and Restarting

Once Directord is up and running, you can restart it across a cluster and
re-encrypt the environment, just as easily as it was bootstrapped. The
`directord-restart-catalog.yaml` catalog file has been provided as an example of
running a re-encryption and restart via SSH, which is useful should the cluster
have been in a downed state.

``` shell
$ directord bootstrap --catalog ${CATALOG_FILE_NAME} --catalog tools/directord-restart-catalog.yaml
```

> Additional key rotation techniques are covered under the following
  [Authentication section](authentication.md#key-rotation).

### Bootstrap with Ansible

It is possible to bootstrap Directord with ansible. The following example is
a minimal inventory which could be used to bootstrap a cluster with Directord.

``` yaml
all:
  vars:
    ansible_user: centos
  children:
    directord_server:
      hosts:
        server0:
          ansible_host: 172.16.27.120
    directord_clients:
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

> An example inventory can be found under `tools/ansible-inventory.yaml`.

With the inventory created, run the bootstrap playbook from the **tools** directordy.

``` shell
$ ansible-playbook --inventory ~/directord-inventory.yaml tools/ansible-bootstap-playbook.yaml
```

> The bootstrap playbook will assume the installation is from source.

##### Package based Installations By Hand

At this time Directord doesn't have a pre-built package for the purpose of
installation. However all of the directord dependencies can be installed
via packaging leaving only directord running in a thin virtual environment.

Before installing Directord appropriate repositories need to be setup within the
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

If you intend to run the Directord server web UI install the one UI dependency.

``` shell
dnf -y install python3-flask
```

Now install the core dependencies.

``` shell
dnf -y install zeromq libsodium
```

As mentioned, Directord doesn't have an a package to install at this time. To
get directord installed create a virtual environment and install directord from a
given checkout into the virtual environment.

``` shell
python3 -m venv --system-site-packages /opt/directord
/opt/directord/bin/pip install git+https://github.com/cloudnull/directord
```

> Once Installed further installation customizations can be made within the
  /etc/directord path. Additionally, systemd unit files can be installed using
  the `directord-server-systemd` or `directord-client-systemd` entry points
  accordingly. See [the Service Setup Section](service-setup.md) for more on these
  options.

##### Installations By Script

The script `prod-setup.sh`, within the tools directordy, can be used to automate
the setup of Directord using a package based installation which was created to
provide a means to bootstrap clusters quickly in a production environment.

The script `dev-setup.sh`, within the tools directordy can be used to automate
the setup of Directord from source, which was created to allow developers to get
and running quickly with Directord on a development system.

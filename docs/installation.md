# Installation

* TOC
{:toc}

Director can be installed and used on systems or in containers. If installing
on a system, the `toos/dev-setup.sh` script can be used to install Director
into a virtual environment.

### Bootstrap natively

Director provides a bootstrap method which uses a **catalog** file to run the
operations. The catalog file uses a subset of the **orchestration** syntax,
with slight modifications to the target layout which is done to support extra
`SSH` information.

This is a **catalog** example

``` yaml
director_server:
  targets:
  - host: 172.16.27.120
    port: 22
    username: centos

director_clients:
  args:
    port: 22
    username: centos
  targets:
  - host: 172.16.27.53
```

> An example inventory catalog can be found under
  `tools/director-inventory-catalog.yaml`.

Once the catalog file is setup, running a cluster wide bootstrap is simple.
In this example the first catalog option is referencing the unique inputs
that represent a given data center. The second catalog file is referencing
built-in file maintained by Director to deploy Director.

``` shell
$ director bootstrap --catalog ${CATALOG_FILE_NAME} --catalog tools/director-bootstrap-catalog.yaml
```

> The catalog input can be used more than once and can be totally user
  defined. While a built-in has been provided as an example, users are
  free to do whatever they see fit to achieve their bootstrap goals.

> In a [touchless](containerization.md#touchless-operations) operations
  scenario only the `director_clients` would need to be defined for a bootstrap
  operation as the server would be provided for using the container image.

This method will bootstrap any defined servers in serial and all clients in
parallel with a maximum default thread count of 10; the thread count can be
modified using the `--thread` switch in the *bootstrap* mode.

###### Encryption Key Rotation and Restarting

Once Director is up and running, you can restart it across a cluster and
re-encrypt the environment, just as easily as it was bootstrapped. The
`director-restart-catalog.yaml` catalog file has been provided as an example of
running a re-encryption and restart via SSH, which is useful should the cluster
have been in a downed state.

``` shell
$ director bootstrap --catalog ${CATALOG_FILE_NAME} --catalog tools/director-restart-catalog.yaml
```

> Additional key rotation techniques are covered under the following
  [Authentication section](authentication.md#key-rotation).

### Bootstrap with Ansible

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

> An example inventory can be found under `tools/ansible-inventory.yaml`.

With the inventory created, run the bootstrap playbook from the **tools** directory.

``` shell
$ ansible-playbook --inventory ~/director-inventory.yaml tools/ansible-bootstap-playbook.yaml
```

> The bootstrap playbook will assume the installation is from source.

##### Package based Installations By Hand

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
  accordingly. See [the Service Setup Section](service-setup.md) for more on these
  options.

##### Installations By Script

The script `prod-setup.sh`, within the tools directory, can be used to automate
the setup of Director using a package based installation which was created to
provide a means to bootstrap clusters quickly in a production environment.

The script `dev-setup.sh`, within the tools directory can be used to automate
the setup of Director from source, which was created to allow developers to get
and running quickly with Director on a development system.

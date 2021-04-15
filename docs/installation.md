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
shared_jobs: &shared_jobs
- ADD: prod-setup.sh prod-setup.sh
- RUN: sudo bash prod-setup.sh

director_server:
  targets:
  - host: 172.16.27.120
    port: 22
    username: centos
  jobs:
  - *shared_jobs
  - RUN: sudo /opt/director/bin/director manage --generate-keys
  - RUN: sudo /opt/director/bin/director-server-systemd
  - RUN: sudo systemctl daemon-reload
  - RUN: sudo systemctl restart director-server.service
  - GET: /etc/director/private_keys/client.key_secret /tmp/client.key_secret
  - GET: /etc/director/public_keys/client.key /tmp/client.key
  - GET: /etc/director/public_keys/server.key /tmp/server.key
  - RUN: |-
      sudo python3 <<EOC
      import yaml
      with open('/etc/director/config.yaml') as f:
          config = yaml.safe_load(f)
      config["curve_encryption"] = True
      with open('/etc/director/config.yaml', 'w') as f:
          f.write(yaml.safe_dump(config, default_flow_style=False))
      EOC

director_clients:
  args:
    port: 22
    username: centos
  targets:
  - host: 172.16.27.53
  jobs:
  - *shared_jobs
  - RUN: sudo mkdir -p /etc/director/private_keys /etc/director/public_keys
  - ADD: /tmp/client.key_secret /tmp/client.key_secret-stash
  - RUN: sudo mv /tmp/client.key_secret-stash /etc/director/private_keys/client.key_secret
  - ADD: /tmp/client.key /tmp/client.key-stash
  - RUN: sudo mv /tmp/client.key-stash /etc/director/public_keys/client.key
  - ADD: /tmp/server.key /tmp/server.key-stash
  - RUN: sudo mv /tmp/server.key-stash /etc/director/public_keys/server.key
  - RUN: sudo /opt/director/bin/director-client-systemd
  - RUN: sudo systemctl daemon-reload
  - RUN: |-
      sudo python3 <<EOC
      import yaml
      with open('/etc/director/config.yaml') as f:
          config = yaml.safe_load(f)
      config["curve_encryption"] = True
      config['server_address'] = "172.16.27.120"
      with open('/etc/director/config.yaml', 'w') as f:
          f.write(yaml.safe_dump(config, default_flow_style=False))
      EOC
  - RUN: sudo systemctl restart director-client.service
```

Once the catalog file is setup, running a cluster wide bootstrap is simple.

``` shell
$ director bootstrap --catalog ${CATALOG_FILE_NAME}
```

This method will bootstrap any defined servers in serial and all clients in
parallel with a maximum default thread count of 10; the thread count can be
modified using the `--thread` switch in the *bootstrap* mode.

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
  accordingly. See [the Service Setup Section](service-setup.md) for more on these
  options.

The script `prod-setup.sh`, within the tools directory, can be used to automate
the setup of Director using a package based installation.

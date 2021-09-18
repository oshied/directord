# Service setup

* TOC
{:toc}

Directord comes with the ability to pre-create systemd service unit files when
required. When directord is installed two additional entrypoints are created for
`directord-server-systemd` and `directord-client-systemd`. These utilities will
create relevant service unit files and ensure the execution path is set
correctly. This allows operators to easily install and run Directord, even when
executing from a virtual-environment.

The service unit, for both server and client, assumes that all configuration
will be performed through the `/etc/directord/config.yaml` file. This
configuration file maps all arguments that can be defined on the CLI to is a
simple key=value pair.

##### Example configuration file

``` yaml
---
debug: true
```

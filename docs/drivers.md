# Messaging Drivers

* TOC
{:toc}

Directord is powered by message platforms. As such, to run Directord a
messaging driver needs to be selected, which may require additional setup
based on the operating environment.

## ZMQ

Status: `Default`

Used for distributed mesh communication between the server and client nodes.
No additional setup is required outside of the initial package installation.

> The following diagram shows the application flow when using the ZeroMQ
  driver.

![Directord](assets/driver-zmq.png)

Directord with the ZMQ driver supports two forms of authentication, **Shared
Key** and **Curve25519**. Both of these authentication methods enhance the
security of an environment however both methods have some pros and cons.

| Method      | Overview    |
| ----------- | ----------- |
| Shared Key  | Plain Text  |
| Curve25519  | Encryption  |

### Shared Key

**Shared Key** is the easiest method to setup and only requires a shared token
be generated on all client and server nodes. **Shared Key** is only an
authentication method and does not provide any encryption. While **Shared Key**
is a simple method to setup, it is not recommended to use this method when
dealing with deployments that extend out of a single data center.

**Shared Key** requires only a simple string to be defined within the Directord
configuration file or on the CLI.

Server setup

``` shell
$ directord --shared-key ${SECRET_TOKEN} server
```

Client Setup

``` shell
$ directord --shared-key ${SECRET_TOKEN} client
```

### Curve

**Curve25519** is a more complicated method to setup as keys have to be
generated and synchronized to all client and server nodes. While generating
keys is simple with the `directord manage --generate-keys` command, the
**Curve25519** method is called out as more complex due to the requirement of
file transfers. **Curve25519** will encrypt the traffic within the cluster
making it suitable for deployments that extend beyond a single data center.

> When starting Directord, both on the server and client, if a keys are directed
  and no other authentication method is provided **Curve25519** will be enabled
  automatically.

Example key generation, and synchronization to client nodes.

The following command will generate the encryption keys required to enable
**Curve25519**.

``` shell
$ directord manage --generate-keys
```

> If the `--generate-keys` command is run more than once it will backup old key
  files before creating new ones. This is important for rollback capabilities
  should that be needed.

This example shows what needs to be created on remote (client) nodes and which
files need to be synchronized to client hosts.

``` shell
$ ssh root@${REMOTE_NODE} "mkdir -p /etc/directord/private_keys /etc/directord/public_keys"
$ rsync -avz /etc/directord/private_keys/client.key_secret root@${REMOTE_NODE}:/etc/directord/private_keys/
$ rsync -avz /etc/directord/public_keys/*.key root@${REMOTE_NODE}:/etc/directord/public_keys/
```

Once the keys are all in place the server can be started using the following command.

``` shell
$ directord --curve-encryption server
```

It is also possible to upgrade an existing, un-encrypted, deployment to an
encrypted one using the provided orchestration file, `sync-curve-keys.yaml`.
This orchestration file assumes keys have been generated on the server.

``` shell
$ directord orchestrate sync-curve-keys.yaml
```

> This orchestration file will push key files to all nodes within the cluster.
  This can be restricted by setting targets within the orchestration file or
  defining a restriction on the CLI. Once files are synchronized the client
  will need to be configured and restarted.

### Key Rotation

When encryption is enabled it is important to be able to rotate keys and
restart services whenever required. Directord makes this simple using both its
built in functions and via a
[bootstrap catalog](installation.md#encryption-key-rotation-and-restarting).

To rotate encryption keys natively the following execution commands can be
run, which will first generate new keys on the server and run a simple
orchestration to rotate the keys across an active cluster.

``` shell
$ directord manage --generate-keys
$ directord orchestrate key-rotation.yaml
```

After key rotation you can validate that all nodes are checking into the
cluster using a simple check

``` shell
$ directord manage --list-nodes
```

> Learn more about [Orchestrations here](orchestrations.md).

## Messaging

Status: `Development`

Based on OSLO messaging and can make use of many messaging backends. For the
purpose of this example, the environment will be configured to use the QPID
dispatch router.

> The following diagram shows the application flow when using the Messaging
  driver.

![Directord](assets/driver-messaging.png)

### Configuration

With the Directord needs to be configured to run with the `messaging` driver.
To do this configuration edit the `/etc/directord/config.yaml` file and add
the following options.

```yaml
driver: messaging
server_address: 127.0.0.1
```

> NOTE: The server address is the location of the AMQP Server and can be
  anywhere, so long as Directord and the client targets are able to
  router to the defined location.

### Requirements

Before running the `messaging` driver, `qdrouterd` needs to be setup within the
environment.

### Running a local QPID Dispatch Router

``` shell
$ sudo dnf install qpid-dispatch-router
```

Once the dependecies are installed, enable and start the server process.

``` shell
$ sudo systemctl enable qdrouterd.service
$ sudo systemctl start qdrouterd.service
```

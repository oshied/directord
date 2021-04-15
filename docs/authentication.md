# Authentication

* TOC
{:toc}

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

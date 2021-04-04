# Director

A deployment framework built to manage the data center life cycle.

Director is a messaging based asynchronous deployment and operations platform
with the aim to simply and better enable faster time to delivery and
consistency.

## Makeup

Director is a single application which consists of three parts:

* **Server** - The server is the centralized manager of all communication and
  application delivery.

* **Client** - The client is the minimal application required for enrolling a
  node into a given cluster.

* **User** - CLI utility which interfaces with the server over a local socket
  connect.


Director allows for the user to configure the application using environment
variables, a configurations file, or command line switches.

### Messaging

The cluster messaging is provided by ZeroMQ in a router format which ensures
that we have bi-directional communication to and from the nodes. The use of
ZeroMQ allows us to create low latency mesh which is highly responsive and
delivering content as fast as possible.

### User facing DSL

When interacting with the **User** CLI utility executive and orchestration
operations follow a simple DSL inspired by the `Containerfile` specification.

### Management

The **User** CLI provides for cluster management and insight into operations.
These functions allow operators to see and manipulate job and node status within
the cluster.

## Containerization

A Containerfile and image has been provided allowing operators to run the
Server and Client components within a container. While containerization
functions and is a great tool for development and test, it is recommended
to only run the **Server** component within a container in production scenarios.

#### Building the container

``` shell
$ podman build -t director.HEAD -f Containerfile
```

#### Running the container in Server mode

``` shell
podman run --env DIRECTOR_MODE=server --detach localhost/director.HEAD director
```

#### Running the container in Server mode

``` shell
podman run --env DIRECTOR_SERVER_ADDRESS=172.16.2.2 --detach localhost/director.HEAD director
```

> NOTE: the DIRECTOR_SERVER_ADDRESS environment variable needs to point to the
  IP address or Domain name of the Director server.

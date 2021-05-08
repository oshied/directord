# Containerization

* TOC
{:toc}

A Containerfile and image has been provided allowing operators to run the
Server and Client components within a container. While containerization
functions and is a great tool for development and test, it is recommended
to only run the **Server** component within a container in production scenarios.

#### Pre-built containers are available

Pre-built Directord images are available on my the major public registries.

##### Github Package

``` shell
$ podman login https://docker.pkg.github.com -u $USERNAME
$ podman pull docker.pkg.github.com/cloudnull/directord/directord:main
```

##### Quay.io

``` shell
$ podman pull quay.io/cloudnull/directord
```

##### Dockerhub

``` shell
$ docker pull cloudnull/directord
```

#### Building the container

``` shell
$ podman build -t directord -f Containerfile
```

#### Running the container in Server mode

When running Directord in server mode two things need to happen.

1. Create a volume for the container to access local artifacts.

2. Create a volume for the client to access the server socket.

``` shell
$ mkdir -p ~/local/share/directord ~/local/share/directord/etc
$ podman run --hostname directord \
             --name directord-server \
             --net=host \
             --env DIRECTORD_MODE=server \
             --volume ${HOME}/local/share/directord/etc:/etc/directord:z \
             --volume ${HOME}/local/share/directord:${HOME}/local/share/directord \
             --detach \
             --user 0 \
             directord directord
```

> NOTE: the volume `--volume ${HOME}/local/share/directord:${HOME}/local/share/directord` is
  specifically using the full path so that the file system structure within the
  server mirrors that of the local file system. This is important when working
  with artifacts that are not native to the container. While this path is a
  share, it could be any mirrored file system path and works perfectly with
  shared file-systems.

> Operators following this example will need to copy content on the local
  system into `${HOME}/local/share/directord` before running jobs that
  assume read access to artifacts; such as exec `COPY` or `ADD` jobs and
  all orchestrations.

Example local client action using a containerized server.

``` shell
$ directord --socket-path /tmp/directord.sock manage --list-nodes
```

> Because the Directord server runs in an unprivileged container, it can also
  run in a root-less container. This also means multiple containerized
  Directord servers can run on a single node, provided `--net=host` isn't used.

#### Running the container in Client mode

> While running clients in a container is functional, their is limited,
  especially as it pertains to physical infrastructure.

``` shell
$ podman run --hostname $(hostname)-client \
             --name directord-client \
             --net=host \
             --env DIRECTORD_SERVER_ADDRESS=172.16.27.120 \
             --env DIRECTORD_SHARED_KEY=secrete \
             --user 0 \
             --detach \
             directord directord
```

> NOTE: the DIRECTORD_SERVER_ADDRESS environment variable needs to point to the
  IP address or Domain name of the Directord server.

#### Running pods

Both the directord server and client can be run within a container pod. Pod
definition files have been provided in the assets directord and can be used to
rapidly instantiate infrastructure.

> At this time `podman play` does require that the command be run as root.

###### Server

``` shell
$ podman play kube pods/pod-directord-server.yaml
```

###### Client

``` shell
$ podman play kube pods/pod-directord-client.yaml
```

#### Touchless Operations

Because the server can be containerized it is possible to run Directord on any
container servicing environment without having to officially install the
application on the local system using conventional packages. Interfacing with a
container can be done in an almost endless number of ways. In the following
example a shell function is used to exec into a running `directord-server`
container and interface with the client.

``` shell
function directord() {
  podman exec -ti directord-server /directord/bin/directord --socket-path /tmp/directord.sock $@;
}
```

> Running *Touchless* with the above container invocations still assumes that
  the working path, where artifacts can be read or written, is `~/directord`.

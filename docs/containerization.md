# Containerization

* TOC
{:toc}

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
$ mkdir -p ~/local/share/director ~/local/share/director/etc
$ podman run --hostname director \
             --name director-server \
             --net=host \
             --env DIRECTOR_MODE=server \
             --volume ${HOME}/local/share/director/etc:/etc/director:z \
             --volume ${HOME}/local/share/director:${HOME}/local/share/director \
             --detach \
             --user 0 \
             director director
```

> NOTE: the volume `--volume ${HOME}/local/share/director:${HOME}/local/share/director` is
  specifically using the full path so that the file system structure within the
  server mirrors that of the local file system. This is important when working
  with artifacts that are not native to the container. While this path is a
  share, it could be any mirrored file system path and works perfectly with
  shared file-systems.

> Operators following this example will need to copy content on the local
  system into `${HOME}/local/share/director` before running jobs that
  assume read access to artifacts; such as exec `COPY` or `ADD` jobs and
  all orchestrations.

Example local client action using a containerized server.

``` shell
$ director --socket-path /tmp/director.sock manage --list-nodes
```

> Because the Director server runs in an unprivileged container, it can also
  run in a root-less container. This also means multiple containerized
  Director servers can run on a single node, provided `--net=host` isn't used.

#### Running the container in Client mode

> While running clients in a container is functional, their is limited,
  especially as it pertains to physical infrastructure.

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

#### Running pods

Both the director server and client can be run within a container pod. Pod
definition files have been provided in the assets director and can be used to
rapidly instantiate infrastructure.

> At this time `podman play` does require that the command be run as root.

###### Server

``` shell
$ podman play kube assets/pod-director-server.yaml
```

###### Client

``` shell
$ podman play kube assets/pod-director-client.yaml
```

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

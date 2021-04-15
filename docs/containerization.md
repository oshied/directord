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

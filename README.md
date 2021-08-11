# Directord

A deployment framework built to manage the data center life cycle.

> Task driven deployment, simplified, directed by you.

Directord is an asynchronous deployment and operations platform with the aim to
better enable simplicity, faster time to delivery, and consistency.

## Design Principles

The Directord design principles can be
[found here](https://cloudnull.github.io/directord#first-principles).

## Documentation

Additional documentation covering everything from application design, wire
diagrams, installation, usage, and more can all be
[found here](https://cloudnull.github.io/directord).

## Welcome Contributors

* Read documentation on how best to deploy and leverage directord.

* When ready, if you'd like to contribute to Directord pull-requests are very
  welcomed. Directord is an open platform built for operators. If you see
  something broken, please feel free to raise a but and/or fix it.

* Information on running tests can be [found here](https://cloudnull.github.io/directord/testing).

### Have Questions?

Join us on [`libera.chat`](https://libera.chat/guides/connect) at
**#directord**. The community is just getting started: folks are here to help,
answer questions, and support one another.

## Quick Introduction

This quick cast shows how easy it is to install, bootstrap, and deploy a scale test environment.

[![asciicast](https://asciinema.org/a/410759.svg)](https://asciinema.org/a/410759)


## Hello World

Let's create a virtual env on your local machine to bootstrap the installation,
once installed you can move to the server node and call all your tasks from there

    python3 -m venv --system-site-packages ~/directord
    ~/directord/bin/pip install --upgrade pip setuptools wheel
    ~/directord/bin/pip install directord

We need to create a catalog for bootstrapping. Let's assume we are installing directord in two machines:

test1 192.168.1.100 : dicectord server, a client
test2 192.168.1.101 : Only a client

for that we create a file

    vi ~/directord-catalog.yaml

with the contents:

    directord_server:
      targets:
      - host: 192.168.1.100
        port: 22
        username: fedora

    directord_clients:
      args:
        port: 22
        username: fedora
      targets:
      - host: 192.168.1.100
      - host: 192.168.1.101

We can now call directord to bootstrap the installation. Bootstrapping uses ssh to connect to the machines but after that ssh is no longer used.
and you only need the ssh keys to connect your local machine to the machines you are installing into the server and client do not need shared keys between themselves.

To kickstart the bootstrapping you call  directord with the catalog file you created and a catalog with the jobs required to bootstrap them.

    ~/directord/bin/directord bootstrap \
    --catalog ~/directord-catalog.yaml  \
    --catalog ~/directord/share/directord/tools/directord-prod-bootstrap-catalog.yaml

Once that is ran you can now ssh to the server and issue all the commands from there

    ssh fedora@192.168.1.100

First to make sure all the nodes are connected

    sudo /opt/directord/bin/directord manage --list-nodes

Should show you:

    ID           EXPIRY  VERSION    UPTIME
    ---------  --------  ---------  --------------
    test1        170.43  0.6.0      1:37:35.330000
    test2        127.36  0.6.0      1:35:25.830000

Then we create our first orchestration job lets add a file called 

    vi helloworld.yaml

with the contents:

    - jobs:
      - RUN: echo hello world

Then we call the orchestration to use it

    sudo /opt/directord/bin/directord orchestrate helloworld.yaml

Should return something like:

    Job received. Task ID: 9bcf31cb-7faf-4367-bf37-57c11b3f81dc

We use that task ID to probe how the job went or we can list all the jobs with"

    sudo /opt/directord/bin/directord manage --list-jobs

That returns something like:

    ID                                    PARENT_JOB_ID                           EXECUTION_TIME    SUCCESS    FAILED
    ------------------------------------  ------------------------------------  ----------------  ---------  --------
    9bcf31cb-7faf-4367-bf37-57c11b3f81dc  9bcf31cb-7faf-4367-bf37-57c11b3f81dc              0.02          2         0

with the task id we can see how the job went:

    sudo /opt/directord/bin/directord manage --job-info 9bcf31cb-7faf-4367-bf37-57c11b3f81dc

And voila here is our first orchestrated hello world:

    KEY                   VALUE
    --------------------  -------------------------------------------------------
    ID                    9bcf31cb-7faf-4367-bf37-57c11b3f81dc
    ACCEPTED              True
    INFO                  test1 = echo hello world
                          test2 = echo hello world
    STDOUT                test1 = hello world
                          test2 = hello world
    ...


## License

Apache License Version 2.0
[COPY](LICENSE)

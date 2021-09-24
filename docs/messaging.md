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

## Messaging

Status: `Development`

Based on OSLO messaging and can make use of many messaging backends. For the
purpose of this example, the environment will be configured to use the QPID
dispatch router.

Before we're able to run with `qdrouterd` the dependencies need to be
installed.

``` shell
$ sudo dnf install qpid-dispatch-router
```

Once the dependecies are installed, enable and start the server process.

``` shell
$ sudo systemctl enable qdrouterd.service
$ sudo systemctl start qdrouterd.service
```

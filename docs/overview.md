# Directord Components

* TOC
{:toc}

Directord is a single application which consists of three parts:

* **Server** - The server is the centralized manager of all communication and
  application delivery.

* **Client** - The client is the minimal application required for enrolling a
  node into a given cluster.

* **User** - CLI utility which interfaces with the server over a local socket
  connect.

![Directord-Data-flow](assets/highlevel-messaging.png)

## Cluster Messaging

The cluster messaging uses a router format which ensures it has bi-directional
communication to and from the nodes. The router allows us to create a low
latency mesh which monitors node health and ensures is highly responsive
instruction delivery network.

![Directord-Data-flow](assets/Directord-Data-flow.png)

The application flow has been built to best enable asynchronous operations,
easily scaling to hundreds of clients without impacting throughput. While the
User is expected to interact with the system via CLI, Directord does provide
bindings for programable interfaces.

### Data storage and persistance

Directord has two modes of operation for data-storage and persistence.

* Ephemeral mode, only retain cluster and job information so long as the server
  process is running.

* Persistent mode, datastore using external datastore; supported datastores
  are: Redis and File. The datastore option available in both config, or on the
  CLI and uses a standard RFC-1738 compatible string. This allows operators to
  connect to different storage backends to suit their environment needs.

> Storing information persistently introduces a dependency on an external
  system and creates latency. While the latency should be minimal, and have
  nearly no impact on task execution, it is something that needs to be considered
  when constructing the cluster topology. Inversely, using an external datastore
  will lower the memory utilization of Directord and can have a profound effect
  on deployment node requirements; this is especially true at hyper-scale.

> The `datastore` option has three potential drivers, **memory**, **file**,
  or **redis**.

> If the datastore option is set to **memory**, the server will spawn a manager
  thread to facilitate the document store.

#### Profiling

Every Directord task is profiled. The execution and the round trip time are
stored and made available when inspecting jobs. This builtin profiling allows
operators to better understand their deployment workloads.

* ROUNDTRIP_TIME: Time taken from task transmit to return. The server will
  timestamp every task when spawned, and will store the delta when the return
  data is received by the server.

* EXECUTION_TIME: Time taken to run a particular task. The client will
  timestamp every task before execution and return the delta once the task
  exits.

To further understand deployment characteristics, Directord also provides an
*analyze* function which will allow operators to dig deeper into their data.
The job and parent analyze functions will highlight outliers, node
discrepancies, failures, and performance for entire orchestrations.

``` shell
$ sudo /opt/directord/bin/directord orchestrate ~/directord/tests/comparison-orchestration.yaml --target directord-{0..5} --wait

# Note the ID used in this command is the "Parent" UUID for a given orchestration
$ sudo /opt/directord/bin/directord manage --analyze-parent fd9c7387-de10-420f-92fe-2ac0a4716c8d
KEY                       VALUE
------------------------  ------------------------------------
ID                        fd9c7387-de10-420f-92fe-2ac0a4716c8d
ACTUAL_RUNTIME            20.34541606903076
COMBINED_EXECUTION_TIME   61.21946573257446
FASTEST_NODE_EXECUTION    directord-0
FASTEST_NODE_ROUNDTRIP    directord-0
SLOWEST_NODE_EXECUTION    directord-4
SLOWEST_NODE_ROUNDTRIP    directord-4
TOTAL_AVG_EXECUTION_TIME  0.06121946573257446
TOTAL_FAILURES            0
TOTAL_JOBS                1000
TOTAL_NODE_COUNT          6
TOTAL_SUCCESSES           6000

Total Items: 12
```

## Comparative Analysis

Because Directord is task driven and messaging backed it is fast, Directord's
time to work is measured in microseconds with return trip times measured in
milliseconds.

To test interactions we used comparison files from the tests directory which
run 1000 tasks across a small 6 node environment.

### Test Results

The following stats were gathered from a deployment host with 4 AMD Opteron
6380 Cores, 4 GiB DDR3, 1 GiB Bonded link, and 32GiB of NVME Storage.

The Six target machines are running 4 AMD Opteron 6380 Cores, 8 GiB DDR3, 1 GiB
Bonded link, and 64GiB of NVME Storage.

| Service                                | Actual Runtime (Seconds) |
| -------------------------------------- | ------------------------ |
| Directord                              | 20                       |
| Directord (async)                      | 15                       |
| Ansible (defaults)                     | 1947                     |
| Ansible (Pipelining)                   | 1556                     |
| Ansible (Pipelining and Free strategy) | 949                      |

### Analysis, Setup and Overview

The following sections detail what was tested and how.

#### Directord

Directord installation was performed in a virtual environment using Directord
version 0.11.0.

``` shell
sudo /opt/directord/bin/pip install --pre directord
```

> Server setup was performed using the documented
  [installation](installation.md#installation) process.

##### Directord Defaults

> The Directord defaults were used across the board.

* Run the Directord orchestration command to execute 1000 trivial jobs.

``` shell
$ sudo /opt/directord/bin/directord orchestrate ~/directord/tests/comparison-orchestration.yaml --target directord-{0..5}
```

Running the comparison orchestration file with a six node test environment
returns an actual run time of **20** seconds.

##### Directord with Async Orchestrations

* Run the directord orchestration command to execute 1000 trival jobs in 10
  asynchronous orchestrations.

``` shell
$ sudo /opt/directord/bin/directord orchestrate ~/directord/tests/comparison-orchestration-async.yaml --target directord-{0..5}
```

Running the comparison orchestration file with a six node test environment
returns an actual run time of **15** seconds.

##### Directord with Bootstrapping

The directord cluster was bootstrapped with the
[Native Bootstrap](installation.md#bootstrap-natively) process. Before running
these tests the bootstrap process had to be completed ahead of time. The
example bootstrap process took **81** seconds (1.5 minutes) to complete.

* Total execution time, including bootstrapping the environment was **101**
  seconds (1.69 minutes) using one linear orchestration.

* Total execution time, including bootstrapping the environment was **96**
  seconds (1.6 minutes) using one linear orchestration.

#### Ansible

Ansible installation was performed in a virtual environment using Ansible
version 4.6.0 and Ansible-Core version 2.11.5.

``` shell
sudo /opt/directord/bin/pip install ansible
```

##### Ansible Defaults

* Run the Ansible playbook command to execute 1000 trivial tasks.

``` shell
$ ansible-playbook -i tools/ansible-inventory.yaml tests/comparison-tasks-playbook.yml
```

Running the comparison orchestration file with a six node test environment
returns an actual run time of **1947** seconds (32.45 minutes).

##### Ansible with Pipelining

* The following configuration file was used to setup the ansible environment.

``` ini
[defaults]
host_key_checking = False
callback_whitelist = profile_tasks

[ssh_connection]
ssh_args = -o ForwardAgent=yes -o ControlMaster=auto -o ControlPersist=60s
pipelining = true
```

* Run the Ansible playbook command to execute 1000 trivial tasks.

``` shell
$ ansible-playbook -i tools/ansible-inventory.yaml tests/comparison-tasks-playbook.yml
```

Running the comparison orchestration file with a six node test environment
returns an actual run time of **1556** seconds (25.93 minutes).

###### Ansible with Pipelining and Free Strategy

* Run the Ansible playbook with the free strategy to execute 1000 trivial
  tasks.

``` shell
$ ansible-playbook -i tools/ansible-inventory.yaml tests/comparison-tasks-playbook-free.yml
```

Running the comparison orchestration file with a six node test environment
returns an actual run time of **949** seconds (15.82 minutes).

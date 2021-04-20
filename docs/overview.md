# Director Components

* TOC
{:toc}

Director is a single application which consists of three parts:

* **Server** - The server is the centralized manager of all communication and
  application delivery.

* **Client** - The client is the minimal application required for enrolling a
  node into a given cluster.

* **User** - CLI utility which interfaces with the server over a local socket
  connect.

Director allows for the user to configure the application using environment
variables, a configurations file, or command line switches.

> NOTE: Because the user interface communicates with the server over a UNIX
  socket, the User and Server components are assumed to exist on the same
  machine.

![Director](assets/Director.png)

### Cluster Messaging

The cluster messaging uses a router format which ensures it has bi-directional
communication to and from the nodes. The router allows us to create a low
latency mesh which monitors node health and ensures is highly responsive
instruction delivery network.

![Director-Data-flow](assets/Director-Data-flow.png)

### Comparative Analysis

Because Director is task driven and messaging backed it is fast, Directors time
to work is measured in microseconds with return trip times measured in
milliseconds.

To test interactions we used comparison files from the tools director to run 1000
tasks across a small 6 node test environment.

#### Director

> The statistics recorded here were provide by the Director application.
  Execution time and roundtrip time are recorded as part of regular job
  interactions.

The director cluster was bootstrapped with the
[Native Bootstrap](installation.md#bootstrap-natively) process. Before running
these tests this process had to be completed ahead of time.

* Run the Director orchestration command to execute 1000 trivial jobs.

``` shell
$ director orchestrate --ignore-cache tools/comparison-orchestration.yaml
```

Running the comparison orchestration file with a six node test environment
returns an execution time of **19.41** seconds.

The system also saw the following command characteristics. Each message had the
following average profile.

| EXECUTION_TIME       | TOTAL_ROUNDTRIP_TIME    |
| -------------------- | ----------------------- |
| 0.007496356964111328 | 0.01715874671936035     |

#### Ansible

Ansible installation was performed in a virtual environment using Ansible
version 3.2.x and Ansible-Base version 2.10.X.

> The statistics recorded here were provide by the Ansible profile callback.

Export environment variables to pull and profile all tasks.

``` shell
$ export PROFILE_TASKS_SORT_ORDER=none
$ export PROFILE_TASKS_TASK_OUTPUT_LIMIT=all
$ export ANSIBLE_CONFIG=tools/ansible.cfg
```

* Run the Ansible playbook command to loop over all 1000 trivial tasks.

``` shell
$ ansible-playbook -i tools/ansible-inventory.yaml tools/comparison-loop-playbook.yml
```

This command runs one shell task with 1000 items within a loop.

| EXECUTION_TIME       |
| -------------------- |
| 1947.63              |

Running the comparison loop playbook with a six node test environment
returns an execution time of **1947** seconds (32 minutes).

* Run the Ansible playbook command to execute 1000 trivial tasks.

``` shell
$ ansible-playbook -i tools/ansible-inventory.yaml tools/comparison-task-playbook.yml
```

This command runs 1000 shell tasks.

| TOTAL_ROUNDTRIP_TIME    |
| ----------------------- |
| 1.793                   |

Running the comparison task playbook with a six node test environment
returns an execution time of **1811.089** seconds (30 minutes).

* Run the Ansible playbook command to execute 1000 trivial tasks with pipelining enabled.

To enable pipelining the export `ANSIBLE_PIPELINING` was set **True**.

``` shell
$ export ANSIBLE_PIPELINING=True
$ ansible-playbook -i tools/ansible-inventory.yaml tools/comparison-task-playbook.yml
```

This command runs 1000 shell tasks.

| TOTAL_ROUNDTRIP_TIME    |
| ----------------------- |
| 0.941                   |

Running the comparison task playbook with a six node test environment
returns an execution time of **963.739** seconds (17 minutes).

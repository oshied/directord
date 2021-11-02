# Comparative Analysis

* TOC
{:toc}

Because Directord is task driven and messaging backed it is fast, Directord's
time to work is measured in microseconds with return trip times measured in
milliseconds.

To test interactions we used comparison files from the tests directory which
run 1000 tasks across a small 6 node environment.

## Analysis, Setup and Overview

he following sections detail what was tested and how. All of the tools used for
these tests are provided within the Directord
[repository](https://github.com/directord/directord).

The server used (orchestration node) within the test environment was a
standalone machine, which was not part of the test executions. The server only
facilitated the test operation. This was done to not artificially boost any of
our results. By forcefully using a server we're creating a network environment
which would be similar one found within production environments.

The server was deployed using the following characteristics

* 4 AMD Opteron 6380 Cores

* 4 GiB DDR3 RAM

* 1 GiB Bonded link

* 32GiB of NVME Storage.

All client targets within the test environment used the same configuration.

* 4 AMD Opteron 6380 Cores

* 8 GiB DDR3 RAM

* 1 GiB Bonded link

* 64GiB of NVME Storage

> The test environment was built in virtual machines, and dedicated 100%
  access to all resources provided to them. There was no use of shared
  memory, cores, storage.

To ensure that the tests were as fair as possible, all tests were first run
using default configurations. Later tests were run using asynchronous
strategies to ensure all of the common basis were covered for our results. In
the case of Ansible, Non-standard configuration was used to ensure we're able
also test using even more optimized execution processes.

### Test Results

The following results cover all the tests executed. All tests were performed
until they ran to completion. The results were then collected using each tools
built-in profiling apparatus; results were further verified using system time
as a point of correlation.

| Service                 | Configuration    | Actual Runtime (Seconds) |
| ----------------------- | ---------------- | ------------------------ |
| Directord               | ZMQ Driver       | 19                       |
| Directord (async)       | ZMQ Driver       | 15                       |
| Directord               | Messaging Driver | 101                      |
| Directord (async)       | Messaging Driver | 99                       |
| Ansible                 | Defaults         | 1947                     |
| Ansible                 | Pipelining       | 1556                     |
| Ansible (free strategy) | Pipelining       | 949                      |

> The configuration and installation process for each of these test
  environments is within the following subsections.

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
$ sudo /opt/directord/bin/directord orchestrate tests/comparison-orchestration.yaml --target directord-{0..5}
```

Running the comparison orchestration file with a six node test environment
returns an actual run time of **19** seconds.

##### Directord Defaults with Async Orchestrations

* Run the directord orchestration command to execute 1000 trivial jobs in 10
  asynchronous orchestrations.

``` shell
$ sudo /opt/directord/bin/directord orchestrate tests/comparison-orchestration-async.yaml --target directord-{0..5}
```

Running the comparison async orchestration file with a six node test
environment returns an actual run time of **15** seconds.

##### Directord Messaging Driver

> The Messaging driver was deployed following the
  [installation](installation.md#installation) process using the
  `directord-dev-bootstrap-messaging-catalog.yaml` catalog.

* Run the Directord orchestration command to execute 1000 trivial jobs.

``` shell
$ sudo /opt/directord/bin/directord orchestrate tests/comparison-orchestration.yaml --target directord-{0..5}
```

Running the comparison orchestration file with a six node test environment
returns an actual run time of **101** seconds (1.68 minutes).

##### Directord Messaging Driver with Async Orchestrations

> The Messaging driver was deployed following the
  [installation](installation.md#installation) process using the
  `directord-dev-bootstrap-messaging-catalog.yaml` catalog.

* Run the Directord orchestration command to execute 1000 trivial jobs.

``` shell
$ sudo /opt/directord/bin/directord orchestrate tests/comparison-orchestration-async.yaml --target directord-{0..5}
```

Running the comparison orchestration file with a six node test environment
returns an actual run time of **99** seconds (1.65 minutes).

##### Directord with Bootstrapping

> The directord cluster was bootstrapped with the
  [Native Bootstrap](installation.md#bootstrap-natively) process. Before
  running these tests the bootstrap process had to be completed ahead of
  time. The example bootstrap process took **81** seconds (1.5 minutes)
  to complete.

* Total execution time for the ZMQ driver with an linear orchestration,
  including bootstrapping the environment was **100** seconds
  (1.69 minutes).

* Total execution time for the ZMQ driver with an async orchestration,
  including bootstrapping the environment was **96** seconds (1.6 minutes).

* Total execution time for the Messaging driver with an linear orchestration,
  including bootstrapping the environment was **182** seconds (3.03 minutes).

* Total execution time for the Messaging driver with an async orchestration,
  including bootstrapping the environment was **180** seconds (3 minutes).

#### Ansible

Ansible installation was performed in a virtual environment using Ansible
version 4.6.0 and Ansible-Core version 2.11.5.

``` shell
sudo /opt/directord/bin/pip install Ansible
```

##### Ansible Defaults

* Run the Ansible playbook command to execute 1000 trivial tasks.

``` shell
$ ansible-playbook -i tools/ansible-inventory.yaml tests/comparison-tasks-playbook.yml
```

Running the comparison orchestration file with a six node test environment
returns an actual run time of **1947** seconds (32.45 minutes).

##### Ansible with Pipelining

* The following configuration file was used to setup the Ansible environment.

``` ini
[defaults]
host_key_checking = False
callback_whitelist = profile_tasks

[ssh_connection]
ssh_args = -o ForwardAgent=yes -o ControlMaster=auto -o ControlPersist=60s
pipelining = true
```

* Running the Ansible playbook command using pipelining to execute 1000 trivial
  tasks.

``` shell
$ ansible-playbook -i tools/ansible-inventory.yaml tests/comparison-tasks-playbook.yml
```

Running the comparison orchestration file with a six node test environment
returns an actual run time of **1556** seconds (25.93 minutes).

###### Ansible with Pipelining and Free Strategy

* Running the Ansible playbook command using pipelining and the **free**
  strategy to execute 1000 trivial tasks.

``` shell
$ ansible-playbook -i tools/ansible-inventory.yaml tests/comparison-tasks-playbook-free.yml
```

Running the comparison free strategy orchestration file with a six node test
environment returns an actual run time of **949** seconds (15.82 minutes).

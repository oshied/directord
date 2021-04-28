# Orchestration file specification

* TOC
{:toc}

Orchestration files allow directord to run any number of jobs against a given
set of targets. The specification file is simple and made to be easy. Each
file is loaded as an array and can contain many jobs.

The values available within an orchestration file are `targets` and `jobs`.

* `targets` is an array of strings.

* `jobs` is an array of hashes.

``` yaml
---
- targets: []
  jobs: []
```

Within the orchestration file the "target" key is optional. If this key is
undefined, Directord will run against all available targets.

``` yaml
---
- jobs: []
```

Running jobs requires each item be a key=value pair. The key is a VERB used for
the given command and the value is the execution.

``` yaml
---
- jobs:
  - RUN: "echo hello world"
```

> Several CLI options are available when orchestrating a deployment, such as
  `--restrict` and `--ignore-cache`. These option provide for the ability to
  replay specific tasks or forcefully ignore the client side cache.

##### Example Orchestration file

This example orchestration file will copy the local client ssh keys from the
directory `/home/centos/.ssh` to all nodes within the clister. Then, on the
three noted targets, `wget` will be installed.

``` yaml
---
- jobs:
  - WORKDIR: /home/centos/.ssh
  - RUN: chmod 600 /home/centos/.ssh/* && chmod 700 /home/centos/.ssh
  - ADD: --chown=centos:centos /home/centos/.ssh/* /home/centos/.ssh/
- targets:
  - df.next-c1.localdomain-client-1
  - df.next-c2.localdomain-client-1
  - df.next-c3.localdomain-client-1
  jobs:
  - RUN: dnf install -y wget
```

Upon the execution of each job, a new UUID will be presented to you for
tracking purposes. This information can be used with the manage commands.

Running an orchestration is simple and follows the same pattern as running an
adhoc execution.

``` shell
$ directord orchestrate ${ORCHESTRATION_FILE_NAME} [<switches> ...]
```

#### Orchestration Library Usage

Running orchestration jobs can also be run using the library. This allows
operators to define jobs in out of band task flows and provides and interface
into Directord that is not strictly defined by shell interactions.

``` python
# Import the required modules.
from directord import mixin, user

# Define a minimal set of arguments.
class args(object):
    debug=False
    socket_path='/var/run/directord.sock'
    mode='orchestrate'

# Define your job(s).
job = {
    "targets": [
        "host1",
        "host2"
    ],
    "jobs": [
        {
            "RUN": "echo hello world"
        }
    ]
}

# Initialize the user interactions
u = user.User(args=args)

# Run the orchestration execution
m = mixin.Mixin(args=args)

# Note, many jobs can be defined in an array of orchestrations.
jobs = m.exec_orchestrations(
    user_exec=u,
    orchestrations=[job],
    raw_return=True  # Returns just the UUID(s)
)

# Poll for job completion
for item in [i.decode() for i in jobs]:
    # Each poll will return True|False on job outcome, and a String.
    status_boolean, info = m.poll_job(job_id=item)
```

The return from `exec_orchestrations` is an array of byte encoded UUID, which
are the ID's for the submitted jobs, breaking out as one UUID for each target
and job combination.

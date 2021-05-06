
# Library Usage

* TOC
{:toc}

Interfacing with Directord is simple with the library connection manager.

Running orchestration jobs, listing nodes, inspecting jobs and more can all be
managed with an easy to use context manager.

``` python
# Import the required module.
from directord import DirectordConnect


# Define your job(s). Jobs are an list of dictionaries which defines a set of
# tasks to run against the cluster. To limit node interactions targets can be
# defined. See https://directord.com/orchestrations.html for more on what's
# possible.
jobs = [
    {
        "jobs": [
            {
                "RUN": "echo hello world"
            }
        ]
    }
]


with DirectordConnect() as d:
    # Run orchestrations.
    ids = d.orchestrate(
        orchestrations=jobs
    )
    for job_id in ids:
        status_boolean, info = d.poll(job_id=job_id)

    # List all active nodes
    nodes = d.list_nodes()

    # List executed jobs
    jobs = d.list_jobs()
```

The return from `orchestrate` is an array of UUIDs, which are the ID's for the
submitted jobs.

### Methods

`DirectorConnect` can be used as a context manager or via object and is built as
a convince method to better help developers and operators streamline their
applications.

##### DirectorConnect

Initialize the connection.

* *param `debug` Enable|Disable debug mode.
* *type `debug` `Boolean`
* *param `socket_path` Socket path used to connect to Directord.
* *type `socket_path` `String`

###### orchestrate

Run an orchestration and return a list of job IDs.

* param `orchestrations` List of dictionary objects used to run orchestrations.
* type `orchestrations` `List`
* param `defined_targets` List of Directord Targets.
* type `defined_targets` `List`
* returns: `List`

###### poll

Poll for the completion of a given job ID.

* *param `job_id` Job UUID.
* *type `job_id` `String`
* *returns `Tuple`

###### list_nodes

Return a list of all active Directord Nodes.

* *returns `List`

###### list_jobs

Return a dictionary of all current Directord jobs.

* *returns `Dictionary`

###### purge_nodes

Purge all nodes from the pool, all remaining active nodes will
recheck-in and be added to the pool.

* returns `Boolean`

###### purge_jobs

purge all jobs from the return manager.

* returns `Boolean`

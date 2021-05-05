
# Library Usage

* TOC
{:toc}

Interfacing with Directord is simple with the library connection manager.

Running orchestration jobs, listing nodes, inspecting jobs and more can all be
managed with an easy to use context manager.

``` python
# Import the required module.
from directord import DirectordConnect


# Define your job(s).
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

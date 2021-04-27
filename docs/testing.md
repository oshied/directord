# Testing Interactions

* TOC
{:toc}

Lots of client containers can be created to test full scale interactions. This
simple example shows how that could be done on a single machine.

``` shell
# Pull the directord container from quay
$ podman pull quay.io/cloudnull/directord

# Start the server
$ directord --debug --shared-key secrete server --bind-address 127.0.0.1 &

# Run 40 client containers
$ for i in {1..40}; do
  podman run --hostname $(hostname)-client-${i} \
             --name $(hostname)-client-${i} \
             --net=host \
             --env DIRECTOR_SERVER_ADDRESS=127.0.0.1 \
             --env DIRECTOR_SHARED_KEY=secrete \
             --user 0 \
             --detach \
             directord directord
done
```

Once running the clients will connect to the server which will stream log
output.

### Running the functional tests

With Directord running, with at least one client, the functional test
orchestration file can be used to exercise the entire suit of tooling. For the
functional tests to work the will need to be executed from the "orchestrations"
directordy within the local checkout of this repository.

``` shell
$ directord orchestrate functional-tests.yaml --ignore-cache
```

This will run the functional tests and ignore all caching all client nodes when
executing. The reason all caching is ignored is to ensure that the application
is executing what we expect on successive test runs.

Once the test execution is complete, the following oneliner can be used to
check for failure and then dump the jobs data to further diagnose problems.

``` shell
$ (directord manage --list-jobs | grep False) && directord manage --export-jobs jobs-failure-information.yaml
```

Run the `--purge-jobs` management command to easily clear the job information
before testing again.

``` shell
directord manage --purge-jobs
```

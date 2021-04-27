ARG VERSION=0.1.0

FROM registry.access.redhat.com/ubi8/python-38 as BUILD

LABEL summary="Directord server used to orchestrate system deployments." \
      description="Directord server used to orchestrate system deployments." \
      io.k8s.description="Directord server used to orchestrate system deployments." \
      io.k8s.display-name="Directord server container" \
      io.openshift.expose-services="5555:job,5556:status,5557:heartbeat" \
      io.openshift.tags="cloudnull,directord" \
      name="directord" \
      version="${VERSION}" \
      maintainer="cloudnull.io <kevin@cloudnull.com>"

USER root

WORKDIR /build
RUN python3.8 -m venv /build/builder
RUN /build/builder/bin/pip install --force --upgrade pip setuptools bindep wheel
ADD . /build/
RUN bash -c "/build/tools/dev-setup.sh /directord /bin/python3.8"

FROM registry.access.redhat.com/ubi8/ubi-minimal
EXPOSE 5555
EXPOSE 5556
EXPOSE 5557
COPY --from=BUILD /etc/yum.repos.d /etc/yum.repos.d
RUN microdnf install -y openssh-clients python3.8 zeromq libsodium && rm -rf /var/cache/{dnf,yum}
RUN /bin/python3.8 -m venv --upgrade /directord
COPY --from=BUILD /directord /directord
ADD assets/entrypoint /bin/entrypoint
RUN chmod +x /bin/entrypoint
USER 1001
ENTRYPOINT ["entrypoint"]

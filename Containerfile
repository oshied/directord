ARG VERSION=0.1.2

FROM registry.access.redhat.com/ubi8/python-39 as BUILD

LABEL summary="Directord used to orchestrate system deployments." \
      description="Directord used to orchestrate system deployments." \
      io.k8s.description="Directord used to orchestrate system deployments." \
      io.k8s.display-name="Directord container" \
      io.openshift.expose-services="5555:job,5556:status,5557:heartbeat" \
      io.openshift.tags="cloudnull,directord" \
      name="directord" \
      version="${VERSION}" \
      maintainer="cloudnull.io <kevin@cloudnull.com>"

USER root

WORKDIR /build
RUN python3.9 -m venv /build/builder
RUN /build/builder/bin/pip install --force --upgrade pip setuptools bindep wheel
ADD . /build/
RUN bash -c "EXTRA_DEPENDENCIES=all /build/tools/dev-setup.sh /directord /bin/python3.9 /build false"

FROM registry.access.redhat.com/ubi8/ubi-minimal
EXPOSE 5555
EXPOSE 5556
EXPOSE 5557
COPY --from=BUILD /etc/yum.repos.d /etc/yum.repos.d
COPY --from=BUILD /etc/pki /etc/pki
RUN microdnf install -y openssh-clients python3.9 zeromq libsodium hostname && rm -rf /var/cache/{dnf,yum}
RUN /bin/python3.9 -m venv --upgrade /directord
COPY --from=BUILD /directord /directord
ADD assets/entrypoint /bin/entrypoint
RUN chmod +x /bin/entrypoint
USER 1001
ENTRYPOINT ["entrypoint"]

%global pypi_name directord
%{?!released_version: %global released_version 0.11.3}
%{?git_ref: %global directord_version git%{git_ref}}
%{!?git_ref: %global directord_version %{released_version}}

Name:           %{pypi_name}
Release:        1%{?dist}
Summary:        A deployment framework built to manage the data center life cycle

License:        None
URL:            https://github.com/directord/directord
Version:        %{directord_version}
Source0:        directord.tar.gz

BuildArch:      noarch

BuildRequires:  python3-devel
BuildRequires:  python3-coverage
BuildRequires:  python3-flake8
BuildRequires:  python3-flask
BuildRequires:  python3-jinja2
BuildRequires:  python3-pyyaml
BuildRequires:  python3-setuptools
BuildRequires:  python3-tabulate
BuildRequires:  python3-tenacity
BuildRequires:  python3-oslo-messaging
BuildRequires:  systemd-rpm-macros

# Source Build Requirements
# TODO(cloudnull): This needs to be packaged officially
BuildRequires:  python3-ssh-python

Requires:       python3-jinja2
Requires:       python3-pyyaml
Requires:       python3-tabulate
Requires:       python3-tenacity

# Recommends
Recommends:       python3-ssh-python
Recommends:       python3-zmq
Recommends:       python3-redis
Recommends:       python3-flask
Recommends:       python3-oslo-messaging
Recommends:       python3-grpcio <= 1.26.0
Recommends:       python3-protobuf

# Source Recommends
# TODO(cloudnull): This needs to be packaged officially
Recommends:     python3dist(podman-py)

Requires(pre):    shadow-utils

%description
Directord deployment framework built to manage the data center life cycle.>
Task driven deployment, simplified, directed by you.Directord is an
asynchronous deployment and operations platform with the aim to better enable
simplicity, faster time to delivery, and consistency.

%pre
getent group directord >/dev/null || groupadd -r directord
exit 0

%prep
%autosetup -n %{pypi_name}
# Remove bundled egg-info
rm -rf %{pypi_name}.egg-info

%build
%py3_build

%install
%py3_install
mkdir -p %{buildroot}/%{_sysconfdir}/directord
mkdir -p %{buildroot}/%{_sysconfdir}/directord/private_keys
mkdir -p %{buildroot}/%{_sysconfdir}/directord/public_keys
mkdir -p %{buildroot}/%{_unitdir}
cp %{buildroot}/%{_datadir}/directord/systemd/directord-server.service %{buildroot}/%{_unitdir}
cp %{buildroot}/%{_datadir}/directord/systemd/directord-client.service %{buildroot}/%{_unitdir}

%check
# (slagle) Disable unit tests for the time being
true

%files
%license LICENSE
%doc README.md
%{_bindir}/directord
%{_bindir}/directord-client-systemd
%{_bindir}/directord-server-systemd
%{_datadir}/directord/components
%{_datadir}/directord/orchestrations
%{_datadir}/directord/pods
%{_datadir}/directord/tools
%{python3_sitelib}/%{pypi_name}
%{python3_sitelib}/%{pypi_name}-%{released_version}-py%{python3_version}.egg-info
%{_sysconfdir}/directord

%package server
Summary:        Server components for Directord

%description server
Server components for Directord, including the Systemd unit files

%files server
%{_bindir}/directord-server-systemd
%{_unitdir}/directord-server.service
%{_datadir}/directord/systemd/directord-server.service

%package client
Summary:        Client components for Directord

%description client
Client components for Directord, including the Systemd unit files

%files client
%{_bindir}/directord-client-systemd
%{_unitdir}/directord-client.service
%{_datadir}/directord/systemd/directord-client.service

%changelog
* Thu Jul 29 2021 Kevin Carter <kecarter@redhat.com>
- Initial package.

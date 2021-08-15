# Created by pyp2rpm-3.3.7
%global pypi_name directord
%define _unpackaged_files_terminate_build 0

Name:           python-%{pypi_name}
Release:        1%{?dist}
Summary:        A deployment framework built to manage the data center life cycle

License:        None
URL:            https://github.com/cloudnull/directord
Version:        XXX
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

# Source Build Requirements
# TODO(cloudnull): This needs to be packaged officially
BuildRequires:  python3-diskcache

%description
 DirectordA deployment framework built to manage the data center life cycle.>
Task driven deployment, simplified, directed by you.Directord is an
asynchronous deployment and operations platform with the aim to better enable
simplicity, faster time to delivery, and consistency. Design PrinciplesThe
Directord design principles can be [found here]( DocumentationAdditional
documentation covering...

%package -n     python3-%{pypi_name}
Summary:        %{summary}
%{?python_provide:%python_provide python3-%{pypi_name}}

Requires:       python3-flask
Requires:       python3-jinja2
Requires:       python3-pyyaml
Requires:       python3-tabulate
Requires:       python3-tenacity

# Source Requirements
# TODO(cloudnull): This needs to be packaged officially
Requires:       python3-diskcache

# Recommends
Recommends:       python3-zmq
Recommends:       python3-redis

# Source Recommends
# TODO(cloudnull): This needs to be packaged officially
Recommends:     python3dist(podman-py)

%description -n python3-%{pypi_name}
 DirectordA deployment framework built to manage the data center life cycle.>
Task driven deployment, simplified, directed by you.Directord is an
asynchronous deployment and operations platform with the aim to better enable
simplicity, faster time to delivery, and consistency. Design PrinciplesThe
Directord design principles can be [found here]( DocumentationAdditional
documentation covering...


%prep
%autosetup -n %{pypi_name}
# Remove bundled egg-info
rm -rf %{pypi_name}.egg-info

%build
%py3_build

%install
%py3_install

%check
%{__python3} setup.py test

%files -n python3-%{pypi_name}
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

%changelog
* Thu Jul 29 2021 Kevin Carter <kecarter@redhat.com>
- Initial package.

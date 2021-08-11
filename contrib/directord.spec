# Created by pyp2rpm-3.3.7
%global pypi_name directord
%global pypi_version 0.6.0

Name:           python-%{pypi_name}
Version:        %{pypi_version}
Release:        1%{?dist}
Summary:        A deployment framework built to manage the data center life cycle

License:        None
URL:            https://github.com/cloudnull/directord
Source0:        %{pypi_source}
BuildArch:      noarch

BuildRequires:  python3-devel
BuildRequires:  python3dist(coverage)
BuildRequires:  python3dist(diskcache)
BuildRequires:  python3dist(flake8)
BuildRequires:  python3dist(flask)
BuildRequires:  python3dist(jinja2)
BuildRequires:  python3dist(paramiko)
BuildRequires:  python3dist(podman-py)
BuildRequires:  python3dist(pyyaml)
BuildRequires:  python3dist(pyzmq)
BuildRequires:  python3dist(redis)
BuildRequires:  python3dist(setuptools)
BuildRequires:  python3dist(tabulate)
BuildRequires:  python3dist(tenacity)

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

Requires:       python3dist(coverage)
Requires:       python3dist(diskcache)
Requires:       python3dist(flake8)
Requires:       python3dist(flask)
Requires:       python3dist(jinja2)
Requires:       python3dist(paramiko)
Requires:       python3dist(podman-py)
Requires:       python3dist(pyyaml)
Requires:       python3dist(pyzmq)
Requires:       python3dist(redis)
Requires:       python3dist(setuptools)
Requires:       python3dist(tabulate)
Requires:       python3dist(tenacity)
%description -n python3-%{pypi_name}
 DirectordA deployment framework built to manage the data center life cycle.>
Task driven deployment, simplified, directed by you.Directord is an
asynchronous deployment and operations platform with the aim to better enable
simplicity, faster time to delivery, and consistency. Design PrinciplesThe
Directord design principles can be [found here]( DocumentationAdditional
documentation covering...


%prep
%autosetup -n %{pypi_name}-%{pypi_version}
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
%doc README.md orchestrations/README.md
%{_bindir}/directord
%{_bindir}/directord-client-systemd
%{_bindir}/directord-server-systemd
%{python3_sitelib}/%{pypi_name}
%{python3_sitelib}/%{pypi_name}-%{pypi_version}-py%{python3_version}.egg-info

%changelog
* Thu Jul 29 2021 Kevin Carter <kecarter@redhat.com> - 0.6.0-1
- Initial package.

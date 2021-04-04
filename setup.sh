dnf install -y https://trunk.rdoproject.org/centos8/component/tripleo/current/python3-tripleo-repos-0.1.1-0.20210118183911.2cfaa48.el8.noarch.rpm
tripleo-repos --stream -b master current-tripleo ceph

dnf install -y zeromq python3 etcd

# development packages
dnf install -y gcc

# Create development workspace
python -m venv /opt/director
/opt/director/bin/pip install --upgrade pip setuptools wheel

# Python packages will need a corresponding RPM
/opt/director/bin/pip install pyzmq etcd3

#!/bin/bash
set -m
sudo ~/venvs/dd/bin/directord --config-file /etc/directord/config.yaml server --zmq-bind-address 0.0.0.0 &
sleep 4
sudo chgrp $USER /var/run/directord.sock  && sudo chmod g+w /var/run/directord.sock
fg %1

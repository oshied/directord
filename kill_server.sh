#!/bin/bash
ps aux | grep zmq-bind-address | grep -v grep | awk {'print $2'} | xargs sudo kill

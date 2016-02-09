#!/bin/bash

cd /opt/wg++

mono WebGrab+Plus.exe  "$(pwd)"
exit $?

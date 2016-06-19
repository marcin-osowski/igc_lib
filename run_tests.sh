#!/bin/bash
set -e

if [ -z "$1" ]; then
    # No argument provided - run all tests
    /usr/bin/env python -m unittest discover
else
    /usr/bin/env python -m unittest $1
fi

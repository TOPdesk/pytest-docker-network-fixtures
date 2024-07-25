#!/usr/bin/env bash

rm -rf build/*

sphinx-build -a -E -b html ./source build/html

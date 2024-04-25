#!/usr/bin/python3
# encoding: utf-8
'''
onDemand -- Iot on demand !

onDemand is a embedded service to connect to IOT platform

@author:     Bertrand Verdu

@copyright:  2015 LazyTech. All rights reserved.

@license:    LGPL 2.1

@contact:    contact@lazytech.io
@deffield    updated: Updated
'''
import os
import sys
from twisted.scripts.twistd import run

sys.path.insert(0, os.path.abspath(os.getcwd()))  # @UndefinedVariable
t_args = []
t_args += ['--nodaemon', '--pidfile=',
           '--originalname', '-n', 'pianocktail', '--port', 'tcp:4242']
print(t_args)
sys.argv[1:] = t_args + sys.argv[1:]

# import tracemalloc
# tracemalloc.start()
# from twisted.scripts.twistd import run
run()

#!/usr/bin/env python

import PyTango

def killdev(d):
  try:
    dp = PyTango.DeviceProxy(d)
    if dp.ping(): dp.Kill()
  except:
    pass
  
killdev('dserver/eventtestds/test1')
killdev('dserver/eventtestds/test2')
killdev('dserver/eventtestds/test3')
killdev('dserver/eventtestds/test4')

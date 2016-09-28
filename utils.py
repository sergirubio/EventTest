#!/usr/bin/env python

import sys,traceback,re,time,threading
import fandango as fn
from fandango.objects import *

class ThreadedObject(Object):
  """
  An Object with a thread pool that provides safe stop on exit
  
  Created to allow safe thread usage in Tango Device Servers
  
  Statistics and execution hooks are provided
  """
  
  def __init__(self,target=None,period=1.,nthreads=1,min_wait=1e-5):

    self._event = threading.Event()
    self._stop = threading.Event()
    self._done = threading.Event()
    self._kill = threading.Event()
    self._min_wait = 1e-5
    self._count = -1
    self._errors = 0
    self._delay = 0
    self._acc_delay = 0
    self._usage = 1.
    
    self._threads = []
    for i in range(nthreads):
      self._threads.append(threading.Thread(target=self.loop))
      self._threads[i].daemon = True

    self.set_period(period)
    self.set_target(target)
    self.stop(wait=False)
    
    for t in self._threads: 
      t.start()
      
  def __del__(self):
    self.kill()
    
  ## HELPERS
    
  def get_count(self): return self._count
  def get_errors(self): return self._errors
  def get_delay(self): return self._delay
  def get_acc_delay(self): return self._acc_delay
  def get_usage(self): return self._usage
  def get_next(self): return self._next
      
  def get_thread(self,i=0): return self._threads[i]
  def get_nthreads(self): return len(self._threads)
  def is_alive(self,i=0): return self.get_thread().is_alive()
    
  def set_period(self,period): self._timewait = period
  def set_target(self,target): self._target = target
  
  ## MAIN METHODS
    
  def start(self):
    #self._event.clear()
    self._done.clear()
    self._stop.clear()
    
  def stop(self,wait=3.):
    self._event.clear()
    self._stop.set()
    if wait:
      self._done.wait(wait)
      self._done.clear()
      
  def kill(self):
    self._kill.set()
    self._stop.set()
    self._event.set()
      
  def start_hook(self,*args,**kwargs):
    """ redefine at convenience, it will return the arguments for target method """
    return [],{}
    print('Starting push_loop(%s)'%self._timewait)
    print('Sending %d events in bunches of %d every %f seconds'%(
      self.MaxEvents,self.ConsecutiveEvents,self._timewait))
    
    t0,t1,ts,self.send_buffer = time.time(),0,0,[]
    tnext = t0 + self._timewait  
    
  def loop_hook(self,*args,**kwargs):
    """ redefine at convenience, it will return the arguments for target method """
    return [],{}
    if self.MaxEvents and self.sent_total<self.MaxEvents:
      self.lost_time += time.time()-tnext #Thread switching also included  
  
  def stop_hook(self,*args,**kwargs):
    """ redefine at convenience """
    pass  
    
  def loop(self):

    self._done.set() #Will not be cleared until stop/start() are called

    while not self._kill.isSet():

      while self._stop.isSet():
        self._event.wait(.01)

      self._done.clear()
      self._count = 0
      self._errors = 0
      self._delay = 0
      self._acc_delay = 0
      
      ts = time.time()
      try:
        args,kwargs = self.start_hook(ts)
      except:
        self._errors += 1
        args,kwargs = [],{}

      print('ThreadedObject.Start() ...')
      while not self._stop.isSet():
        self._event.clear()
        try:
          if self._target:
            self._target(*args,**kwargs)
        except:
          self._errors += 1

        t1 = time.time()
        self._next = ts+self._timewait
        tw = self._next-t1
        self._usage = (t1-ts)/self._timewait
        
        self._event.wait(max((tw,self._min_wait)))
        
        ts = time.time()
        self._delay = ts>self._next and ts-self._next or 0
        self._acc_delay = self._acc_delay + self._delay
        try:
          args,kwargs = self.loop_hook(ts)
        except:
          self._errors += 1
          args,kwargs = [],{}
          
        self._count += 1
          
      self._done.set() #Will not be cleared until stop/start() are called
  
    print('ThreadedObject.Kill() ...')
    return #<< Will never get to this point


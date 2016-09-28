
import sys,traceback,re,time,threading
import PyTango
import fandango as fn
from fandango.dynamic import DynamicDS,DynamicDSClass,DynamicAttribute
from utils import ThreadedObject

class EventTestDS(DynamicDS):
  """
  This device will monitor both incoming and outgoing events.
  
  Events will be pushed for attributes in UseEvents property.
  
  In addition, the CurrentTime attribute will be pushed at 
  PushPeriod period (if set in UseEvents).
  """
  
  def __init__(self,cl, name):
    DynamicDS.__init__(self,cl,name)
    self.thread = ThreadedObject(self.push_loop)
    EventTestDS.init_device(self)
    
  def delete_device(self):
    self.thread.stop(wait=3.)
    
  def init_device(self):
    #self.setLogLevel('DEBUG')
    print("In "+self.get_name()+"::init_device()")
    self.get_DynDS_properties()
    self.set_state(PyTango.DevState.ON)
    self.rec_total = 0
    self.sent_total = 0
    self.value_delay = 0
    self.avg_delay = 0.
    self.last_event = 0.
    self.last_check = time.time()
    self.last_total = self.sent_total
    self.lost_time = 0
    self.rec_per_second = 0.
    self.period = self.PushPeriod or 1e9
    self.eids = []
    self.buffer = []
    self.send_buffer = []
    self.subscribed = []

    for attr in EventTestDSClass.attr_list:
      if fn.inCl(attr,self.UseEvents):
        print('Enabling manual events for %s'%attr)
        self.set_change_event(attr,True,False)

    self.thread.set_period(self.period)
    self.thread.set_start_hook(self.start_hook)
    print("Ready, waiting for Start()")
    
  def dyn_attr(self):
    DynamicDS.dyn_attr(self)
    
  def always_executed_hook(self):
    for attr in self.EventSources:
      if attr not in self.subscribed:
        if fn.check_attribute(attr):
          print('Subscribing to %s'%attr)
          d,a = attr.rsplit('/',1)
          self.eids.append(PyTango.DeviceProxy(d).subscribe_event(a,PyTango.EventType.CHANGE_EVENT,self.event_received))
          self.subscribed.append(attr)
    
    pass #DynamicDS.always_executed_hook(self)
    
  ## Put your methods here
  
  def start_hook(self,starttime):
    try:
      self.send_buffer = [starttime+i*self.period for i in range(int(self.MaxEvents))]
    except Exception,e:
      traceback.print_exc()
      raise e
    return [],{}
  
  def push_loop(self):

    if self.MaxEvents and self.sent_total==self.MaxEvents:
      if not self.t1:
        self.t1 = time.time()-self.thread.get_started()
        te = (float(self.MaxEvents)/self.ConsecutiveEvents)*self.period
        print('Sending finished after %f seconds (%f expected)'%(self.t1,te))

    else:
      for i in range(self.ConsecutiveEvents):
        value = self.send_buffer.pop(0) #value=self.thread.get_next())
        self.read_CurrentTime(value=value)
        if self.sent_total in [int(f*self.MaxEvents) for f in (.25,.5,.75)]:
          print(self.sent_total)
  
  def event_received(self,data):
    """
    Types of event hooks:
    
    - TaurusListener.eventReceived(self,source,type_,value)
    - TaurusBaseComponent.handleEvent(self,evt_source,evt_type,evt_value)
    - PyTango.push_event(evt_data)

    evt_data has the following attributes:
    
        date = evt.get_date().todatetime()
        reception_date = evt.reception_date.todatetime()
        evt_type = evt.event.upper()
        dev_name = evt.device.dev_name().upper()
        attr_name = evt.attr_name.split("/")[-1].upper()
        value = self._get_value(evt)

    """
    self.rec_total+=1
    self.buffer.append((time.time(),data))
    self.last_event = time.time()
    try:
      if hasattr(data,'attr_value'):
        value =data.attr_value.value
        delay = self.last_event-value
        self.value_delay = delay
        if self.rec_total <= 1:
          self.avg_delay = delay
        elif self.rec_total == 2:
          self.avg_delay = (delay+self.avg_delay)/2.
        else:
          self.avg_delay = ((delay/self.rec_total)+self.avg_delay)/(1+1./self.rec_total)
    except:
      pass #traceback.print_exc()
    while len(self.buffer) > self.BufferSize: self.buffer.pop(0)
    self.send_event('EventsReceivedTotal',self.rec_total)
    
  def send_event(self,attr_name,data):
    #print('In send_event(%s,%s)'%(attr_name,data))
    if self.MaxEvents and self.sent_total>=self.MaxEvents:
      return
    #t0 = time.time()    
    try:
      if fn.inCl(attr_name,self.UseEvents):
        self.sent_total += 1
        self.push_change_event(attr_name,data)#,time.time(),PyTango.AttrQuality.ATTR_VALID,1,0)
    except:
      traceback.print_exc()
    try:
      if fn.inCl('eventssenttotal',self.UseEvents):
        self.push_change_event('EventsSentTotal',self.sent_total)#,time.time(),PyTango.AttrQuality.ATTR_VALID)
    except:
      traceback.print_exc()
    #self.lost_time+=time.time()-t0
    
  ## Put your read_attribute methods here
  
  def read_EventsReceivedPerSecond(self, attr):
    attr.set_value(len([e for e in self.buffer if e[0]>time.time()-1]))
    
  def read_EventsReceivedTotal(self, attr):
    attr.set_value(self.rec_total)
    
  def read_EventsSentTotal(self, attr):
    attr.set_value(self.sent_total)
    
  def read_EventsSentPerSecond(self, attr):
    if not self.last_total:
      attr.set_value(0)
    else:
      attr.set_value((self.sent_total-self.last_total)/(time.time()-self.last_check))
    self.last_check = time.time()
    self.last_total = self.sent_total
    
  def read_CurrentTime(self, attr=None,value=None):
    #print('In read_CurrentTime(%s,%s)'%(attr,self.UseEvents))
    t = value or time.time()
    self.send_event('CurrentTime',t)
    if attr: 
      attr.set_value(t)
    return attr

  def read_LostTime(self, attr):
    attr.set_value(self.lost_time)    
    
  def read_ValueDelay(self, attr):
    if (time.time()-self.last_event)>1.:
      self.value_delay = 0
    attr.set_value(1e3*self.value_delay)
    
  def read_EventFrequency(self, attr):
    attr.set_value(1./self.period)    

  def write_EventFrequency(self, attr):
    try: #PyTango8
        data = attr.get_write_value()
    except:
        data = []
        attr.get_write_value(data)
        data = data[0]
    try:
      self.period = 1./data
    except:
      self.period = 1e9
    self.thread.set_period(self.period)

  def read_InternalDelay(self, attr):
    attr.set_value(self.rec_total)    

  ## Put your commands here
  
  def Start(self):
    self.t1 = 0
    self.sent_total = 0
    self.send_buffer = []
    print('Start(%d events in bunches of %d every %f seconds)'%(
      self.MaxEvents,self.ConsecutiveEvents,self.period))
    self.thread.start()
    
  def Stop(self):
    print('Stop()')
    self.thread.stop()
  
class EventTestDSClass(DynamicDSClass):
  
  device_property_list = {
    'BufferSize': [PyTango.DevLong,"Max Buffer Size for incoming events.",[ 100000 ] ],
    'UseEvents': [PyTango.DevVarStringArray,"",['EventsReceivedTotal','CurrentTime']],
    'EventSources': [PyTango.DevVarStringArray,"",[]],
    'PushPeriod': [PyTango.DevDouble,"Internal thread period in seconds",[1.]],
    'MaxEvents': [PyTango.DevDouble,"maximum number of events to sent",[0]],
    'ConsecutiveEvents': [PyTango.DevLong,"maximum number of events to sent",[1]],
    }
  
  cmd_list = {
    'Help':[[PyTango.DevVoid, ""],[PyTango.DevString, "python docstring"],],
    'Start':[[PyTango.DevVoid, ""],[PyTango.DevVoid, "start event sending"],],
    'Stop':[[PyTango.DevVoid, ""],[PyTango.DevVoid, "stop event sending"],],
    }
  
  attr_list = {
    'EventsReceivedPerSecond':[[PyTango.DevDouble,PyTango.SCALAR,PyTango.READ]],
    'EventsReceivedTotal':[[PyTango.DevDouble,PyTango.SCALAR,PyTango.READ]],
    'EventsSentTotal':[[PyTango.DevDouble,PyTango.SCALAR,PyTango.READ]],
    'EventsSentPerSecond':[[PyTango.DevDouble,PyTango.SCALAR,PyTango.READ]],
    'CurrentTime':[[PyTango.DevDouble,PyTango.SCALAR,PyTango.READ]],
    'LostTime':[[PyTango.DevDouble,PyTango.SCALAR,PyTango.READ]],
    'ValueDelay':[[PyTango.DevDouble,PyTango.SCALAR,PyTango.READ]],
    'InternalDelay':[[PyTango.DevDouble,PyTango.SCALAR,PyTango.READ]],
    'EventFrequency':[[PyTango.DevDouble,PyTango.SCALAR,PyTango.READ_WRITE]],
    }
  
  def __init__(self,name):
    PyTango.DeviceClass.__init__(self,name)
    self.set_type(name)
    
  def dyn_attr(self,dev_list):
      for dev in dev_list:
          EventTestDS.dyn_attr(dev)

EventTestDSClass.cmd_list.update(DynamicDSClass.cmd_list)
EventTestDSClass.attr_list.update(DynamicDSClass.attr_list)

def main(*args,**kwargs):
  """ 
  argument run=False can be used to disable Device Server main thread start 
  If false, then server can be launched in a background thread.
  """
  args = args or [a for a in sys.argv if not a.startswith('--')]
  print('EventTestDS.main(%s)'%args)
  py = PyTango.Util(['EventTestDS',args[1]])
  py.add_TgClass(EventTestDSClass,EventTestDS,'EventTestDS')
  U = PyTango.Util.instance()
  U.server_init()
  if int(kwargs.get('run',True)):
    U.server_run()
  else:
    print('Server initialized, waiting for PyTango.Util.instance().server_run() to start processing events')
  return U
  
if __name__ == '__main__':
  U = main(run=True)


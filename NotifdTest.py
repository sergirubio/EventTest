
import PyTango,fandango
from fandango.tango import *
from fandango import *
from fandango.dynamic import *
from fandango.interface import *
import taurus
import time

"""
Creating an event callback

# The callback must be a callable or an object with a push_event(self,event) method

def callback_function(*args): print args

(
  EventData(attr_name = 'tango://tbl0901.cells.es:10000/bl09/vc/all/state', attr_value = None, device = PyStateComposer(bl09/vc/all), 
      err = True, errors = (DevError(desc = 'Event channel is not responding anymore, maybe the server or event system is down', 
      origin = 'EventConsumer::KeepAliveThread()', reason = 'API_EventTimeout', 
      severity = PyTango._PyTango.ErrSeverity.ERR),), 
      event = 'change', 
      reception_date = TimeVal(tv_nsec = 0, tv_sec = 1391531528, tv_usec = 597630)),
)
Configuring an event

#From the client side
#subscribe_event(attr_name, event_type, cb_or_queuesize, filters=[], stateless=False, extract_as=PyTango._PyTango.ExtractAs.Numpy)
dp = PyTango.DeviceProxy(deviceName)
event_id = dp.subscribe_event(attributeName,PyTango.EventType.CHANGE_EVENT,callback_function,[],True)

#From inside the device server
self.set_change_event('State',True,True) 

dp.unsubscribe_event(event_id)
"""
#Error reproduced with 350n,3000ms,20ms~50Hz; once the "peak" occurred then any combination will reproduce; api_event_timeout seem periodical, but sometimes every 10 s and sometimes every 30s

#Error not reproduced at 150n,3000ms,20ms ; after a fresh restart of notifd this values keep the system stable

#around 220*50 seems to be the limit of events to be sent (although only ~1000 are processed)

NATTRIBUTES = 270
DP_TIMEOUT = 3000
DELAY_MS = 33

class NotifdTest(PyTango.Device_4Impl):
  
  memes = dict(('MemUsage%03d'%i, [[PyTango.DevDouble,PyTango.SCALAR,PyTango.READ]]) for i in range(NATTRIBUTES))
  
  def __init__(self,cl, name):
    #PyTango.Device_3Impl.__init__(self,cl,name)
    DynamicDS.__init__(self,cl,name,_locals={},useDynStates=True)
    NotifdTest.init_device(self)
    for a in self.memes:
      setattr(self,'read_%s'%a,self.read_MemUsage)
    
  def init_device(self):
    print "In ", self.get_name(), "::init_device()"
    try: 
            DynamicDS.init_device(self) #New in Fandango 11.1
    except:
            self.get_DynDS_properties() #LogLevel is already set here
    self.configured = getattr(self,'configured',False)
    self.times = []
    self.events = []

  def pusher(self):
    print 'PUSHING!!!'*10
    self.counter = 0
    self.t0 = time.time()
    t1 = self.t0
    while(True):
      self.mem_usage = fandango.random.randint(0,10000)
      t = (time.time()-t1)
      self.times.append(t)
      d = max([(self.Delay_ms*1e-3)-t,0])      
      time.sleep(d)
      t1 = time.time()      
      for att in self.memes:
        self.push_change_event(att,self.mem_usage)
        self.counter+=1
        time.sleep(1e-10)
        if time.time()>(self.t0+1):
          self.events.append(self.counter)
          print 'N = %s, Delay_ms = %s vs %s (%s ms/push): %d events/s (%s avg., %s tot.)' % (NATTRIBUTES,self.Delay_ms,d,sum(self.times)/len(self.times),self.counter,float(sum(self.events))/len(self.events),sum(self.events))
          self.counter,self.t0 = 0,time.time()
       
    
  def always_executed_hook(self):
    if not self.configured:
            print 'GOOOOOOOOOOOOOOOOOOOOOo'
            U = PyTango.Util.instance()
            dev = U.get_device_by_name(self.get_name())
            for att in self.memes:
                    ac = dev.get_attribute_config_3(att)[0]
                    if 'n' in str((ac.event_prop.ch_event.abs_change)).lower():
                      ac.event_prop.ch_event.abs_change = '1'
                      dev.set_attribute_config_3(ac)
                    print ac.event_prop.ch_event.abs_change
                    self.set_change_event(att,True,False)    
            self.push_thread = fandango.threads.Thread(target=self.pusher)
            self.push_thread.start()
            self.configured=True
    
  #------------------------------------------------------------------
  #    Read MemUsage attribute
  #------------------------------------------------------------------
  def read_MemUsage(self, attr):
      #print "In ", self.get_name(), "::read_MemUsage()"
      self.debug("In read_MemUsage()")
      
      #    Add your own code here
      attr.set_value(self.mem_usage)
    
class NotifdTestClass(PyTango.DeviceClass):
    device_property_list = {'Delay_ms':[PyTango.DevFloat,"",[DELAY_MS]]}
    
    attr_list = NotifdTest.memes
    
    def __init__(self, name):
        PyTango.DeviceClass.__init__(self, name)
        self.set_type(name);
        print "In PySignalSimulatorClass  constructor"
        
class DeviceClient(object):
  def __init__(self,device):
    self.device = device
    self.dp = PyTango.DeviceProxy(device)
    self.dp.set_timeout_millis(DP_TIMEOUT)
    self.subscribe()
    
  def subscribe(self):
    print 'subscribing ....'
    self.t0 = time.time()
    self.counter = 0  
    #self.eid = self.dp.subscribe_event('MemUsage',PyTango.EventType.CHANGE_EVENT,self,[],True)
    self.eids = [self.dp.subscribe_event(att,PyTango.EventType.CHANGE_EVENT,self,[],True) for att in NotifdTest.memes]
    
  def push_event(self,event):
     self.counter += 1
     if event.err: 
       print time.time(),fandango.shortstr(event.errors)
     if time.time()>(self.t0+1):
       print '%s: %d events/s' % (self.device,self.counter)
       self.counter = 0
       self.t0 = time.time()
       
  def unsubscribe(self):
     map(self.dp.unsubscribe_event,self.eids)
     
class Hi(taurus.core.TaurusListener):
    #NOTE: THIS WORKS (que no es poco)
    def __init__(self):
      self.t0 = time.time()
      self.counter = 0      
      self.times = []
      self.events = []

    #CUIDAO!!! This is usable for TaurusListener BUT NOT FOR WIDGETS/COMPONENTS; THEY SHOULD USE handleEvent INSTEAD!
    def eventReceived(self,source,type_,value):
        #BE CAREFUL, source is not an string but a TaurusAttribute object!!
        try:
          if type_ is taurus.core.TaurusEventType.Error or getattr(value,'has_failed',False):
            print '>'*240
            print time.time(),str(value)
        except:
          import traceback
          print dir(value)
          print(traceback.format_exc())
        self.counter += 1
        if time.time()>(self.t0+1):
          self.events.append(self.counter)
          print '%s: %d events/s (%s, %s)' % (time.ctime(),self.counter,float(sum(self.events))/len(self.events),sum(self.events))
          self.counter = 0
          self.t0 = time.time()          

class TaurusClient(object):
  def __init__(self,device):
    self.device = device
    self.dp = taurus.Device(device)
    self.dp.set_timeout_millis(DP_TIMEOUT)
    self.listener = Hi()
    self.subscribe()
    
  def subscribe(self):
    print 'subscribing ....'
    #self.eid = self.dp.subscribe_event('MemUsage',PyTango.EventType.CHANGE_EVENT,self,[],True)
    #self.eids = [self.dp.subscribe_event(att,PyTango.EventType.CHANGE_EVENT,self,[],True) for att in NotifdTest.memes]
    self.eids = []
    for m in NotifdTest.memes:
      self.eids.append(taurus.Attribute(self.device+'/'+m))
      self.eids[-1].addListener(self.listener)
       
  def unsubscribe(self):
     [a.removeListener(self.listener) for a in self.eids]
  
   
if __name__ == '__main__':
    try:
      if 'client' in sys.argv:
        client = DeviceClient('test/test/notifd')
        while True: fandango.threads.wait(0.01)
      elif 'taurus' in sys.argv:
        client = TaurusClient('test/test/notifd')
        while True: fandango.threads.wait(0.01)        
      else:
        py = PyTango.Util(sys.argv)
        # Adding all commands/properties from fandango.DynamicDS
        NotifdTest,NotifdTestClass = FullTangoInheritance('NotifdTest',NotifdTest,NotifdTestClass,DynamicDS,DynamicDSClass,ForceDevImpl=True)
        py.add_TgClass(NotifdTestClass,NotifdTest,'NotifdTest')

        U = PyTango.Util.instance()
        fandango.dynamic.CreateDynamicCommands(NotifdTest,NotifdTestClass)
        U.server_init()
        U.server_run()

    except PyTango.DevFailed,e:
        print '-------> Received a DevFailed exception:',traceback.format_exc()
    except Exception,e:
        print '-------> An unforeseen exception occured....',traceback.format_exc()

        
        
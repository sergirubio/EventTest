 #!/usr/bin/env python
 
import fandango as fn,time,os,threading
 
servers = [
  ('test1','EventTestDS','test/events/1',{'UseEvents':['CurrentTime'],'MaxEvents':10000}),
  ('test2','EventTestDS','test/events/2',{'EventSources':['test/events/1/CurrentTime']}),
  #('test3','EventTestDS','test/events/3',{'UseEvents':['CurrentTime'],'MaxEvents':10000}),
  #('test4','EventTestDS','test/events/4',{'UseEvents':['CurrentTime'],'MaxEvents':10000}),
  ]

N_EMITTERS = 1

devs = fn.get_matching_devices('test/events/*')

def cmd(s):
  print(s)
  os.system(s)

print('Checking if devices exist')
for s,c,d,p in servers:
  if d not in devs:
    print('Create %s'%str((c,s,d,p)))
    fn.tango.add_new_device(c+'/'+s,c,d)
    fn.tango.put_device_property(d,p)

print('Launching the servers')
for s,c,d,p in servers:
  if not fn.check_device(d):
    print('Start %s'%str((c,s,d,p)))
    cmd('python EventTestDS.py %s -v4 &'%s)

print('Launch taurustrend')
attrs = [
  'test/events/1/eventfrequency',
  'test/events/1/eventssentpersecond',
  'test/events/2/eventsreceivedpersecond',
  'test/events/2/usage',
  ]
cmd('taurustrend -r 100 %s &'%' '.join(attrs))
#cmd('taurustrend %s &'%' '.join(attrs))

attrs = [
  'test/events/1/eventfrequency',
  'test/events/2/valuedelay',
  ]
cmd('taurustrend -r 100 %s &'%' '.join(attrs))
#cmd('taurustrend %s &'%' '.join(attrs))


print('Start Testing in 10 seconds ...')
time.sleep(10.)

t1 = fn.get_device('test/events/1')
t2 = fn.get_device('test/events/2')
#t3 = fn.get_device('test/events/3')
#t4 = fn.get_device('test/events/4')

for t in (t1,): #t3,t4):
  t.set_timeout_millis(10000)
  t.EventFrequency = 0
time.sleep(1.)

for f in range(100,2000,100):
 print('Sending %d events in 5 seconds at %s Hz ...'%(f*5,f))
 [t.Reset() for t in (t1,t2,)] #t3,t4)]
 for t in (t1,):#t3,t4):
  t.EventFrequency = f/N_EMITTERS
  t.Start()

 ev,r = threading.Event(),time.time()
 while time.time()<r+5.:
   try:
     t2.read_attribute('ValueDelay')
   except Exception,e:
     print('test2 timeout: %s'%e)
   ev.wait(.1)

 for t in (t1,):#t3,t4):
  t.stop()
  t.EventFrequency = 0
  
 #time.sleep(1.)
 sent,received = N_EMITTERS*t1.EventsSentTotal,t2.EventsReceivedTotal
 print('%d events sent'%(sent))
 print('%d events received'%(received))
 print('%d data lost'%(100.*(sent-received)/sent))
 time.sleep(5.)
 
print('Finished')

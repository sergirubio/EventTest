 #!/usr/bin/env python
 
import fandango as fn,time,os
 
servers = [
  ('test1','EventTestDS','test/events/1',{'UseEvents':['CurrentTime'],'MaxEvents':10000}),
  ('test2','EventTestDS','test/events/2',{'EventSources':['test/events/1/CurrentTime']}),
  ]

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
  'test/events/2/valuedelay',
  ]
cmd('taurustrend -r 100 %s &'%' '.join(attrs))

print('Start Testing in 10 seconds ...')
time.sleep(10.)

t1 = fn.get_device('test/events/1')
t1.set_timeout_millis(10000)
t1.EventFrequency = 0

for f in range(100,2000,100):
 t1.EventFrequency = f
 t1.start()
 time.sleep(10.)
 t1.stop()
 t1.EventFrequency = 0
 time.sleep(5.)
 
print('Finished')

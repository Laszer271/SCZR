import time
import main
import process
import os
import json

def test(repeat_times=3):
    communication_mode = ['buffers', 'files']
    i = 0
    times = {}
    for mode in communication_mode:
        cores = [0]
        for core1 in range(len(cores) + 1):
            cores_depth1 = cores.copy()
            if core1 not in cores_depth1:
                cores_depth1.append(core1)
            for core2 in range(len(cores_depth1) + 1):
                cores_depth2 = cores_depth1.copy()
                if core2 not in cores_depth2:
                    cores_depth2.append(core2)
                for core3 in range(len(cores_depth2) + 1):
                    cores_depth3 = cores_depth2.copy()
                    if core3 not in cores_depth3:
                        cores_depth3.append(core3)
                    for scheduler_scheme in ['round_robin', 'fifo']:
                        for _ in range(repeat_times):
                            print('='*50)
                            kwargs = {'communication_mode': mode,
                                      'input_path': os.path.join('bin', 'woj'),
                                      'proc1_core': core1,
                                      'proc2_core': core2,
                                      'proc3_core': core3}
                            print(kwargs)
                            start = time.time()
                            processes = main.build_processes(**kwargs)
                            if scheduler_scheme == 'round_robin':
                                scheduler = process.Scheduler(processes, process.round_robin)
                            else:
                                scheduler = process.Scheduler(processes, process.fifo)
                            scheduler.schedule()
                            main.stop_processes(processes)
                            t = time.time() - start
                            if i not in times:
                                times[i] = {'time': t,
                                            'parameters': {**kwargs, 'scheduler_scheme': scheduler_scheme}}
                            elif t < times[i]['time']:
                                times[i]['time'] = t
                        print('current_time:', times[i]['time'])
                        i += 1
    return times    

if __name__ == '__main__':
    times = test()
    print(times)
    with open('times.json', 'w') as f:
        json.dump(times, f)
import multiprocessing
import time
import psutil
from ctypes import c_bool
import os

current_process_idx = 0

def round_robin(processes, current_process_idx):
    while True:
        proc_chosen = processes[current_process_idx]
        
        proc_chosen.lock2.acquire()
        if proc_chosen.tasks_waiting.value and not proc_chosen.is_busy():
            #print(proc_chosen, 'scheduled')
            break
        proc_chosen.lock2.release()
        
    current_process_idx = (current_process_idx + 1) % len(processes)   
    return current_process_idx, proc_chosen

def fifo(processes, current_process_idx):
    while True:
        proc_chosen = processes[current_process_idx]
        
        proc_chosen.lock2.acquire()
        if not proc_chosen.tasks_waiting.value:
            current_process_idx = (current_process_idx + 1) % len(processes)
        elif not proc_chosen.is_busy():
            #print(proc_chosen, 'scheduled')
            break
        proc_chosen.lock2.release()
         
    return current_process_idx, proc_chosen

class Scheduler:
    def __init__(self, processes, scheduling_scheme, core_nr=0):
        self.processes = processes
        self.scheduling_scheme = scheduling_scheme
        self.core_nr = core_nr
        self.current_process_idx = 0
        
    def change_scheduling_scheme(self, scheduling_scheme):
        self.scheduling_scheme = scheduling_scheme
        
    def schedule(self):
        p = psutil.Process()
        p.cpu_affinity([self.core_nr])
        #print('Scheduler using cpu core number', p.cpu_affinity()[0])
            
        tasks = sum([process.tasks_waiting.value for process in self.processes])
        tasks *= len(self.processes) # the first process produces task for second process and the second produces task for third so there are 3 tasks per every inital one
        #print('tasks:', tasks)
        while tasks > 0:
            self.current_process_idx, next_process = self.scheduling_scheme(self.processes, self.current_process_idx)
            
            next_process.cores_status_running[next_process.core_nr.value] = True
            next_process.release()
            tasks -= 1
            
class Process:
    def __init__(self, fun, cores_status_running, input_buffer=None, input_path=None,
                 output_buffer=None, output_path=None, next_proc_tasks=None,
                 core_nr=0, p=0.1):
        self.p = p
        self.running = multiprocessing.Value(c_bool, True)
        
        self.lock = multiprocessing.Lock()
        self.lock.acquire()
        self.lock2 = multiprocessing.Lock()

        self.last_worked = time.time()
        self.eta = 0.0
        self.tasks_waiting = multiprocessing.Value('i', 0)
        self.terminated = multiprocessing.Value(c_bool, False)
        self.next_proc_tasks = next_proc_tasks
        
        if core_nr not in cores_status_running:
            cores_status_running[core_nr] = False
        self.core_nr = multiprocessing.Value('i', core_nr)
        self.cores_status_running = cores_status_running
        
        if input_buffer is not None:
            self.input_buffer = input_buffer
            self.input_path = None
        else:
            self.input_path = input_path # get all images paths
            self.input_buffer = None
            
        if output_buffer is not None:
            self.output_buffer = output_buffer
            self.output_path = None
        elif output_path is not None:
            self.output_path = output_path
            if not os.path.exists(output_path):
                os.makedirs(output_path)
            self.output_buffer = None
            
        self.process = multiprocessing.Process(target=self.do_work, args=(fun,))
    
    def do_work(self, fun):
        p = psutil.Process()
        p.cpu_affinity([self.core_nr.value])
        #print(self, 'using cpu core number', p.cpu_affinity()[0])
        
        while True:
            #print(self, 'before wait')
            self.wait()
            #print(self, 'after wait')
            if not self.running.value:
                self.terminated.value = True
                self.clean()
                return
            
            self.tasks_waiting.value -= 1
            self.lock2.release()
                
            start = time.time()
            fun()
            if self.next_proc_tasks is not None:
                self.next_proc_tasks.value += 1
            self.last_worked = time.time()
            
            temp = self.last_worked - start
            if not self.eta:
                self.eta = temp
            else:
                self.eta = (1.0 - self.p) * self.eta + self.p * temp
                
            self.cores_status_running[self.core_nr.value] = False
            
    def is_busy(self):
        return self.cores_status_running[self.core_nr.value]
            
    def wait(self):
        self.lock.acquire()
        
    def check_if_ready(self):
        return self.tasks_waiting > 0
        
    def release(self):
        self.lock.release()
        
    def stop(self):
        self.running.value = False
        i = False
        while not self.terminated.value:
            try:
                self.release()
            except ValueError:
                pass
            if i:
                time.sleep(0.5)
            else:
                i = True
            
    def start(self):
        self.process.start()
        
    def clean(self):
        pass
            

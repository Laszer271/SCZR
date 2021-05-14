import process
import image_processing
from multiprocessing import Manager

def build_processes(communication_mode='buffers', input_path='bin', output_file='results.csv',
                    proc1_core=1, proc2_core=2, proc3_core=3, verbose=False):
    
    stats = ['resolution', 'n_pixels', 'offsets', 'sizes', 'bbox',
             'char size', 'ratios', 'variety', 'brightness']
    manager = Manager()
    d = manager.dict()
    
    fetcher_kwargs = {'core_nr': proc1_core}
    fetcher_args = (d,)
    
    statistics_kwargs = {'core_nr': proc2_core}
    statistics_args = (stats, d)
    
    logger_kwargs = {'verbose': verbose, 'output_path': output_file, 'core_nr': proc3_core}
    logger_args = (d,)
    
    if communication_mode == 'files':
        fetcher_kwargs['input_path'] = input_path
        fetcher_kwargs['output_path'] = 'cropped'
        
        statistics_kwargs['input_path'] = 'cropped'
        statistics_kwargs['output_path'] = 'stats'
        
        logger_kwargs['input_path'] = 'stats'
    elif communication_mode == 'buffers':
        fetcher_kwargs['input_path'] = input_path
        imgs_buf = manager.list()
        fetcher_kwargs['output_buffer'] = imgs_buf
        
        statistics_kwargs['input_buffer'] = imgs_buf
        stats_buf = manager.list()
        statistics_kwargs['output_buffer'] = stats_buf
        
        logger_kwargs['input_buffer'] = stats_buf
    else:
        raise AttributeError('Communication mode not supported:', communication_mode)
    
    logger = image_processing.Logger(*logger_args, **logger_kwargs)
    images_stats = image_processing.ImageStatistics(*statistics_args,
                                                    next_proc_tasks=logger.tasks_waiting,
                                                    **statistics_kwargs)
    images_fetcher = image_processing.ImageFetcher(*fetcher_args, 
                                                   next_proc_tasks=images_stats.tasks_waiting,
                                                   **fetcher_kwargs)
    processes = [images_fetcher,
                 images_stats,
                 logger]
    
    for proc in processes:
        proc.start()
        
    return processes

def stop_processes(processes):
    for proc in processes:
        proc.stop()
        proc.process.join()

if __name__ == '__main__':
    mode = 'files'
    input_path = 'bin'
    processes = build_processes(communication_mode=mode, input_path=input_path, verbose=True)
    
    scheduler = process.Scheduler(processes, process.round_robin)
    scheduler.schedule()
    
    stop_processes(processes)

import subprocess
from a2a_framework.utils.initialize_os_agents import OSAgentsInitializer
import joblib
from pathlib import Path
from a2a_framework.utils.keys import set_api_keys
import time
import os
from a2a_framework.utils.static import *




def initialize(config : str, log_file : str, dir : str, num_workers : int = 1, venv_path : str = None):
    '''
        This Function initialises twice once for the main process and the second time for the worker process. 
        Inputs : 
            1. config : str = A name of the agent configuration json
            2. log_file : str = A name of the log file to store functionalities
            3. dir : str = A name of the directory to store the log 
            4. num_workers : int = The number of worker processes to start
            5. venv_path : str = Optional python virtual env path
        Outputs : None 
    '''
    set_api_keys(config)
    os.makedirs(Path.cwd()/"artifacts",exist_ok=True)
    os.makedirs(Path.cwd()/"worker_store",exist_ok=True)
    os.makedirs(Path.cwd()/"pending_human_task",exist_ok=True)
    os.makedirs(Path.cwd()/dir,exist_ok=True)

    logger_path = OSAgentsInitializer(config,log_file,diff_dir=dir).initialize_all_agents()
    procs = []
    python_path = venv_path if venv_path else "python"
    for worker in range(1,num_workers+1):
        # We use this to run each worker and initialise a redis worker
        proc = subprocess.Popen([python_path,"-m","a2a_framework.a2a.Worker", "--config",config, "--log-file",log_file, "--dir",dir, "--worker", str(worker)],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True,)
        procs.append(proc)

    time.sleep(20)
    if proc.poll() is not None:
        out, err = proc.communicate()
        print("Process died immediately!")
        print("STDOUT:", out)
        print("STDERR:", err)
    
    pid_list = [proc.pid for proc in procs]
    joblib.dump(pid_list,WORKER_PATH)
    return logger_path


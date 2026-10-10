#!/usr/bin/env python3
"""Load/temperature watchdog for a detached job. SIGSTOP the job's process group when the machine is
busy or hot, SIGCONT after 3 consecutive normal readings, SIGTERM if still over after --kill_after s.
Usage: watchdog.py --pgid PGID [--max_load 64] [--max_cpu_c 85] [--max_gpu_c 83]"""
import argparse, glob, os, signal, subprocess, time
ap=argparse.ArgumentParser(); ap.add_argument("--pgid",type=int,required=True)
ap.add_argument("--max_load",type=float,default=64); ap.add_argument("--max_cpu_c",type=float,default=85)
ap.add_argument("--max_gpu_c",type=float,default=83); ap.add_argument("--kill_after",type=int,default=600)
ap.add_argument("--poll",type=int,default=30)
ap.add_argument("--max_gpu_total_w",type=float,default=None,help="pause when the SUM of power draw over ALL GPUs (incl. other users) exceeds this (the box lost power at ~892 W dual-GPU draw)")
ap.add_argument("--gpu_index",type=int,default=None,help="GPU this job uses: only its temperature counts, and any foreign compute process on it terminates the job")
a=ap.parse_args()
def cpu_c():
    best=0
    for d in glob.glob("/sys/class/hwmon/hwmon*"):
        try:
            if open(d+"/name").read().strip()=="k10temp": best=max(best,int(open(d+"/temp1_input").read())/1000)
        except Exception: pass
    return best
def gpu_c():
    if a.gpu_index is None: return 0
    try: return float(subprocess.check_output(["nvidia-smi","-i",str(a.gpu_index),"--query-gpu=temperature.gpu","--format=csv,noheader"],text=True).split()[0])
    except Exception: return 0
def gpu_total_w():
    try: return sum(float(x) for x in subprocess.check_output(["nvidia-smi","--query-gpu=power.draw","--format=csv,noheader,nounits"],text=True).split())
    except Exception: return 0.0
def foreign_gpu_procs():
    """PIDs using our GPU that are not members of the job's process group (tree)."""
    if a.gpu_index is None: return []
    try:
        uuid=subprocess.check_output(["nvidia-smi","-i",str(a.gpu_index),"--query-gpu=uuid","--format=csv,noheader"],text=True).strip()
        apps=subprocess.check_output(["nvidia-smi","--query-compute-apps=pid,gpu_uuid","--format=csv,noheader"],text=True).strip().splitlines()
        mine=set(int(x) for x in subprocess.check_output(["ps","-o","pid=","-g",str(a.pgid)],text=True).split())
        return [int(l.split(",")[0]) for l in apps if l.split(",")[1].strip()==uuid and int(l.split(",")[0]) not in mine]
    except Exception: return []
def alive():
    try: os.killpg(a.pgid,0); return True
    except ProcessLookupError: return False
paused=False; ok=0; since=None
while alive():
    l,c,g=os.getloadavg()[0],cpu_c(),gpu_c(); pw=gpu_total_w() if a.max_gpu_total_w else 0.0; bad=l>a.max_load or c>a.max_cpu_c or g>a.max_gpu_c or (a.max_gpu_total_w is not None and pw>a.max_gpu_total_w)
    fp=foreign_gpu_procs()
    if fp:
        os.killpg(a.pgid,signal.SIGCONT); os.killpg(a.pgid,signal.SIGTERM); print(time.strftime("%F %T"),f"FOREIGN GPU PROCESS(ES) {fp} on GPU {a.gpu_index}: TERMINATED job (resumable)",flush=True); break
    print(time.strftime("%F %T"),f"load={l:.1f} cpu={c:.0f}C gpu={g:.0f}C gpuW={pw:.0f} paused={paused}",flush=True)
    if bad:
        ok=0
        if not paused: os.killpg(a.pgid,signal.SIGSTOP); paused=True; since=time.time(); print("PAUSED",flush=True)
        elif time.time()-since>a.kill_after: os.killpg(a.pgid,signal.SIGCONT); os.killpg(a.pgid,signal.SIGTERM); print("TERMINATED (resumable)",flush=True); break
    elif paused:
        ok+=1
        if ok>=3: os.killpg(a.pgid,signal.SIGCONT); paused=False; print("RESUMED",flush=True)
    time.sleep(a.poll)

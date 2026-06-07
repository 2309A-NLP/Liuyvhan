import subprocess, sys, time, os, threading

os.chdir(r'C:\Users\刘禹含\Desktop\RAG-工单05')
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

proc = subprocess.Popen(
    [r'D:\Anaconda\envs\RAG\python.exe', '-m', 'uvicorn', 'main:app',
     '--host', '0.0.0.0', '--port', '8001', '--log-level', 'info'],
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    cwd=r'C:\Users\刘禹含\Desktop\RAG-工单05',
    bufsize=0,
)

print(f'PID: {proc.pid}', flush=True)

def reader():
    for line in iter(proc.stdout.readline, b''):
        decoded = line.decode('utf-8', errors='replace').rstrip()
        print(f'  {decoded}', flush=True)
    print('READER: EOF reached', flush=True)

t = threading.Thread(target=reader, daemon=True)
t.start()

time.sleep(60)

ret = proc.poll()
if ret is None:
    print(f'Server still running after 60s', flush=True)
    import urllib.request
    try:
        r = urllib.request.urlopen('http://127.0.0.1:8001/', timeout=5)
        print(f'HEALTH: {r.status} {r.read().decode()[:200]}', flush=True)
    except Exception as e:
        print(f'HEALTH FAIL: {type(e).__name__}: {e}', flush=True)
else:
    print(f'Process exited: {ret}', flush=True)

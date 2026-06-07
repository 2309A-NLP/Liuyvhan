import subprocess, sys, os, time, threading

os.chdir(r'C:\Users\刘禹含\Desktop\RAG-工单05')
sys.stdout.reconfigure(encoding='utf-8')

proc = subprocess.Popen(
    [r'D:\Anaconda\envs\RAG\python.exe', '-m', 'uvicorn', 'main:app',
     '--host', '0.0.0.0', '--port', '8001', '--log-level', 'info'],
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    cwd=r'C:\Users\刘禹含\Desktop\RAG-工单05',
    bufsize=0,
)

print(f'STARTED PID={proc.pid}', flush=True)

def reader():
    for line in iter(proc.stdout.readline, b''):
        decoded = line.decode('utf-8', errors='replace').rstrip()
        print(f'  {decoded}', flush=True)
    print('READER_DONE', flush=True)

t = threading.Thread(target=reader, daemon=True)
t.start()

# Wait for server to be ready
for i in range(30):
    time.sleep(2)
    import urllib.request
    try:
        r = urllib.request.urlopen('http://127.0.0.1:8001/', timeout=2)
        print(f'READY! Status={r.status} Body={r.read().decode()[:100]}', flush=True)
        break
    except:
        pass

ret = proc.poll()
if ret is None:
    print(f'SERVER_RUNNING PID={proc.pid}', flush=True)
    # Keep alive - don't let the script exit
    while True:
        time.sleep(10)
        # Print heartbeat
        print(f'KEEPALIVE uptime={int(time.time())}s', flush=True)

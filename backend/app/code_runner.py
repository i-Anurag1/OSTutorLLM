import subprocess,tempfile,os,resource
BLOCKED={'curl','wget','nc','netcat','ssh','scp','sudo','su','rm','mkfs','dd','shutdown','reboot','mount','umount','chmod','chown','kill','pkill','python','python3','perl','ruby','node','npm','git'}
def run_shell(script,timeout=3):
    lines=[x.strip() for x in script.splitlines() if x.strip() and not x.strip().startswith('#')]
    for line in lines:
        cmd=line.split()[0].replace('/bin/','') if line.split() else ''
        if cmd in BLOCKED or any(x in line for x in ['> /','>> /','/proc','/sys','/dev']): return {'ok':False,'stdout':'','stderr':'Command blocked by sandbox policy','exit_code':126}
    env={'PATH':'/usr/bin:/bin','HOME':'/tmp'}
    def limits():
        resource.setrlimit(resource.RLIMIT_CPU,(timeout,timeout)); resource.setrlimit(resource.RLIMIT_FSIZE,(1024*1024,1024*1024)); resource.setrlimit(resource.RLIMIT_NPROC,(20,20))
    try:
        p=subprocess.run(['/bin/bash','--noprofile','--norc','-e','-c',script],capture_output=True,text=True,timeout=timeout,cwd='/tmp',env=env,preexec_fn=limits)
        return {'ok':p.returncode==0,'stdout':p.stdout[-10000:],'stderr':p.stderr[-10000:],'exit_code':p.returncode}
    except subprocess.TimeoutExpired: return {'ok':False,'stdout':'','stderr':'Execution timed out','exit_code':124}

def run_python(source, timeout=3):
    import ast
    try: tree=ast.parse(source)
    except SyntaxError as e: return {'ok':False,'stdout':'','stderr':f'SyntaxError: {e}','exit_code':1}
    banned={'os','sys','subprocess','socket','pathlib','shutil','ctypes','requests','urllib','importlib','builtins'}
    for n in ast.walk(tree):
        if isinstance(n,ast.Import) and any(a.name.split('.')[0] in banned for a in n.names): return {'ok':False,'stdout':'','stderr':'Import blocked by sandbox policy','exit_code':126}
        if isinstance(n,ast.ImportFrom) and n.module and n.module.split('.')[0] in banned: return {'ok':False,'stdout':'','stderr':'Import blocked by sandbox policy','exit_code':126}
    fd,path=tempfile.mkstemp(suffix='.py',dir='/tmp'); os.close(fd); open(path,'w').write(source)
    env={'PYTHONPATH':'','HOME':'/tmp'}
    def limits():
        resource.setrlimit(resource.RLIMIT_CPU,(timeout,timeout)); resource.setrlimit(resource.RLIMIT_FSIZE,(1024*1024,1024*1024)); resource.setrlimit(resource.RLIMIT_NPROC,(20,20)); resource.setrlimit(resource.RLIMIT_NOFILE,(32,32))
    try:
        p=subprocess.run(['/usr/local/bin/python',path],capture_output=True,text=True,timeout=timeout,cwd='/tmp',env=env,preexec_fn=limits)
        return {'ok':p.returncode==0,'stdout':p.stdout[-10000:],'stderr':p.stderr[-10000:],'exit_code':p.returncode}
    except subprocess.TimeoutExpired:return {'ok':False,'stdout':'','stderr':'Execution timed out','exit_code':124}
    finally:
        try:os.unlink(path)
        except OSError:pass

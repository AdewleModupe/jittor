# ***************************************************************
# Copyright (c) 2020 Jittor. Authors: Dun Liang <randonlang@gmail.com>. All Rights Reserved.
# This file is subject to the terms and conditions defined in
# file 'LICENSE.txt', which is part of this source code package.
# ***************************************************************
from multiprocessing import Pool
import subprocess as sp
import os
import re
import sys
import inspect
import datetime
import contextlib
import threading
import time
from ctypes import cdll

class LogWarper:
    def __init__(self):
        self.log_silent = int(os.environ.get("log_silent", "0"))
        self.log_v = int(os.environ.get("log_v", "0"))

    def log_capture_start(self):
        cc.log_capture_start()

    def log_capture_stop(self):
        cc.log_capture_stop()

    def log_capture_read(self):
        return cc.log_capture_read()

    def _log(self, level, verbose, *msg):
        if len(msg):
            msg = " ".join([ str(m) for m in msg ])
        else:
            msg = str(msg)
        f = inspect.currentframe()
        fileline = inspect.getframeinfo(f.f_back.f_back)
        fileline = f"{os.path.basename(fileline.filename)}:{fileline.lineno}"
        if cc and hasattr(cc, "log"):
            cc.log(fileline, level, verbose, msg)
        else:
            if self.log_silent or verbose > self.log_v:
                return
            time = datetime.datetime.now().strftime("%m%d %H:%M:%S.%f")
            tid = threading.get_ident()%100
            v = f" v{verbose}" if verbose else ""
            print(f"[{level} {time} {tid:02}{v} {fileline}] {msg}")
    
    def V(self, verbose, *msg): self._log('i', verbose, *msg)
    def v(self, *msg): self._log('i', 1, *msg)
    def vv(self, *msg): self._log('i', 10, *msg)
    def vvv(self, *msg): self._log('i', 100, *msg)
    def vvvv(self, *msg): self._log('i', 1000, *msg)
    def i(self, *msg): self._log('i', 0, *msg)
    def w(self, *msg): self._log('w', 0, *msg)
    def e(self, *msg): self._log('e', 0, *msg)
    def f(self, *msg): self._log('f', 0, *msg)

# check is in jupyter notebook
def in_ipynb():
    try:
        cfg = get_ipython().config 
        if 'IPKernelApp' in cfg:
            return True
        else:
            return False
    except:
        return False

@contextlib.contextmanager
def simple_timer(name):
    LOG.i("Timer start", name)
    now = time.time()
    yield
    LOG.i("Time stop", name, time.time()-now)

@contextlib.contextmanager
def import_scope(flags):
    prev = sys.getdlopenflags()
    sys.setdlopenflags(flags)
    yield
    sys.setdlopenflags(prev)

def try_import_jit_utils_core(silent=None):
    global cc
    if cc: return
    if not (silent is None):
        prev = os.environ.get("log_silent", "0")
        os.environ["log_silent"] = str(int(silent))
    try:
        # if is in notebook, must log sync, and we redirect the log
        if is_in_ipynb: os.environ["log_sync"] = "1"
        import jit_utils_core as cc
        if is_in_ipynb:
            global redirector
            redirector = cc.ostream_redirect(stdout=True, stderr=True)
            redirector.__enter__()
    except Exception as _:
        pass
    if not (silent is None):
        os.environ["log_silent"] = prev

def run_cmd(cmd, cwd=None, err_msg=None, print_error=True):
    LOG.v(f"Run cmd: {cmd}")
    if cwd:
        r = sp.run(cmd, cwd=cwd, shell=True, stdout=sp.PIPE, stderr=sp.STDOUT)
    else:
        r = sp.run(cmd, shell=True, stdout=sp.PIPE, stderr=sp.STDOUT)
    s = r.stdout.decode('utf8')
    if r.returncode != 0:
        if print_error:
            sys.stderr.write(s)
        if err_msg is None:
            err_msg = f"Run cmd failed: {cmd}"
        if not print_error:
            err_msg += "\n"+s
        raise Exception(err_msg)
    if len(s) and s[-1] == '\n': s = s[:-1]
    return s


def do_compile(args):
    cmd, cache_path, jittor_path = args
    try_import_jit_utils_core(True)
    if cc:
        return cc.cache_compile(cmd, cache_path, jittor_path)
    else:
        run_cmd(cmd)
        return True

def run_cmds(cmds, cache_path, jittor_path):
    cmds = [ [cmd, cache_path, jittor_path] for cmd in cmds ]
    with Pool(8) as p:
        p.map(do_compile, cmds)

def download(url, filename):
    from six.moves import urllib
    if os.path.isfile(filename):
        if os.path.getsize(filename) > 100:
            return
    LOG.v("Downloading", url)
    urllib.request.urlretrieve(url, filename)
    LOG.v("Download finished")

def find_cache_path():
    from pathlib import Path
    path = str(Path.home())
    dirs = [".cache", "jittor", os.path.basename(cc_path)]
    if os.environ.get("debug")=="1":
        dirs[-1] += "_debug"
    cache_name = "default"
    try:
        if "cache_name" in os.environ:
            cache_name = os.environ["cache_name"]
        else:
            # try to get branch name from git
            r = sp.run(["git","branch"], cwd=os.path.dirname(__file__), stdout=sp.PIPE,
                   stderr=sp.PIPE)
            assert r.returncode == 0
            bs = r.stdout.decode()
            for b in bs:
                if b.startswith("* "): break
            cache_name = b[2:]
        for c in " (){}": cache_name = cache_name.replace(c, "_")
    except:
        pass
    for name in cache_name.split("/"):
        dirs.insert(-1, name)
    os.environ["cache_name"] = cache_name
    for d in dirs:
        path = os.path.join(path, d)
        if not os.path.isdir(path):
            os.mkdir(path)
        assert os.path.isdir(path)
    if path not in sys.path:
        sys.path.append(path)
    return path

def get_version(output):
    version = run_cmd(output+" --version")
    v = re.findall("[0-9]+\\.[0-9]+\\.[0-9]+", version)
    if len(v) == 0:
        v = re.findall("[0-9]+\\.[0-9]+", version)
    assert len(v) != 0, f"Can not find version number from: {version}"
    version = "("+v[-1]+")"
    return version

def find_exe(name, check_version=True):
    output = run_cmd(f'which {name}', err_msg=f'{name} not found')
    if check_version:
        version = get_version(name)
    else:
        version = ""
    LOG.i(f"Found {name}{version} at {output}.")
    return output

def env_or_find(name, bname):
    if name in os.environ:
        path = os.environ[name]
        if path != "":
            version = get_version(path)
            LOG.i(f"Found {bname}{version} at {path}")
        return path
    return find_exe(bname)

def get_cc_type(cc_path):
    bname = os.path.basename(cc_path)
    if "clang" in bname: return "clang"
    if "icc" in bname or "icpc" in bname: return "icc"
    if "g++" in bname: return "g++"
    LOG.f(f"Unknown cc type: {bname}")


is_in_ipynb = in_ipynb()
cc = None
LOG = LogWarper()

cc_path = env_or_find('cc_path', 'g++')
os.environ["cc_path"] = cc_path
cc_type = get_cc_type(cc_path)
cache_path = find_cache_path()

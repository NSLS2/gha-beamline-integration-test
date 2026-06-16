"""
Workaround for queueserver v0.0.23 + ipykernel namespace copy issue.

ipykernel creates a COPY of the user_ns dict passed to IPKernelApp, so
queueserver's self._re_namespace stays empty after startup files populate
the kernel's copy. This script is uploaded via 'qserver script upload' and
runs inside the kernel (in exec context with self._re_namespace as globals).
It copies generator functions (plans) and ophyd devices from get_ipython().user_ns
into globals() (= self._re_namespace), enabling plan/device discovery.
"""
import inspect

try:
    from bluesky.protocols import Readable, Flyable
    _has_protocols = True
except ImportError:
    _has_protocols = False

try:
    from IPython import get_ipython as _get_ipython
    _ip = _get_ipython()
    if _ip is not None:
        _copied = []
        for _k, _v in list(_ip.user_ns.items()):
            if _k.startswith('_'):
                continue
            _is_plan = inspect.isgeneratorfunction(_v)
            _is_device = (
                (_has_protocols and isinstance(_v, (Readable, Flyable))) or
                (hasattr(_v, 'children') and not inspect.isclass(_v))
            )
            if _is_plan or _is_device:
                globals()[_k] = _v
                _copied.append(_k)
        print(f"Copied {len(_copied)} items from IPython user_ns to re_namespace: {_copied[:10]}")
    else:
        print("get_ipython() returned None — not running in IPython kernel")
except Exception as _e:
    print(f"Namespace population error: {_e}")

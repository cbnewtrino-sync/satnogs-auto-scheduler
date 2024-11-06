from .satellite import Satellite  # noqa

try:
    from auto_scheduler._version import __version__
except ModuleNotFoundError:
    __version__ = "0.3.1-noinstall"

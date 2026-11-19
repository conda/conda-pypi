"""Report the target Python's import paths and PEP 508 markers using only its stdlib."""

import json
import os
import platform
import sys


def marker_environment():
    version = sys.implementation.version
    implementation_version = f"{version.major}.{version.minor}.{version.micro}"
    if version.releaselevel != "final":
        implementation_version += f"{version.releaselevel[0]}{version.serial}"
    return {
        "implementation_name": sys.implementation.name,
        "implementation_version": implementation_version,
        "os_name": os.name,
        "platform_machine": platform.machine(),
        "platform_release": platform.release(),
        "platform_system": platform.system(),
        "platform_version": platform.version(),
        "python_full_version": platform.python_version(),
        "platform_python_implementation": platform.python_implementation(),
        "python_version": ".".join(platform.python_version_tuple()[:2]),
        "sys_platform": sys.platform,
    }


if __name__ == "__main__":  # pragma: no cover
    print(json.dumps({"sys_path": sys.path, "markers": marker_environment()}))

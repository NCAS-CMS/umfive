import numpy as np
from setuptools import Extension, setup

print(np.get_include())
setup(
    ext_modules=[
        Extension(
            "ppfive._wgdos",
            sources=["ppfive/c_ext/wgdos_module.c"],
            include_dirs=[np.get_include(), "ppfive/c_ext"],
        )
    ]
)

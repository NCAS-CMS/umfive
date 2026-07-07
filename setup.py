import numpy as np
from setuptools import Extension, setup

print(np.get_include())
setup(
    ext_modules=[
        Extension(
            "umfive._wgdos",
            sources=["umfive/c_ext/wgdos_module.c"],
            include_dirs=[np.get_include(), "umfive/c_ext"],
        )
    ]
)

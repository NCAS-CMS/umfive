import numpy
from setuptools import Extension, setup

setup(
    ext_modules=[
        Extension(
            "ppfive._wgdos",
            sources=["ppfive/c_ext/wgdos_module.c"],
            include_dirs=[numpy.get_include(), "ppfive/c_ext"],
        )
    ]
)

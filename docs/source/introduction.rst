Introduction
============

Overview
--------

`umfive` is a Python open source library for representing `UK Met
Office PP, UM fields file, and UM dump datasets
<https://artefacts.ceda.ac.uk/badc_datadocs/um/umdp_F3-UMDPF3.pdf>`_
with `CF-netCDF <https://cfconventions.org/>`_-like structures that
follow the API of `pyfive <https://pyfive.readthedocs.io>`_, an HDF5
reader.

The contents of a PP, UM fields file, or UM dump dataset are mapped to
a `umfive.File` object that follows the `CF conventions
<https://cfconventions.org/>`_ in that it contains data variables
(`umfive.DataVariable` objects); dimensions and coordinate variables
(`umfive.DimensionScale` objects); and auxiliary coordinate, domain
ancillary, bounds, and grid mapping variables (`umfive.Variable`
objects).

32-bit and 64-bit PP, UM fields file, and UM dump datasets of any
endian-ness can be read.

2-d "slices" defined by a single lookup headers are always combined,
where possible, into fields with 3-d or 4-d data.

A simple example
----------------

The dataset `test.pp` (`download 704 kB
<https://raw.githubusercontent.com/NCAS-CMS/umfive/main/tests/data/test.pp>`_)
contains 15 lookup headers, for 3 different times and 5 different
heights, of the same physical variable. This is read with `umfive` as
a single data variable with 9 supporting metadata variables.

.. code-block:: python
   :caption: Example

   >>> import umfive
   >>> um = umfive.File('test.pp')  # Open the dataset
   >>> print(um)  # Inspect the dataset contents
   test.pp: <umfive.File: 1 data variable, 9 metadata variables>
       Data variables:
           UM_m01s15i201_vn405: <umfive.DataVariable: UM_m01s15i201_vn405, shape=(3, 5, 110, 106), dimensions=(time, air_pressure, grid_latitude, grid_longitude)>
       Metadata variables:
           time: <umfive.DimensionScale: time, shape=(3,)>
           bounds2: <umfive.DimensionScale: bounds2, size=2>
           time_bounds: <umfive.Variable: time_bounds, shape=(3, 2), dimensions=(time, bounds2)>
           air_pressure: <umfive.DimensionScale: air_pressure, shape=(5,)>
           grid_latitude: <umfive.DimensionScale: grid_latitude, shape=(110,)>
           grid_latitude_bounds: <umfive.Variable: grid_latitude_bounds, shape=(110, 2), dimensions=(grid_latitude, bounds2)>
           grid_longitude: <umfive.DimensionScale: grid_longitude, shape=(106,)>
           grid_longitude_bounds: <umfive.Variable: grid_longitude_bounds, shape=(106, 2), dimensions=(grid_longitude, bounds2)>
           rotated_latitude_longitude: <umfive.Variable: rotated_latitude_longitude, shape=(), dimensions=()>
   >>> um['UM_m01s15i201_vn405'].attrs  # Get a variable's attributes
   {'DIMENSION_LIST': (('time',),
                       ('air_pressure',),
                       ('grid_latitude',),
                       ('grid_longitude',)),
    '_FillValue': np.float32(-1.0737418e+09),
    'cell_methods': 'time: mean',
    'coordinates': 'time air_pressure grid_latitude grid_longitude',
    'grid_mapping': 'rotated_latitude_longitude',
    'lbcode': '101',
    'lbpack': '0',
    'lbproc': '128',
    'lbtim': '121',
    'lbvc': '8',
    'long_name': 'U COMPNT OF WIND ON PRESSURE LEVELS',
    'missing_value': np.float32(-1.0737418e+09),
    'runid': 'aaacf',
    'source': 'UM',
    'standard_name': 'eastward_wind',
    'stash_code': '15201',
    'submodel': '1',
    'um_identity': 'UM_m01s15i201_vn405',
    'um_stash_source': 'm01s15i201',
    'um_version': '4.5',
    'units': 'm s-1'}
   >>> um['time'][...]  # Get a variable's data array
   array([ 510.,  870., 1230.])

See :ref:`Quick-start` and :ref:`CF-netCDF-structure` for more
examples.

Local and remote datasets
-------------------------

A dataset can be passed to `umfive.File` with one of the following
dataset definitions:

- A string-like path name of a local dataset (such as a `str` or
  `pathlib.Path` instance).
  
- A file-like object that accesses a local or remote dataset (such as
  a `io.BufferedReader` instance, or the result of an `fsspec` file
  system open).
  
- A `umfive.LocalPosixReader` or `umfive.FileObjReader` object (or any
  subclass of `umfive.ByteReader`) that accesses a local or remote
  dataset.

`pyfive` compatibility
----------------------

`umfive` is designed to be `pyfive
<https://pyfive.readthedocs.io>`_-compatible meaning that, as far as
possible, code that manipulates a `pyfive.File` object will work
identically if that object is replaced by a `umfive.File` object.

In addition, `umfive.File` is registered as a virtual subclass of
`pyfive.File`; and `umfive.DataVariable`, `umfive.Variable`, and
`umfive.DimensionScale` are all registered as virtual subclasses of
`pyfive.Dataset`.

Performance
-----------

The read of a dataset is lazy in that only the metadata (i.e. the
lookup headers and any extra data) are accessed during the initial
read of the dataset. A data array in the dataset is then accessed on
demand, and then only for the part of the data array requested by the
indexing.

Data array reads are parallelised over the 2-d slices defined by each
lookup header (see `umfive.File.set_parallelism` and
`umfive.File.get_parallelism`).

The initial lazy read of the dataset is faster for a fields file or
dump than for the equivalent PP file, because in the former case all
of the lookup headers are in a contiguous block in the file, as
opposed to be being spread out throughout the file. When the dataset
is being accessed remotely, the difference in performance can be
large. For instance in one test, a remote S3 fields file (64-bit, 7.0
GiB) containing 210 lookup headers took 4 seconds to read lazily, and
the PP equivalent with the same number of lookup headers (32-bit, 3.7
GiB) took 63 seconds to read lazily.

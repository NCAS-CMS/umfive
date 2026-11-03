.. _CF-netCDF-structure:

CF-netCDF structure
===================

The contents of a PP, UM fields file, or UM dump dataset are mapped to
a `umfive.File` object that follows the `CF conventions
<https://cfconventions.org/>`_ in that it contains data variables
(`umfive.DataVariable` objects); and metadata variables comprising
dimensions and coordinate variables (`umfive.DimensionScale` objects),
and auxiliary coordinate, domain ancillary, bounds, and grid mapping
variables (`umfive.Variable` objects).

The examples in this section use the `test.pp` dataset (`download 704
kB
<https://raw.githubusercontent.com/NCAS-CMS/umfive/main/tests/data/test.pp>`_).

.. _CF-attributes:

CF attributes
-------------

The following `CF
<https://cfconventions.org/cf-conventions/cf-conventions.html>`_
attributes are derived from the lookup headers and, are added to the
output variables, or as global attributes, where possible and
appropriate:

=================  ========================================================
CF attribute       CF variable/global usage
=================  ========================================================
``_FillValue``     Data
``add_offset``     Data
``axis``           Coordinate, Auxiliary coordinate
``bounds``         Coordinate, Domain ancillary
``calendar``       Coordinate
``climatology``    Coordinate
``Conventions``    Global
``coordinates``    Data
``cell_methods``   Data
``formula_terms``  Coordinate (see :ref:`Orography`)
``grid_mapping``   Data
``long_name``      Data, Coordinate, Auxiliary coordinate, Domain ancillary
``missing_value``  Data
``positive``       Coordinate, Auxiliary coordinate
``scale_factor``   Data
``source``         Data
``standard_name``  Data, Coordinate, Auxiliary coordinate, Domain ancillary
``units``          Data, Coordinate, Auxiliary coordinate, Domain ancillary
=================  ========================================================

.. _Orography:
   
Orography
^^^^^^^^^

When a data variable has vertical coordinates that are defined by a
2-d orography field (such as `atmosphere hybrid height coordinates
<https://cfconventions.org/cf-conventions/cf-conventions.html#atmosphere-hybrid-height-coordinate>`_, LBVC = 65),
if the orography field is present as a data variable in the same
dataset then it will be referenced by the ``formula_terms`` attribute
of any applicable vertical coordinate variables.

.. _UM-attributes:

UM attributes
-------------

The following attributes, derived from the dataset lookup headers, are
added to data variables (i.e. added to `umfive.DataVariable`
instances):

===================  =========================================================
Attribute            Description
===================  =========================================================
``lbtim``            The value of LBTIM (word 13, time indicator)
``lbcode``           The value of LBCODE (word 16, grid code)
``lbpack``           The value of LBPACK (word 20, packing method indicator)
``lbproc``           The value of LBPROC (word 25, pocessing code)
``lbvc``             The value of LBVC (word 26, vertical co-ordinate type)
``runid``            The runid decoded from LBEXP (word 28, experiment number)
``source``           The source decoded from LBSRCE (word 38)
``stash_code``       The value of LBUSER(4) (word 42, stash code)
``submodel``         The value of LBUSER(7) (word 45, model code)
``um_identity``      A definitive identifier for the field
``um_stash_source``  The stash code and source
``um_version``       The UM version
===================  =========================================================

.. _Dataset:

Dataset
-------

A PP, UM fields file, or UM dump dataset is mapped to a `umfive.File`
object.

Dataset definition
^^^^^^^^^^^^^^^^^^

A dataset can be passed to `umfive.File` with one of the following
dataset definitions:

- A string-like path name of a local dataset (such as a `str` or
  `pathlib.Path` instance).
  
- A file-like object that accesses a local or remote dataset (such as
  a `io.BufferedReader` instance, or the result of an `fsspec` file
  system open).
  
- A subclass of `umfive.ByteReader` that accesses a local or remote
  dataset (such as `umfive.LocalPosixReader` or
  `umfive.FileObjReader`).

.. code-block:: python
   :caption: Example

   >>> import umfive
   >>> um = umfive.File('test.pp')  # Open the dataset
   >>> um
   test.pp: <umfive.File: 1 data variable, 9 metadata variables>
   >>> um.filename
   'test.pp'

Dataset indexing
^^^^^^^^^^^^^^^^

A data or metadata variable object can be accessed by indexing a
`umfive.File` instance with the variable's name.

The name can be provided with or without a leading ``/`` character.

.. code-block:: python
   :caption: Example

   >>> import umfive
   >>> um = umfive.File('test.pp')  # Open the dataset
   >>> print(um)
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
   >>> um['UM_m01s15i201_vn405']
   <umfive.DataVariable: UM_m01s15i201_vn405, shape=(3, 5, 110, 106), dimensions=(time, air_pressure, grid_latitude, grid_longitude)>
   >>> um['/UM_m01s15i201_vn405']
   <umfive.DataVariable: UM_m01s15i201_vn405, shape=(3, 5, 110, 106), dimensions=(time, air_pressure, grid_latitude, grid_longitude)>
   >>> um['time']
   <umfive.DimensionScale: time, shape=(3,)>

Dataset attributes
^^^^^^^^^^^^^^^^^^

The attributes of a `umfive.File` instance are accessed with the
`attrs` attribute.

.. code-block:: python
   :caption: Example

   >>> import umfive
   >>> um = umfive.File('test.pp')  # Open the dataset
   >>> um
   test.pp: <umfive.File: 1 data variable, 9 metadata variables>
   >>> um.attrs  # Get the attributes
   {'Conventions': 'CF-1.13'}

Dataset variables
^^^^^^^^^^^^^^^^^

The data and and metadata variables of a `umfive.File` instance are
accessed with the `~umfive.File.data_variables`,
`~umfive.File.metadata_variables`, and `~umfive.File.variables`
attributes.

.. code-block:: python
   :caption: Example

   >>> import umfive
   >>> um = umfive.File('test.pp')  # Open the dataset
   >>> um
   test.pp: <umfive.File: 1 data variable, 9 metadata variables>
   >>> um.data_variables  # Data variables
   {'UM_m01s15i201_vn405': <umfive.DataVariable: UM_m01s15i201_vn405, shape=(3, 5, 110, 106), dimensions=(time, air_pressure, grid_latitude, grid_longitude)>}
   >>> um.metadata_variables  # Metadata variables
   {'time': <umfive.DimensionScale: time, shape=(3,)>,
    'bounds2': <umfive.DimensionScale: bounds2, size=2>,
    'time_bounds': <umfive.Variable: time_bounds, shape=(3, 2), dimensions=(time, bounds2)>,
    'air_pressure': <umfive.DimensionScale: air_pressure, shape=(5,)>,
    'grid_latitude': <umfive.DimensionScale: grid_latitude, shape=(110,)>,
    'grid_latitude_bounds': <umfive.Variable: grid_latitude_bounds, shape=(110, 2), dimensions=(grid_latitude, bounds2)>,
    'grid_longitude': <umfive.DimensionScale: grid_longitude, shape=(106,)>,
    'grid_longitude_bounds': <umfive.Variable: grid_longitude_bounds, shape=(106, 2), dimensions=(grid_longitude, bounds2)>,
    'rotated_latitude_longitude': <umfive.Variable: rotated_latitude_longitude, shape=(), dimensions=()>}
   >>> um.variables  # Data and metadata variables
   {'UM_m01s15i201_vn405': <umfive.DataVariable: UM_m01s15i201_vn405, shape=(3, 5, 110, 106), dimensions=(time, air_pressure, grid_latitude, grid_longitude)>,
    'time': <umfive.DimensionScale: time, shape=(3,)>,
    'bounds2': <umfive.DimensionScale: bounds2, size=2>,
    'time_bounds': <umfive.Variable: time_bounds, shape=(3, 2), dimensions=(time, bounds2)>,
    'air_pressure': <umfive.DimensionScale: air_pressure, shape=(5,)>,
    'grid_latitude': <umfive.DimensionScale: grid_latitude, shape=(110,)>,
    'grid_latitude_bounds': <umfive.Variable: grid_latitude_bounds, shape=(110, 2), dimensions=(grid_latitude, bounds2)>,
    'grid_longitude': <umfive.DimensionScale: grid_longitude, shape=(106,)>,
    'grid_longitude_bounds': <umfive.Variable: grid_longitude_bounds, shape=(106, 2), dimensions=(grid_longitude, bounds2)>,
    'rotated_latitude_longitude': <umfive.Variable: rotated_latitude_longitude, shape=(), dimensions=()>}

Dataset dimensions
^^^^^^^^^^^^^^^^^^

Dimensions are defined by the subset of metadata variables that are
`umfive.DimensionScale` objects, and are accessed with the
`~umfive.File.dimension_variables` attribute.

.. code-block:: python
   :caption: Example

   >>> import umfive
   >>> um = umfive.File('test.pp')  # Open the dataset
   >>> um
   test.pp: <umfive.File: 1 data variable, 9 metadata variables>
   >>> um.dimension_variables  # Dimension variables
   {'time': <umfive.DimensionScale: time, shape=(3,)>,
    'bounds2': <umfive.DimensionScale: bounds2, size=2>,
    'air_pressure': <umfive.DimensionScale: air_pressure, shape=(5,)>,
    'grid_latitude': <umfive.DimensionScale: grid_latitude, shape=(110,)>,
    'grid_longitude': <umfive.DimensionScale: grid_longitude, shape=(106,)>}

A `umfive.DimensionScale` dimension metadata variable may also define
a coordinate data array for the dimension.

.. code-block:: python
   :caption: Example

   >>> um['bounds2'].has_coordinates
   False
   >>> um['time'].has_coordinates
   True
   >>> um['time'][...]
   array([120.5, 121.5, 122.5])

Data and metadata variables
---------------------------

Variable name
^^^^^^^^^^^^^

The name of a data or metadata variable instance is accessed with the
`!name` attribute.

.. code-block:: python
   :caption: Example

   >>> import umfive
   >>> um = umfive.File('test.pp')  # Open the dataset
   >>> um
   test.pp: <umfive.File: 1 data variable, 9 metadata variables>
   >>> um['UM_m01s15i201_vn405'].name
   'UM_m01s15i201_vn405'
   >>> um['time'].name
   'time'
   
.. _Variable-data-and-indexing:

Variable data and indexing
^^^^^^^^^^^^^^^^^^^^^^^^^^

The data array of a data or metadata variable is accessed by direct
indexing, following the same indexing rules as `pyfive`.

The requested subspace is always returned as a `numpy` array.

.. code-block:: python
   :caption: Example

   >>> import umfive
   >>> um = umfive.File('test.pp')  # Open the dataset
   >>> um
   test.pp: <umfive.File: 1 data variable, 9 metadata variables>
   >>> z = um['air_pressure']  # Select a metadata variable
   >>> z.shape
   (5,)
   >>> z[...]
   array([850.00006 , 700.00006 , 500.00003 , 250.00002 ,  50.000004],
         dtype=float32)
   >>> x = um['grid_longitude']
   >>> x.shape
   (106,)
   >>> x[10:18]
   array([-16.14001101, -15.70001101, -15.26001102, -14.82001102,
          -14.38001102, -13.94001102, -13.50001103, -13.06001103])
   >>> v = um['UM_m01s15i201_vn405']  # Select a data variable
   >>> v.shape
   (3, 5, 110, 106)
   >>> v[:, ::-2, 0, [1, 3, 4]]
   array([[[ 1.9971831 ,  2.0868094 ,  2.0961797 ],
           [24.7883    , 24.573233  , 24.599092  ],
           [ 0.3053741 ,  1.6385416 ,  2.4959655 ]],
   
          [[ 1.1319677 ,  1.1473515 ,  1.1232048 ],
           [25.576569  , 26.36779   , 26.69227   ],
           [ 3.3617647 ,  4.632866  ,  5.4127526 ]],
   
          [[-0.82124394, -1.0082524 , -1.0969521 ],
           [22.701277  , 25.178629  , 26.253435  ],
           [ 1.975026  ,  2.9471946 ,  3.5579882 ]]], dtype=float32)

.. _Variable-attributes:

Variable attributes
^^^^^^^^^^^^^^^^^^^

The attributes of a data or metadata variable are accessed by the
`!attrs` attribute.

.. code-block:: python
   :caption: Example

   >>> import umfive
   >>> um = umfive.File('test.pp')  # Open the dataset
   >>> um
   test.pp: <umfive.File: 1 data variable, 9 metadata variables>
   >>> z = um['air_pressure']  # Select a metadata variable
   >>> z.attrs  # Get the attributes
   {'CLASS': b'DIMENSION_SCALE',
    'NAME': b'netCDF dimension coordinate variable',
    '_Netcdf4Dimid': np.int32(2),
    'axis': 'Z',
    'positive': 'down',
    'standard_name': 'air_pressure',
    'units': 'hPa'}
   >>> v = um['UM_m01s15i201_vn405']  # Select a data variable
   >>> v.attrs
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

The attributes include ``CLASS``, ``NAME``, ``DIMENSION_SCALE``, and
``DIMENSION_LIST``, which are special HDF5 attributes required to
interpret the dataset as netCDF4 dataset.  See :ref:`Use-with-xnetcdf`
for a netCDF (as opposed to HDF5) view.

Variable dimensions
^^^^^^^^^^^^^^^^^^^

The dimensions of a data or metadata instance are accessed with the
`!dimensions` attribute

.. code-block:: python
   :caption: Example

   >>> import umfive
   >>> um = umfive.File('test.pp')  # Open the dataset
   >>> um
   test.pp: <umfive.File: 1 data variable, 9 metadata variables>
   >>> z = um['air_pressure']
   >>> z.dimensions
   ('air_pressure',)
   >>> v = um['UM_m01s15i201_vn405']
   >>> v.dimensions
   ('time', 'air_pressure', 'grid_latitude', 'grid_longitude')

.. _Quick-start:

Quick start
===========

The examples in this section use the `test.pp` dataset (`download 704
kB
<https://raw.githubusercontent.com/NCAS-CMS/umfive/main/tests/data/test.pp>`_).

----

Using `umfive` to open a dataset and inspect its contents:

.. code-block:: python
   :caption: Example

    import umfive

    # Open the dataset
    with umfive.File('test.pp') as um:
        # A one-line summary of the dataset
        print(repr(um))

        # A longer summary of the dataset
        print(um)

        # Use the dump() method for an even more detailed view
        um.dump()

        # Use the dump() method with "data=True" for yet more detail
        um.dump(data=True)

        # Access a variable
	var = um['UM_m01s15i201_vn405']

        # A one-line summary of the variable
        print(repr(var))
	
        # Print the variable attributes
        print(var.attrs)

        # Print the data array from the variable
        print(var[...])
	    
.. rubric:: Import the library and open the dataset.

See :ref:`Dataset`.

.. code-block:: python
   :caption: Example

   >>> import umfive
   >>> um = umfive.File('test.pp')

.. rubric:: Display the `repr` description of the dataset

This one-line description includes the dataset name, and how many data
variables and metadata variables there are.

.. code-block:: python
   :caption: Example
		
   >>> um
   test.pp: <umfive.File: 1 data variable, 9 metadata variables>

.. rubric:: Display the `str` description of the dataset

In addition to the `repr` output, this shows some details about each
data and metadata variable. The `umfive.DataVariable` and
`umfive.Variable` variable descriptions indicate which dimensions are
spanned by their data arrays.

.. code-block:: python
   :caption: Example
		
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
	
.. rubric:: Display the `~umfive.File.dump` description of the dataset

In addition to the `str` description, this shows the attribute of
each data and metadata variable. IF the `data=True` keyword is used, then each variable's data array also displayed.

.. code-block:: python
   :caption: Example

   >>> um.dump()
   test.pp: <umfive.File: 1 data variable, 9 metadata variables>
    Attributes:
        Conventions: 'CF-1.13'
    Data variables:
        UM_m01s15i201_vn405: <umfive.DataVariable: UM_m01s15i201_vn405, shape=(3, 5, 110, 106), dimensions=(time, air_pressure, grid_latitude, grid_longitude)>
            Attributes:
                DIMENSION_LIST: (('time',), ('air_pressure',), ('grid_latitude',), ('grid_longitude',))
                _FillValue: np.float32(-1.0737418e+09)
                cell_methods: 'time: mean'
                coordinates: 'time air_pressure grid_latitude grid_longitude'
                grid_mapping: 'rotated_latitude_longitude'
                lbcode: '101'
                lbpack: '0'
                lbproc: '128'
                lbtim: '121'
                lbvc: '8'
                long_name: 'U COMPNT OF WIND ON PRESSURE LEVELS'
                missing_value: np.float32(-1.0737418e+09)
                runid: 'aaacf'
                source: 'UM'
                standard_name: 'eastward_wind'
                stash_code: '15201'
                submodel: '1'
                um_identity: 'UM_m01s15i201_vn405'
                um_stash_source: 'm01s15i201'
                um_version: '4.5'
                units: 'm s-1'
    Metadata variables:
        time: <umfive.DimensionScale: time, shape=(3,)>
            Attributes:
                CLASS: b'DIMENSION_SCALE'
                NAME: b'netCDF dimension coordinate variable'
                _Netcdf4Dimid: np.int32(0)
                axis: 'T'
                bounds: 'time_bounds'
                calendar: 'gregorian'
                standard_name: 'time'
                units: 'days since 1979-1-1'
        bounds2: <umfive.DimensionScale: bounds2, size=2>
            Attributes:
                CLASS: b'DIMENSION_SCALE'
                NAME: b'This is a netCDF dimension but not a netCDF variable.'
                _Netcdf4Dimid: np.int32(1)
        time_bounds: <umfive.Variable: time_bounds, shape=(3, 2), dimensions=(time, bounds2)>
            Attributes:
                DIMENSION_LIST: (('time',), ('bounds2',))
        air_pressure: <umfive.DimensionScale: air_pressure, shape=(5,)>
            Attributes:
                CLASS: b'DIMENSION_SCALE'
                NAME: b'netCDF dimension coordinate variable'
                _Netcdf4Dimid: np.int32(2)
                axis: 'Z'
                positive: 'down'
                standard_name: 'air_pressure'
                units: 'hPa'
        grid_latitude: <umfive.DimensionScale: grid_latitude, shape=(110,)>
            Attributes:
                CLASS: b'DIMENSION_SCALE'
                NAME: b'netCDF dimension coordinate variable'
                _Netcdf4Dimid: np.int32(3)
                axis: 'Y'
                bounds: 'grid_latitude_bounds'
                standard_name: 'grid_latitude'
                units: 'degrees'
        grid_latitude_bounds: <umfive.Variable: grid_latitude_bounds, shape=(110, 2), dimensions=(grid_latitude, bounds2)>
            Attributes:
                DIMENSION_LIST: (('grid_latitude',), ('bounds2',))
        grid_longitude: <umfive.DimensionScale: grid_longitude, shape=(106,)>
            Attributes:
                CLASS: b'DIMENSION_SCALE'
                NAME: b'netCDF dimension coordinate variable'
                _Netcdf4Dimid: np.int32(4)
                axis: 'X'
                bounds: 'grid_longitude_bounds'
                standard_name: 'grid_longitude'
                units: 'degrees'
        grid_longitude_bounds: <umfive.Variable: grid_longitude_bounds, shape=(106, 2), dimensions=(grid_longitude, bounds2)>
            Attributes:
                DIMENSION_LIST: (('grid_longitude',), ('bounds2',))
        rotated_latitude_longitude: <umfive.Variable: rotated_latitude_longitude, shape=(), dimensions=()>
            Attributes:
                DIMENSION_LIST: ()
                grid_mapping_name: 'rotated_latitude_longitude'
                grid_north_pole_latitude: np.float32(38.0)
                grid_north_pole_longitude: np.float32(190.0)

.. rubric:: Access variable attributes

See :ref:`Variable-attributes`.

.. code-block:: python
   :caption: Example
		
   >>> var = um['UM_m01s15i201_vn405']
   >>> var.attrs
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
   >>> air_pressure = um['air_pressure']
   >>> air_pressure.attrs
   {'CLASS': b'DIMENSION_SCALE',
    'NAME': b'netCDF dimension coordinate variable',
    '_Netcdf4Dimid': np.int32(2),
    'axis': 'Z',
    'positive': 'down',
    'standard_name': 'air_pressure',
    'units': 'hPa'}
	
.. rubric:: Access variable data.

See :ref:`Variable-data-and-indexing`.

.. code-block:: python
   :caption: Example
	
   >>> var[...]
   array([[[[-1.28504544e-01,  3.05374086e-01,  8.93456340e-01, ...,
              4.12485838e+00,  4.27008438e+00,  4.22145319e+00],
            [ 4.74474072e-01,  9.77664232e-01,  1.43804467e+00, ...,
              3.98733783e+00,  4.09150171e+00,  4.04539061e+00],
            [ 8.05260956e-01,  1.24306083e+00,  1.74817479e+00, ...,
              3.80105686e+00,  3.98432851e+00,  3.94045901e+00],
            ...,
            [ 5.67281818e+00,  5.62275362e+00,  5.59070444e+00, ...,
             -1.69666624e+00, -1.95548487e+00, -1.96797502e+00],
            [ 5.14257669e+00,  5.06531000e+00,  5.00876808e+00, ...,
             -1.68950760e+00, -1.70027304e+00, -1.71349967e+00],
            [ 4.59499311e+00,  4.50737619e+00,  4.43036985e+00, ...,
             -1.15786588e+00, -1.21203947e+00, -1.22635651e+00]]]],
         shape=(3, 5, 110, 106), dtype=float32)
   >>> air_pressure[1:3]
   array([700.00006 , 500.00003], dtype=float32)

.. rubric:: Display a variable's attributes and data array using the
            variable's `!dump` method

.. code-block:: python
   :caption: Example

   >>> z = um['air_pressure']
   >>> z.dump(data=True)
   air_pressure: <umfive.DimensionScale: air_pressure, shape=(5,)>
       Attributes:
           CLASS: b'DIMENSION_SCALE'
           NAME: b'netCDF dimension coordinate variable'
           _Netcdf4Dimid: np.int32(2)
           axis: 'Z'
           positive: 'down'
           standard_name: 'air_pressure'
           units: 'hPa'
       Data float32:
           [850.00006 , 700.00006 , 500.00003 , 250.00002 ,
             50.000004]

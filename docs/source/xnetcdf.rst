.. _Use-with-xnetcdf:

Use with `xnetcdf`
==================

A netCDF (as opposed to HDF5) view of the dataset, that more clearly
defines the dimensions, is easily found via the `xnetcdf
<https://xnetcdf.readthedocs.io>`_ library, a Python library for
representing datasets with a common netCDF view.

`xnetcdf` can convert an existing `umfive.File` instance, or if passed
the dataset name it will itself use `umfive` internally to open the
dataset. In both cases, the access to the data arrays is lazy.

The examples in this section use the `test.pp` dataset (`download 704
kB
<https://raw.githubusercontent.com/NCAS-CMS/umfive/main/tests/data/test.pp>`_).

.. code-block:: python
   :caption: Create a `umfive.File` instance.

   >>> import umfive
   >>> um = umfive.File('test.pp')  # Open the dataset with umfive
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
	   
.. code-block:: python
   :caption: Convert the `umfive.File` instance to a `xnetcdf.Dataset`
             instance.

   >>> import xnetcdf
   >>> x = xnetcdf.Dataset(um)  # Pass the umfive.File instance to xnetcdf
   >>> x
   test.pp: <xnetcdf.Dataset: /, 5 dimensions, 9 variables, 0 groups>
   >>> print(x)
   test.pp: <xnetcdf.Dataset: /, 5 dimensions, 9 variables, 0 groups>
        Dimensions:
            time: <xnetcdf.Dimension: /time, size=3>
            bounds2: <xnetcdf.Dimension: /bounds2, size=2>
            air_pressure: <xnetcdf.Dimension: /air_pressure, size=5>
            grid_latitude: <xnetcdf.Dimension: /grid_latitude, size=110>
            grid_longitude: <xnetcdf.Dimension: /grid_longitude, size=106>
        Variables:
            UM_m01s15i201_vn405: <xnetcdf.Variable: /UM_m01s15i201_vn405, shape=(3, 5, 110, 106), dimensions=(/time, /air_pressure, /grid_latitude, /grid_longitude)>
            time: <xnetcdf.Variable: /time, shape=(3,), dimensions=(/time,)>
            time_bounds: <xnetcdf.Variable: /time_bounds, shape=(3, 2), dimensions=(/time, /bounds2)>
            air_pressure: <xnetcdf.Variable: /air_pressure, shape=(5,), dimensions=(/air_pressure,)>
            grid_latitude: <xnetcdf.Variable: /grid_latitude, shape=(110,), dimensions=(/grid_latitude,)>
            grid_latitude_bounds: <xnetcdf.Variable: /grid_latitude_bounds, shape=(110, 2), dimensions=(/grid_latitude, /bounds2)>
            grid_longitude: <xnetcdf.Variable: /grid_longitude, shape=(106,), dimensions=(/grid_longitude,)>
            grid_longitude_bounds: <xnetcdf.Variable: /grid_longitude_bounds, shape=(106, 2), dimensions=(/grid_longitude, /bounds2)>
            rotated_latitude_longitude: <xnetcdf.Variable: /rotated_latitude_longitude, shape=(), dimensions=()>
	    
.. code-block:: python
   :caption: Create a `xnetcdf.Dataset` instance from directly from the file.

   >>> x = xnetcdf.Dataset('test.pp')  # Pass the dataset name to xnetcdf
   >>> x.ncdump()
   netcdf test.pp {
   dimensions:
        time = 3 ;
        bounds2 = 2 ;
        air_pressure = 5 ;
        grid_latitude = 110 ;
        grid_longitude = 106 ;
   variables:
        float UM_m01s15i201_vn405(time, air_pressure, grid_latitude, grid_longitude) ;
            UM_m01s15i201_vn405:_FillValue = -1073741824.f ;
            UM_m01s15i201_vn405:cell_methods = "time: mean" ;
            UM_m01s15i201_vn405:coordinates = "time air_pressure grid_latitude grid_longitude" ;
            UM_m01s15i201_vn405:grid_mapping = "rotated_latitude_longitude" ;
            UM_m01s15i201_vn405:lbcode = "101" ;
            UM_m01s15i201_vn405:lbpack = "0" ;
            UM_m01s15i201_vn405:lbproc = "128" ;
            UM_m01s15i201_vn405:lbtim = "121" ;
            UM_m01s15i201_vn405:lbvc = "8" ;
            UM_m01s15i201_vn405:long_name = "U COMPNT OF WIND ON PRESSURE LEVELS" ;
            UM_m01s15i201_vn405:missing_value = -1073741824.f ;
            UM_m01s15i201_vn405:runid = "aaacf" ;
            UM_m01s15i201_vn405:source = "UM" ;
            UM_m01s15i201_vn405:standard_name = "eastward_wind" ;
            UM_m01s15i201_vn405:stash_code = "15201" ;
            UM_m01s15i201_vn405:submodel = "1" ;
            UM_m01s15i201_vn405:um_identity = "UM_m01s15i201_vn405" ;
            UM_m01s15i201_vn405:um_stash_source = "m01s15i201" ;
            UM_m01s15i201_vn405:um_version = "4.5" ;
            UM_m01s15i201_vn405:units = "m s-1" ;
        double time(time) ;
            time:axis = "T" ;
            time:bounds = "time_bounds" ;
            time:calendar = "gregorian" ;
            time:standard_name = "time" ;
            time:units = "days since 1979-1-1" ;
        double time_bounds(time, bounds2) ;
        float air_pressure(air_pressure) ;
            air_pressure:axis = "Z" ;
            air_pressure:positive = "down" ;
            air_pressure:standard_name = "air_pressure" ;
            air_pressure:units = "hPa" ;
        double grid_latitude(grid_latitude) ;
            grid_latitude:axis = "Y" ;
            grid_latitude:bounds = "grid_latitude_bounds" ;
            grid_latitude:standard_name = "grid_latitude" ;
            grid_latitude:units = "degrees" ;
        double grid_latitude_bounds(grid_latitude, bounds2) ;
        double grid_longitude(grid_longitude) ;
            grid_longitude:axis = "X" ;
            grid_longitude:bounds = "grid_longitude_bounds" ;
            grid_longitude:standard_name = "grid_longitude" ;
            grid_longitude:units = "degrees" ;
        double grid_longitude_bounds(grid_longitude, bounds2) ;
        string rotated_latitude_longitude ;
            rotated_latitude_longitude:grid_mapping_name = "rotated_latitude_longitude" ;
            rotated_latitude_longitude:grid_north_pole_latitude = 38.f ;
            rotated_latitude_longitude:grid_north_pole_longitude = 190.f ;
   
   // global attributes:
            :Conventions = "CF-1.13" ;
   }


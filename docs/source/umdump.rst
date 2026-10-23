a.. _The-umdump-utility:

The `umdump` utility
====================

`umfive` includes a command line tool `umdump` which can be used to
dump the contents of a PP or fields file dataset to the terminal
(e.g. `umdump test.pp`). `umdump` displays the CF-netCDF view of the
dataset CDL format, using a very similarly layout to `ncdump -h`
(i.e. it does not include any variable data arrays), but without any
dependencies on the netCDF C library.

The example in this section uses the `test.pp` dataset (`download 704
kB
<https://raw.githubusercontent.com/NCAS-CMS/umfive/main/tests/data/test.pp>`_).

.. code-block:: console
   :caption: Example   

   $ umdump --help
   An ncdump-like view of a UK Met Office PP, fields file or dump dataset.

   Usage: umdump [--help] [<dataset name>]
   $ umdump test.pp
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


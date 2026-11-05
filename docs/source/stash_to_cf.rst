.. _STASH-to-CF-mappings:

STASH-to-CF mappings
====================

``umfive`` provides a mapping between Unified Model (UM) STASH codes
and the Climate and Forecast (CF) metadata conventions. It is used to
assign standard names, units, and sometimes coordinates and cell
methods, to UM data variables.

This STASH-to-CF table of mappings stored is the package's
``STASH_to_CF.txt`` file, which can be viewed :ref:`here
<The-STASH-to-CF-table>`.

:ref:`Programmatic access to the table
<Accessing-and-modifying-the-STASH-to-CF-table>` is also available.

Table structure
---------------

The table is a plain text file that uses the exclamation mark (``!``)
as a delimiter. Each line represents the CF mapping for a single STASH
code in a single UM submodel for a range of valid UM versions, and
consists of nine columns. Empty columns are permitted and represent
missing or inapplicable data for that field, and may have default
interpretations. The columns are:

1. **Submodel**: The STASH code's UM submodel (e.g. ``1`` for
   atmosphere, ``2`` for ocean, ``3`` for slab, ``4`` for
   wave). This field is always present. Note that the same STASH code
   can appear in more than submodel (for instance, submodels ``1`` and
   ``2`` have a STASH code of ``101``).

2. **STASH code**: The STASH code (e.g. ``1``, ``33``, ``101``,
   ``3236``, ``53206``). This field is always present.

3. **Description**: The description of the STASH code (e.g. ``U COMPNT
   OF WIND AFTER TIMESTEP``). The description is taken from the UM
   STASHmaster files. This field is always present.

4. **Units**: The physical units of the STASH code, in UDUNITS format
   (e.g. ``Pa``, ``m s-1``, ``K``, ``1``, ``kg kg-1``). If this field
   is empty it means that no units have been assigned, not that there
   are no units, nor does it imply that the STASH code is
   dimensionaless (although it may be).

5. **Valid from**: The UM version from which the STASH code and its CF
   mapping is valid (e.g. ``407`` for UM version 4.7, ``606.4`` for UM
   version 6.6.4, ``1308`` for UM version 13.8). When this field is
   empty it means that the STASH code is valid for all versions up to
   and including the version in the "valid from" field, or for all
   versions if that field is also empty.

6. **Valid to**: The UM version until which this STASH code and its CF
   mapping is valid. When this field is empty it means that the STASH
   code is valid for all versions from and after the "valid from"
   field, or for all versions if that field is also empty.

7. **CF standard name**: The CF standard name for the STASH code
   (e.g. ``surface_air_pressure``, ``eastward_wind``). If this field
   is empty it means that no standard name has been assigned, not
   necessarily that there is no standard name (but note that a
   standard name mapping will not exist for all STASH codes).

8. **CF extra metadata**: Additional CF coordinate and cell methods
   qualifiers conditions associated with the STASH variable
   (e.g. ``height=10m``, ``where_land``, ``where_open_sea``).

9. **Coordinate system**: Specifies the UM coordinate system to which
   the mapping applies (e.g. ``true_latitude_longitude``,
   ``rotated_latitude_longitude``). This is used when the same STASH
   code at the same UM version has different standard names for
   different UM coordinate systems.

Examples
--------

Consider the following entry from the STASH-to-CF table:

.. code-block:: text

   1!3209!10 METRE WIND U-COMP                !m s-1!501!!eastward_wind!height=10m!true_latitude_longitude

The columns are:

1. **Submodel ID**: ``1`` (Atmosphere)
2. **STASH Code**: ``3209`` 
3. **Description**: ``10 METRE WIND U-COMP``
4. **Units**: ``m s-1`` (metres per second)
5. **Valid from**: ``501`` (Valid from UM version 5.1)
6. **Valid to**: *empty* (Valid for all UM versions from 5.1 onwards)
7. **CF standard name**: ``eastward_wind``
8. **CF extra metadata**: ``height=10m`` (Requires a CF size 1 height
   coordinate at 10 metres)
9. **Coordinate system**: ``true_latitude_longitude`` (This mapping is
   only for UM models with a true (i.e. unrotated) latitude-longitude
   grid)

Here is an example for which there is no CF information:

.. code-block:: text

   2!107!ZOOPLANKTON                         !!606.2!606.4!!!

The columns are:

1. **Submodel ID**: ``2`` (Ocean)
2. **STASH Code**: ``107`` 
3. **Description**: ``ZOOPLANKTON``
4. **Units**: *empty* (No units assigned)
5. **Valid from**: ``606.2`` (Valid from UM version 6.6.2)
6. **Valid to**: ``606.4`` (Valid until UM version 6.6.4)
7. **CF standard name**: *empty* (No standard name assigned)
8. **CF extra metadata**: *empty*
9. **Coordinate system**: *empty*

.. _Accessing-and-modifying-the-STASH-to-CF-table:

Accessing and modifying the STASH-to-CF table
---------------------------------------------

The ``umfive`` module provides public functions to load, query,
and modify the STASH table in memory.

.. code-block:: python

   import umfive

   # Load the default STASH table (from umfive/data/STASH_to_CF.txt)
   umfive.load_stash_table()

   # Retrieve the CF mapping records for a specific submodel and STASH
   # code e.g. Submodel 1 (atmosphere), STASH code 5   
   records = umfive.stash_records(1, 5)
   for record in records:
       print(record)
       
   # Output:
   # ('THETAL IN THE EXTERNAL DUMP         ', 'K', None, 407.0, None, {}, '')
   # ('OROGRAPHIC GRADIENT  X COMPONENT    ', None, 606.0, None, None, {}, '')

   # Get a copy of the entire loaded STASH table dictionary. Keys are
   # (submodel, stash_code) tuples, values are tuples of records
   
   table = umfive.stash_table()

   # Add a new STASH code to the table in memory
   umfive.add_stash_record(
       submodel=3,
       stash_code=999,
       name='MY WATER TABLE DEPTH',
       units='m',
       standard_name='water_table_depth'
   )
   
   print(umfive.stash_records(3, 999))
   # Output:
   # (('MY WATER TABLE DEPTH', 'm', None, None, 'water_table_depth', {}, ''),)

   # Get a copy of updated STASH table dictionary, which has one more
   # entry than the default table.
   new_table = umfive.stash_table()
   assert len(new_table) == len(table) + 1

   # You can also load a custom table, choosing to merging it with the
   # existing table, or to replace the existing table entirely.
   #
   # umfive.load_stash_table('my_custom_table.txt', merge=True)
   # umfive.load_stash_table('my_custom_table.txt', merge=False)

.. _The-STASH-to-CF-table:

The STASH-to-CF table
---------------------

The following is the default STASH-to-CF table stored in the
``STASH_to_CF.txt`` file that is included with ``umfive``:

.. literalinclude:: ../../umfive/data/STASH_to_CF.txt
   :language: text

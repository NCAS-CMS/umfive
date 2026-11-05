.. _Lookup-headers:

Lookup headers                                         
==============

The underlying Unified Model (UM) lookup headers that define a data
variable can be inspected using the
`~umfive.DataVariable.lookup_header` and
`~umfive.DataVariable.lookup_header_items` methods of a
`umfive.DataVariable` instance.

The examples in this section use the `test.pp` dataset (`download 704
kB
<https://raw.githubusercontent.com/NCAS-CMS/umfive/main/tests/data/test.pp>`_).
and the `extra_data.pp` dataset (`download 2 kB
<https://raw.githubusercontent.com/NCAS-CMS/umfive/main/tests/data/extra_data.pp>`_).

Inspecting full lookup headers
------------------------------                                       

The `~umfive.DataVariable.lookup_header` method displays the full
contents of one or all of the lookup headers associated with the data
variable.

.. code-block:: python

   >>> import umfive                                                
   >>> um = umfive.File('test.pp')
   >>> var = um['UM_m01s15i201_vn405']                                  
   >>> var.lookup_header(0)  # Display the first lookup header (index 0)
   UM_m01s15i201_vn405: Lookup header 1 of 15
   ------------------------------------------
   LBYR: 1979 LBMON: 5 LBDAT: 1 LBHR: 0 LBMIN: 0 LBDAY: 121 LBYRD: 1979 LBMOND: 5
   LBDATD: 2 LBHRD: 0 LBMIND: 0 LBDAYD: 122 LBTIM: 121 LBFT: 3648 LBLREC: 11660
   LBCODE: 101 LBHEM: 3 LBROW: 110 LBNPT: 106 LBEXT: 0 LBPACK: 0 LBREL: 2 LBFC: 56
   LBCFC: 0 LBPROC: 128 LBVC: 8 LBRVC: 0 LBEXP: 133 LBEGIN: 1390592 LBNREC: 12288
   LBPROJ: 900 LBTYP: 5 LBLEV: 50 LBRSVD1: 0 LBRSVD2: 0 LBRSVD3: 0 LBRSVD4: 0
   LBSRCE: 1111 LBUSER1: 1 LBUSER2: 1390592 LBUSER3: 0 LBUSER4: 15201 LBUSER5: 0
   LBUSER6: 0 LBUSER7: 1 BRSVD1: 0.0 BRSVD2: 0.0 BRSVD3: 0.0 BRSVD4: 0.0
   BDATUM: 0.0 BACC: -99.0 BLEV: 50.000003814697266 BRLEV: 0.0 BHLEV: 0.0
   BHRLEV: 0.0 BPLAT: 38.0 BPLON: 190.0 BGOR: 0.0 BZY: 23.760000228881836
   BDY: -0.4399999976158142 BZX: 339.0199890136719 BDX: 0.4399999976158142
   BMDI: -1073741824.0 BMKS: 1.0
                                                                             
You can also pass ``'all'`` to display every lookup header, or set
``display=False`` to return the output as a string instead of printing
it.

If there is any extra data, then this is also displayed:

.. code-block:: python

   >>> import umfive                                                
   >>> um = umfive.File('extra_data.pp')
   >>> var = um['UM_m01s03i236_vn405']
   >>> var.lookup_header(0)
   UM_m01s03i236_vn405: Lookup header 1 of 1
   -----------------------------------------
   LBYR: 2289 LBMON: 12 LBDAT: 1 LBHR: 0 LBMIN: 0 LBDAY: 331 LBYRD: 2389
   LBMOND: 12 LBDATD: 1 LBHRD: 0 LBMIND: 0 LBDAYD: 331 LBTIM: 22 LBFT: 2585520
   LBLREC: 444 LBCODE: 11323 LBHEM: 3 LBROW: 100 LBNPT: 3 LBEXT: 144 LBPACK: 0
   LBREL: 2 LBFC: 16 LBCFC: 0 LBPROC: 131200 LBVC: 1 LBRVC: 0 LBEXP: 387253263
   LBEGIN: 2159211 LBNREC: 7008 LBPROJ: 7 LBTYP: 58 LBLEV: 9999 LBRSVD1: 0
   LBRSVD2: 0 LBRSVD3: 0 LBRSVD4: 0 LBSRCE: 1111 LBUSER1: 1 LBUSER2: 2159211
   LBUSER3: 0 LBUSER4: 3236 LBUSER5: 0 LBUSER6: 0 LBUSER7: 1 BRSVD1: 0.0
   BRSVD2: 0.0 BRSVD3: 0.0 BRSVD4: 0.0 BDATUM: 0.0 BACC: -99.0 BLEV: -1.0
   BRLEV: 0.0 BHLEV: 0.0 BHRLEV: 0.0 BPLAT: 90.0 BPLON: 0.0 BGOR: 0.0 BZY: 0.0
   BDY: 0.0 BZX: 0.0 BDX: 0.0 BMDI: -1073741824.0 BMKS: 1.0
   EXTRA DATA:
   domain_title: array(['Northern Hemisphere', 'Southern Hemisphere', 'Global'],
         dtype='<U19')
   x: array([1., 2., 3.], dtype=float32)
   x_domain_lower_bound: array([-1.875, -1.875, -1.875], dtype=float32)
   x_domain_upper_bound: array([358.125, 358.125, 358.125], dtype=float32)
   y: array([824550., 824910., 825270., 825630., 825990., 826350., 826710.,
          827070., 827430., 827790., 828150., 828510., 828870., 829230.,
          829590., 829950., 830310., 830670., 831030., 831390., 831750.,
          832110., 832470., 832830., 833190., 833550., 833910., 834270.,
          834630., 834990., 835350., 835710., 836070., 836430., 836790.,
          837150., 837510., 837870., 838230., 838590., 838950., 839310.,
          839670., 840030., 840390., 840750., 841110., 841470., 841830.,
          842190., 842550., 842910., 843270., 843630., 843990., 844350.,
          844710., 845070., 845430., 845790., 846150., 846510., 846870.,
          847230., 847590., 847950., 848310., 848670., 849030., 849390.,
          849750., 850110., 850470., 850830., 851190., 851550., 851910.,
          852270., 852630., 852990., 853350., 853710., 854070., 854430.,
          854790., 855150., 855510., 855870., 856230., 856590., 856950.,
          857310., 857670., 858030., 858390., 858750., 859110., 859470.,
          859830., 860190.], dtype=float32)
   y_domain_lower_bound: array([  1.25, -91.25, -91.25], dtype=float32)
   y_domain_upper_bound: array([91.25,  1.25, 91.25], dtype=float32)
   z_domain_lower_bound: array([-1.e+30, -1.e+30, -1.e+30], dtype=float32)
   z_domain_upper_bound: array([-1.e+30, -1.e+30, -1.e+30], dtype=float32)

Inspecting specific header items
--------------------------------

The `~umfive.DataVariable.lookup_header_items` method allows you to
extract the values of specific header items across all of the lookup
headers associated with the data variable.

.. code-block:: python

   >>> import umfive
   >>> um = umfive.File('test.pp')
   >>> var = um['UM_m01s15i201_vn405']
   >>> var.lookup_header_items(['LBYR', 'BLEV'])  # Display the LBYR and BLEV items for all 15 headers
   LBDAT: [1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3]
   BLEV: [850.0000610351562, 700.0000610351562, 500.0000305175781, 250.00001525878906, 50.000003814697266, 850.0000610351562, 700.0000610351562, 00.0000305175781, 250.00001525878906, 50.000003814697266, 850.0000610351562, 700.0000610351562, 500.0000305175781, 250.00001525878906, 0.000003814697266]

By default, ``items='all'`` will display all 64 header items. Setting
``display=False`` returns a dictionary of the requested items instead
of printing them.

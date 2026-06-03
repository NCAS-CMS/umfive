CF_CONVENTIONS = "CF-1.13"

N_INT_HDR = 45
N_REAL_HDR = 19
N_HDR = N_INT_HDR + N_REAL_HDR

(INDEX_LBYR,
INDEX_LBMON,
INDEX_LBDAT,
INDEX_LBHR,
INDEX_LBMIN,
INDEX_LBDAY,
INDEX_LBYRD,
INDEX_LBMOND,
INDEX_LBDATD,
INDEX_LBHRD,
INDEX_LBMIND,
INDEX_LBDAYD,
INDEX_LBTIM,
INDEX_LBFT,
INDEX_LBLREC,
INDEX_LBCODE,
INDEX_LBHEM,
INDEX_LBROW,
INDEX_LBNPT,
INDEX_LBEXT,
INDEX_LBPACK,
INDEX_LBREL,
INDEX_LBFC,
INDEX_LBCFC,
INDEX_LBPROC,
INDEX_LBVC,
INDEX_LBRVC,
INDEX_LBEXP,
INDEX_LBEGIN,
INDEX_LBNREC,
INDEX_LBPROJ,
INDEX_LBTYP,
INDEX_LBLEV,
INDEX_LBRSVD1,
INDEX_LBRSVD2,
INDEX_LBRSVD3,
INDEX_LBRSVD4,
INDEX_LBSRCE,
INDEX_LBUSER1,
INDEX_LBUSER2,
INDEX_LBUSER3,
INDEX_LBUSER4,
INDEX_LBUSER5,
INDEX_LBUSER6,
INDEX_LBUSER7) = tuple(range(45))

(INDEX_BRSVD1,
 INDEX_BRSVD2,
 INDEX_BRSVD3 ,
 INDEX_BRSVD4 ,
 INDEX_BDATUM ,
 INDEX_BACC  ,
 INDEX_BLEV ,
 INDEX_BRLEV,
 INDEX_BHLEV,
 INDEX_BHRLEV,
 INDEX_BPLAT ,
 INDEX_BPLON ,
 INDEX_BGOR ,
 INDEX_BZY ,
 INDEX_BDY ,
 INDEX_BZX ,
 INDEX_BDX ,
 INDEX_BMDI,
INDEX_BMKS) = tuple(range(19))

INT_MISSING_DATA = -32768

# PP missing data indicator
PP_RMDI = -1.0e30

# No no-missing-data value of BMDI (as described in UMDP F3 v805)
BMDI_no_missing_data_value = -1.0e30

# Reference surface pressure in Pascals
PSTAR = 1.0e5

# --------------------------------------------------------------------
# Characters used in decoding LBEXP into a runid
# --------------------------------------------------------------------
_runid_characters = (
    "a",
    "b",
    "c",
    "d",
    "e",
    "f",
    "g",
    "h",
    "i",
    "j",
    "k",
    "l",
    "m",
    "n",
    "o",
    "p",
    "q",
    "r",
    "s",
    "t",
    "u",
    "v",
    "w",
    "x",
    "y",
    "z",
    "0",
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "9",
)

_n_runid_characters = len(_runid_characters)

# --------------------------------------------------------------------
# Names of PP integer and real header items
# --------------------------------------------------------------------
_header_names = (
    "LBYR",
    "LBMON",
    "LBDAT",
    "LBHR",
    "LBMIN",
    "LBDAY",
    "LBYRD",
    "LBMOND",
    "LBDATD",
    "LBHRD",
    "LBMIND",
    "LBDAYD",
    "LBTIM",
    "LBFT",
    "LBLREC",
    "LBCODE",
    "LBHEM",
    "LBROW",
    "LBNPT",
    "LBEXT",
    "LBPACK",
    "LBREL",
    "LBFC",
    "LBCFC",
    "LBPROC",
    "LBVC",
    "LBRVC",
    "LBEXP",
    "LBEGIN",
    "LBNREC",
    "LBPROJ",
    "LBTYP",
    "LBLEV",
    "LBRSVD1",
    "LBRSVD2",
    "LBRSVD3",
    "LBRSVD4",
    "LBSRCE",
    "LBUSER1",
    "LBUSER2",
    "LBUSER3",
    "LBUSER4",
    "LBUSER5",
    "LBUSER6",
    "LBUSER7",
    "BRSVD1",
    "BRSVD2",
    "BRSVD3",
    "BRSVD4",
    "BDATUM",
    "BACC",
    "BLEV",
    "BRLEV",
    "BHLEV",
    "BHRLEV",
    "BPLAT",
    "BPLON",
    "BGOR",
    "BZY",
    "BDY",
    "BZX",
    "BDX",
    "BMDI",
    "BMKS",
)

# --------------------------------------------------------------------
# Positions of PP header items in their arrays
# --------------------------------------------------------------------
(
    lbyr,
    lbmon,
    lbdat,
    lbhr,
    lbmin,
    lbday,
    lbyrd,
    lbmond,
    lbdatd,
    lbhrd,
    lbmind,
    lbdayd,
    lbtim,
    lbft,
    lblrec,
    lbcode,
    lbhem,
    lbrow,
    lbnpt,
    lbext,
    lbpack,
    lbrel,
    lbfc,
    lbcfc,
    lbproc,
    lbvc,
    lbrvc,
    lbexp,
    lbegin,
    lbnrec,
    lbproj,
    lbtyp,
    lblev,
    lbrsvd1,
    lbrsvd2,
    lbrsvd3,
    lbrsvd4,
    lbsrce,
    lbuser1,
    lbuser2,
    lbuser3,
    lbuser4,
    lbuser5,
    lbuser6,
    lbuser7,
) = tuple(range(45))

(
    brsvd1,
    brsvd2,
    brsvd3,
    brsvd4,
    bdatum,
    bacc,
    blev,
    brlev,
    bhlev,
    bhrlev,
    bplat,
    bplon,
    bgor,
    bzy,
    bdy,
    bzx,
    bdx,
    bmdi,
    bmks,
) = tuple(range(19))

# --------------------------------------------------------------------
# Map PP axis codes to CF standard names (The full list of field code
# keys may be found at
# http://cms.ncas.ac.uk/html_umdocs/wave/@header.)
# --------------------------------------------------------------------
_coord_standard_name = {
    0: None,  # Sigma (or eta, for hybrid coordinate data).
    1: "air_pressure",  # Pressure (mb).
    2: "height",  # Height above sea level (km)
    # Eta (U.M. hybrid coordinates) only:
    3: "atmosphere_hybrid_sigma_pressure_coordinate",
    4: "depth",  # Depth below sea level (m)
    5: "model_level_number",  # Model level.
    6: "air_potential_temperature",  # Theta
    7: "atmosphere_sigma_coordinate",  # Sigma only.
    8: None,  # Sigma-theta
    10: "latitude",  # Latitude (degrees N).
    11: "longitude",  # Longitude (degrees E).
    # Site number (set of parallel rows or columns e.g.Time series):
    13: None,  # "region",
    14: "atmosphere_hybrid_height_coordinate",
    15: "height",
    20: "time",  # Time (days) (Gregorian calendar (not 360 day year))
    21: "time",  # Time (months)
    22: "time",  # Time (years)
    23: "time",  # Time (model days with 360 day model calendar)
    40: None,  # pseudolevel
    99: None,  # Other
    -10: "grid_latitude",  # Rotated latitude (degrees).
    -11: "grid_longitude",  # Rotated longitude (degrees).
    -20: "radiation_wavelength",
}

# --------------------------------------------------------------------
# Map PP axis codes to CF long names
# --------------------------------------------------------------------
_coord_long_name = {13: "site"}

# --------------------------------------------------------------------
# Map PP axis codes to UDUNITS strings
# --------------------------------------------------------------------
_axiscode_to_units = {
    0: "1",  # Sigma (or eta, for hybrid coordinate data)
    1: "hPa",  # air_pressure
    2: "m",  # altitude
    3: "1",  # atmosphere_hybrid_sigma_pressure_coordinate
    4: "m",  # depth
    5: "1",  # model_level_number
    6: "K",  # air_potential_temperature
    7: "1",  # atmosphere_sigma_coordinate
    10: "degrees_north",  # latitude
    11: "degrees_east",  # longitude
    13: "",  # region
    14: "1",  # atmosphere_hybrid_height_coordinate
    15: "m",  # height
    20: "days",  # time (gregorian)
    23: "days",  # time (360_day)
    40: "1",  # pseudolevel
    -10: "degrees",  # rotated latitude  (not an official axis code)
    -11: "degrees",  # rotated longitude (not an official axis code)
}

# --------------------------------------------------------------------
# Map PP axis codes to CF axis attributes
# --------------------------------------------------------------------
_coord_axis = {
    1: "Z",  # air_pressure
    2: "Z",  # altitude
    3: "Z",  # atmosphere_hybrid_sigma_pressure_coordinate
    4: "Z",  # depth
    5: "Z",  # model_level_number
    6: "Z",  # air_potential_temperature
    7: "Z",  # atmosphere_sigma_coordinate
    10: "Y",  # latitude
    11: "X",  # longitude
    13: None,  # region
    14: "Z",  # atmosphere_hybrid_height_coordinate
    15: "Z",  # height
    20: "T",  # time (gregorian)
    23: "T",  # time (360_day)
    40: None,  # pseudolevel
    -10: "Y",  # rotated latitude  (not an official axis code)
    -11: "X",  # rotated longitude (not an official axis code)
}

# --------------------------------------------------------------------
# Map PP axis codes to CF positive attributes
# --------------------------------------------------------------------
_coord_positive = {
    1: "down",  # air_pressure
    2: "up",  # altitude
    3: "down",  # atmosphere_hybrid_sigma_pressure_coordinate
    4: "down",  # depth
    5: None,  # model_level_number
    6: "up",  # air_potential_temperature
    7: "down",  # atmosphere_sigma_coordinate
    10: None,  # latitude
    11: None,  # longitude
    13: None,  # region
    14: "up",  # atmosphere_hybrid_height_coordinate
    15: "up",  # height
    20: None,  # time (gregorian)
    23: None,  # time (360_day)
    40: None,  # pseudolevel
    -10: None,  # rotated latitude  (not an official axis code)
    -11: None,  # rotated longitude (not an official axis code)
}

# --------------------------------------------------------------------
# Map LBVC codes to PP axis codes. The full list of field code keys
# may be found at http://cms.ncas.ac.uk/html_umdocs/wave/@fcodes
# --------------------------------------------------------------------
_lbvc_to_axiscode = {
    1: 2,  # altitude (Height)
    2: 4,  # depth (Depth)
    3: None,  # (Geopotential (= g*height))
    4: None,  # (ICAO height)
    6: 4,  # model_level_number  # Changed from 5 !!!
    7: None,  # (Exner pressure)
    8: 1,  # air_pressure  (Pressure)
    9: 3,  # atmosphere_hybrid_sigma_pressure_coordinate (Hybrid pressure)
    # dch check:
    10: 7,  # atmosphere_sigma_coordinate (Sigma (= p/surface p))
    16: None,  # (Temperature T)
    19: 6,  # air_potential_temperature (Potential temperature)
    27: None,  # (Atmospheric) density
    28: None,  # (d(p*)/dt .  p* = surface pressure)
    44: None,  # (Time in seconds)
    65: 14,  # atmosphere_hybrid_height_coordinate (Hybrid height)
    129: None,  # Surface
    176: 10,  # latitude    (Latitude)
    177: 11,  # longitude   (Longitude)
}

# --------------------------------------------------------------------
# Map model identifier codes to model names. The model identifier code
# is the last four digits of LBSRCE.
# --------------------------------------------------------------------
_lbsrce_model_codes = {1111: "UM"}

# --------------------------------------------------------------------
# Names of PP extra data codes
# --------------------------------------------------------------------
_extra_data_name = {
    1: "x",
    2: "y",
    3: "y_domain_lower_bound",
    4: "x_domain_lower_bound",
    5: "y_domain_upper_bound",
    6: "x_domain_upper_bound",
    7: "z_domain_lower_bound",
    8: "x_domain_upper_bound",
    9: "title",
    10: "domain_title",
    11: "x_lower_bound",
    12: "x_upper_bound",
    13: "y_lower_bound",
    14: "y_upper_bound",
}

# --------------------------------------------------------------------
# LBCODE values for unrotated latitude longitude grids
# --------------------------------------------------------------------
_true_latitude_longitude_lbcodes = set((1, 2))

# --------------------------------------------------------------------
# LBCODE values for rotated latitude longitude grids
# --------------------------------------------------------------------
_rotated_latitude_longitude_lbcodes = set((101, 102, 111))

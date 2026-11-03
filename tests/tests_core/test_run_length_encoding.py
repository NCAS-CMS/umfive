import struct

import numpy as np

# Import your umfive parser module
import umfive


def generate_run_length_encoded_pp_file(
    filepath="run_length_encoding.pp", endian=">"
):
    """Creates a 32-bit PP file containing 3 fields:

    1. Uncompressed land-sea mask (STASH 30, LBPACK=0) on a 3x4 grid
       (5 land, 7 sea).
    2. Land-compressed field (STASH 511, LBPACK=120) with 5 land values.
    3. Sea-compressed field (STASH 507, LBPACK=220) with 7 sea values.

    """
    ny, nx = 3, 4
    n_total = ny * nx

    bmdi = -999.0

    # 1. Land-Sea Mask (1.0 = Land, 0.0 = Sea)
    mask_grid = np.array(
        [1.0, 0.0, 1.0, 0.0, 0.0, 1.0, 0.0, 1.0, 1.0, 0.0, 0.0, 0.0],
        dtype=np.float32,
    )

    land_indices = np.where(mask_grid == 1.0)[0]  # 5 land points
    sea_indices = np.where(mask_grid == 0.0)[0]  # 7 sea points

    # 2. Compressed Data Values
    land_values = np.array([10, 20, 30, 40, 50], dtype=np.float32)
    sea_values = np.array([1, 2, 3, 4, 5, 6, 7], dtype=np.float32)

    # Ground-truth expected 2D matrices
    expected_land_3d = np.full(n_total, bmdi, dtype=np.float32)
    expected_land_3d[land_indices] = land_values
    expected_land_3d = expected_land_3d.reshape((1, ny, nx))

    expected_sea_3d = np.full(n_total, bmdi, dtype=np.float32)
    expected_sea_3d[sea_indices] = sea_values
    expected_sea_3d = expected_sea_3d.reshape((1, ny, nx))

    def write_fortran_record(f, payload_bytes):
        length = len(payload_bytes)
        bcw = struct.pack(f"{endian}I", length)
        f.write(bcw + payload_bytes + bcw)

    def build_pp_header(stash_item, lbpack, lblrec, lbrow, lbnpt):
        # 45 x Int32
        ints = [0] * 45
        ints[0] = 1963  # Word 1:  LBYR
        ints[1] = 6  # Word 2:  LBMON
        ints[2] = 1  # Word 3:  LBDAT
        ints[12] = 1  # Word 13: LBTIM
        ints[14] = lblrec  # Word 15: LBLREC
        ints[15] = 1  # Word 16: LBCODE
        ints[17] = lbrow  # Word 18: LBROW
        ints[18] = lbnpt  # Word 19: LBNPT
        ints[20] = lbpack  # Word 21: LBPACK (0=unpacked, 120=land, 220=sea)
        ints[22] = 395 if stash_item == 30 else 1907  # Word 23: LBFC
        ints[25] = 129  # Word 26: LBVC (Surface)
        ints[32] = 9999  # Word 33: LBLEV
        ints[37] = 13081111  # Word 38: LBSRCE
        ints[38] = 1  # Word 39: LBUSER1
        ints[41] = stash_item  # Word 42: LBUSER4
        ints[44] = 1  # Word 45: LBUSER7

        # 19 x Float32
        reals = [0.0] * 19
        reals[10] = 90.0  # Word 56: BPLAT
        reals[13] = -90.046875  # Word 59: BZY
        reals[14] = 0.09375  # Word 60: BDY
        reals[15] = -0.0703125  # Word 61: BZX
        reals[16] = 0.140625  # Word 62: BDX
        reals[17] = bmdi  # Word 63: BMDI
        reals[18] = 1.0  # Word 64: BMKS

        return struct.pack(f"{endian}45i", *ints) + struct.pack(
            f"{endian}19f", *reals
        )

    with open(filepath, "wb") as f:
        # Field 1: Land-Sea Mask
        hdr_mask = build_pp_header(
            stash_item=30, lbpack=0, lblrec=n_total, lbrow=ny, lbnpt=nx
        )
        write_fortran_record(f, hdr_mask)
        write_fortran_record(f, struct.pack(f"{endian}{n_total}f", *mask_grid))

        # Field 2: Land-Compressed Data
        hdr_land = build_pp_header(
            stash_item=511,
            lbpack=120,
            lblrec=len(land_indices),
            lbrow=ny,
            lbnpt=nx,
        )
        write_fortran_record(f, hdr_land)
        write_fortran_record(
            f, struct.pack(f"{endian}{len(land_indices)}f", *land_values)
        )

        # Field 3: Sea-Compressed Data
        hdr_sea = build_pp_header(
            stash_item=507,
            lbpack=220,
            lblrec=len(sea_indices),
            lbrow=ny,
            lbnpt=nx,
        )
        write_fortran_record(f, hdr_sea)
        write_fortran_record(
            f, struct.pack(f"{endian}{len(sea_indices)}f", *sea_values)
        )

    return mask_grid.reshape((1, ny, nx)), expected_land_3d, expected_sea_3d


def test_umfive_run_length_decompression(tmp_path):
    """Tests that umfive correctly loads a PP file with 3 fields and
    decompresses both land (LBPACK=120) and sea (LBPACK=220) compressed
    fields using a Land-Sea Mask."""
    pp_file = tmp_path / "run_length_encoding.pp"
    import os

    os.system(f"cp {str(pp_file)} /home/david/umfive/run_length_encoding.pp")
    expected_mask, expected_land, expected_sea = (
        generate_run_length_encoded_pp_file(pp_file)
    )

    INDEX_LBPACK = 20
    INDEX_LBUSER4 = 41

    subspace = (0, slice(1, None), slice(2, None))

    # Parse PP file using umfive
    fields = umfive.File(pp_file)

    # Verify field count
    assert (
        len(fields.data_variables) == 3
    ), f"Expected 3 data variables, found {len(fields.data_variables)}"

    # Test land-sea mask (uncompressed)
    mask_field = fields["UM_m01s00i030_vn1308"]
    int_hdr = mask_field.chunk_records[0].int_hdr
    assert int_hdr[INDEX_LBPACK] == 0
    assert int_hdr[INDEX_LBUSER4] == 30
    assert mask_field.data_loader_options.get("mask") is None
    assert mask_field.shape == (1, 3, 4)
    np.testing.assert_allclose(mask_field[...], expected_mask, rtol=1e-5)

    # Test land-compressed Field (LBPACK=120)
    land_field = fields["UM_m01s00i511_vn1308"]
    int_hdr = land_field.chunk_records[0].int_hdr
    assert int_hdr[INDEX_LBPACK] == 120
    assert int_hdr[INDEX_LBUSER4] == 511

    assert isinstance(
        land_field.data_loader_options.get("mask"), umfive.DataVariable
    )
    assert land_field.data_loader_options["mask"].dtype == np.float32
    assert land_field.data_loader_options["mask"].shape == (1, 3, 4)

    assert land_field.shape == (1, 3, 4)
    np.testing.assert_allclose(land_field[...], expected_land, rtol=1e-5)

    assert isinstance(land_field.data_loader_options.get("mask"), np.ndarray)
    assert land_field.data_loader_options["mask"].dtype == bool
    assert land_field.data_loader_options["mask"].shape == (3, 4)

    np.testing.assert_allclose(
        land_field[subspace], expected_land[subspace], rtol=1e-5
    )
    assert isinstance(land_field.data_loader_options.get("mask"), np.ndarray)
    assert land_field.data_loader_options["mask"].shape == (3, 4)

    # Test sea-compressed field (LBPACK=220)
    sea_field = fields["UM_m01s00i507_vn1308"]
    int_hdr = sea_field.chunk_records[0].int_hdr
    assert int_hdr[INDEX_LBPACK] == 220
    assert int_hdr[INDEX_LBUSER4] == 507

    assert isinstance(
        sea_field.data_loader_options.get("mask"), umfive.DataVariable
    )
    assert sea_field.data_loader_options["mask"].dtype == np.float32
    assert sea_field.data_loader_options["mask"].shape == (1, 3, 4)

    assert sea_field.shape == (1, 3, 4)
    np.testing.assert_allclose(sea_field[...], expected_sea, rtol=1e-5)

    assert isinstance(sea_field.data_loader_options.get("mask"), np.ndarray)
    assert sea_field.data_loader_options["mask"].dtype == bool
    assert sea_field.data_loader_options["mask"].shape == (3, 4)

    np.testing.assert_allclose(
        sea_field[subspace], expected_sea[subspace], rtol=1e-5
    )
    assert isinstance(sea_field.data_loader_options.get("mask"), np.ndarray)
    assert sea_field.data_loader_options["mask"].shape == (3, 4)

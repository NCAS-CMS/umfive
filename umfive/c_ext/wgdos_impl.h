#ifndef WG_NAME
#error WG_NAME macro must be defined
#endif
#ifndef WG_REAL
#error WG_REAL macro must be defined
#endif
#ifndef WG_WORD_SIZE
#error WG_WORD_SIZE macro must be defined
#endif
#ifndef WG_SWAP_BYTES
#error WG_SWAP_BYTES macro must be defined
#endif

static int WG_NAME(xpnd)(int ix, int32_t *icomp, WG_REAL *field, WG_REAL prec,
                         int ibit, WG_REAL base, int nop, WG_REAL mdi);
static int WG_NAME(extrin)(int32_t *icomp, int iword, int istart, int nbit,
                           int *inum, int isign);

int WG_NAME(unwgdos)(void *datain, int nbytes, WG_REAL *dataout, int nout, WG_REAL mdi)
{
    int isc, ix, iy;
    WG_REAL prec, base;
    int icx, j;
    int ibit, nop;
    int swap;
    char *p, *p1;

    p = datain;
    swap = -1;

    ix = get_int16_value(p + 8, big_endian);
    iy = get_int16_value(p + 10, big_endian);
    if (ix * iy == nout) {
        swap = 0;
    }

    if (swap == -1) {
        ix = get_int16_value(p + 10, little_endian);
        iy = get_int16_value(p + 8, little_endian);
        if (ix * iy == nout) {
            swap = 4;
        }
    }

    if (swap == -1) {
        ix = get_int16_value(p + 14, little_endian);
        iy = get_int16_value(p + 12, little_endian);
        if (ix * iy == nout) {
            swap = 8;
        }
    }

    if (swap == -1) {
        error_mesg("WGDOS data header record mismatch");
        return 1;
    } else if (swap == 4) {
        swap_bytes_sgl(datain, nbytes / 4);
    } else if (swap == 8) {
        swap_bytes_dbl(datain, nbytes / 8);
    }

    isc = get_int32_value(p + 4, big_endian);
    ix = get_int16_value(p + 8, big_endian);
    iy = get_int16_value(p + 10, big_endian);

    prec = pow(2.0, (double)isc);
    icx = 3;

    for (j = 0; j < iy; j++) {
        p1 = p + icx * 4;
        base = (WG_REAL)get_float32_value(p1);
        ibit = get_int16_value(p1 + 4, big_endian);
        nop = get_int16_value(p1 + 6, big_endian);
#if NATIVE_ORDERING == little_endian
        swap_bytes_sgl(p1 + 8, nop);
#endif
        if (WG_NAME(xpnd)(ix, (int32_t *)(p1 + 8), dataout, prec, ibit, base, nop, mdi)) {
            return 1;
        }
        icx += nop + 2;
        dataout += ix;
    }

    return 0;
}

static int WG_NAME(xpnd)(int ix, int32_t *icomp, WG_REAL *field, WG_REAL prec,
                         int ibit, WG_REAL base, int nop, WG_REAL mdi)
{
    int btmap = 0;
    int btmis = 0;
    int btmin = 0;
    int btzer = 0;
    int jword;
    int jbit;
    int j;
    int iscale;
    int *imap = NULL;
    int *imis = NULL;
    int *imin = NULL;
    int *izer = NULL;

    if (ibit >= 128) {
        btzer = 1;
        btmap = 1;
        ibit -= 128;
    }

    if (ibit >= 64) {
        btmin = 1;
        btmap = 1;
        ibit -= 64;
    }

    if (ibit >= 32) {
        btmis = 1;
        btmap = 1;
        ibit -= 32;
    }

    if (ibit > 32) {
        error_mesg("Number of bits used to pack wgdos data = %d must be <= 32", ibit);
        return 1;
    }

    if (btmap) {
        imap = malloc((size_t)ix * sizeof(int));
        if (imap == NULL) {
            error_mesg("Unable to allocate bitmap workspace");
            return 1;
        }
        for (j = 0; j < ix; j++) {
            imap[j] = 1;
        }
    }

    jword = 0;
    jbit = 31;

    if (btmis) {
        imis = malloc((size_t)ix * sizeof(int));
        if (imis == NULL) {
            free(imap);
            error_mesg("Unable to allocate missing-data bitmap workspace");
            return 1;
        }

        for (j = 0; j < ix; j++) {
            if (bit_test_value(icomp + jword, jbit)) {
                imis[j] = 1;
                imap[j] = 0;
            } else {
                imis[j] = 0;
            }

            if (jbit > 0) {
                jbit--;
            } else {
                jbit = 31;
                jword++;
            }
        }
    }

    if (btmin) {
        imin = malloc((size_t)ix * sizeof(int));
        if (imin == NULL) {
            free(imap);
            free(imis);
            error_mesg("Unable to allocate minimum-value bitmap workspace");
            return 1;
        }

        for (j = 0; j < ix; j++) {
            if (bit_test_value(icomp + jword, jbit)) {
                imin[j] = 1;
                imap[j] = 0;
            } else {
                imin[j] = 0;
            }

            if (jbit > 0) {
                jbit--;
            } else {
                jbit = 31;
                jword++;
            }
        }
    }

    if (btzer) {
        izer = malloc((size_t)ix * sizeof(int));
        if (izer == NULL) {
            free(imap);
            free(imis);
            free(imin);
            error_mesg("Unable to allocate zero-value bitmap workspace");
            return 1;
        }

        for (j = 0; j < ix; j++) {
            if (bit_test_value(icomp + jword, jbit)) {
                izer[j] = 0;
            } else {
                izer[j] = 1;
                imap[j] = 0;
            }

            if (jbit > 0) {
                jbit--;
            } else {
                jbit = 31;
                jword++;
            }
        }
    }

    if (btmap && jbit != 31) {
        jbit = 31;
        jword++;
    }

    if (ibit > 0) {
        for (j = 0; j < ix; j++) {
            if (btmap && imap[j] == 0) {
                continue;
            }

            WG_NAME(extrin)(icomp + jword, 4, jbit, ibit, &iscale, 0);
            field[j] = base + (WG_REAL)iscale * prec;

            jbit -= ibit;
            if (jbit < 0) {
                jword++;
                jbit += 32;
            }
        }

        if (btmin) {
            for (j = 0; j < ix; j++) {
                if (imin[j] == 1) {
                    field[j] = base;
                }
            }
        }
    } else {
        for (j = 0; j < ix; j++) {
            field[j] = base;
        }
    }

    if (btmis) {
        for (j = 0; j < ix; j++) {
            if (imis[j] == 1) {
                field[j] = mdi;
            }
        }
    }

    if (btzer) {
        for (j = 0; j < ix; j++) {
            if (izer[j] == 1) {
                field[j] = 0.0;
            }
        }
    }

    free(imap);
    free(imis);
    free(imin);
    free(izer);
    return 0;
}

static int WG_NAME(extrin)(int32_t *icomp, int iword, int istart, int nbit,
                           int *inum, int isign)
{
    (void)iword;
    if (isign == 0) {
        move_bits_value(icomp, istart, nbit, inum);
    } else if (isign == 1) {
        move_bits_value(icomp, istart - 1, nbit - 1, inum);
        *inum = (*icomp << (31 - istart)) & (~0 << 31);
        if (*inum < 0) {
            *inum = (~0 << (nbit - 1)) | *inum;
        }
    } else if (isign == 2) {
        move_bits_value(icomp, istart - 1, nbit - 1, inum);
        if (bit_test_value(icomp, istart)) {
            *inum = -*inum;
        }
    }

    return 0;
}

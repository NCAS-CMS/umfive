import logging
from concurrent.futures import ThreadPoolExecutor

from ppfive.core.data import (
    decode_record_array_from_raw,
    get_record_packed_nbytes,
    read_record_array,
)

# from ppfive.io.fsspec_reader import FsspecReader
from .bytereader import ByteReader
from .local_posix_reader import LocalPosixReader

logger = logging.getLogger(__name__)


class ChunkReadMixin:
    """Chunk selection reader.

    Chunk selection reader with serial, local-threaded, and fsspec bulk
    strategies.

    """

    def _get_required_chunks(self, indexer):
        """Get chunk information for the indexer.

        Walk *indexer* and return a list of ``(chunk_coords,
        chunk_selection, out_selection, storeinfo)246`` tuples for every
        chunk needed to satisfy the selection.

        :Parameters:

            indexer:

        :Returns:

            `list` of `tuple`

        """
        required = []
        for chunk_coords, chunk_selection, out_selection in indexer:
            chunk_offset = tuple(
                int(coord * chunk)
                for coord, chunk in zip(
                    chunk_coords, self._variable.chunks
                )
            )
            rec = self._record_cache.get(chunk_offset)
            if rec is None:
                raise OSError(
                    "Chunk coordinates not found in record index: "
                    f"{chunk_offset}"
                )

            chunk_shape = tuple(
                min(int(chunk), int(dim) - int(offset))
                for offset, chunk, dim in zip(
                    chunk_offset,
                    self._variable.chunks,
                    self._variable.shape,
                )
            )
            required.append(
                (
                    chunk_offset,
                    chunk_selection,
                    out_selection,
                    rec,
                    chunk_shape,
                )
            )

        return required

    def _decode_chunk_buffer(self, raw, rec, chunk_shape):
        """Apply the filter pipeline (if any).

        :Parameter:

            raw: `bytes`
                The raw bytes of the packed data.

            rec: `RecordInfo`
                The record for the data array.

            chunk_shape: `tuple` of `int`
                The chunks shape.

        :Returns:

            `numpy.ndarray`
                The array with the same shape as the chunk shape.

        """
        return decode_record_array_from_raw(raw, rec).reshape(chunk_shape)

    def _store_and_assign(self, decoded_chunks, out):
        """Put data values into *out*.

        :Parameters:

            decoded_chunks:

            out: `nump.ndarray`

        :Returns:

            `None`

        """
        for (
            _chunk_offset,
            chunk_selection,
            out_selection,
            chunk_data,
        ) in decoded_chunks:
            out[out_selection] = chunk_data[chunk_selection]

    def _read_serial_chunks(self, required, out):
        """Read one chunk at a time (safe for any file-like object).

        :Parameters:

            required:

            out: `nump.ndarray`

        :Returns:

            `None`

        """
        decoded_chunks = []
        for (
            chunk_offset,
            chunk_selection,
            out_selection,
            rec,
            chunk_shape,
        ) in required:
            #            chunk_data = read_record_array(
            #                self._variable.file._reader,
            #                rec,
            #            ).reshape(chunk_shape)
            chunk_data = read_record_array(self._variable.file._reader, rec)
            chunk_data = chunk_data.reshape(chunk_shape)
            decoded_chunks.append(
                (chunk_offset, chunk_selection, out_selection, chunk_data)
            )

        self._store_and_assign(decoded_chunks, out)

    def _read_parallel_local_chunks(self, required, out, thread_count):
        """Thread-parallel read via `os.pread`.

        `os.pread` does not advance the file-position pointer, so all
        worker threads share a single open file descriptor safely.

        :Parameters:

            required:

            out: `nump.ndarray`

            thread_count: `int`

        :Returns:

            `None`

        """

        def _read_one(item):
            chunk_offset, chunk_selection, out_selection, rec, chunk_shape = (
                item
            )
            chunk_data = read_record_array(
                self._variable.file._reader,
                rec,
            ).reshape(chunk_shape)
            return chunk_offset, chunk_selection, out_selection, chunk_data

        with ThreadPoolExecutor(max_workers=thread_count) as executor:
            for (
                _chunk_offset,
                chunk_selection,
                out_selection,
                chunk_data,
            ) in executor.map(_read_one, required):
                out[out_selection] = chunk_data[chunk_selection]

    def _read_bulk_fsspec_chunks(self, required, out, thread_count):
        """Bulk read via `fsspec` cat_ranges.

        Issues a single pipelined request for all required byte-ranges,
        which on object stores typically translates to a small number of
        HTTP range requests rather than one round-trip per chunk
        (reaching through the MetadataBufferingWrapper).

        :Parameters:

            required:

            out: `nump.ndarray`

            thread_count: `int`

        :Returns:

            `None`

        """
        reader = self._variable.file._reader
        path = reader.path
        fs = reader.fs
        starts = [rec.data_offset for _, _, _, rec, _ in required]
        stops = [
            rec.data_offset + get_record_packed_nbytes(rec)
            for _, _, _, rec, _ in required
        ]
        buffers = fs.cat_ranges([path] * len(required), starts, stops)
        items = list(zip(required, buffers))

        def _decode_one(item):
            (
                (
                    chunk_offset,
                    chunk_selection,
                    out_selection,
                    rec,
                    chunk_shape,
                ),
                raw,
            ) = item
            chunk_data = self._decode_chunk_buffer(raw, rec, chunk_shape)
            return chunk_offset, chunk_selection, out_selection, chunk_data

        if thread_count > 1:
            with ThreadPoolExecutor(max_workers=thread_count) as executor:
                decoded_iter = executor.map(_decode_one, items)
        else:
            decoded_iter = map(_decode_one, items)

        self._store_and_assign(decoded_iter, out)

    def _select_chunks(self, indexer, out):
        """Get required chunks and dispatch I/O to the best strategy.

        Called by `_get_selection_via_chunks` in place of the serial loop.

        :Parameters:

            indexer:

            out: `nump.ndarray`

        :Returns:

            `None`

        """
        file_obj = self._variable.file
        reader = file_obj._reader
        thread_count = int(getattr(file_obj, "_thread_count", 0) or 0)
        cat_range_allowed = bool(getattr(file_obj, "_cat_range_allowed", True))
        cat_str = "Cat ranges ON" if cat_range_allowed else "Cat ranges OFF"
        logger.info(
            f"[ppfive] select chunks: thread_count={thread_count}, {cat_str}"
        )

        required = self._get_required_chunks(indexer)
        logger.info(f"[ppfive] {len(required)} chunks required")

        if not required:
            return

        if thread_count:
            # if cat_range_allowed and isinstance(reader, FsspecReader):
            #    fh = getattr(reader, "_fh", None)
            #    actual_fh = getattr(fh, "fh", fh)
            #    if (
            #        actual_fh is not None
            #        and hasattr(actual_fh, "fs")
            #        and hasattr(actual_fh.fs, "cat_ranges")
            #    ):
            #        self._read_bulk_fsspec_chunks(required, out, thread_count)
            #        return

            if cat_range_allowed and isinstance(reader, ByteReader):
                fs = getattr(reader, "fs", None)
                if hasattr(fs, "cat_ranges"):
                    self._read_bulk_fsspec_chunks(required, out, thread_count)
                    return

            # Still here?
            if isinstance(reader, LocalPosixReader):
                self._read_parallel_local_chunks(required, out, thread_count)
                return

        # if (
        #    thread_count != 0
        #    and cat_range_allowed
        #    and isinstance(reader, FsspecReader)
        # ):
        #    fh = getattr(reader, "_fh", None)
        #    actual_fh = getattr(fh, "fh", fh)
        #    if (
        #        actual_fh is not None
        #        and hasattr(actual_fh, "fs")
        #        and hasattr(actual_fh.fs, "cat_ranges")
        #    ):
        #        self._read_bulk_fsspec_chunks(required, out, thread_count)
        #        return
        #
        # if thread_count != 0 and isinstance(reader, LocalPosixReader):
        #    self._read_parallel_local_chunks(required, out, thread_count)
        #    return

        # Still here?
        self._read_serial_chunks(required, out)

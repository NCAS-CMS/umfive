class MockFilesystem:
    """A mock `fsspec.filesystem` class.

    Used to store `fsspec.filesystem`-like attributes.

    **Initialisation**

    :Parameters:

        kwargs:
            The attribute names and values to store
            (e.g. ``protocol='file'``).

    """

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

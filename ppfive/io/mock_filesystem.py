class MockFilesystem:
    """A mock `fsspec.filesystem` class.

    Used to store `fsspec.filesystem` class attributes.

    """

    def __init__(self, **kwargs):
        """**Initialisation**

        :Parameters:

            kwargs:
                The attribute names and values to store
                (e.g. ``protocol='file'``).

        """
        for key, value in kwargs.items():
            setattr(self, key, value)

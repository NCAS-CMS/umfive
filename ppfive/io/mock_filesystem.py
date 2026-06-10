class MockFilesystem:
    """A mock `fsspec.filesystem` class for attribute storage."""

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

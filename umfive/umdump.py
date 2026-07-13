import signal
import sys

from .inspect import ppncdump


def main(argv=None):
    """Provides some of the functionality of ncdump and h5dump.

    By default this will attempt to do something similar to ncdump.
    - h will return this information
    - s is accepted for compatibility with p5dump output modes.

    """
    if argv is None:
        argv = sys.argv[1:]

    match argv:
        case []:
            raise ValueError("No filename provided")
        case ["-h"]:
            print(main.__doc__)
            return 0
        case ["--help"]:
            print(main.__doc__)
            return 0
        case [filename]:
            ppncdump(filename, special=False)
            return 0
        case ["-s", filename]:
            ppncdump(filename, special=True)
            return 0
        case _:
            raise ValueError(f"Invalid arguments: {argv}")


if __name__ == "__main__":
    try:
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    except (AttributeError, ValueError):
        pass

    try:
        sys.exit(main())
    except BrokenPipeError:
        try:
            sys.stderr.flush()
        except Exception:
            pass
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

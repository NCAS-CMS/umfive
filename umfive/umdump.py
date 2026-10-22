"""An `ncdump -h` view of a UK Met Office PP or fields file dataset."""

import sys


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    info = (
        "An ncdump-like view of a UK Met Office PP, fields file "
        "or dump dataset."
        "\n\n"
        "Usage: umdump [--help] [<dataset name>]"
    )

    match argv:
        case []:
            print(info)
            return 1

        case ["--help"]:
            print(info)
            return 0

        case [filename]:
            try:
                import xnetcdf
            except Exception as error:
                print(
                    f"Error: umdump requires the Python module 'xnetcdf' "
                    f"to be installed ({error})"
                )
                return 2

            try:
                import umfive

                u = umfive.File(filename)
                x = xnetcdf.Dataset(u, backend="umfive")
                x.ncdump()
            except Exception as error:
                print(
                    "Error: Python module 'xnetcdf' failed to generate the "
                    f"output ({error})"
                )
                return 3

            return 0

        case _:
            args = " ".join([f"{arg}" for arg in argv])
            print(f"Invalid arguments: {args}")
            return 2


if __name__ == "__main__":
    import signal

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

    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(4)

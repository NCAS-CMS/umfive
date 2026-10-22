import subprocess


def test_umdump_no_args():
    """Test running 'umdump' with no arguments."""
    result = subprocess.run(["umdump"], capture_output=True, text=True)
    assert result.returncode == 1
    output = result.stderr or result.stdout
    assert "usage" in output.lower()


def test_umdump_help():
    """Test running 'umdump --help'."""
    result = subprocess.run(
        ["umdump", "--help"], capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "usage" in result.stdout.lower()


def test_umdump_single_file():
    """Test running 'umdump <file>'."""
    pp_file = "tests/data/hybrid_height.pp"

    result = subprocess.run(
        ["umdump", pp_file], capture_output=True, text=True
    )

    assert result.returncode == 0

    output = result.stdout.lower()
    assert "dimensions" in output
    assert "variables" in output

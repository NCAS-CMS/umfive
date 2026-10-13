"""Generate the dump outputs in tests/data."""

import umfive

directory = "tests/data"

dataset_suffix = {
    "cl_umfile": "",
    "test": ".pp",
    "extra_data": ".pp",
    "umfile": ".pp",
    "wgdos_packed": ".pp",
    "hybrid_height": ".pp",
}

for dataset, suffix in dataset_suffix.items():
    infile = f"{directory}/{dataset}{suffix}"
    outfile = f"{directory}/{dataset}_dump.txt"
    print("Generating", outfile, "from", infile)
    u = umfive.File(infile)
    dump = u.dump(display=False, data=True)
    with open(outfile, "w", encoding="utf-8") as f:
        f.write(dump)

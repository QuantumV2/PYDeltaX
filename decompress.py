import os
import sys
from format import *
from pathlib import Path

destination = sys.argv[2]
Path(destination).mkdir(parents=True, exist_ok=True)
with open(sys.argv[1], 'rb') as f:
    data = f.read()

archive = DeltaXArchive.unpack(data)

# get all the patterns 
patterns = []
for pattern in archive[1].patterns:
    patterns.append(pattern.data)

#start building the file data

# "path": [data, size]
file_data = {}
for file in archive[2].files:
    file_data[file.path] = [b'', file.original_size]
    for chunk in file.chunks:
        if chunk.raw_data:
            file_data[file.path][0] += chunk.data
        else:
            file_data[file.path][0] += patterns[chunk.data]

#print([p.__dict__ for p in archive[1].patterns])
for file, filedata in file_data.items():
    file = f"{destination}{os.sep}{file}"
    filepath = Path(file)
    filepath.parent.mkdir(exist_ok=True, parents=True)
    with filepath.open('wb') as f:
        f.write(filedata[0])
for dir in archive[2].emptydirs:
    try:
        Path(f"{destination}{os.sep}{dir.decode('utf-8')}").mkdir()
    except:
        pass
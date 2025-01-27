import sys
import pathlib
from format import *
import utils
import re
import os
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed

archivedata = [DeltaXHeader()]

sepsymbol = ""
target = pathlib.Path(sys.argv[1])
try:
    chunksize = int(sys.argv[2])
except:
    chunksize = None
    sepsymbol = bytes(sys.argv[2], encoding="utf-8")

# track all chunk occurrences
chunk_counts = {}  # hash -> total count of appearances
chunk_data = {}    # hash -> actual chunk content

files = []
directories = []
for item in target.rglob("*"):
    if item.is_file():
        relative_path = str(item.relative_to(target))
        files.append(relative_path)
    elif item.is_dir() and not any(item.iterdir()):
        relative_path = str(item.relative_to(target))
        directories.append(relative_path)

use_chunks = True if chunksize != None else False

def process_file(file):
    local_chunk_counts = {}
    local_chunk_data = {}
    with open(f"{sys.argv[1]}{os.sep}{file}", "rb") as f:
        print(f"Counting {file.encode('utf-8').decode('utf-8')}")
        if use_chunks:
            while True:
                chunk = f.read(chunksize)
                if not chunk:
                    break
                chunk_hash = hashlib.sha1(chunk).hexdigest()
                local_chunk_counts[chunk_hash] = local_chunk_counts.get(chunk_hash, 0) + 1
                local_chunk_data[chunk_hash] = chunk
        else:
            data = f.read()
            spaces = re.split(rb'[\s' + sepsymbol + rb']+', data)
            for space in spaces:
                if space:  # ignore empty spaces
                    space = space + sepsymbol
                    space_hash = hashlib.sha1(space).hexdigest()
                    local_chunk_counts[space_hash] = local_chunk_counts.get(space_hash, 0) + 1
                    local_chunk_data[space_hash] = space
    return local_chunk_counts, local_chunk_data

# first pass: count all chunks or spaces
with ThreadPoolExecutor() as executor:
    futures = [executor.submit(process_file, file) for file in files]
    for future in as_completed(futures):
        local_chunk_counts, local_chunk_data = future.result()
        for chunk_hash, count in local_chunk_counts.items():
            chunk_counts[chunk_hash] = chunk_counts.get(chunk_hash, 0) + count
        for chunk_hash, chunk in local_chunk_data.items():
            chunk_data[chunk_hash] = chunk

# murder chunks that only appear once
chunks = {h: chunk_data[h] for h, count in chunk_counts.items() if count > 1}

def build_file_data(file):
    with open(f"{sys.argv[1]}{os.sep}{file}", "rb") as f:
        print(f"Building {file.encode('utf-8').decode('utf-8')}")
        file_data = [[], int(pathlib.Path(f"{sys.argv[1]}{os.sep}{file}").stat().st_size)]
        ref_chunks = {}  # (0,5): "hello"
        filebytes = f.read()
        for chunk_hash, chunk in list(chunks.items()):
            occurrences = utils.find_all(filebytes, chunk)
            if occurrences:
                for occurrence in occurrences:
                    ref_chunks[(occurrence, len(chunk))] = chunk
        current_pos = 0
        for (start, length), chunk in list(ref_chunks.items()):
            if current_pos < start:
                rawdat = filebytes[current_pos:start]
                file_data[0].append(DeltaXChunk(True, rawdat))
                current_pos = start
            if current_pos == start:
                file_data[0].append(DeltaXChunk(False, list(chunks.values()).index(chunk)))
                current_pos += length
        if current_pos < len(filebytes):
            remaining = filebytes[current_pos:]
            file_data[0].append(DeltaXChunk(True, remaining))
            current_pos = len(filebytes)
    return file, file_data

# second pass for building file data
filedata = {}  # filename -> [ [DeltaXChunk, ...], size]
with ThreadPoolExecutor() as executor:
    futures = [executor.submit(build_file_data, file) for file in files]
    for future in as_completed(futures):
        file, file_data = future.result()
        filedata[file] = file_data

patterns = []
for chunk in list(chunks.values()):
    patterns.append(DeltaXPattern(bytes(chunk)))
pattable = DeltaXPatternTable(patterns)

archivedata.append(pattable)

dxfiles = []
for name, file in filedata.items():
    dxfiles.append(DeltaXFileData(name, file[1], file[0]))
filetable = DeltaXFileTable(dxfiles, directories)

archivedata.append(filetable)

archive = DeltaXArchive(archivedata)
packed = archive.pack()

with open(f"output.dx", "wb") as f:
    f.write(packed)
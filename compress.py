#import random
import sys
import pathlib
from format import *
#import binascii
import utils
import re
import os
import hashlib

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

# first pass: count all chunks or spaces
for file in files:
    with open(f"{sys.argv[1]}{os.sep}{file}", "rb") as f:
        if use_chunks:
            while True:
                chunk = f.read(chunksize)
                if not chunk:
                    break
                chunk_hash = hashlib.sha1(chunk).hexdigest()
                chunk_counts[chunk_hash] = chunk_counts.get(chunk_hash, 0) + 1
                chunk_data[chunk_hash] = chunk
        else:
            data = f.read()
            spaces =  re.split(rb'[\s'+ sepsymbol + rb']+', data)
            for space in spaces:
                if space:  # ignore empty spaces
                    space = space + sepsymbol
                    space_hash = hashlib.sha1(space).hexdigest()
                    chunk_counts[space_hash] = chunk_counts.get(space_hash, 0) + 1
                    chunk_data[space_hash] = space


# murder chunks that only appear once
chunks = {h: chunk_data[h] for h, count in chunk_counts.items() if count > 1}

# second pass for building file data
filedata = {}  # filename -> [ [DeltaXChunk, ...], size]
for file in files:
    with open(f"{sys.argv[1]}{os.sep}{file}", "rb") as f:
        filedata[file] = [[], int(pathlib.Path(f"{sys.argv[1]}{os.sep}{file}").stat().st_size)]
        ref_chunks = {} # (0,5): "hello"
        filebytes = f.read()
        for chunk_hash, chunk in list(chunks.items()):
            occurences = utils.find_all(filebytes, chunk)

            if occurences != []:
                for occurence in occurences:
                    #print(f"CHUNK {chunk} DETECTED AS A REFERENCE")
                    ref_chunks[(occurence, len(chunk))] = chunk
        current_pos = 0
        for (start, length), chunk in list(ref_chunks.items()):
            if current_pos < start:
                rawdat = filebytes[current_pos:start]
                filedata[file][0].append(DeltaXChunk(True, rawdat))
                current_pos = start
            if current_pos == start:
                filedata[file][0].append(DeltaXChunk(False, list(chunks.values()).index(chunk)))
                current_pos += length
                
        if current_pos < len(filebytes):
            remaining = filebytes[current_pos:]
            filedata[file][0].append(DeltaXChunk(True, remaining))
            current_pos = len(filebytes)

    #print(chunk_data)
    #for chunk in filedata['format.py'][0]:
        #print(chunk.__dict__)
patterns = []
for chunk in list(chunks.values()):
    patterns.append(DeltaXPattern(bytes(chunk)))
pattable = DeltaXPatternTable(patterns)

archivedata.append(pattable)

dxfiles = []
for name, file in filedata.items():
    dxfiles.append(DeltaXFileData(name, file[1], file[0] ))
filetable = DeltaXFileTable(dxfiles, directories)

archivedata.append(filetable)



archive = DeltaXArchive(archivedata)
packed = archive.pack()
#print(binascii.hexlify(packed))

#print(chunks)
with open(f"output.dx", "wb") as f:
    f.write(packed)
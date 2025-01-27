# DeltaX
## Overview
DeltaX is a compression format that uses patterns to compress multiple files efficiently
## Usage

Compress:


    python compress.py "folder" "separator or a number interval"

Decompress:


    python decompress.py "output.dx" "target folder"





DeltaX (ΔX) v1 - Format Specification

    Note: Everything except the header uses GZIP for compression

    HEADER (8 bytes)
        Magic bytes "DX" (2 bytes)
        Version number (variable length)
        Flags:
            [Bit 1 - Bit 32] - reserved for future use

        PATTERN TABLE 
            Pattern count (variable length)
            For each pattern:
                Pattern length (2 bytes)
                Pattern data (variable length)
        FILE TABLE
            File count (variable length)
            For each file:
                Path length (2 bytes)
                Path string (UTF-8)
                Original file size (variable length)
                Chunk count (variable length)
                For each chunk:
                    Chunk type (1 byte):
                    Pattern reference (0x0)
                    Pattern index (variable length)
                    Raw data (0x1)
                    Length (2 bytes)
                    Raw bytes (variable length)
            If there's any empty folders, it adds “DIR” bytes
            at the end and lists all the folder names in the 
            following format:
                Length (var length)
                Name Bytes (var length)

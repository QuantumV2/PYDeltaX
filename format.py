import struct
import gzip
def encode_varint(number):
    bytes_list = []
    while number > 0:
        byte = number & 0x7f
        number >>= 7
        if number > 0:
            byte |= 0x80
        bytes_list.append(byte)
    return bytes(bytes_list) if bytes_list else bytes([0])

def decode_varint(buffer, offset=0):
    result = 0
    shift = 0
    while True:
        byte = buffer[offset]
        offset += 1
        result |= (byte & 0x7f) << shift
        if not (byte & 0x80):
            break
        shift += 7
    return result, offset


class DeltaXArchive:
    def __init__(self, data):
        self.data = data

    def pack(self):
        # Pack header normally
        result = self.data[0].pack()
        
        # Compress pattern table
        pattern_table = gzip.compress(self.data[1].pack())
        result += encode_varint(len(pattern_table))
        result += pattern_table
        
        # Compress file table
        file_table = gzip.compress(self.data[2].pack())
        result += encode_varint(len(file_table))
        result += file_table
        
        return result

    @classmethod
    def unpack(cls, buffer):
        result = []
        current_pos = 0

        # Unpack header
        hdr = DeltaXHeader.unpack(buffer)
        result.append(hdr)
        current_pos += len(hdr.pack())

        # Unpack and decompress pattern table
        pattern_size, offset = decode_varint(buffer[current_pos:])
        current_pos += offset
        pattern_data = gzip.decompress(buffer[current_pos:current_pos + pattern_size])
        ptrt = DeltaXPatternTable.unpack(pattern_data)
        result.append(ptrt)
        current_pos += pattern_size

        # Unpack and decompress file table
        file_size, offset = decode_varint(buffer[current_pos:])
        current_pos += offset
        file_data = gzip.decompress(buffer[current_pos:current_pos + file_size])
        ft = DeltaXFileTable.unpack(file_data)
        result.append(ft)

        return result


class DeltaXHeader:
    def __init__(self):
        self.magic = 0x4458  # 'DX'
        self.version = 1
        self.flags = 0

    def pack(self):
        return struct.pack('>HHI', self.magic, self.version, self.flags)
    @classmethod
    def unpack(cls, buffer):
        header = cls()
        header.magic, header.version, header.flags = struct.unpack('>HHI', buffer[:8])
        
        if header.magic != 0x4458:
            raise ValueError("Invalid magic number - not a valid DeltaX file")
            
        return header
class DeltaXPattern:
    def __init__(self, datbytes=bytes()):
        data = bytes(datbytes) if isinstance(datbytes, list) else datbytes
        self.patternlength = len(data)
        self.data = data

    def pack(self):
        self.patternlength = len(self.data)
        result = bytearray()
        result.extend(encode_varint(self.patternlength))
        result.extend(self.data)
        return bytes(result)

    @classmethod
    def unpack(cls, buffer):
        pattern = cls()
        pattern.patternlength, offset = decode_varint(buffer)
        pattern.data = buffer[offset:offset + pattern.patternlength]
        return pattern

class DeltaXPatternTable:
    def __init__(self, patterns=None):
        self.patterns = patterns if patterns else []
        self.patterncount = len(self.patterns)

    def pack(self):
        self.patterncount = len(self.patterns)
        result = bytearray()
        result.extend(encode_varint(self.patterncount))

        for pattern in self.patterns:
            result.extend(pattern.pack())

        return bytes(result)

    @classmethod
    def unpack(cls, buffer):
        table = cls()
        current_pos = 0

        table.patterncount, offset = decode_varint(buffer)
        current_pos += offset

        table.patterns = []
        for _ in range(table.patterncount):
            pattern = DeltaXPattern.unpack(buffer[current_pos:])
            pattern_size = len(pattern.pack())
            table.patterns.append(pattern)
            current_pos += pattern_size

        return table
class DeltaXChunk:
    def __init__(self, raw_data=True, data=bytes()):
        self.raw_data = raw_data
        self.data = data

    def pack(self):
        result = bytearray()
        # Boolean flag stays as 1 byte
        result.extend(struct.pack('>?', self.raw_data))
        
        if self.raw_data:
            # For raw data, encode length as varint and append data
            result.extend(encode_varint(len(self.data)))
            result.extend(self.data)
        else:
            # For reference chunks, just encode the index as varint
            result.extend(encode_varint(self.data))
        
        return bytes(result)

    @classmethod
    def unpack(cls, buffer):
        chunk = cls()
        current_pos = 0
        
        # Get boolean flag
        chunk.raw_data = struct.unpack('>?', buffer[0:1])[0]
        current_pos += 1

        if chunk.raw_data:
            # Get length as varint and then raw data
            length, offset = decode_varint(buffer[current_pos:])
            current_pos += offset
            chunk.data = buffer[current_pos:current_pos + length]
        else:
            # Get reference index as varint
            chunk.data, _ = decode_varint(buffer[current_pos:])

        return chunk
class DeltaXFileData:
    def __init__(self, path, size, chunks):
        self.path = path
        self.original_size = size
        self.chunks = chunks  # chunk objects

    def pack(self):
        result = bytearray()
        
        # Path length and path
        path_bytes = self.path.encode('utf-8')
        result.extend(encode_varint(len(path_bytes)))
        result.extend(path_bytes)
        
        # Original size
        result.extend(encode_varint(self.original_size))
        
        # Chunk count
        result.extend(encode_varint(len(self.chunks)))
        
        # Pack each chunk
        for chunk in self.chunks:
            result.extend(chunk.pack())
          
        return bytes(result)
    
    @classmethod
    def unpack(cls, buffer):
        file_data = cls("", 0, [])
        current_pos = 0
        # Path length and path
        path_length, offset = decode_varint(buffer, current_pos)
        current_pos = offset
        file_data.path = buffer[current_pos:current_pos+path_length].decode('utf-8')
        current_pos += path_length
        # Original size
        file_data.original_size, offset = decode_varint(buffer, current_pos)
        current_pos = offset
        # Chunk count
        chunk_count, offset = decode_varint(buffer, current_pos)
        current_pos = offset
        # Unpack chunks
        file_data.chunks = []
        for _ in range(chunk_count):
            chunk = DeltaXChunk.unpack(buffer[current_pos:])
            
            chunk_size = len(chunk.pack())
            file_data.chunks.append(chunk)
            current_pos += chunk_size
        return file_data
    
class DeltaXFileTable:
    def __init__(self, files=[], emptydirs=[]):
        self.files = files
        self.emptydirs = emptydirs
        self.filecount = len(self.files)

    def pack(self):
        self.filecount = len(self.files)
        result = bytearray()

        # Store file count as varint instead of 4 bytes
        result.extend(encode_varint(self.filecount))

        # Pack each file
        for file in self.files:
            result.extend(file.pack())
        
        if self.emptydirs:
            result.extend(b'DIR')
            for dir in self.emptydirs:
                result.extend(encode_varint(len(dir)))
                result.extend(bytes(dir, encoding="utf-8"))
        
        return bytes(result)

    @classmethod
    def unpack(cls, buffer):
        table = cls()
        current_pos = 0

        # Get file count from varint
        table.filecount, offset = decode_varint(buffer)
        current_pos += offset

        # Unpack each file
        table.files = []
        for _ in range(table.filecount):
            file_data = DeltaXFileData.unpack(buffer[current_pos:])
            file_size = len(file_data.pack())
            table.files.append(file_data)
            current_pos += file_size

        if current_pos+3 < len(buffer) and buffer[current_pos:current_pos+3] == b'DIR':
            current_pos += 3
            while current_pos < len(buffer):
                
                dirlen, offset = decode_varint(buffer, current_pos)
                current_pos = offset
                table.emptydirs.append(buffer[current_pos:current_pos+dirlen])
                current_pos += dirlen

        return table
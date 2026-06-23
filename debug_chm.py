import struct

with open(r'c:\Users\mdval\Desktop\etaps mcp\CSI API ETABS v1.chm', 'rb') as f:
    data = f.read()

off = 120  # 0x78 - ITSP header offset
fmt = "<I"

print('ITSP header raw dump:')
for i in range(0, 0x60, 4):
    if off + i + 4 <= len(data):
        val = struct.unpack_from(fmt, data, off + i)[0]
        print(f'  +0x{i:02X}: 0x{val:08x}  ({val})')

print()
print('Interpreted ITSP:')
print(f'  Signature: {data[off:off+4]}')
print(f'  Version: {struct.unpack_from(fmt, data, off+4)[0]}')
print(f'  Dir header length: {struct.unpack_from(fmt, data, off+8)[0]}')
print(f'  Unknown: 0x{struct.unpack_from(fmt, data, off+12)[0]:x}')
print(f'  Chunk size: {struct.unpack_from(fmt, data, off+16)[0]}')
print(f'  Quickref density: {struct.unpack_from(fmt, data, off+20)[0]}')
print(f'  Index depth: {struct.unpack_from(fmt, data, off+24)[0]}')
print(f'  Root index chunk: {struct.unpack_from("<i", data, off+28)[0]}')
print(f'  First PMGL chunk: {struct.unpack_from(fmt, data, off+32)[0]}')
print(f'  Last PMGL chunk: {struct.unpack_from(fmt, data, off+36)[0]}')
print(f'  Unknown2: {struct.unpack_from("<i", data, off+40)[0]}')
print(f'  Num dir chunks: {struct.unpack_from(fmt, data, off+44)[0]}')
print(f'  Language ID: {struct.unpack_from(fmt, data, off+48)[0]}')

# Check what's at the first chunk position
chunk_size = struct.unpack_from(fmt, data, off+16)[0]
dir_header_len = struct.unpack_from(fmt, data, off+8)[0]
first_chunk_off = off + dir_header_len
print(f'\nFirst chunk at offset: {first_chunk_off}')
print(f'First chunk signature: {data[first_chunk_off:first_chunk_off+4]}')
print(f'Chunk size: {chunk_size}')

# Dump first 64 bytes of first chunk
print('\nFirst chunk raw:')
for i in range(0, min(64, chunk_size), 4):
    val = struct.unpack_from(fmt, data, first_chunk_off + i)[0]
    print(f'  +0x{i:02X}: 0x{val:08x}')

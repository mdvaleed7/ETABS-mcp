"""
Pure Python CHM reader/extractor v3 - correct ITSP field layout
"""
import struct
import os
import shutil

class CHMReader:
    def __init__(self, filename):
        with open(filename, 'rb') as f:
            self.data = f.read()
        self.parse_itsf_header()
        self.parse_itsp_header()
        self.parse_directory()
        
    def parse_itsf_header(self):
        sig = self.data[0:4]
        assert sig == b'ITSF'
        self.itsf_version = struct.unpack_from('<I', self.data, 4)[0]
        
        # Header section 1 (directory)
        self.dir_offset = struct.unpack_from('<Q', self.data, 0x48)[0]
        self.dir_len = struct.unpack_from('<Q', self.data, 0x50)[0]
        # Content section offset
        self.content_offset = struct.unpack_from('<Q', self.data, 0x58)[0]
        
    def parse_itsp_header(self):
        off = self.dir_offset
        assert self.data[off:off+4] == b'ITSP'
        
        self.dir_header_len = struct.unpack_from('<I', self.data, off + 8)[0]
        self.chunk_size = struct.unpack_from('<I', self.data, off + 0x10)[0]
        self.index_depth = struct.unpack_from('<I', self.data, off + 0x18)[0]
        self.first_pmgl = struct.unpack_from('<I', self.data, off + 0x20)[0]
        self.last_pmgl = struct.unpack_from('<I', self.data, off + 0x24)[0]
        self.num_chunks = struct.unpack_from('<I', self.data, off + 0x2C)[0]
        
        print(f"Chunks: {self.num_chunks}, size: {self.chunk_size}, PMGL range: {self.first_pmgl}-{self.last_pmgl}")
        
    def read_encint(self, offset):
        result = 0
        while offset < len(self.data):
            byte = self.data[offset]
            offset += 1
            result = (result << 7) | (byte & 0x7F)
            if not (byte & 0x80):
                break
        return result, offset
    
    def parse_directory(self):
        self.entries = {}
        chunks_start = self.dir_offset + self.dir_header_len
        
        for chunk_num in range(self.num_chunks):
            chunk_offset = chunks_start + chunk_num * self.chunk_size
            sig = self.data[chunk_offset:chunk_offset + 4]
            
            if sig == b'PMGL':
                self.parse_pmgl(chunk_offset)
                
    def parse_pmgl(self, chunk_offset):
        free_space = struct.unpack_from('<I', self.data, chunk_offset + 4)[0]
        
        offset = chunk_offset + 0x14
        end = chunk_offset + self.chunk_size - free_space
        
        while offset < end:
            try:
                name_len, offset = self.read_encint(offset)
                if name_len <= 0 or name_len > 5000 or offset + name_len > len(self.data):
                    break
                    
                name = self.data[offset:offset + name_len]
                offset += name_len
                
                try:
                    name_str = name.decode('utf-8')
                except:
                    name_str = name.decode('latin-1')
                
                section, offset = self.read_encint(offset)
                entry_offset, offset = self.read_encint(offset)
                entry_length, offset = self.read_encint(offset)
                
                self.entries[name_str] = {
                    'section': section,
                    'offset': entry_offset,
                    'length': entry_length
                }
            except Exception as e:
                break
    
    def get_content(self, entry):
        if entry['section'] == 0:
            offset = self.content_offset + entry['offset']
            return self.data[offset:offset + entry['length']]
        return None
    
    def extract_to(self, out_dir):
        os.makedirs(out_dir, exist_ok=True)
        count = 0
        
        for name, entry in sorted(self.entries.items()):
            if entry['length'] == 0 or name.endswith('/'):
                continue
            
            content = self.get_content(entry)
            if content:
                out_path = os.path.join(out_dir, name.lstrip('/').replace('/', os.sep))
                dirname = os.path.dirname(out_path)
                if dirname:
                    os.makedirs(dirname, exist_ok=True)
                with open(out_path, 'wb') as f:
                    f.write(content)
                count += 1
        
        return count


if __name__ == '__main__':
    chm_path = r'c:\Users\mdval\Desktop\etaps mcp\CSI API ETABS v1.chm'
    out_dir = r'c:\Users\mdval\Desktop\etaps mcp\extracted_docs'
    
    if os.path.exists(out_dir):
        shutil.rmtree(out_dir)
    
    reader = CHMReader(chm_path)
    
    print(f"\nTotal entries: {len(reader.entries)}")
    
    s0 = {n: e for n, e in reader.entries.items() if e['section'] == 0 and e['length'] > 0 and not n.endswith('/')}
    s1 = {n: e for n, e in reader.entries.items() if e['section'] == 1 and e['length'] > 0 and not n.endswith('/')}
    
    print(f"Section 0 (uncompressed): {len(s0)}")
    for name in sorted(s0.keys())[:10]:
        print(f"  {name} ({s0[name]['length']} bytes)")
    
    print(f"\nSection 1 (compressed): {len(s1)}")
    for name in sorted(s1.keys())[:50]:
        print(f"  {name} ({s1[name]['length']} bytes)")
    
    count = reader.extract_to(out_dir)
    print(f"\nExtracted {count} uncompressed files")
    
    # Read the hhc (table of contents) if it's in section 0
    for name in reader.entries:
        if name.endswith('.hhc') and reader.entries[name]['section'] == 0:
            content = reader.get_content(reader.entries[name])
            if content:
                print(f"\nTable of Contents ({name}):")
                print(content.decode('utf-8', errors='ignore')[:2000])

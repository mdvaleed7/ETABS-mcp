"""Parse the ETABS HHC (Table of Contents) file to extract all interfaces and methods"""
import re
import json

with open(r'c:\Users\mdval\Desktop\etaps_mcp_extracted\CSI API ETABS v1.hhc', 'r', encoding='utf-8') as f:
    content = f.read()

# Extract all name/local pairs
pattern = r'<param name="Name" value="([^"]+)">\s*(?:<param name="Local" value="([^"]+)">)?'
matches = re.findall(pattern, content)

# Build structure
interfaces = {}
current_interface = None
current_section = None  # 'properties' or 'methods'

for name, local in matches:
    name = name.strip()
    
    if ' Interface' in name:
        current_interface = name.replace(' Interface', '')
        interfaces[current_interface] = {'properties': [], 'methods': [], 'local': local}
        current_section = None
    elif name.endswith(' Properties') and current_interface:
        current_section = 'properties'
    elif name.endswith(' Methods') and current_interface:
        current_section = 'methods'
    elif current_interface and current_section:
        if name.endswith(' Method ') or name.endswith(' Method'):
            method_name = name.replace(' Method', '').strip()
            interfaces[current_interface]['methods'].append({'name': method_name, 'local': local})
        elif name.endswith(' Property ') or name.endswith(' Property'):
            prop_name = name.replace(' Property', '').strip()
            interfaces[current_interface]['properties'].append({'name': prop_name, 'local': local})
        elif 'Method' not in name and 'Property' not in name and 'Members' not in name:
            # Could be an enum or other item
            pass

print(f"Total interfaces: {len(interfaces)}")
print()

for iface_name in sorted(interfaces.keys()):
    iface = interfaces[iface_name]
    methods_count = len(iface['methods'])
    props_count = len(iface['properties'])
    print(f"  {iface_name}: {methods_count} methods, {props_count} properties")

# Save to JSON for later use
with open(r'c:\Users\mdval\Desktop\etaps mcp\api_structure.json', 'w') as f:
    json.dump(interfaces, f, indent=2)

print(f"\nSaved API structure to api_structure.json")

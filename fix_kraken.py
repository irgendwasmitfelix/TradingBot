import sys
file_path = 'kraken_interface.py'
with open(file_path, 'r') as f:
    lines = f.readlines()
# find line numbers for the block we want to replace
# We'll search for the pattern: '# compute allowed by margin (simple estimate using leverage)'
start = None
for i, line in enumerate(lines):
    if '# compute allowed by margin (simple estimate using leverage)' in line:
        start = i
        break
if start is None:
    sys.exit(1)
# find the line after that which contains 'allowed_by_margin = max'
end = None
for i in range(start, len(lines)):
    if 'allowed_by_margin = max' in lines[i]:
        end = i
        break
if end is None:
    # fallback: assume it's the next line after the lev assignment? but we'll just set end = start+2
    end = start + 2
# Now replace lines[start:end+1] with new block
indent = len(lines[start]) - len(lines[start].lstrip())
new_lines = [
    lines[start],  # keep the comment line
    '{0}if leverage is None:\n'.format(' ' * indent),
    '{0}    lev = 1.0\n'.format(' ' * indent),
    '{0}else:\n'.format(' ' * indent),
    '{0}    try:\n'.format(' ' * indent),
    '{0}        lev = float(leverage)\n'.format(' ' * indent),
    '{0}    except (ValueError, TypeError):\n'.format(' ' * indent),
    '{0}        self.logger.warning(f"Invalid leverage value {{leverage!r}}, treating as 1.0")\n'.format(' ' * indent),
    '{0}        lev = 1.0\n'.format(' ' * indent),
    '{0}allowed_by_margin = max(0.0, (mf - min_buffer) * lev)\n'.format(' ' * indent)
]
lines[start:end+1] = new_lines
with open(file_path, 'w') as f:
    f.writelines(lines)
print('Fixed')

path = '/home/saniyachavani/Documents/PrecisionpulseDocs/dspl-precision-pulse-frontend/src/app/dashboard/content.tsx'
content = open(path).read()

# Find the loadParameters function and replace it
import re

old_pattern = r'  // .* Load parameters .*\n  const loadParameters = useCallback\(async \(\) => \{.*?\n  \}, \[\]\);'
match = re.search(old_pattern, content, re.DOTALL)
if match:
    print('Found at:', match.start(), '-', match.end())
    print('Content:', repr(match.group()[:200]))
else:
    print('NOT FOUND')
    # Show lines 128-145
    lines = content.split('\n')
    for i, l in enumerate(lines[127:146], 128):
        print(f'{i}: {repr(l)}')

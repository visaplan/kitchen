#!/usr/bin/env python
import sys
i = 1
print('sys.path dump')
for pa in sys.path:
    if pa:
        print('%(i)3d. %(pa)s' % locals())
    else:
        print('%(i)3d (empty)' % locals())
    i += 1

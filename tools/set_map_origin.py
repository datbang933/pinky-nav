#!/usr/bin/env python3
"""Make a chosen physical point the map origin (0, 0), so coordinates such as the safe zone (1.2, 1.2) have a physical meaning.

usage: set_map_origin.py maps/room3.yaml X Y      # X,Y = where the NEW origin currently is in this map's frame
Edits the yaml's `origin` (backup saved as .yaml.bak). The image is unchanged. Afterwards every coordinate
(tools/places.yaml, initial pose, goals) is in the NEW frame: new = old - (X, Y).  Re-set the initial pose after restarting Nav2.
"""
import sys, re, shutil, yaml
path, X, Y = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
d = yaml.safe_load(open(path)); ox, oy, oth = d['origin']
shutil.copy(path, path + '.bak')
txt = open(path).read()
new = f'origin: [{ox - X:.4f}, {oy - Y:.4f}, {oth}]'
txt = re.sub(r'^origin:.*$', new, txt, flags=re.M)
open(path, 'w').write(txt)
print(f'{path}: origin [{ox}, {oy}] -> [{ox - X:.4f}, {oy - Y:.4f}]  (backup: {path}.bak)')

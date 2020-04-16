#!/usr/bin/env python3
import argparse
import re
import struct

from io import StringIO
from zipfile import ZipFile
from zipfile import ZIP_DEFLATED

from Krakatau.Krakatau import script_util
from Krakatau.Krakatau.classfileformat.reader import Reader
from Krakatau.Krakatau.classfileformat.classdata import ClassData
from Krakatau.Krakatau.assembler.disassembly import Disassembler
from Krakatau.Krakatau.assembler import parse
from Krakatau.Krakatau.assembler.tokenize import Tokenizer

import mapping

from patches import *

parser = argparse.ArgumentParser(description='DVGaming Minecraft patcher')
parser.add_argument('server', help='the Minecraft server JAR')
parser.add_argument('mapping', help='the corresponding obfuscation map')
parser.add_argument('output', help='output patch JAR')
parser.add_argument('-x', '--extract', action='store_true', help='extracts disassembly of unmodded class files')
parser.add_argument('-y', '--extract-mod', action='store_true', help='extracts disassembly of modded class files')
args = parser.parse_args()

patches = [CreeperPatch(), RespawnAnchorPatch()]

# OBSOLETE
def patch_creeper(cls, clsName):
    global args
    print('patching Creeper class: ' + clsName)

    # disassemble
    output = StringIO()
    Disassembler(cls, output.write, roundtrip=False).disassemble()
    code = output.getvalue()
    output = None

    # extract
    if args.extract:
        fname = clsName + '.j'
        print('    extracting unmodded file ' + fname)
        with open(fname, 'wb') as f:
            f.write(code.encode('UTF-8'))

    # find the Explode method
    m = re.search('.method private (..) : \(\)V \n'
                  '    .code stack 10 locals 3', code)
    if m:
        methodName = m.group(1)
        methodStart = m.end()
        methodEnd = code.find('.end code', methodStart)
        if methodEnd > methodStart:
            # we will now find the line where we conditionally get ExplosionType.DAMAGE_AND_DESTROY
            # which is enum field c in (...)$a
            pattern = re.compile('getstatic Field (...)\$a c L(...)\$a;')
            m = pattern.search(code, methodStart, methodEnd)
            if m:
                # we want to replace this by ExplosionType.DAMAGE_ONLY
                # which is enum field a
                enumName = m.group(1)
                assert enumName == m.group(2)

                code = code[:m.start()] + 'getstatic Field ' + enumName + '$a a L' + enumName + '$a;' + code[m.end():]

                # extract mod
                if args.extract_mod:
                    fname = clsName + '.mod.j'
                    print('    extracting modded file ' + fname)
                    with open(fname, 'wb') as f:
                        f.write(code.encode('UTF-8'))

                # re-assemble and return
                return list(parse.assemble(code, ''))[0][1]

    return False

print('loading deobfuscation map ...', flush=True)
classes = mapping.parse(args.mapping)

# patch callbacks
print('preparing patchers ...', flush=True)

patchesByClass = dict()
for patch in patches:
    if patch.className in classes:
        obfs = classes[patch.className].obfs
        patchesByClass[obfs] = patch
    else:
        print('FAILED to register patch for unmapped class ' + patch.className)

# patch queue
class PatchQueueEntry:
    def __init__(self, filename, classData, patcher):
        self.filename = filename
        self.classData = classData
        self.patcher = patcher

patchQueue = []

# open server JAR
print('processing server JAR ...', flush=True)
with ZipFile(args.server, 'r') as server:
    with ZipFile(args.output, 'w') as mod:
        # preserve comment
        mod.comment = server.comment
        
        # walk server files
        for item in server.infolist():
            filename = item.filename
            filedata = server.read(filename)
            
            if filename.endswith('.class') and not '/' in filename:
                obfs = filename[:-6]
                if obfs in patchesByClass:
                    patcher = patchesByClass[obfs]
                    print('    patching class ' + obfs + ' (' + patcher.className + ') ...', flush=True)
                    
                    # read class data
                    cls = ClassData(Reader(server.read(filename)))
                    
                    # disassemble
                    output = StringIO()
                    Disassembler(cls, output.write, roundtrip=False).disassemble()
                    code = output.getvalue()
                    output = None
                    
                    # extract
                    if args.extract:
                        with open(obfs + '.j', 'wb') as f:
                            f.write(code.encode('UTF-8'))
                    
                    # patch
                    code = patcher.patch(code, classes)
                    
                    # extract mod
                    if args.extract:
                        with open(obfs + '.mod.j', 'wb') as f:
                            f.write(code.encode('UTF-8'))
                    
                    # re-assemble
                    filedata = list(parse.assemble(code, ''))[0][1]

            # write to mod
            mod.writestr(item, filedata)

#!/usr/bin/python3
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

parser = argparse.ArgumentParser(description='DVGaming Minecraft patcher')
parser.add_argument('server', help='Minecraft server JAR')
parser.add_argument('output', help='Output patch JAR')
parser.add_argument('-x', '--extract', action='store_true', help='extracts disassembly of unmodded class files')
parser.add_argument('-y', '--extract-mod', action='store_true', help='extracts disassembly of modded class files')
args = parser.parse_args()

def read_index(cls):
    # take a guess that this class is the one containing the Entity class registry
    strings = dict()
    i = 0
    for i, x in enumerate(cls.pool.slots):
        if x.tag == 'Utf8':
            try:
                strings[x.data.decode()] = i
            except:
                pass

    # simple heuristic:
    # if the constant pool contains this set of strings, it's the index class
    # works reliably for versions 1.12 through 1.14
    if ('area_effect_cloud' in strings) and ('creeper' in strings) and ('zombie' in strings):
        # another heuristic follows
        # assume that we know the position of an entity ID string in the constant pool
        # then the name of its class is two entries further in the pool
        # this is because of how they are used in a static initializer
        # works reliably for versions 1.12 through 1.14
        return {
            'Creeper': cls.pool.getutf(strings['creeper'] + 2).decode()
        }
    else:
        return False

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

# open original file
with ZipFile(args.server, 'r') as server:
    # find class name index first
    idx = False
    for item in server.infolist():
        fname = item.filename
        fdata = server.read(fname)
        patched = False

        if fname.endswith('.class') and not '/' in fname:
            cls = ClassData(Reader(fdata))
            clsName = cls.pool.getclsutf(2).decode()

            idx = read_index(cls)
            if idx:
                break

    # next, apply patches
    patched = set()

    if idx:
        creeperClassName = idx['Creeper']
        creeperClassFileName = creeperClassName + '.class'
        creeperMod = patch_creeper(ClassData(Reader(server.read(creeperClassFileName))), creeperClassName)
        if creeperMod:
            patched.add(creeperClassFileName)
        else:
            print('failed to mod Creeper class, aborting')
            exit(1)
    else:
        print('failed to find class name index')
        exit(1)

    # write mod
    print('writing mod: ' + args.output)
    with ZipFile(args.output, 'w') as mod:
        # preserve comment
        mod.comment = server.comment

        # add mods
        mod.writestr(creeperClassFileName, creeperMod)

        # copy unmodded files
        for item in server.infolist():
            if not item.filename in patched:
                mod.writestr(item, server.read(item.filename))

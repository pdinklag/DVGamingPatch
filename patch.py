#!/usr/bin/python3
import argparse
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
args = parser.parse_args()

def patch_creeper(aue_in):
    # this patch changes Creeper explosions to NEVER destroy the world,
    # even if mob griefing is on!
    
    # disassemble
    aue = ClassData(Reader(aue_in))
    output = StringIO()
    Disassembler(aue, output.write, roundtrip=False).disassemble()
    text = output.getvalue()
    output = None

    with open('aue.j', 'w') as f:
        f.write(text)

    # aue.ea = Creeper.explode
    ea = text.find('.method private ea : ()V')
    assert ea >= 0
    
    # find method end
    ea_end = text.find('.end method', ea)
    assert ea_end > ea

    # bhk$a is an enum of explosion types,
    # a = do damage, but don't destroy the world
    # b = unknown
    # c = do damage and destroy the world
    # we want to patch usage of type c to type a here
    ea_patchline = text.find('getstatic Field bhk$a c Lbhk$a;', ea)
    assert ea_patchline >= 0 and ea_patchline < ea_end

    # apply patch
    text = text[:ea_patchline] + 'getstatic Field bhk$a a Lbhk$a;' + text[ea_patchline+31:]

    # re-assemble
    return list(parse.assemble(text, 'dummy'))[0][1]

# open original file
with ZipFile(args.server, 'r') as server:
    # apply patches
    with server.open('aue.class') as f:
        aue = patch_creeper(f.read())

    # write mod
    with ZipFile(args.output, 'w') as mod:
        # preserve comment
        mod.comment = server.comment

        # copy unpatched files
        for item in server.infolist():
            if item.filename != 'aue.class':
                mod.writestr(item, server.read(item.filename))

        # store patched files
        mod.writestr('aue.class', aue, ZIP_DEFLATED)

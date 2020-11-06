import re

# base class
class Patch:
    def __init__(self):
        self.className = None # must be set by subclass

    def findMethodBody(self, sig, code, mapping):
        cls = mapping[self.className]
        if sig in cls.methods:
            obfs = cls.methods[sig]
            m = re.search('\.method .+ ' + re.escape(obfs), code)
            methodStart = m.end() + 2 # cut off trailing space and newline
            return (methodStart, code.find('.end method', methodStart)) if m else (-1, -1)
        else:
            return (-1, -1)

# replace BlockInteraction.DESTROY by BlockInteraction.NONE to make an explosion not destroy the world
def makeNonDestroyingExplosion(disableFire, code, scopeStart, scopeEnd, mapping):
    explosionBlockInteraction = mapping['net.minecraft.world.level.Explosion$BlockInteraction']
    _none = explosionBlockInteraction.fields['NONE']
    _destroy = explosionBlockInteraction.fields['DESTROY']
    
    q = 'getstatic Field ' + explosionBlockInteraction.obfs + ' ' + _destroy
    start = code.find(q, scopeStart, scopeEnd)
    if start >= 0:
        end = start + len(q)
        code = code[:start] + 'getstatic Field ' + explosionBlockInteraction.obfs + ' ' + _none + code[end:]
        
        if disableFire:
            # also disable fire
            fire = 'iconst_1'
            fireStart = code.rfind(fire, scopeStart, start)
            if fireStart >= 0:
                fireEnd = fireStart + len(fire)
                return code[:fireStart] + 'iconst_0' + code[fireEnd:]
            else:
                print('disableFire failed')
        else:
            return code
    else:
        print('makeNonDestroyingExplosion failed')
        return code

# make Creeper explosions not destroy the world
class CreeperPatch(Patch):
    def __init__(self):
        self.className = 'net.minecraft.world.entity.monster.Creeper'

    def patch(self, code, mapping):
        (start, end) = self.findMethodBody('explodeCreeper : ()V', code, mapping)
        if start >= 0 and end > start:
            return makeNonDestroyingExplosion(False, code, start, end, mapping)
        else:
            print('failed to find method to patch')
            return code

# make bed or respawn anchor explosions not destroy the world
class BedExplosionPatchBase(Patch):
    def patch(self, code, mapping):
        (start, end) = self.findMethodBody('explode : (Lnet.minecraft.world.level.block.state.BlockState;Lnet.minecraft.world.level.Level;Lnet.minecraft.core.BlockPos;)V', code, mapping)
        if start >= 0 and end > start:
            return makeNonDestroyingExplosion(True, code, start, end, mapping)
        else:
            print('failed to find method to patch')
            return code

class RespawnAnchorPatch(BedExplosionPatchBase):
    def __init__(self):
        self.className = 'net.minecraft.world.level.block.RespawnAnchorBlock'

class BedPatch(BedExplosionPatchBase):
    def __init__(self):
        self.className = 'net.minecraft.world.level.block.BedBlock'

import re

# java name mangling
javaPrimitiveMangling = {
    'boolean': 'Z',
    'char':    'C',
    'double':  'D',
    'float':   'F',
    'int':     'I',
    'long':    'J',
    'short':   'S',
    'void':    'V',
}

def javaMangle(typeName):
    if typeName in javaPrimitiveMangling:
        # primitive
        return javaPrimitiveMangling[typeName]
    elif typeName.endswith('[]'):
        # array
        return '[' + javaMangle(typeName[0:-2])
    elif typeName.endswith('>'):
        # generic class
        openPos = typeName.find('<')
        return 'L' + typeName[:openPos] + '<' + ''.join(map(lambda x: javaMangle(x), typeName[openPos+1:-1].split(','))) + '>;'
    else:
        # class
        return 'L' + typeName + ';'

# mappings parser helpers
class ClassMapping:
    def __init__(self, obfs):
        self.obfs = obfs
        self.fields = dict()
        self.methods = dict()
        self._methods = []

class PreliminaryMethodMapping:
    def __init__(self, name, obfs, retn, parm):
        self.name = name
        self.obfs = obfs
        self.retn = retn
        self.parm = parm

# parse mapping
def parse(filename):
    classes = dict()
    cls = None # current class
    with open(filename, 'r') as mapping:
        for line in mapping:
            if len(line) == 0 or line.startswith('#'):
                continue # skip empty lines and comments

            if line.startswith('    '):
                # field or method in cls
                m = re.search('    (.+\(.*\)) -> (.+)', line)
                if m:
                    # method
                    decl = m.group(1)
                    obfs = m.group(2)
                    
                    # some method declarations are preceded by line and column numbers
                    m = re.search('.+:.+:(.+)', decl)
                    if m:
                        decl = m.group(1)
                    
                    m = re.search('(.+) (.+)\((.*)\)', decl)
                    retn = m.group(1)
                    name = m.group(2)
                    parm = m.group(3)
                    parm = parm.split(',') if len(parm) > 0 else []
                    
                    cls._methods.append(PreliminaryMethodMapping(name, obfs, retn, parm))
                    
                else:
                    # field
                    m = re.search('    (.+) -> (.+)', line)
                    decl = m.group(1)
                    obfs = m.group(2)
                    m = re.search('(.+) (.+)', decl)

                    name = m.group(2)
                    cls.fields[name] = obfs
            else:
                # class
                m = re.search('(.+) -> (.+):', line)
                name = m.group(1)
                obfs = m.group(2)
                cls = ClassMapping(obfs)
                classes[name] = cls

    # mangle method signatures
    for _, cls in classes.items():
        for m in cls._methods:
            # use same format that Krakatau outputs with
            sig = m.name + ' : (' + ''.join(map(lambda x: javaMangle(x), m.parm)) + ')' + javaMangle(m.retn)
            obfs = m.obfs + ' : (' + ''.join(map(lambda x: javaMangle(classes[x].obfs if x in classes else x), m.parm)) + ')' + javaMangle(classes[m.retn].obfs if m.retn in classes else m.retn)
            cls.methods[sig] = obfs
            
        cls._methods = None # no longer needed

    # done
    return classes

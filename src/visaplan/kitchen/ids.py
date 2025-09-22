# -*- coding: utf-8 -*- äöü vim: ts=8 sts=4 sw=4 si et tw=79
"""\
ids.py: Generierung von IDs
"""

# Python compatibility:
from __future__ import absolute_import

from six import string_types as six_string_types
from six.moves import map

# Standard library:
from collections import defaultdict

__author__ = "Tobias Herp <tobias.herp@visaplan.com>"
VERSION = (0,
           1,  # Abgespeckte Kopie von Products.unitracc.tools.misc
           )
__version__ = '.'.join(map(str, VERSION))

__all__ = [
           # ---------------- [ aus Products.unitracc.tools.misc ... [
           'id_factory',
           'sibling_id',
           # ---------------- ] ... aus Products.unitracc.tools.misc ]
           ]


# --------------------------- [ aus Products.unitracc.tools.misc ... [
def id_factory(existing=None, mask='%(prefix)s-%(idx)d'):
    """
    Erzeuge eine Funktion, die eindeutige IDs zurückgibt.

    existing -- wenn übergeben, ein Set schon existierender IDs
    mask -- ein Namensschema in Python-dict-Syntax
    """
    if existing is None:
        existing = set()
    number_range = defaultdict(int)

    def new_id(prefix, prefered=None):
        """
        prefix -- ein String
        prefered -- optional: ein kompletter Wert, der nicht in das erzeugte
                    Muster zu passen braucht; wird verwendet, falls nicht schon
                    vergeben
        """
        # Argumente prüfen ...
        none_allowed = False
        for val in (prefix, prefered):
            if none_allowed:
                if val is None:
                    continue
            else:
                none_allowed = True
            if not isinstance(val, six_string_types):
                raise ValueError('String expected; got %(val)r'
                                 % locals())
        # Präferenz angegeben?
        if prefered is not None and prefered not in existing:
            existing.add(prefered)
            return prefered
        idx = number_range[prefix] + 1
        while True:
            theid = mask % locals()
            if theid not in existing:
                number_range[prefix] = idx
                existing.add(theid)
                return theid
            idx += 1
    return new_id


def sibling_id(elem, well_prefix, sink_prefix, make_id):
    """
    - Lies die ID des Quellelements <elem> aus (i.d.R. noch nicht vorhanden)
      und ergänze diese nötigenfalls, unter Verwendung des Präfixes
      <well_prefix>
    - Erzeuge eine entsprechende ID (mit möglichst derselben Nummer,
      aber einem anderen Präfix); dies ist der Rückgabewert

    >>> class E:
    ...     def __init__(self, id=None):
    ...         self.attrs = {}
    ...         if id: self.attrs['id'] = id
    >>> make_id = id_factory()
    >>> e1 = E()
    >>> sibling_id(e1, 'prim', 'sec', make_id)
    'sec-1'
    >>> e1.attrs['id']
    'prim-1'

    Wenn das Element <elem> schon eine ID hat, wird diese erhalten:
    >>> e2 = E('honk')
    >>> sibling_id(e2, 'prim', 'sec', make_id)
    'sec-2'
    >>> e2.attrs['id']
    'honk'
    """
    well_id = elem.attrs.get('id')
    if not well_id:
        well_id = make_id(well_prefix)
        elem.attrs['id'] = well_id
    sink_id = None
    try:
        liz = well_id.split('-')
        if liz[1:]:
            int(liz[-1])
            sink_id = '-'.join([sink_prefix] +
                               liz[1:])
    except ValueError:
        pass
    return make_id(sink_prefix, sink_id)
# --------------------------- ] ... aus Products.unitracc.tools.misc ]


if __name__ == '__main__':
    # Standard library:
    import doctest
    doctest.testmod()

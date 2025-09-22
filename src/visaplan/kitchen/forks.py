# -*- coding: utf-8 -*- vim: ts=8 sts=4 sw=4 si et tw=72
"""\
forks.py - Gabeln, um darin herumzustochern,
           was in dicker Suppe so herumschwimmt ...

Für Doctests muß BeautifulSoup importiert werden:

>>> from bs4 import BeautifulSoup
"""
# Python compatibility:
from __future__ import absolute_import, print_function

from six.moves import map

__all__ = [
    'convert_dimension_styles',  # img[width] (...) from style
    'extract_linktext',
    'inject_number',
    # function map:
    'EXTRACT_FUNC',
    # mapped functions:
    'extract_from_a',
    'extract_from_div',
    'extract_from_img',
    'extract_from__string',
    'extract_from_table',
    'ignore',
    'extract_from__children',  # the default
    'extract_from__title',     # helper for extract_from_a
    # little helpers:
    'get_numeric_px',  # for convert_dimension_styles
    'dots',           # numerate headlines
    'appendix_dots',  # numerate appendixes
    'upper_alpha',    # 4 --> 'D'
    'has_caption_class',
    'styledict',
    ]


# Standard library:
from collections import defaultdict
from string import ascii_uppercase

# Local imports:
from visaplan.kitchen.spoons import extract_uid_and_tail

# aus kitchen-Modul importieren? (noch nicht verwendet)
END_BRACE = {'(': ')',
             '[': ']',
             # (noch?) nicht verwendet:
             '{': '}',
             '<': '>',
             }

# -------------------------------------------- [ Hilfsfunktionen ... [
def get_numeric_px(txt, verbose=False):
    """
    Gib None oder eine Zahl != 0 zurück.

    >>> get_numeric_px('100%')
    >>> get_numeric_px('100px')
    100
    >>> get_numeric_px('101')
    101
    """
    if not txt:
        return None
    try:
        if txt.endswith('px'):
            txt = txt[:-2]
        num = int(txt)
        if num:
            return num
    except ValueError as e:
        if verbose:
            print("get_numeric_px(%(txt)r): Can't transform to integer!"
                  % locals())
        return None


def has_caption_class(elem):
    try:
        classes = elem.attrs['class']
    except (KeyError, AttributeError):
        return False
    else:
        return 'caption' in classes


def styledict(s):
    """
    *Sehr einfacher* Parser für HTML-Style-Attribute;
    versucht *nicht*, alle erlaubten Deklarationen korrekt zu parsen,
    insbesondere nicht solche, die evtl. ein Semikolon enthalten.

    >>> styledict('width:180px;')
    {'width': '180px'}

    Spätere Angaben überschreiben frühere:
    >>> styledict('width:180px;width : 100px')
    {'width': '100px'}

    Es findet keinerlei Konversion in Zahlen o.ä. statt; dimensionslose
    Angaben sind ohnehin nicht erlaubt.
    """
    res = {}
    for chunk in s.split(';'):
        if not chunk.strip():
            continue
        try:
            key, val = tuple([s.strip()
                              for s in chunk.split(':', 1)
                              ])
        except IndexError:
            try:
                key, val = tuple([s.strip()
                                  for s in chunk.split('=', 1)
                                  ])
            except IndexError:
                continue
        res[key] = val
    return res
# -------------------------------------------- ] ... Hilfsfunktionen ]

# ------------------------------------------ [ Spezialfunktionen ... [
def extract_from__string(elem, collector):
    """
    Extrahiere aus einen String-Element
    """
    txt = elem.string
    if txt:
        txt = txt.strip()
        if not txt:
            return None
        collector.append(txt)
        return True


def extract_from__title(elem, collector):
    txt = elem.get('title', '').strip()
    if txt:
        collector.append(txt)
        return True


def extract_from__children(elem, collector):
    ok = False
    for child in elem.children:
        if EXTRACT_FUNC[child.name](child, collector):
            # Erfolg vermerken, aber weitermachen:
            ok = True
    return ok


def extract_from_table(elem, collector):
    for caption in elem.find_all('caption'):
        if extract_from__children(caption, collector):
            return True
    return False


def extract_from_div(elem, collector):
    """
    Extrahiere Text aus einem div-Element
    """
    for caption in elem.find_all(has_caption_class):
        if extract_from__children(caption, collector):
            return True
    for table in elem.find_all('table'):
        if extract_from_table(table, collector):
            return True
    return extract_from__children(elem, collector)

    for child in elem.children:
        pass


def extract_from_img(elem, collector):
    alt = elem.get('alt')
    if alt is not None:
        alt = alt.strip()
    if alt:
        collector.append(alt)
        return True


def extract_from_a(elem, collector):
    classes = elem.get('class', [])
    if 'contains-preview-img' in classes:
        if extract_from__title(elem, collector):
            return True
    if ('content-only' in classes
        and 'glossar' not in classes
        ):
        return False
    return extract_from__string(elem, collector) or \
           extract_from__children(elem, collector)


def convert_dimension_styles(elem, dic, remove_empty=True):
    """
    Konvertiere das übergebene Element:
    - wenn das Element height- und width-Angaben erlaubt
      (vorerst: nur img) ...
    - ... lies ein etwaiges style-Attribut aus;
      - wenn height- und width-Angaben mit px-Dimension gefunden werden,
        ersetze sie durch numerische height- und width-Attribute;
      - schon vorhandene height- und width-Attribute haben Vorrang.
      - wenn das style-Attribut anschließend leer ist, wird es entfernt
        (<remove_empty>)
    - und notiere die ermittelten Werte für 'height' und 'width'
      im übergebenen Dict `dic`

    Argumente:
    elem -- das (BeautifulSoup-) Element (wird modifiziert)
    dic -- ein Dict, das die ermittelten Angaben noch einmal aufführt;
           kann einen width-Schlüssel enthalten (für Breite aus
           src-Angabe), der ggf. verwendet wird
    remove_empty -- soll ein leeres style-Attribut anschließend entfernt
                    werden?

    >>> txt = '<img style="height: 30px; width:40px" src="/any">'
    >>> elem = BeautifulSoup(txt).img
    >>> dic = {}
    >>> convert_dimension_styles(elem, dic)
    True
    >>> elem
    <img height="30" src="/any" width="40"/>
    >>> sorted(dic.items())
    [('height', 30), ('width', 40)]

    Andere Höhen- und Breitenangaben bleiben unberührt:
    >>> txt = '<img style="height: auto; width: 100%" src="/any">'
    >>> elem = BeautifulSoup(txt).img
    >>> dic = {}
    >>> convert_dimension_styles(elem, dic)
    False
    >>> elem
    <img src="/any" style="height: auto; width: 100%"/>
    >>> sorted(dic.items())
    []

    Wenn die Dimensionen (insbesondere die Breite) nicht den sonstigen
    Attributen entnommen werden können, wird auch das übergebene Dict
    <dic> herangezogen:

    >>> txt = '<img src="/resolveuid/abc123/image_mini">'
    >>> elem = BeautifulSoup(txt).img
    >>> dic = {'width': 240}
    >>> convert_dimension_styles(elem, dic)
    True
    >>> elem
    <img src="/resolveuid/abc123/image_mini" width="240"/>
    >>> sorted(dic.items())
    [('width', 240)]
    """
    if elem.name != 'img':
        return
    a_dict = elem.attrs
    style_val = a_dict.get('style', '')
    changed = False
    styles = styledict(style_val)
    width = get_numeric_px(a_dict.get('width'))
    height = get_numeric_px(a_dict.get('height'))
    if 'width' in styles:
        width_s = get_numeric_px(styles['width'])
        if width_s is not None:
            del styles['width']
            changed = True
            if width is None:
                width = width_s
                a_dict['width'] = width
    if 'height' in styles:
        height_s = get_numeric_px(styles['height'])
        if height_s is not None:
            del styles['height']
            changed = True
            if height is None:
                height = height_s
                a_dict['height'] = height
    if width is None:
        # keine Breite aus den einschl. Attributen;
        # aber vielleicht schon im übergebenen Dict?
        # (aus get_imgtag_info-Aufruf)
        width = dic.get(width)
        if width:
            a_dict['width'] = str(width)
            changed = True

    if width is not None:
        dic['width'] = width
    if height is not None:
        dic['height'] = height
    if changed:
        if styles:
            a_dict['style'] = '; '.join([': '.join(tup)
                                             for tup in sorted(styles.items())
                                             ])
        else:
            del a_dict['style']
    return changed

# ------------------------------------------ ] ... Spezialfunktionen ]

def ignore(elem, collector):
    return False

EXTRACT_FUNC = defaultdict(lambda: extract_from__children)
EXTRACT_FUNC.update({
        None:     extract_from__string,
        # 'x': extract_from_x,
        'a':      extract_from_a,
        'div':    extract_from_div,
        'img':    extract_from_img,
        'object': ignore,
        'table':  extract_from_table,
        'video':  ignore,
        })

def extract_linktext(elem, key=None, func=None):
    """
    elem -- das Element
    key -- zus. Argument für die ggf. aufzurufende Funktion ...
    func -- eine Funktion, die im Mißerfolgsfall aufgerufen wird

    >>> a_soup = BeautifulSoup('<a>link <em>em-text</em></a>')
    >>> extract_linktext(a_soup)
    u'link em-text'
    >>> a1_soup = BeautifulSoup('<a>link text</a>')
    >>> extract_linktext(a1_soup)
    u'link text'
    >>> img_soup = BeautifulSoup('<img alt="alternate" title="ignored">')
    >>> extract_linktext(img_soup)
    'alternate'
    >>> txt = ' '.join(('<a class="glossar content-only no-breaket transformed-booklink"',
    ...                    'href="#topic-12" id="ref-12"',
    ...                    'title="CaO; Freikalk; Anteil des CaO &hellip;">'
    ...                 'Freikalk'
    ...                 '</a>'))
    >>> a2_soup = BeautifulSoup(txt)
    >>> extract_linktext(a2_soup)
    u'Freikalk'
    """
    collector = []
    EXTRACT_FUNC[elem.name](elem, collector)
    txt = ' '.join([s.strip()
                    for s in collector
                    ]).strip()
    if txt:
        return txt
    if func is not None:
        return func(elem, key)


def dots(seq):
    """
    Für Überschriftnumerierung:

    >>> dots((1, 2, 3))
    '1.2.3'
    """
    return '.'.join(map(str, seq))


def upper_alpha(i, strict=False):
    """
    "Nummern" in Großbuchstaben, CSS: upper-alpha

    >>> upper_alpha(0, False)
    >>> upper_alpha(1)
    'A'
    >>> upper_alpha(2)
    'B'
    >>> upper_alpha(26)
    'Z'
    """
    liz = []
    if not i:
        if strict:
            raise ValueError('Die Null ist nicht darstellbar!'
                             ' (%(i)r)'
                             % locals())
        else:
            return None
    if 1 <= i <= 26:
        return ascii_uppercase[i-1]
    else:
        raise ValueError('Ganze Zahl zwischen 1 und 26 erwartet!'
                         ' (%(i)r)'
                         % locals())


def appendix_dots(seq):
    """
    Für Numerierung von Anhängen.

    Die erste Nummer wird ignoriert, die zweite in Großbuchstaben
    ausgegeben:

    >>> appendix_dots((1, 2, 3))
    'B.3'

    >>> appendix_dots((3, None, 1))
    '1'

    >>> appendix_dots((3, 0, 1))
    '1'
    """
    tail = list(seq[1:])
    if not tail:
        return None
    res = []
    leader = tail.pop(0)
    if leader:
        res.append(upper_alpha(leader))
    res.extend(tail)
    return '.'.join(map(str, res))


def inject_number(soup, number, elem, func=dots):
    """
    Zur serverseitigen Injektion von Kapitelnummern;
    Gib das frisch ergänzte Element zurück.

    >>> soup = BeautifulSoup('<h2>Die Antwort</h2>')
    >>> h2 = soup.h2
    >>> inject_number(soup, (4, 2), h2)
    <h2><span class="chapter-number">4.2</span> <span class="headline-text">Die Antwort</span></h2>

    >>> soup = BeautifulSoup('<h3 id="abc">Mit Attributen</h3>')
    >>> h3 = soup.h3
    >>> inject_number(soup, (4, 3), h3)
    <h3 id="abc"><span class="chapter-number">4.3</span> <span class="headline-text">Mit Attributen</span></h3>

    Wenn die Nummer leer ist (z. B. weil bei Anhängen die erste
    Nummernkomponente verworfen wird), wird das span.chapter-number
    nicht erzeugt:

    >>> soup = BeautifulSoup('<h2 id="appendix">Anhang</h2>')
    >>> h2 = soup.h2
    >>> inject_number(soup, (2,), h2, appendix_dots)
    <h2 id="appendix"><span class="headline-text">Anhang</span></h2>

    >>> txt = '<h4><a class="headline-text" href="#section-29">Fragenkatalog zu LB 3.1 - Drehrohrofen</a></h4>'
    >>> soup = BeautifulSoup(txt)
    >>> h4 = soup.h4
    >>> inject_number(soup, (1, 2, 3), h4, appendix_dots)
    <h4><span class="chapter-number">B.3</span> <a class="headline-text" href="#section-29">Fragenkatalog zu LB 3.1 - Drehrohrofen</a></h4>
    """
    text_el = elem.find(class_='headline-text')
    if text_el is None:
        # alles mitnehmen, was drin ist - also erstmal einpacken:
        wrapper = elem.wrap(soup.new_tag('span', **{'class': 'headline-text'}))
        # nun den Inhalt der Eingabe-Überschrift auspacken:
        headline = elem.unwrap()
        elem = wrapper.wrap(headline)
    num_string = func(number)
    if num_string:
        numel = soup.new_tag('span', **{'class': 'chapter-number'})
        numel.string = num_string
        elem.insert(0, numel)
        elem.insert(1, ' ')
    return elem


if __name__ == '__main__':
    # Standard library:
    import doctest

    # 3rd party:
    from bs4 import BeautifulSoup
    def set_trace(): pass
    doctest.testmod()
else:
    # Logging / Debugging:
    from pdb import set_trace

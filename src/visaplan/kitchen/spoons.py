# -*- coding: utf-8 -*- äöü vim: ts=8 sts=4 sw=4 si et tw=79
"""\
spoons: Werkzeuge für BeautifulSoup

blame markers:
- swap_classes procedure
  (Python 2 compatible)
"""
# Python compatibility:
from __future__ import absolute_import, print_function

from six.moves import map, range

__author__ = "Tobias Herp <tobias.herp@visaplan.com>"
VERSION = (0,
           5,  # split_paragraphs (und benötigte Helferlein)
           5,  # stripped_soup bugfix
           )
__version__ = '.'.join(map(str, VERSION))
__all__ = [
    'make_tag',
    'make_script',
    'extract_content',  # siehe auch --> body_content und parsed_text
    'top_elements',     # gibt eine Liste zurück
    'get_single_element',
    'insertAdjacentElement',
    'INSERT_POSITIONS',
    'parse_selector',
    'make_levelfunc',
    'make_find_expression',
    # arbeiten mit Klassen;
    # nur-lesende Filterfunktionen:
    'has_class',
    'has_all_classes',
    'has_any_class',
    'make_classes_generator',  # (kein Filter, sondern Generator-Factory)
    'is_empty',
    'is_whitespace',
    'is_meat',
    # sonstige Filterfunktionen:
    'has_empty_line',
    'is_block_element',
    'is_block_with_p',
    'is_hyperlink',
    # Navigation:
    'interesting_successor',
    # Bearbeitungsfunktionen:
    # (see swap_classes function in visaplan.plone.tomoodle.helpers._spoons!)
    'classes_of',
    'swap_classes',  # substitute {add,append}_class, remove_class{,es}, ...
    'append_class',
    'add_class',
    'remove_class',
    'remove_classes',
    'check_class',
    'change_text',
    'extract_attributes',
    # HTML-Bereinigung:
    'split_paragraphs',
    'strip_linebreaks',
    'fence_texts',
    'strip_empty_successor',
    # ... Eigenarten der Parser einebnen:
    'parsed_text',
    'stripped_soup',
    # IDs:
    'gen_id_and_name',
    'get_id_or_name',
    # Kapitelnummern:
    'ChapterCounter',
    'parent_chapters',
    # Sonstige Funktionen:
    'fix_webdivs',
    'fix_class_arg',  # class_ --> class
    'hyperlinkable_strings',
    'find_headline',
    'body_content',  # --> neu, besser: parsed_text
    'contents_stripped',
    'contents_stripped2',
    'extract_uid',  # aus browser.transform.utils
    'extract_local_uid',
    'extract_uid_from_qs',
    'extract_uids',
    'DEFAULT_TAGS_AND_ATTRIBUTES',
    'make_taginfo_extractor',  # --> z. B. der folgende:
    'get_tag_info',          # generiert; kein def!
    'make_uid_generator',      # --> z. B. der folgende:
    'generate_uids',         # generiert; kein def!
    'extract_uid_and_tail',
    'extract_1st_image_info',
    'generate_image_infos',  # new in 1.0.3
    # 'is_uid_shaped',  --> nun in .functions
    # Daten:
    'SOFT_HYPHEN',
    ]

# Python compatibility:
from six.moves.urllib.parse import parse_qs, urlsplit, urlunsplit

# Standard library:
import re
from collections import defaultdict
from string import ascii_letters, digits, whitespace

# 3rd party:
from bs4 import BeautifulSoup, NavigableString, Tag

# visaplan:
try:
    # module .html renamed to .htmlohmy in v1.4+:
    from visaplan.tools.htmlohmy import (
        BLOCK_ELEMENT_NAMES,
        EMPTY_ELEMENT_NAMES,
        REPLACED_ELEMENT_NAMES,
        entity,
        )
except ImportError:
    from visaplan.tools.html import (
        BLOCK_ELEMENT_NAMES,
        EMPTY_ELEMENT_NAMES,
        REPLACED_ELEMENT_NAMES,
        entity,
        )
from visaplan.tools.sequences import inject_indexes

# -------------------------------------------- [ Daten ... [
SOFT_HYPHEN = entity['shy']
# -------------------------------------------- ] ... Daten ]


def clone(el):
    """
    Klonfunktion von Martijn Pieters,
    http://stackoverflow.com/a/23058678/1051649:

    >>> soup = BeautifulSoup('<h2 id="42">Die Antwort</h2>', 'lxml')
    >>> h2 = soup.h2
    >>> h2
    <h2 id="42">Die Antwort</h2>
    >>> h3 = clone(h2)
    >>> h3
    <h2 id="42">Die Antwort</h2>
    >>> h3 is h2
    False
    >>> h3.name = 'h3'
    >>> h3
    <h3 id="42">Die Antwort</h3>
    >>> h2
    <h2 id="42">Die Antwort</h2>
    """
    if isinstance(el, NavigableString):
        return type(el)(el)

    copy = Tag(None, el.builder, el.name, el.namespace, el.nsprefix)
    # work around bug where there is no builder set
    # https://bugs.launchpad.net/beautifulsoup/+bug/1307471
    copy.attrs = dict(el.attrs)
    for attr in ('can_be_empty_element', 'hidden'):
        setattr(copy, attr, getattr(el, attr))
    for child in el.contents:
        copy.append(clone(child))
    return copy


def make_tag(soup, tag, txt=None, **kwargs):
    """
    Erzeuge ein Element und fülle es ggf. gleich mit Text

    >>> soup = BeautifulSoup()
    >>> elem = make_tag(soup, 'div', 'A', class_='group')
    >>> elem
    <div class="group">A</div>
    """
    fix_class_arg(kwargs)
    elem = soup.new_tag(tag, **kwargs)
    if txt is not None:
        elem.string = txt
    return elem


def make_script(soup, src=None, txt=None, type='text/javascript', **kwargs):
    """
    Erzeuge ein <script>-Element

    >>> soup = BeautifulSoup()
    >>> make_script(soup, '/custom.js')
    <script src="/custom.js" type="text/javascript"></script>
    >>> make_script(soup, txt="alert('Hello world!')")
    <script type="text/javascript">alert('Hello world!')</script>
    """
    if src is not None:
        if txt is not None:
            raise ValueError('src (%(src)r) and txt given!'
                             % locals())
        return soup.new_tag('script', src=src, type=type, **kwargs)
    if txt is None:
        raise ValueError('no src nor txt given!')
    elem = soup.new_tag('script', type=type, **kwargs)
    elem.string = txt
    return elem


def extract_content(soup):
    """
    Nicht zu verwechseln mit --> @@transform.forks.extract_linktext;
    siehe auch --> body_content und --> parsed_text

    Durch Aufruf eines Templates erzeugter HTML-Code zeitigt - wenn von lxml
    geparst - oftmals einen <html><body>-Container. Diese Funktion ...

    - gibt ein 2-Tupel (isSingle, elem_or_sequence) zurück
    - entfernt das html- und das body-Element, wenn vorhanden, und wenn das
      html-Element kein head-Element enthält

    >>> soup = BeautifulSoup('<b>one</b><em>two</em>', 'html.parser')
    >>> soup.name
    '[document]'
    >>> boo, seq = extract_content(soup)
    >>> boo
    False
    >>> list(map(str, seq))
    ['<b>one</b>', '<em>two</em>']

    Wenn keine "Suppe" übergeben wird, handelt es sich um ein einzelnes
    Element, und es wird angenommen, daß keine weitere Verarbeitung nötig ist:

    >>> boo, elem = extract_content(seq[0])
    >>> boo
    True
    >>> str(elem)
    '<b>one</b>'

    >>> soup = BeautifulSoup(' <p> a paragraph', 'lxml')
    >>> tup = extract_content(soup)
    >>> tup[0]
    True
    >>> str(tup[1])
    '<p> a paragraph</p>'

    """
    if soup.name != '[document]':
        # Kein vom Parser erzeugtes Dokument, sondern schon ein Element:
        return True, soup
    children = list(soup.children)
    if len(children) != 1:
        # ein Dokument, aber mit mehreren Kindern (!= html):
        return False, children
    the_child = children[0]
    if the_child.name != 'html':
        return True, the_child
    grandchildren = list(the_child.children)
    if len(grandchildren) != 1:
        # mutmaßlich head und body; html-Element zurückgeben:
        return True, the_child
    # mutmaßlich body:
    the_body = grandchildren[0]
    great_grandchildren = list(the_body.children)
    if len(great_grandchildren) == 1:
        return True, great_grandchildren[0]
    else:
        return False, great_grandchildren


def extract_uid(path):
    """
    Extrahiere die UID; es findet keine weitere Prüfung statt.

    >>> extract_uid('./resolveUid/abc123/honk_view')
    'abc123'
    >>> extract_uid('resolveuid/abc456')
    'abc456'

    Wenn kein Treffer für 'resolveuid', kommt None zurück:

    >>> extract_uid('./resolvUid/abc123/honk_view')

    Resolveuid ohne folgendes Segment:
    >>> extract_uid('./resolveUid')
    Traceback (most recent call last):
    ...
    IndexError: list index out of range
    >>> extract_uid('./resolveUid/')

    Kombination mit Query-String:

    >>> extract_uid('./resolveUid/abc123?contentonly=true')
    'abc123'

    Auch URLs mit Browser-Syntax erkennen:

    >>> extract_uid('/@@resolveuid/52081f256b1347289b0b81bf0ecba15e/image_preview')
    '52081f256b1347289b0b81bf0ecba15e'

    """
    segments_lower = path.lower().split('/')
    for marker in ('resolveuid',
                   '@@resolveuid',
                   ):
        try:
            i = segments_lower.index(marker)
        except (ValueError, IndexError):
            pass
        else:
            if 0 <= i < len(segments_lower):
                seg = segments_lower[i+1]
                if '?' in seg:
                    seg = seg.split('?', 1)[0]
                return seg or None
    return None


def extract_local_uid(url, default=None):
    """
    Extrahiere eine UID aus einer lokalen URL, die also keine Angabe eines
    Ports oder Servers enthält

    >>> extract_local_uid('resolveuid/abc789')
    'abc789'

    Jegliche URLs mit Protokollangabe geben None zurück:
    >>> extract_local_uid('http://localhost/resolveuid/abc789')
    >>> extract_local_uid('http://anyhost/resolveuid/abc789')
    >>> extract_local_uid('https://anyhost/resolveuid/abc789')
    """
    parsed = urlsplit(url)
    if parsed.netloc:
        return None
    return extract_uid(parsed.path)


def extract_uid_from_qs(url, checkfunc=None, default=None):
    """
    Extrahiere eine UID aus einer URL mit Query-String

    >>> url1='/e-learning/kurse/d-05-.../course_ppt_view?uid=a02f024f66072aa493121ab56b13d186&template_id=course_ppt_view'
    >>> extract_uid_from_qs(url1)
    'a02f024f66072aa493121ab56b13d186'

    """

    urlinfo = urlsplit(url)
    qs = urlinfo.query
    qsdict = parse_qs(qs)
    if 'uid' in qsdict:
        val = qsdict['uid']
        if checkfunc is not None:
            if checkfunc(val):
                return val
            if isinstance(val, (list, tuple)):
                for part in val:
                    if checkfunc(part):
                        return part
        elif isinstance(val, (list, tuple)):
            if val and not val[1:]:
                return val[0]
        return val
    return default


def extract_uid_and_tail(url):
    """
    Gib ein 2-Tupel (uid, tail) zurück:
    - uid ist die UID (das Segment nach 'resolveuid')
    - tail ist alles, was danach kommt (wenn uid nicht None ist, ein String)

    Grundannahmen sind:
    - alles vor der UID ist uninteressant
    - wenn keine UID vorhanden ist, ist der <tail> ebenfalls uninteressant
      (gegenwärtig ist er dann None; das könnte sich aber ändern,
      wenn es dafür einen zwingenden Grund gibt)

    >>> extract_uid_and_tail('/resolveuid/abc123')
    ('abc123', '')
    >>> extract_uid_and_tail('/resolveuid/')
    (None, None)
    >>> extract_uid_and_tail('/resolveuid/abc123?honk#bonk')
    ('abc123', '?honk#bonk')
    >>> extract_uid_and_tail('/resolveuid/abc123/image?honk#bonk')
    ('abc123', 'image?honk#bonk')
    >>> extract_uid_and_tail('resolveuid/cb9390b5055147569fb35dca5ac79ecc/image_mini')
    ('cb9390b5055147569fb35dca5ac79ecc', 'image_mini')

    Auch Browser-Syntax erkennen:

    >>> extract_uid_and_tail('/@@resolveuid/abc468?honk#bonk')
    ('abc468', '?honk#bonk')

    UIDs mit Großbuchstaben werden implizit konvertiert
    (ohne daß sie ansonsten gültig wären ...):
    >>> extract_uid_and_tail('/@@resolveuid/ABC579?honk#bonk')
    ('abc579', '?honk#bonk')

    Für nicht-relative URLs wird (None, None) zurückgegeben:

    >>> extract_uid_and_tail('http://www.unitracc.de/resolveuid/abc123')
    (None, None)

    Um den Pfad des Objekts mit der ermittelten UID wieder mit dem <tail> zu
    verheiraten, siehe -> join_path_and_tail.
    """
    urlinfo = urlsplit(url)
    if urlinfo.scheme or urlinfo.netloc:
        return (None, None)
    pa = urlinfo.path
    lopali = pa.lower().split('/')
    i = None
    for j in range(len(lopali)):
        if lopali[j] in ('resolveuid', '@@resolveuid'):
            i = j
            break
    if i is None:
        return (None, None)
    try:
        uid = lopali[i+1] or None
        if uid is None:
            return (None, None)
        urllist = list(urlinfo)
        pali = pa.split('/')
        urllist[2] = '/'.join(pali[i+2:])
        return (uid, urlunsplit(urllist))
    except (ValueError, IndexError):
        return (None, None)


def extract_uids(soup):
    """
    Zur Ermittlung verwendeter oder referenzierter Elemente, z. B. für Exporte
    (Transmogrifier):

    Extrahiere alle mutmaßlichen UIDs aus der übergebenen Suppe;
    je nach Element werden die üblichen verdächtigen Attribute inspiziert.

    >>> html = ('<img src="/resolveuid/abc123">'
    ...         '<a href="./resolveUid/cde456">honk</a>'
    ...         '<a href="./@@resolveUid/cde789">honk</a>'
    ...         '<a href="/resolveuid/fab789#bcd024">bonk</a>'
    ...         '<a href="/@@resolveuid/cde123#efa567">zonk</a>')
    >>> soup = BeautifulSoup(html, 'lxml')
    >>> list(extract_uids(soup))
    ['abc123', 'cde456', 'cde789', 'fab789', 'bcd024', 'cde123', 'efa567']

    """
    for elem in soup.find_all(['a', 'img']):
        if elem.name == 'a':
            aname = 'href'
        else:
            aname = 'src'
        val = elem.get(aname)
        if not val:
            continue
        uid = extract_uid(val)
        if uid is not None:
            for val in uid.split('#'):
                yield val


def extract_1st_image_info(txt, uid_only=True, builder='lxml'):
    """
    Extrahiere die Informationen zum ersten im Text verwendeten Bild
    (ein Python-Dict, oder None).

    uid_only -- Wenn True (Vorgabe), werden nur Bilder berücksichtigt, die über
                ihre UID angesprochen werden

    >>> txt = ('<p src="/resolveuid/abcdef0123456789abcdef0123456789"></p>'
    ...        '<img src="spec/by/path.png">'
    ...        '<img src="resolveuid/0123456789abcdef0123456789abcdef">')
    >>> extract_1st_image_info(txt)
    {'uid': '0123456789abcdef0123456789abcdef'}
    >>> extract_1st_image_info(txt, uid_only=False)
    {'path': 'spec/by/path.png'}
    """
    soup = BeautifulSoup(txt, builder)
    for elem in soup.find_all(['img']):
        val = elem.get('src')
        if not val:
            continue
        uid = extract_uid(val)
        if uid is not None:
            return {'uid': uid}
        elif not uid_only:
            return {'path': val}


def generate_image_infos(txt=None, **kwargs):
    """
    Scan the text (or soup) for image references and yield dictionaries

    Roughly like extract_1st_image_info, except ...

    - we don't stop after the first image use (because we might not be
      satisfied), and

    - we allow a soup (if already prepared) to be specified

    >>> txt = ('<p src="/resolveuid/abcdef0123456789abcdef0123456789"></p>'
    ...        '<img src="spec/by/path.png">'
    ...        '<img src="resolveuid/0123456789abcdef0123456789abcdef">')
    >>> def gii(txt, **kw):
    ...     return list(generate_image_infos(txt, **kw))

    By default, we ignore specifications without UIDs:
    >>> gii(txt)
    [{'uid': '0123456789abcdef0123456789abcdef'}]

    >>> gii(txt, uid_only=False)              # doctest: +NORMALIZE_WHITESPACE
    [{'path': 'spec/by/path.png'},
     {'uid': '0123456789abcdef0123456789abcdef'}]

    We expect either text or soup, but not both:
    >>> gii(None)
    Traceback (most recent call last):
      ...
    TypeError: Please specify either txt or soup!
    >>> gii('some text', soup="not None")  # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: Got both txt (<... 'str'>) and soup (<... 'str'>)!

    """
    pop = kwargs.pop
    uid_only = pop('uid_only', 1)
    soup = pop('soup', None)
    if txt is None and soup is None:
        raise TypeError('Please specify either txt or soup!')
    elif soup is None:
        builder = pop('builder', 'lxml')
        soup = BeautifulSoup(txt, builder)
    elif txt is not None:
        raise TypeError('Got both txt (%s) and soup (%s)!' %
                (type(txt), type(soup),
                 ))
    if kwargs:
        unused = sorted(kwargs.keys())[0]
        raise TypeError('Unused keyword argument(s): %(unused)r[..?]'
                        % locals())
    for elem in soup.find_all(['img']):
        val = elem.get('src')
        if not val:
            continue
        uid = extract_uid(val)
        if uid is not None:
            yield {'uid': uid}
        elif not uid_only:
            yield {'path': val}


def top_elements(txt, parser=None):
    """
    Wrapper für extract_content:
    - erledigt das Parsen
    - gibt jedenfalls eine Liste zurück

    NOTE: Please don't specify the (currently optional) 2nd argument by name;
          we'll likely rename it to 'builder'!
    """
    try:
        soup = BeautifulSoup(txt, parser)
    except Exception as e:
        print('!!! %s: %s' % (e.__class__.__name__, e))
        print(txt)
        print(txt())
        raise
    single, tmp = extract_content(soup)
    if single:
        return [tmp]
    else:
        return tmp


# Positionsangaben für DOM-Methode insertAdjacentHTML:
# (https://developer.mozilla.org/en-US/docs/Web/API/Element.insertAdjacentHTML)
INSERT_POSITIONS = ('beforebegin',
                    'afterbegin',
                    'beforeend',
                    'afterend',
                    )
def insertAdjacentElement(elem, position, new):
    """
    Nachbildung der DOM-API-Methode insertAdjacentHTML als Funktion.

    elem -- das existierende Element im Baum
    position -- eine der 4 aus INSERT_POSITIONS
    new -- der einzufügende Inhalt (hier: ein Element)

    """
    if position == 'beforebegin':
        elem.insert_before(new)
    elif position == 'afterbegin':
        elem.insert(0, new)
    elif position == 'beforeend':
        elem.append(new)
    elif position == 'afterend':
        elem.insert_after(new)
    else:
        raise ValueError('Invalid position: %(position)r'
                         % locals())


def gen_id_and_name(elem):
    """
    Generiere id- und name-Attribut des übergebenen Elements
    (jeweils sofern nicht leer)

    >>> soup = BeautifulSoup('<div/>', 'lxml')
    >>> elem = soup.new_tag('a', href='#', id='honk')
    >>> list(gen_id_and_name(elem))
    ['honk']
    >>> elem.attrs['name'] = ''
    >>> list(gen_id_and_name(elem))
    ['honk']
    """
    attribute = elem.attrs
    for a in ('id', 'name'):
        try:
            val = attribute[a].strip()
            if val:
                yield val
        except KeyError:
            pass


def get_id_or_name(elem):
    """
    Gib das id- oder notfalls name-Attribut des übergebenen Elements zurück
    (oder None)
    """
    for val in gen_id_and_name(elem):
        return val
    return None


DEFAULT_TAGS_AND_ATTRIBUTES = {
    'a':   ('href', extract_local_uid),
    'img': ('src',  extract_local_uid),
    }
def make_taginfo_extractor(themap=DEFAULT_TAGS_AND_ATTRIBUTES,
                           attribute='uid',
                           tagname_attribute='tagname',
                           searchedattribute_key=None,
                           default=None,
                           use_default=True):
    """
    Erzeuge eine Funktion, die eine Information je nach Tag-Name aus dem
    jeweils passenden Attribut ermittelt

    >>> get_tag_info = make_taginfo_extractor()
    >>> soup=BeautifulSoup('<a href="/resolveuid/abc123"/>'
    ...                    '<img src="resolveUid/def456"/>',
    ...                    'lxml')
    >>> dic1 = get_tag_info(soup.a)
    >>> sorted(dic1.items())
    [('href', '/resolveuid/abc123'), ('tagname', 'a'), ('uid', 'abc123')]
    >>> dic2 = get_tag_info(soup.img)
    >>> sorted(dic2.items())
    [('src', 'resolveUid/def456'), ('tagname', 'img'), ('uid', 'def456')]
    >>> soup2=BeautifulSoup('<img alt="image" class="image-caption"'
    ... 'src="./resolveUid/9e166a01d51569baf679d971167a1d5c/@@scaling'
    ... '/get?scaling=180x120" />',
    ... 'lxml')
    >>> dic3 = get_tag_info(soup2.img)
    >>> sorted(dic3.items())
    [('src', './resolveUid/9e166a01d51569baf679d971167a1d5c/@@scaling/get?scaling=180x120'), ('tagname', 'img'), ('uid', '9e166a01d51569baf679d971167a1d5c')]
    """
    if searchedattribute_key is None:
        searchedattribute_key = '-searched-for-%(attribute)s-' % locals()

    def get_tag_info(tag, default=default, use_default=use_default):
        """
        Extrahiere Informationen aus dem übergebenen Tag
        """
        tagname = tag.name
        try:
            a_name, a_func = themap[tagname]
        except KeyError:
            if use_default:
                return default
            raise
        else:
            attrs = tag.attrs
            a_value = attrs.get(a_name)
            if a_value:
                tmp = a_func(a_value)
            else:
                tmp = None
            info = {tagname_attribute: tagname,
                    a_name: a_value,
                    attribute: tmp,
                    }
            if tmp is None and searchedattribute_key:
                info.update({
                    searchedattribute_key: a_name,
                    })
        return info

    return get_tag_info
get_tag_info = make_taginfo_extractor()


def make_uid_generator(themap=DEFAULT_TAGS_AND_ATTRIBUTES, builder='lxml'):
    """
    Erzeuge eine Funktion, die aus Text oder Suppe die verwendeten UIDs
    extrahiert und generiert

    >>> f = make_uid_generator()
    >>> txt = ('<a href="/resolveuid/abc123"/>'
    ...        '<img src="resolveUid/def456"/>')
    >>> list(f(text=txt))
    ['abc123', 'def456']

    >>> txt = ('<a href="./@@resolveuid/ab1234"/>'
    ...        '<img src="@@resolveuid/de5678"/>')
    >>> list(f(text=txt))
    ['ab1234', 'de5678']

    Reale Beispiele:
    >>> txt2 = ('<p>'
    ... 'Text vor der eingebetteten Animation. Bitte beachten Sie die weiterführenden Informationen.</p>'
    ... '<p>'
    ... '<a class="unitracc-animation no-breaket" href="resolveuid/918f7934473e42f4a20f195f92115615/view">resolveuid/918f7934473e42f4a20f195f92115615/view</a></p>'
    ... '<p>'
    ... 'Text nach der eingebetteten Animation</p>'
    ... '<p>'
    ... '&nbsp;</p>')
    >>> soup2 = BeautifulSoup(txt2, 'html.parser')
    >>> list(f(txt2))
    ['918f7934473e42f4a20f195f92115615']
    """
    element_names = list(themap.keys())
    get_tag_info = make_taginfo_extractor(themap=themap)

    def generate_uids(text=None, soup=None, builder=builder):
        if soup is None:
            soup = BeautifulSoup(text or '', builder)
        elif text is not None:
            raise ValueError('Both text and soup given!')
        for elem in soup.find_all(element_names):
            dic = get_tag_info(elem)
            uid = dic['uid']
            if uid is not None:
                yield uid

    return generate_uids
generate_uids = make_uid_generator()


# ------------------------- [ CSS-Selektoren auswerten ... [
class SelectorParsingError(ValueError):
    """
    Fehler beim Parsen eines CSS-Selektors
    """
    def __init__(self, spec, val=None, res=None):
        self._dic = dict(locals())

    def __str__(self):
        self._dic['Class'] = self.__class__.__name__
        try:
            return self.__doc__.strip() % self._dic
        except:
            dic = self._dic
            other_keys = sorted([key for key in dic.keys()
                                 if key not in ('Class', 'self')
                                 ])
            txt = ' '.join(['%s=%r' % (key, dic[key])
                            for key in other_keys
                            ])
            return '%s(%s)' % (dic['Class'], txt)

class DuplicateNameError(SelectorParsingError):
    """
    %(spec)s: duplicate name %(val)r (%(res)s)
    """

class DuplicateIdError(SelectorParsingError):
    """
    %(spec)s: duplicate id %(val)r (%(res)s)
    """

class EmptyValueInModeError(SelectorParsingError):
    """
    %(spec)s: empty value %(val)r in mode %(mode)s (%(res)s)
    """
    def __init__(self, spec, val, mode, res=None):
        self._dic = dict(locals())

class UnsupportedCharacterError(SelectorParsingError):
    """
    %(spec)s: %(ch)r characters not (yet?) supported (%(res)s)
    """
    def __init__(self, spec, ch, res=None):
        self._dic = dict(locals())

class MisplacedCharacterError(SelectorParsingError):
    """
    %(spec)s: %(ch)r character must be first (%(res)s)
    """
    def __init__(self, spec, ch='*', res=None):
        self._dic = dict(locals())


NAMECHARS = frozenset(ascii_letters + digits + '_-')
def parse_selector(spec):
    """
    Analysiere den übergebenen (atomaren) CSS-Selektor.

    >>> def parse_selector_(arg):
    ...     res = parse_selector(arg)
    ...     return (res[0], sorted(res[1].items()))
    >>> parse_selector_('h1#toc.bonk')
    ('h1', [('class', ['bonk']), ('id', 'toc')])
    >>> parse_selector_('*#toc.bonk')
    (None, [('class', ['bonk']), ('id', 'toc')])
    >>> parse_selector_('p.bonk.honk')
    ('p', [('class', ['bonk', 'honk'])])

    Folgende Selektoren würden die Untersuchung des Kontexts des HTML-Knotens
    erfordern, der aber hier nicht übergeben wird, und werden daher *nicht*
    unterstützt (Notierung aus CSS-2.1-Standard):

    E F   -- descendant
    E > F -- child
    E + F -- sibling
    E:first-child
    E:lang(c)

    Das geht noch nicht:
    >x> parse_selector('h1[class~=toc].bonk')
    """
    res = {}
    tmp = []
    mode = 1
    def consume():
        val = ''.join(tmp)
        del tmp[:]
        if mode == 1:
            if '-name-' in res:
                raise DuplicateNameError(spec, val, res)
            res['-name-'] = val
        elif not val:
            if mode:
                raise EmptyValueInModeError(spec, val, mode, res)
        elif mode == 2:
            if 'id' in res:
                raise DuplicateIdError(spec, val, res)
            res['id'] = val
        elif mode == 3:
            if res.get('class') is None:
                res['class'] = []
            res['class'].append(val)
        elif mode == 0:
            res['-name-'] = '*'
            raise DuplicateNameError(spec, val, res)

    first = True
    for ch in spec:
        if ch == '*':
            if first:
                res['-name-'] = None
                mode = 0
            else:
                raise MisplacedCharacterError(spec, '*', res)
        elif ch in NAMECHARS:
            tmp.append(ch)
        elif ch == '#':
            consume()
            mode = 2
        elif ch == '.':
            consume()
            mode = 3
        else:
            raise UnsupportedCharacterError(spec, ch, res)
        if first:
            first = False
    consume()
    return (res.pop('-name-', None), res)
# ------------------------- ] ... CSS-Selektoren auswerten ]


# ----------------------------------- [ Metafunktionen ... [
def make_check_equal(key, val):
    """
    Erzeuge eine Funktion, die das übergebene Element auf das Attribut
    <key> mit dem exakten Wert <val> prüft.

    >>> f = make_check_equal('id', 'honk')
    >>> soup = BeautifulSoup('<div/>', 'lxml')
    >>> elem1 = soup.new_tag('a', id='honk')
    >>> f(elem1)
    True
    >>> elem2 = soup.new_tag('a', id='bonk')
    >>> f(elem2)
    False
    """
    def has_attribute(elem):
        try:
            return elem.attrs[key] == val
        except (KeyError, AttributeError):
            return False
    return has_attribute


def make_check_hasall(key, seq):
    """
    Erzeuge eine Funktion, die das übergebene Element auf das Attribut
    <key> mit allen Werten in <seq> prüft.

    >>> f = make_check_hasall('class', ['honk', 'bonk'])
    >>> dic = {'class': ['honk', 'bonk', 'other']}
    >>> soup = BeautifulSoup('<div/>', 'lxml')
    >>> elem1 = soup.new_tag('a', **dic)
    >>> f(elem1)
    True
    >>> dic['class'].remove('bonk')
    >>> elem2 = soup.new_tag('a', **dic)
    >>> f(elem2)
    False
    """
    def has_all(elem):
        try:
            found = elem.attrs[key]
            for item in seq:
                if item not in found:
                    return False
            return True
        except (KeyError, AttributeError):
            return False
    return has_all


def make_check_tagname(val):
    """
    >>> f = make_check_tagname('a')
    >>> soup = BeautifulSoup('<div/>', 'lxml')
    >>> elem1 = soup.new_tag('a', id='honk')
    >>> f(elem1)
    True
    >>> elem2 = soup.new_tag('p')
    >>> f(elem2)
    False
    """

    def has_tagname(elem):
        return elem.name == val
    return has_tagname


def make_levelfunc(specs):
    """
    Erzeuge eine Funktion, die für das übergebene Element das Verzeichnislevel ermittelt,
    und zwar durch Abgleich mit der Liste der Spezifikationen.
    """
    funcs = []
    for spec in specs:
        funcs.append(make_find_expression(spec, True))

    def get_level(elem):
        level = 1
        for f in funcs:
            if f(elem):
                return level
            level += 1
        raise ValueError('Could not detect level for %(elem)s!'
                         % locals())
    return get_level
# ----------------------------------- ] ... Metafunktionen ]


# ------------------------------- [ Klassenoperationen ... [
def classes_of(elem):
    """
    Gib die Liste der Klassen des übergebenen Elements zurück
    (das nämliche Listenobjekt).
    Wenn das Attribut noch nicht existiert, wird es erzeugt.
    """
    A = elem.attrs
    try:
        return A['class']
    except KeyError:
        A['class'] = []
        return A['class']


def swap_classes(elem, **kwargs):
    """
    Add and/or remove class entries to the given element

    add - one or more class entries to be added
    remove -- one or more class entries to be removed
    clear_empty -- finally delete an empty 'class' attribute?
    conflicting -- what if a class is both contained in the add and remove options?

    >>> div = BeautifulSoup('<div class="bogus-class kept-class">', 'lxml').div
    >>> div
    <div class="bogus-class kept-class"></div>

    Both options `add` and `remove` can be given as strings
    (which will be split), a set, or something we can turn into a set:

    >>> swap_classes(div, remove='bogus-class junk-class')
    True
    >>> div
    <div class="kept-class"></div>

    We check for likely unintentional argument conflicts:
    >>> swap_classes(div, add='to-be-or-not-to-be', remove='to-be-or-not-to-be')
    Traceback (most recent call last):
      ...
    ValueError: ['to-be-or-not-to-be'] specified for both addition and removal!

    But you may decide how to handle such conflicts:
    >>> swap_classes(div, add='whatever', remove='whatever', conflicting='add')
    True
    >>> div
    <div class="kept-class whatever"></div>

    Any sets you specify are left unspoiled in such cases:
    >>> add_set = {'whatever'}
    >>> remove_set = {'whatever'}
    >>> swap_classes(div, add=add_set, remove=remove_set, conflicting='remove')
    True
    >>> div
    <div class="kept-class"></div>

    As we had a conflict and decided to 'remove' in that case, the `add` set
    was changed internally;
    but the input sets are untouched:

    >>> sorted(add_set)
    ['whatever']
    >>> sorted(remove_set)
    ['whatever']

    The default behaviour is to delete an empty class attribute:
    >>> swap_classes(div, remove='kept-class whatever')
    True
    >>> div
    <div></div>

    Now for some edge cases.
    If you don't specify neither `add` nor `remove`, we consider this an error:

    >>> swap_classes(div)
    Traceback (most recent call last):
      ...
    TypeError: Didn't you intend to add or remove anything?!

    But it is quite possible that both arguments *evaluate* to None:
    >>> swap_classes(div, add='')
    False
    >>> div
    <div></div>
    >>> swap_classes(div, remove='')
    False
    >>> div
    <div></div>
    >>> swap_classes(div, add='same-value-again')
    True
    >>> div
    <div class="same-value-again"></div>

    A True return value currently doesn't guarantee the element has been modified:
    >>> swap_classes(div, remove='another-value')
    True
    >>> div
    <div class="same-value-again"></div>

    You might want to keep the empty class attribute for further processing:
    >>> swap_classes(div, remove='same-value-again', clear_empty=False)
    True
    >>> div
    <div class=""></div>

    But note: This won't add a class attribute which was not present before;
    for this to happen, you need to add something!

    We don't check whether the given element has an `attrs` attribute
    (which is not the case for NavigableStrings);
    in most cases, your .find or .find_all call will give you a proper element
    anyway (and it is on you to ensure this!):
    >>> soup = BeautifulSoup('<p class="">Some text', 'lxml')
    >>> swap_classes(soup.p.contents[0], add='some-value')
    Traceback (most recent call last):
      ...
    AttributeError: 'NavigableString' object has no attribute 'attrs'

    So, this is how a "final cleanup" could look like:

      for tag in soup.find_all(True):
          swap_classes(tag, remove=my_zoo_of_helper_classes)

    This `remove` argument might pretty well be falsy (but not None!);
    in this case, at least the empty class attributes will be removed:

    >>> soup.p
    <p class="">Some text</p>
    >>> swap_classes(soup.p, remove=[])
    True
    >>> soup.p
    <p>Some text</p>

    Unknown named arguments trigger a TypeError:
    >>> swap_classes(soup.p, remove=[], bogus=True)
    ... #  will look slightly different in Python-3-only implementation
    ... #                               doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: Disallowed argument(s) ('bogus',)
    """
    get = kwargs.get
    add = get('add', None)
    remove = get('remove', None)
    clear_empty = get('clear_empty', None)
    conflicting = get('conflicting', 'fail')
    disallowed = set(kwargs) - set(['add', 'remove',
                                    'clear_empty', 'conflicting',
                                    ])
    if disallowed:
        raise TypeError('Disallowed argument(s) %s'
                        % (tuple(sorted(disallowed)),
                           ))

    given = set()
    if add is not None:
        given.add('add')
        if isinstance(add, str):
            add = add.split()
        if not add:
            add = None
        elif not isinstance(add, set) or conflicting == 'remove':
            add = set(add)

    if remove is not None:
        given.add('remove')
        if isinstance(remove, str):
            remove = remove.split()
        if not remove:
            remove = None
        elif not isinstance(remove, set) or conflicting == 'add':
            remove = set(remove)

    if add is not None and remove is not None:
        confl = add.intersection(remove)  # I want the walrus!
        if not confl:
            pass
        elif conflicting == 'fail':
            raise ValueError('{} specified for both addition and removal!'
                             .format(sorted(confl)))
        elif conflicting == 'add':
            remove -= confl
            if not remove:
                remove = None
        elif conflicting == 'remove':
            add -= confl
            if not add:
                add = None
        else:
            raise ValueError('Invalid conflicting choice {}'
                             .format(conflicting))

    if not given:
        raise TypeError("Didn't you intend to add or remove anything?!")
    elif clear_empty is None:
        clear_empty = add is None

    attrs = elem.attrs
    oldval = attrs.get('class')
    if oldval is None and add is None:
        return False  # no changes

    cls_set = set(attrs.setdefault('class', []))
    if remove is not None:
        cls_set -= remove

    if add is not None:
        cls_set.update(add)

    if cls_set or not clear_empty:
        attrs['class'] = sorted(cls_set)
    else:
        del attrs['class']

    return True  # we *might* have applied changes!


def append_class(elem, val, force=False):
    """
    Füge die übergebene Klasse hinzu - ohne Überprüfung, ob sie
    evtl. schon vorhanden ist; es kann dann ja mit remove_class[es] sauber
    aufgeräumt werden.

    (append: normales Verhalten einer Liste)

    val -- der Wert (ein String)

    force -- jedenfalls classes_of aufrufen

    >>> soup = BeautifulSoup('<a/>', 'lxml')
    >>> append_class(soup.a, 'test1')
    >>> classes_of(soup.a)
    ['test1']

    Nach erneutem Aufruf ist die Klasse doppelt vorhanden:

    >>> append_class(soup.a, 'test1')
    >>> classes_of(soup.a)
    ['test1', 'test1']
    """
    if val:
        classes_of(elem).append(val)
    elif force:
        classes_of()


def add_class(elem, val, force=False):
    """
    Füge die übergebene Klasse hinzu, sofern noch nicht vorhanden.

    (add: angelehnt an das Verhalten eines Sets)

    >>> soup = BeautifulSoup('<a class="test1 test1"/>', 'lxml')

    Das erzeugte Attribut ist eine schnöde Liste:

    >>> type(soup.a.attrs['class']) # doctest: +ELLIPSIS
    <... 'list'>

    >>> add_class(soup.a, 'test2')
    >>> classes_of(soup.a)
    ['test1', 'test1', 'test2']

    Diese Klasse wird *nicht* doppelt hinzugefügt:

    >>> add_class(soup.a, 'test2')
    >>> classes_of(soup.a)
    ['test1', 'test1', 'test2']

    Das <force>-Argument ist nur relevant, wenn <val> logisch falsch ist; dann
    kann es verwendet werden, um das class-Attribut jedenfalls zu erzeugen.
    """
    if val:
        classes = classes_of(elem)
        if val not in classes:
            classes.append(val)
    elif force:
        classes_of()


def remove_class(elem, val):
    """
    Entferne die übergebene Klasse, sofern vorhanden.

    >>> soup = BeautifulSoup('<a class="test1 test1 test2"/>', 'lxml')
    >>> classes_of(soup.a)
    ['test1', 'test1', 'test2']
    >>> remove_class(soup.a, 'test1')
    >>> classes_of(soup.a)
    ['test2']
    """
    classes = classes_of(elem)
    while val in classes:
        classes.remove(val)


def remove_classes(elem, seq):
    """
    Entferne die übergebene Klassen, soweit vorhanden.
    Siehe auch has_any_class.
    """
    classes = classes_of(elem)
    for val in set(seq):
        while val in classes:
            classes.remove(val)


def check_class(elem, val):
    """
    Gib True zurück, wenn die übergebene Klasse schon vorhanden ist;
    andernfalls füge sie hinzu, und gib False zurück.

    >>> soup = BeautifulSoup('<a/>', 'lxml')
    >>> check_class(soup.a, 'test')
    False
    >>> classes_of(soup.a)
    ['test']
    >>> check_class(soup.a, 'test')
    True
    """
    classes = classes_of(elem)
    if val in classes:
        return True
    classes.append(val)
    return False
# ------------------------------- ] ... Klassenoperationen ]


# -------------------- [ Argumente für soup.find[_all] ... [
def gimme_true(elem):
    # gib True zurück
    # (BeautifulSoup.find(True) paßt auf jedes Element)
    return True


def has_class(elem, val):
    """
    Zum schnellen Feststellen, ob die übergebene Klasse vorhanden ist.
    Wenn weitere Operationen mit dem Klassenattribut anstehen, besser das
    Attribut holen und damit arbeiten; siehe classes_of
    und auch check_class.
    """
    try:
        classes = elem.attrs['class']
    except (KeyError, AttributeError):
        return False
    else:
        return val in classes


def has_all_classes(elem, seq):
    """
    Zum schnellen Feststellen, ob *alle* übergebenen Klassen vorhanden sind.
    """
    try:
        classes = elem.attrs['class']
    except (KeyError, AttributeError):
        return False
    else:
        for val in seq:
            if val not in classes:
                return False
        return True


def has_any_class(elem, seq, prefix=None):
    """
    Zum schnellen Feststellen, ob *eine* der übergebenen Klassen vorhanden ist.

    seq -- eine Sequenz konkreter Werte
    prefix -- ein Präfix; wenn der Leerstring übergeben wird, ist das Ergebnis
              für *jede* vorhandene Klasse True (und nur False, wenn *keine*
              Klasse vorhanden ist)

    >>> soup = BeautifulSoup('<a class="foo">bar</a>', 'lxml')
    >>> soup.a
    <a class="foo">bar</a>
    >>> has_any_class(soup.a, ('foo', 'bar'))
    True
    >>> has_any_class(soup.a, ('bar', 'baz'))
    False

    Das <seq>-Element muß eine Sequenz sein; insbesondere Strings dürfen
    derzeit nicht übergeben werden, ohne sie z. B. in eine Liste oder ein
    Tupel zu packen:

    >>> has_any_class(soup.a, 'foo')
    False

    Das untersuchte Element bleibt natürlich unverändert:

    >>> soup.a
    <a class="foo">bar</a>

    Zur Untersuchung, ob überhaupt eine Klasse vergeben wurde:

    >>> has_any_class(soup.a, (), '')
    True

    >>> soup = BeautifulSoup('<a href="#">Klassenloser Anker</a>', 'lxml')
    >>> has_any_class(soup.a, (), '')
    False

    >>> soup = BeautifulSoup('<a href="#" class="">Ebenfalls klassenlos</a>', 'lxml')
    >>> soup.a.attrs['class']
    []
    >>> has_any_class(soup.a, (), '')
    False

    Siehe auch --> make_classes_generator
    """
    try:
        classes = elem.attrs['class']
    except (KeyError, TypeError):
        return False
    else:
        if prefix is None:
            for val in seq:
                if val in classes:
                    return True
        else:
            for val in classes:
                if val in seq:
                    return True
                if val and val.startswith(prefix):
                    return True
        return False


def make_classes_generator(regex):
    """
    Erzeuge eine Funktion, die alle Klassen des gegebenen Elements generiert,
    die auf den gegebenen regulären Ausdruck passen

    >>> f = make_classes_generator('^level-[1-9][0-9]*$')
    >>> elem = BeautifulSoup('<div class="level-2 clearfix">x/div>', 'lxml').div
    >>> list(f(elem))
    ['level-2']
    >>> img = BeautifulSoup('<img>', 'lxml').img
    >>> list(f(img))
    []

    Siehe auch --> has_any_class
    """
    RE = re.compile(regex)
    match = RE.match

    def interesting_classes(elem):
        try:
            classes = elem.attrs['class']
        except (KeyError, TypeError):
            return
        else:
            for cls in classes:
                if match(cls):
                    yield cls

    return interesting_classes


def is_empty(elem):
    r"""
    Das Element ist komplett leer, oder es enthält nur Leerraum.

    >>> txt = '''<div class="question-hint-appendix">
    ... a) Betreten des Siloinnenraumes nur, wenn das Silo
    ...    leer ist.<br/>
    ... </div>'''
    >>> div = BeautifulSoup(txt, 'html.parser').div
    >>> is_empty(div)
    False
    >>> is_empty(div.br)
    True
    >>> txt2 = '<div>      \n  \t      </div>'
    >>> soup2 = BeautifulSoup(txt2, 'html.parser')
    >>> div2 = soup2.div
    >>> is_empty(div2)
    True

    Online-Editoren fügen zuweilen Leerzeilen ein, damit die Bearbeitung z. B.
    unter einer Tabelle möglich bleibt; inmitten des Textes stören diese
    jedoch:
    >>> after_table = '''<p>
    ...     &nbsp;</p>
    ... '''
    >>> p = BeautifulSoup(after_table, 'lxml').p
    >>> p.name
    'p'
    >>> is_empty(p)
    True

    Achtung - nicht jedes "leere" Element kann auch gelöscht werden!
    Siehe auch --> is_meat()

    >>> img = BeautifulSoup('<img src="img.png">', 'lxml').img
    >>> is_empty(img)
    True

    >>> div = BeautifulSoup('<div class="row" style="margin-bottom:10px;">\n'
    ...                     '</div>', 'lxml').div
    >>> div
    <div class="row" style="margin-bottom:10px;">
    </div>
    >>> is_empty(div)
    True
    """
    s = elem.string
    if s is None:
        return not elem.contents
    return not s.strip()


def is_whitespace(elem):
    r"""
    Das Element ist Leerraum und an den inneren Rändern von Blockelementen
    uninteressant

    >>> div = BeautifulSoup('''<div><!-- a comment -->
    ... <em>another element</em><br>
    ... some text</div>''', 'lxml').div
    >>> [(is_whitespace(child), child) for child in div.contents]
    ...                                  # doctest: +NORMALIZE_WHITESPACE
    [(False, ' a comment '),
     (True,  '\n'),
     (False, <em>another element</em>),
     (True,  <br/>),
     (False, '\nsome text')]

    But note:
    >>> div = BeautifulSoup('<div><!-- -->'
    ...     '<!-- the previous comment is empty! -->', 'lxml').div
    >>> [(is_whitespace(child), child) for child in div.contents]
    ...                                  # doctest: +NORMALIZE_WHITESPACE
    [(True,  ' '),
     (False, ' the previous command is empty! ')]

    This is considered a bug and will be fixed in a future release.

    """
    n = elem.name
    if n is None:
        return not elem.string.strip()
    if n == 'br':
        return not elem.attrs
    return False


def is_meat(elem):
    """
    Das Element ist sinnvoller Inhalt, der seinen Container erhaltenswert
    macht: Entweder ein benanntes Element, oder zumindest nicht-leerer Text.

    >>> img = BeautifulSoup('<img src="img.png">', 'lxml').img
    >>> is_meat(img)
    True
    """
    return elem.name is not None or bool(elem.string.strip())


def interesting_successor(elem, is_meat=is_meat):
    """
    Der folgende interessante Nachbar im gleichen Level.
    """
    for succ in elem.next_siblings:
        if is_meat(succ):
            return succ


def has_empty_line(elem):
    r"""
    Enthält das übergebene Element zwei br-Elemente als direkte Kinder,
    die allenfalls durch Leerraum getrennt werden?

    >>> txt1 = '<p><br><br></p>'
    >>> p1 = BeautifulSoup(txt1, 'html.parser').p
    >>> has_empty_line(p1)
    True

    >>> txt2 = '<p><br>\n<br></p>'
    >>> p2 = BeautifulSoup(txt2, 'html.parser').p
    >>> has_empty_line(p2)
    True

    >>> txt3 = '<p><br>inbetween<br></p>'
    >>> p3 = BeautifulSoup(txt3, 'html.parser').p
    >>> has_empty_line(p3)
    False
    """
    prev_name = None
    for child in elem.children:
        this_name = child.name
        if this_name is None:
            if not child.string.rstrip():
                continue
        if this_name == 'br':
            if prev_name == this_name:
                return True
        prev_name = this_name
    return False


def is_block_element(elem):
    """
    Ist das übergebene Element lt. HTML-Standard ein Blockelement?

    Blockelemente im Sinne dieser Funktion sind solche, die
    in Inline-Elementen sowie <p> nicht vorkommen dürfen.

    >>> txt = '<div><p><a><img></a></p></div>'
    >>> soup = BeautifulSoup(txt, 'html.parser')
    >>> is_block_element(soup.div)
    True
    >>> is_block_element(soup.p)
    True
    >>> is_block_element(soup.a)
    False
    >>> is_block_element(soup.img)
    False

    But, what about Navigable strings?
    >>> soup2 = BeautifulSoup('<div>A naked string'
    ...                       '<!-- a comment -->'
    ...                       '<p>Some text', 'lxml')
    >>> soup2.div
    <div>A naked string<!-- a comment --><p>Some text</p></div>
    >>> [(child.string, child.name, is_block_element(child))
    ...  for child in soup2.div.children]  # doctest: +NORMALIZE_WHITESPACE
    [('A naked string', None, False),
     (' a comment ',    None, False),
     ('Some text',      'p',  True)]
    """
    return elem.name in BLOCK_ELEMENT_NAMES


def is_block_with_p(elem):
    """
    Etwas speziell, zugegeben ...

    Wenn ein div- oder sonstiges Blockelement direkte p-Kinder hat,
    sollten auch alle anderen Inline-Kinder in Absätze gefaßt werden
    (Ausnahme: img- und a-Elemente vor der Transformation in Blockelemente).
    Also ist es sinnvoll, nach solchen Blockelementen suchen zu können.
    """
    if not is_block_element(elem):
        return False
    for child in elem.children:
        if child.name == 'p':
            return True
    return False


def was_erroneously_filled(elem):
    """
    Das Element hat Inhalt, den es nicht haben dürfte!
    The element has contents which it shouldn't have!

    Currently we can't reproduce the problem anymore that parsers filled e.g.
    <br> elements with the following text:

    >>> txt = '<div>Text<br>mit Zeilenumbruch</div>'
    >>> soup1 = BeautifulSoup(txt, 'html.parser')
    >>> soup1
    <div>Text<br/>mit Zeilenumbruch</div>
    >>> was_erroneously_filled(soup1.br)
    False
    >>> soup2 = BeautifulSoup(txt, 'lxml')
    >>> soup2
    <html><body><div>Text<br/>mit Zeilenumbruch</div></body></html>
    >>> was_erroneously_filled(soup2.br)
    False

    ... but of course we can't be sure it won't happen again.
    Thus, we construct an invalid element ourselves for this test:

    >>> soup1.br.string = "I shouldn't be here!"
    >>> was_erroneously_filled(soup1.div)
    False
    >>> soup1.br
    <br>I shouldn't be here!</br>
    >>> was_erroneously_filled(soup1.br)
    True
    """
    if elem.name is None:
        return False
    if elem.name not in EMPTY_ELEMENT_NAMES:
        return False
    if elem.string is not None:
        return True
    for child in elem.children:
        return True
    return False


def is_hyperlink(elem):
    """
    Ein Hyperlink ist ein a-Element mit einem href-Attribut.

    >>> is_hyperlink(BeautifulSoup('<a/>', 'lxml').a)
    False
    >>> is_hyperlink(BeautifulSoup('<a href="#"/>', 'lxml').a)
    True

    Es ist derzeit nicht erheblich, ob das href-Attribut leer ist:

    >>> is_hyperlink(BeautifulSoup('<a href=""/>', 'lxml').a)
    True
    >>> is_hyperlink(BeautifulSoup('<a href/>', 'lxml').a)
    True
    """
    try:
        return elem.name == 'a' and 'href' in elem.attrs
    except (TypeError, AttributeError):
        return False


def meaningful_attr(name, val):
    """
    Ist das übergebene Attribut signifikant?

    >>> meaningful_attr('href', '#')
    True
    >>> meaningful_attr('href', '')
    False

    class-Attribute werden von BeautifulSoup als Liste erzeugt:
    >>> div = BeautifulSoup('<div class=""/>', 'lxml').div
    >>> div
    <div class=""></div>
    >>> div.attrs['class']
    []
    >>> meaningful_attr('class', [''])
    False

    Boolean-Attribute können ohne Wert, mit leerem Wert oder mit ihrem Namen
    als Wert vorkommen; daher wird bei ihnen (i.e. bei allen, die nicht als
    Nicht-Boolean bekannt sind) der Wert nicht näher untersucht:

    >>> meaningful_attr('readonly', None)
    True
    """
    if name not in ('class',
                    'id', 'name',
                    'href', 'src',
                    'rel',
                    ):
        return True
    if isinstance(val, list):
        # z. B. "class": wir prüfen nicht auf die generelle Existenz des
        # Attributs, sondern stets auf einen konkreten Wert
        for item in val:
            if item:
                return True
        return False
    elif val:
        return True
    return False


def is_meaningful(elem, f=meaningful_attr):
    """
    Trägt das übergebene Element eine Bedeutung, oder kann es weg?
    I.d.R. nur für echte Elemente aufgerufen; NavigableStrings werden
    hier als bedeutsam betrachtet, wenn sie nicht nur Leerraum enthalten.

    Leere div- und span-Elemente ohne Attribute haben keine semantische
    Bedeutung:

    >>> is_meaningful(BeautifulSoup('<div/>', 'lxml').div)
    False
    >>> is_meaningful(BeautifulSoup('<span/>', 'lxml').span)
    False

    Ein leeres Klassenattribut interessiert nicht; eine nicht-leere ID schon:

    >>> is_meaningful(BeautifulSoup('<div class=""/>', 'lxml').div)
    False
    >>> is_meaningful(BeautifulSoup('<div id="x"/>', 'lxml').div)
    True

    p und td (z. B.) haben aus sich heraus eine Bedeutung:

    >>> is_meaningful(BeautifulSoup('<p/>', 'lxml').p)
    True
    >>> is_meaningful(BeautifulSoup('<td/>', 'lxml').td)
    True
    """
    n = elem.name
    if n is None:
        return bool(elem.string.strip())
    if n not in ('div', 'span'):
        return True
    for tup in elem.attrs.items():
        if f(*tup):
            return True
    return False


def make_find_expression(selector, force_func=False):
    """
    Gib das passende Argument für soup.find bzw. soup.find_all zurück.

    selector -- ein einfacher CSS-Selektor ([name][#id][.klasse][...])

    Wenn nötig (oder erzwungen; siehe unten), generiere eine Funktion;
    andernfalls einen einfachen Wert.

    >>> make_find_expression('')
    True
    >>> make_find_expression('h1')
    'h1'

    Wenn Attribute involviert sind, wird eine Funktion erzeugt:

    >>> f = make_find_expression('h1#toc')
    >>> soup = BeautifulSoup('<div/>', 'lxml')
    >>> elem = soup.new_tag('h1', id='tic')
    >>> f(elem)
    False
    >>> elem = soup.new_tag('h1', id='toc')
    >>> f(elem)
    True

    Wenn für andere Zwecke erzeugt, wird manchmal zwingend
    eine Funktion benötigt; dies kann mit force_func=True erzwungen werden:

    >>> f = make_find_expression('h1', True)
    >>> f(elem)
    True
    """
    name, kwargs = parse_selector(selector)
    funcs = []
    if name:
        if not kwargs:
            if force_func:
                return make_check_tagname(name)
            return name
        funcs.append(make_check_tagname(name))
    elif not kwargs:
        if force_func:
            return gimme_true
        return True
    val = kwargs.pop('id', None)
    if val is not None:
        funcs.append(make_check_equal('id', val))
    val = kwargs.pop('class', None)
    if val is not None:
        funcs.append(make_check_hasall('class', val))

    def check_funcs(elem):
        for f in funcs:
            if not f(elem):
                return False
        return True
    return check_funcs
# -------------------- ] ... Argumente für soup.find[_all] ]


# -------------------------- [ Kapitelnummern erzeugen ... [
class ChapterCounter(object):
    """
    Zum zählen von Kapiteln

    >>> chapter = ChapterCounter()
    >>> chapter.tuple()
    ()
    >>> chapter.count(1)
    >>> chapter.count(2)
    >>> chapter.tuple()
    (1, 1)
    >>> chapter.count(2)
    >>> chapter.tuple()
    (1, 2)
    >>> chapter.count(1)
    >>> chapter.tuple()
    (2,)

    Wenn ein Level übersprungen wird, können Nullen auftreten:
    >>> chapter.count(3)
    >>> chapter.tuple()
    (2, 0, 1)
    """
    def __init__(self):
        self._lastlevel = 0
        self._count = defaultdict(int)

    def count(self, level):
        if not isinstance(level, int):
            raise ValueError('Ganze Zahl > 0 erwartet (%(level)r)'
                             % locals())
        elif level <= 0:
            raise ValueError('Ganze Zahl > 0 erwartet (%(level)r)'
                             % locals())
        self._count[level] += 1
        if level < self._lastlevel:
            # alle niederrangigen Level auf 0 zurücksetzen:
            for i in sorted(self._count.keys()):
                if i > level:
                    self._count[i] = 0
        self._lastlevel = level

    def tuple(self):
        """
        Gib das sortierbare Tupel zurück.
        Beim Größenvergleich von Tupeln werden zunächst die Einzelelemente
        verglichen.  Hier ein Test für die Grundannahmen:

        >>> (2,) > (1, 1)
        True
        >>> (1, 1) > (1,)
        True
        """
        return tuple([self._count[level]
                      for level in range(1, self._lastlevel+1)
                      ])


def parent_chapters(tup):
    """
    Für Gruppierung in Verzeichnissen: Generiere die Nummern der Elternkapitel

    >>> list(parent_chapters((1, 2, 3)))
    [(1,), (1, 2), (1, 2, 3)]
    """
    liz = list(tup)
    stack = []
    while liz:
        stack.append(tuple(liz))
        liz.pop()
    while stack:
        yield stack.pop()
# -------------------------- ] ... Kapitelnummern erzeugen ]


def fix_webdivs(soup, counter=None, ch=SOFT_HYPHEN):
    r"""
    Ersetze div.web-Elemente mit Inhalt "-" durch weiche Trennzeichen

    soup - die Suppe (direkt bearbeitet)
    counter - optional
    ch - Zeichen (nur zur besseren Testbarkeit)

    >>> txt1 = '<div>Trenn<div class="web">-</div>mich</div>'
    >>> soup1 = BeautifulSoup(txt1, 'html.parser')
    >>> fix_webdivs(soup1, ch='|')
    >>> soup1.div
    <div>Trenn|mich</div>

    Wenn das div-Element schon von einem Autorentool (wie z. B. dem CKeditor)
    bearbeitet wurde, ist i.d.R. Leerraum ergänzt worden, um das vermeintliche
    Blockelement zu "verschönern"; dieser sitzt dann in den umgebenden
    Elementen:

    >>> txt2 = ('<div>  <b>eine</b> Emissions\n  <div class="web">\n'
    ... '  -\n  </div>\nminderungs\n  <div class="web">\n  -\n'
    ... '  </div>\nmaßnahme <em>unter vielen</em></div>')
    >>> soup2 = BeautifulSoup(txt2, 'lxml')
    >>> fix_webdivs(soup2, ch='|')
    >>> print(soup2.div)
    <div> <b>eine</b> Emissions|minderungs|maßnahme <em>unter vielen</em></div>

    Die Möglichkeit, daß die Schwesterelemente vor und nach dem div.web keine
    NavigableStrings, sondern (benannte) HTML-Elemente sind, wird bislang nicht
    berücksichtigt.
    """
    # TODO: change_text verwenden
    if counter is None:
        counter = defaultdict(int)
    for div in soup.find_all('div', class_='web'):
        s = div.string
        if s is not None and s.strip() == '-':
            counter['web.div'] += 1
            pred = div.previous_sibling
            if pred is not None:
                counter['web.div.prev'] += 1
                s = str(pred.string)
                if s is not None:
                    s2 = s.rstrip()
                    if s2 != s:
                        counter['web.div.prev.fix'] += 1
                        # pred.string = s2
                        pred.replaceWith(s2)
            succ = div.next_sibling
            if succ is not None:
                counter['web.div.succ'] += 1
                s = succ.string
                if s is not None:
                    s2 = s.lstrip()
                    if s2 != s:
                        counter['web.div.succ.fix'] += 1
                        succ.replaceWith(s2)
            div.replaceWith(ch)


def change_text(elem, txt, force=False):
    """
    Ändere den Text des übergebenen Elements auf den übergebenen Wert.
    Gedacht für:
    - NavigableString-Objekte
    - einfache Inline-Elemente (em, strong, a etc. )

    >>> soup=BeautifulSoup('<p>( <em>bonk</em> )</p>', 'lxml')
    >>> em = soup.em
    >>> prev_s = em.previous_sibling
    >>> next_s = em.next_sibling
    >>> change_text(prev_s, '(')
    >>> change_text(next_s, ')')
    >>> soup.p
    <p>(<em>bonk</em>)</p>
    """
    try:
        if elem.name is None:
            elem.replaceWith(txt)
        elif elem.string is not None or not elem.contents:
            elem.string = txt
        elif force:
            elem.string = txt
        else:
            print('ELEMENT %s NOT CHANGED' % elem)
    except AttributeError as e:
        # Standard library:
        from pprint import pprint
        print('#'*79)
        print('change_text:')
        pprint(sorted(locals().items())+ [
               ('type:', type(elem)),
               ('.string:', elem.string),
               ('.previous_sibling:', elem.previous_sibling),
               ('.next_sibling:', elem.next_sibling),
               ('.parent:', elem.parent),
               ])
        print('Exception %s:' % e.__class__)
        print(e)
        print('#'*79)
        raise


def extract_attributes(elem, alist):
    """
    Extrahiert die in <alist> genannte Attribute aus dem übergebenen Element;
    konform zu den üblichen BeautifulSoup-Gepflogenheiten sind sie dann in
    diesem nicht mehr vorhanden (was auch der Hauptzweck dieser Operation ist).
    Soweit die Attribute vorhanden waren, sind sie im zurückgegebenen
    dict-Objekt enthalten.

    >>> soup = BeautifulSoup('<p title="Ohne Worte">Hugh.</p>', 'lxml')
    >>> soup.p
    <p title="Ohne Worte">Hugh.</p>
    >>> extract_attributes(soup.p, ('title', 'id'))
    {'title': 'Ohne Worte'}
    >>> soup.p
    <p>Hugh.</p>
    """
    res = {}
    attrs = elem.attrs
    for aname in set(alist):
        try:
            res[aname] = attrs.pop(aname)
        except KeyError:
            pass
    return res


def fix_class_arg(kwargs, default=None, force=False):
    """
    kwargs - ein dict

    >>> dic = {'class_': 'honk', 'id': 'bonk'}
    >>> fix_class_arg(dic)
    >>> sorted(dic.items())
    [('class', 'honk'), ('id', 'bonk')]

    """
    if 'class_' in kwargs:
        if 'class' in kwargs:
            assert kwargs['class'] == kwargs['class_'], \
                    ('Only class (%(class)r) or class_ %(class_)r allowed!'
                     % kwargs)
        kwargs['class'] = kwargs.pop('class_')
    if not 'class' in kwargs and (force or default is not None):
        kwargs['class'] = default


def hyperlinkable_strings(soup, all=False, blacklist=['a']):
    """
    Suche ein Textelement heraus, das sich eignet, einen Hyperlink aufzunehmen.

    >>> txt = '<img alt="kein Text"> <b>fett</b> <a>und schon verlinkt</a>'
    >>> soup = BeautifulSoup(txt, 'html.parser')
    >>> list(hyperlinkable_strings(soup))[0]
    'fett'
    """
    for se in soup.strings:
        if (se.parent.name not in blacklist
            and se.string.strip()
            ):
            yield se
            if not all:
                return


def find_headline(elem, func):
    """
    Durchsuche die Suppe vor dem angegebenen Element nach "seiner" Überschrift
    und gib sie zurück.

    >>> text1 = u'<h2>Übungsaufgaben</h2><ol><li>Frage ...</li></ol>'
    >>> soup1 = BeautifulSoup(text1, 'lxml')
    >>> ffunc = lambda el: el.name == 'h2'
    >>> print(find_headline(soup1.ol, ffunc))
    <h2>Übungsaufgaben</h2>

    Überschriften sind manchmal in div-Elementen geschachtelt:
    >>> text2 = '<div><h2>Schwer zu finden</h2></div><ol><li>Frage ...</li></ol>'
    >>> soup2 = BeautifulSoup(text2, 'html.parser')
    >>> print(find_headline(soup2.ol, ffunc))
    <h2>Schwer zu finden</h2>

    Oft muß die Elternschaft des angeg. Elements durchsucht werden:
    >>> text3 = '<div><h2>Noch schwerer zu finden</h2></div><div><ol><li>Frage</li></ol></div>'
    >>> soup3 = BeautifulSoup(text3, 'html.parser')
    >>> print(find_headline(soup3.ol, ffunc))
    <h2>Noch schwerer zu finden</h2>

    >>> text4 = '<div><h2>Ham</h2><p>Spam</p></div><div><ol><li>Frage</li></ol></div>'
    >>> soup4 = BeautifulSoup(text4, 'html.parser')
    >>> print(find_headline(soup4.ol, ffunc))
    <h2>Ham</h2>

    Die Überschrift darf Unterelemente haben:
    >>> text5 = '<div><h2>CO<sub>2</sub></h2></div><div><ol><li>Frage</li></ol></div>'
    >>> soup5 = BeautifulSoup(text5, 'html.parser')
    >>> print(find_headline(soup5.ol, ffunc))
    <h2>CO<sub>2</sub></h2>

    Es wird eine "vernünftige" Struktur vorausgesetzt: ein div wird maximal
    eine Überschrift enthalten für Inhalte, die nicht in ihm selbst enthalten
    sind.
    """
    for el in elem.previous_siblings:
        if func(el):
            return el
        if el.name == 'div':
            for subel in el.descendants:
                if func(subel):
                    return subel
    # Die Überschrift ist selbst kein Elternelement:
    for el in elem.parents:
        cand = find_headline(el, func)
        if cand is not None:
            return cand


def body_content(soup):
    """
    Gib den Inhalt des body-Elements als utf-8-codierten String zurück.

    BeautifulSoup erzeugt - zumindest bei Verwendung von lxml - stets implizit
    html > body:

    >>> soup = BeautifulSoup('<p>Nur ein Absatz</p>', 'lxml')
    >>> soup.body
    <body><p>Nur ein Absatz</p></body>

    Diese Funktion gibt einen String zurück, der alle Kinder dieses implizit
    erzeugten body-Elements enthält:

    >>> body_content(soup)
    '<p>Nur ein Absatz</p>'

    >>> soup.body.append('nur ein String')
    >>> soup.body.append(make_tag(soup, 'div', 'noch ein div'))
    >>> body_content(soup)
    '<p>Nur ein Absatz</p>nur ein String<div>noch ein div</div>'

    """
    res = []
    body = soup.body
    if not body:
        return ''
    for child in body.children:
        res.append(str(child))
    return ''.join(res)


def contents_stripped(elem):
    """
    Wie elem.contents; allerdings werden das erste und/oder letzte Kindelement
    weggelassen, wenn sie NavigableStrings sind und nur Leerraum enthalten:

    >>> txt = '''<div>
    ... <img src="bild.jpg">
    ... </div>'''
    >>> soup = BeautifulSoup(txt, 'html.parser')
    >>> div = soup.div
    >>> len(div.contents)
    3
    >>> len(contents_stripped(div))
    1

    Leere "echte" Elemente werden nicht entfernt:

    >>> txt2 = '''<div><span></span><img src="bild.jpg">
    ... </div>'''
    >>> soup2 = BeautifulSoup(txt2, 'html.parser')
    >>> div2 = soup2.div
    >>> len(div2.contents)
    3
    >>> len(contents_stripped(div2))
    2

    >>> txt3 = '''<div>
    ... Dieser Text ist nicht leer
    ... <img src="bild.jpg">
    ... </div3>'''
    >>> soup3 = BeautifulSoup(txt3, 'html.parser')
    >>> div3 = soup3.div
    >>> len(div3.contents)
    3
    >>> len(contents_stripped(div3))
    2
    """
    res = []
    for child, prev, idx, next in inject_indexes(elem.children):
        if prev is None or next is None:
            if isinstance(child, NavigableString) and not child.string.strip():
                continue
        res.append(child)
    return res


def contents_stripped2(elem):
    r"""
    Wie contents_stripped;
    zusätzlich wird jeglicher Leerraum am Anfang entfernt,
    der nicht als separates Element vorliegt
    (oder in einer tieferen Schachtelungsebene).

    >>> txt = '''<div>
    ... <tt>  Text 1  </tt>
    ... <tt>  Text 2  </tt></div>'''
    >>> soup = BeautifulSoup(txt, 'html.parser')
    >>> div = soup.div
    >>> contents_stripped(div)
    [<tt>  Text 1  </tt>, '\n', <tt>  Text 2  </tt>]
    >>> contents_stripped2(div)
    [<tt>Text 1  </tt>, '\n', <tt>  Text 2  </tt>]

    Wenn das letzte Kindelement ein String ist, wird der hängende Leerraum
    entfernt: (FUNKTIONIERT NOCH NICHT!)

    >>> txt = '''<div>
    ... <tt>  Text 1  </tt>
    ...   Text 2  </div>'''
    >>> soup = BeautifulSoup(txt, 'html.parser')
    >>> div = soup.div
    >>> contents_stripped2(div)  # doctest: +SKIP
    [<tt>Text 1  </tt>, u'\n  Text 2']
    """
    res = []
    leaders_left = True
    for child, prev, idx, next in inject_indexes(elem.children):
        if leaders_left:
            if _strip_leading_whitespace(child):
                continue
            leaders_left = False
        """
        # print('Das Ende naht!', (next, child, prev, leaders_left))
        if next is None and _strip_trailing_whitespace(child):
            continue
        """
        res.append(child)
    return res


def _strip_leading_whitespace(elem):
    """
    Entferne führenden Leerraum

    Gib True zurück, wenn nach Entfernen des Leerraums nichts mehr übrigbleibt
    (und das Element samt seiner Kinder somit entfernt werden kann).
    """
    if isinstance(elem, NavigableString):
        s = elem.string.lstrip()
        if not s:
            return True
        else:
            # elem.string = s
            elem.replaceWith(s)
            return False
    elif elem.name in REPLACED_ELEMENT_NAMES:
        return False
    else:
        has_nonempty_children = False
        for child, prev, idx, next in inject_indexes(elem.children):
            if _strip_leading_whitespace(child):
                child.extract()
            else:
                return False
        return True


def _strip_trailing_whitespace(elem):
    """
    Entferne angehängten Leerraum
    (bisher primitiver als das Pendant _strip_leading_whitespace)

    Gib True zurück, wenn nach Entfernen des Leerraums nichts mehr übrigbleibt
    (und das Element samt seiner Kinder somit entfernt werden kann).
    """
    if isinstance(elem, NavigableString):
        s = elem.string.rstrip()
        if not s:
            return True
        else:
            vorher = elem
            elem.replaceWith(s)
            assert elem is vorher
            return False
    else:
        return False


def get_single_element(txt, builder='lxml'):
    r"""
    Konvertiere HTML-Text und gib seinen Inhalt - ein einziges Element -
    zurück.  Wenn mehrere Elemente auf oberster Ebene vorhanden sind (bzw. im
    body, wenn vom Parser in html>body eingefaßt), tritt ein Fehler auf.
    (Um ggf. mehrere Elemente zu extrahieren, siehe extract_content(soup).)

    >>> txt = '<html><body><p>Ein Absatz</p></body></html>'
    >>> get_single_element(txt)
    <p>Ein Absatz</p>

    Etwaiger Leerraum wird entfernt:

    >>> txt2 = '<div id="honk">Ein Div</div>\n'
    >>> soup2 = BeautifulSoup(txt2, 'html.parser')
    >>> print(soup2)
    <div id="honk">Ein Div</div>
    <BLANKLINE>
    >>> get_single_element(txt2)
    <div id="honk">Ein Div</div>
    """
    soup = BeautifulSoup(txt.strip(), builder)
    cont = soup
    inner = soup.body
    if inner is not None:
        cont = inner
    res = []
    children = contents_stripped(cont)
    cnt = len(children)
    if cnt == 1:
        return children[0]
    else:
        raise ValueError('1 child expected; %(cnt)d found! txt=%(txt)r'
                         % locals())


def fix_empty_elements(soup):
    """
    Bereinige leere HTML-Elemente, die z. B. vom Standardparser
    irrtümlich gefüllt wurden.

    The problem tackled by this function is perhaps related to older versions
    of BeautifulSoup an/or lxml and/or the standard parser only;
    thus, we construct some faulty soup ourselves.

    >>> txt = '<div>Ein Text<br>'
    >>> soup = BeautifulSoup(txt, 'html.parser')
    >>> soup.br.string = 'mit Zeilenumbruch'
    >>> soup
    <div>Ein Text<br>mit Zeilenumbruch</br></div>

    Der Inhalt des br-Elements ist natürlich Unfug!
    Er wird daher ausgepackt:

    >>> res = fix_empty_elements(soup)
    >>> soup
    <div>Ein Text<br/>mit Zeilenumbruch</div>

    Da solche fehlerhaften Füllungen geschachtelt auftreten,
    gibt die Funktion einen Zähler zurück, der angibt, wieviele Fundstellen
    korrigiert wurden; wenn 0 zurückkommt, ist alles in Ordnung, und die
    wiederholten Aufrufe können beendet werden.

    >>> res
    1
    """
    cnt = 0
    for elem in soup.find_all(was_erroneously_filled):
        new = soup.new_tag(elem.name, **elem.attrs)
        elem.insert_before(new)
        # gibt ein Ding wie <new> zurück; aber die Position ist wichtig!
        elem.unwrap()
        cnt += 1
    return cnt


def parsed_text(txt, builder='lxml', **kwargs):
    r"""
    Gib eine geparste Version des übergebenen Texts zurück;
    für den Fall, daß der Text benötigt wird, z. B. um ihn zu speichern.

    Der lxml-Parser z. B. packt stets das fehlende html- und body-Element
    drumherum:

    >>> txt = '<div>Ein Text<br>mit Zeilenumbruch'
    >>> BeautifulSoup(txt, 'lxml')
    <html><body><div>Ein Text<br/>mit Zeilenumbruch</div></body></html>

    Dieses Artefakt ist zum Speichern üblicherweise hinderlich und wird
    entfernt:

    >>> parsed_text(txt, 'lxml')
    '<div>Ein Text<br/>mit Zeilenumbruch</div>'

    Wir hatten früher Unfug festgestellt -- dergestalt, daß der Standard-Parser
    per Standard leere Elemente mit Inhalt füllte.
    Dies stellen wir hier noch einmal nach, um die durchgeführte Korrektur
    testen zu können:
    >>> txt = '<div>Ein Text<br>'
    >>> soup = BeautifulSoup(txt, 'html.parser')
    >>> soup.br.string = 'mit Zeilenumbruch'
    >>> soup
    <div>Ein Text<br>mit Zeilenumbruch</br></div>
    >>> txt = str(soup)

    Die Funktion parsed_text räumt damit auf; das Ergebnis ist nun dasselbe wie
    bei Verwendung von lxml:

    >>> html5 = parsed_text(txt, 'html.parser')
    >>> html5
    '<div>Ein Text<br/>mit Zeilenumbruch</div>'

    Mit diesem Ergebnis macht auch der Python-Standardparser keinen Unsinn
    mehr:

    >>> BeautifulSoup(html5, 'html.parser')
    <div>Ein Text<br/>mit Zeilenumbruch</div>

    Leerraum am Ende wird derzeit NICHT entfernt:
    >>> txt2 = '<span>Bla</span>\n\n'
    >>> soup2 = BeautifulSoup(txt2, 'lxml')
    >>> print(soup2)
    <html><body><span>Bla</span>
    </body></html>
    >>> parsed_text(txt2, 'lxml')
    '<span>Bla</span>\n'

    """
    soup = BeautifulSoup(txt, builder, **kwargs)
    while fix_empty_elements(soup):
        pass
    return stripped_soup(soup)


def stripped_soup(soup):
    """
    Gib die übergebene Suppe als Text zurück und entferne dabei
    einen implizit erzeugten html>body-Rahmen.

    Von parsed_text verwendet, aber auch davon losgelöst nützlich

    >>> stripped_soup('<html><body><span>Test1</span></body></html>')
    '<span>Test1</span>'
    >>> stripped_soup('<html><body></body></html>')
    ''
    >>> stripped_soup('')
    ''
    """
    res = str(soup)
    start, end = (0, None)
    if res.startswith('<html><body>') and res.endswith('</body></html>'):
        start, end = (12, -14)
    if not res[start:]:
        return ''
    while res[start] in whitespace:
        start += 1
    if end is None:
        return res[start:]
    return res[start:end]


# evtl. counter-Argument vorsehen:
# wenn übergeben, einfach verwenden;
# andernfalls erzeugen und abschließend ausgeben
def split_paragraphs(root, soup,
        move_blocks=False,
        is_block=is_block_element,
        keep_root=is_meaningful):
    """
    Durchsuche den Baum unter <root> nach Sequenzen von zwei br-Elementen,
    sprich: Leerzeilen, wo besser Absätze stehen würden.

    >>> txt = '''<html><body>
    ... <div>Eine Zeile<br>
    ... <br>
    ... Noch eine</div>
    ... </body></html>'''
    >>> soup = BeautifulSoup(txt, 'html.parser')
    >>> split_paragraphs(soup.body, soup)
    >>> print(soup.body)
    <body>
    <p>Eine Zeile</p><p>
    Noch eine</p>
    </body>

    Etwaige schon vorhandene Absätze werden geteilt:

    >>> txt = '''<html><body>
    ... <p>Dieser Absatz<br>
    ... <br>
    ... wird zweigeteilt</p>
    ... </body></html>'''
    >>> soup = BeautifulSoup(txt, 'html.parser')
    >>> split_paragraphs(soup.body, soup)
    >>> b2 = soup.body
    >>> print(b2)
    <body>
    <p>Dieser Absatz</p><p>
    wird zweigeteilt</p>
    </body>

    Dasselbe nochmal mit Dreiteilung; randständige br-Elemente werden entfernt:

    >>> txt = '''<html><body>
    ... <p>Dieser Absatz<br>
    ... <br>
    ... ergibt
    ... <br> <br>
    ... drei Portionen<br>
    ... </p>
    ... </body></html>'''
    >>> soup = BeautifulSoup(txt, 'html.parser')
    >>> split_paragraphs(soup.body, soup)
    >>> print(soup.body)
    <body>
    <p>Dieser Absatz</p><p>
    ergibt
    </p><p>
    drei Portionen</p>
    </body>

    Wenn ein p-Element mit Attributen verarbeitet wird, bleiben die Attribute
    jedenfalls erhalten; nötigenfalls wird das Element in ein div konvertiert:

    >>> txt = '<body><p id="honk"><br>Zwei<br> <br>Abs&auml;tze<br></p></body>'
    >>> soup = BeautifulSoup(txt, 'html.parser')
    >>> split_paragraphs(soup.body, soup)
    >>> print(soup.body)
    <body><div id="honk"><p>Zwei</p><p>Absätze</p></div></body>

    Unterschiedliche Ursache, dasselbe Ergebnis: Ein div-element bleibt
    erhalten, wenn es Attribute trägt (Funktionsargument <keep_root>):

    >>> txt = '<body><div id="bonk"><br>Zwei<br> <br>Abs&auml;tze<br></div></body>'
    >>> soup = BeautifulSoup(txt, 'html.parser')
    >>> split_paragraphs(soup.body, soup)
    >>> print(soup.body)
    <body><div id="bonk"><p>Zwei</p><p>Absätze</p></div></body>

    """
    for elem in root.find_all(has_empty_line):
        split_div_to_paragraphs(elem, soup, move_blocks, is_block, keep_root)


def split_div_to_paragraphs(root, soup,
        move_blocks=False,
        is_block=is_block_element,
        keep_root=is_meaningful):
    """
    Konvertiere ein div-Element in eine Sequenz von echten Absätzen.

    root -- das zu verarbeitende Element (div oder body; td?). Ob es erhalten
            bleibt, entscheidet die Funktion <keep_root>
    soup -- die Suppe, in-place geändert.  Wird auch benötigt, um Elemente
            zu erzeugen.
    move_blocks -- Boolean-Wert.
        True:  aufgefundene Blockelemente werden jeweils vor den Absatz
               verschoben, in dem sie sonst fehlerhafterweise stünden;
        False: sie bleiben an Ort und Stelle und bewirken eine Absatzteilung.

    is_block -- Funktion, die für jedes Element aufgerufen wird und
                entscheidet, ob es als Blockelement betrachtet wird. Das
                Element kann dabei modifiziert werden (z. B. Konversion eines
                div.marginalia nach span.marginalia, das dann an Ort und Stelle
                verbleiben kann).
    keep_root -- Funktion, die -- abschließend auf <root> angewendet --
                 entscheidet, ob das Wurzelelement erhalten bleibt.

    Zu beachten:
    - Blockelemente werden ggf. vor den Absatz gezogen, in dem sie sonst
      landen würden (--> <move_blocks>)
    - einzelne br-Elemente bleiben unbehelligt
    - manche Blockelemente können konvertiert werden und dann auch in einem
      p-Element verbleiben (--> <is_block>)

    >>> txt1 = '''<html><body>
    ... <div>Eine Zeile<br><br>
    ... Noch eine</div>
    ... </body></html>'''
    >>> soup1 = BeautifulSoup(txt1, 'html.parser')
    >>> has_empty_line(soup1.div)
    True
    >>> split_div_to_paragraphs(soup1.div, soup1)
    >>> print(soup1.body)
    <body>
    <p>Eine Zeile</p><p>
    Noch eine</p>
    </body>

    Häufig sind die beiden Zeilenumbrüche durch Leerraum getrennt:

    >>> txt2 = '''<html><body>
    ... <div>Eine Zeile<br>
    ... <br>
    ... Noch eine</div>
    ... </body></html>'''
    >>> soup2 = BeautifulSoup(txt2, 'html.parser')
    >>> has_empty_line(soup2.div)
    True
    >>> split_div_to_paragraphs(soup2.div, soup2)
    >>> print(soup2.body)
    <body>
    <p>Eine Zeile</p><p>
    Noch eine</p>
    </body>

    Wenn Name des Wurzelelements <root> ...
    - 'p': abschließend das erste Kind des sink-Elements extrahieren, als
      erstes Kind der Wurzel einfügen und "auspacken"; wenn andere Kinder
      vorhanden, diese mit root.insert_after anhängen
    - 'div': Wenn keine Attribute, durch <sink> vollständig ersetzen
    - andere (z. B. 'body', 'td'):
      das Element erhalten; <sink> darin entpacken.
    ...
    """
    # TODO: Test/Dokumentation für move_blocks
    buf = []
    prev_name = None
    sink = soup.new_tag('div')
    for child in contents_stripped(root):
        cur_name = child.name
        cur_elem = child.extract()
        if cur_name == 'br':
            if prev_name == 'br':
                this_p = _consume_buffer(buf, soup)
                if this_p is not None:
                    sink.append(this_p)
                prev_name = None
                continue
            elif not buf:
                # br am Anfang eines Absatzes ->
                # einfach ignorieren
                continue
            else:
                buf.append(cur_elem)
        elif cur_name is None:
            if prev_name == 'br' and not cur_elem.string.strip():
                continue
            buf.append(cur_elem)
        elif is_block(cur_elem):
            if not move_blocks:
                this_p = _consume_buffer(buf, soup)
                if this_p is not None:
                    sink.append(this_p)
            sink.append(cur_elem)
            prev_name = None
        else:
            buf.append(cur_elem)
        prev_name = cur_name
    # Schleife beendet: alles extrahiert; das root-Element ist jetzt leer.

    this_p = _consume_buffer(buf, soup)
    if this_p is not None:
        sink.append(this_p)

    if not sink.contents:
        # wenn leer, wenigstens das Wurzelelement (vorerst?) erhalten
        return

    if root.name == 'p':  # Spezialfall
        if root.attrs:
            root.name = 'div'
            root.append(sink)
            sink.unwrap()
        else:
            root.insert_after(sink)
            sink.unwrap()
            root.extract()
    else:
        root.append(sink)
        sink.unwrap()
        if not keep_root(root):
            root.unwrap()


def _consume_buffer(buf, soup):
    """
    Wenn der Puffer Elemente enthält, gib diese in einem neuen
    p-Element zurück; ansonsten None.
    """
    _crop_buffer(buf)
    if not buf:
        return
    p = soup.new_tag('p')
    while buf:
        p.append(buf.pop(0))
    return p


def _crop_buffer(buf):
    # Helferlein für _consume_buffer
    while buf:
        item = buf[0]
        if is_whitespace(item):
            del buf[0]
        else:
            break

    while buf[1:]:
        item = buf[-1]
        if is_whitespace(item):
            del buf[-1]
        else:
            break


def strip_linebreaks(elem, remove_empty=False, is_meat=is_meat):
    """
    Entferne etwaige äußere <br>-Elemente.

    >>> txt = '<p> <br>Text <br> </p>'
    >>> soup = BeautifulSoup(txt, 'html.parser')
    >>> soup.p
    <p> <br/>Text <br/> </p>
    >>> strip_linebreaks(soup.p)
    >>> soup.p
    <p> Text  </p>

    Wenn das übergebene Element nur Leerraum und ein <br> enthält,
    kann es entfernt weden:

    >>> txt2 = '<div><p> <br> </p></div>'
    >>> soup2 = BeautifulSoup(txt2, 'html.parser')
    >>> strip_linebreaks(soup2.p, remove_empty=True)
    >>> soup2.div
    <div></div>
    """
    meat_found = False
    for child, prev, idx, next in inject_indexes(contents_stripped(elem)):
        if prev is None or next is None:
            if child.name == 'br' and not child.attrs:
                if remove_empty and prev is None and next is None:
                    elem.extract()
                    return
                child.extract()
        elif not meat_found:
            if is_meat(child):
                meat_found = True
    if remove_empty and not meat_found:
        elem.extract()


def fence_texts(elem, soup, is_block=is_block_element):
    """
    Hege alle Texte usw. ein, die nicht in Absätze gefaßt sind.
    Gib True zurück, wenn solche gefunden (und korrigiert) wurden,
    ansonsten False.

    >>> txt = '<div>Running free<p>fenced</p></div>'
    >>> soup = BeautifulSoup(txt, 'html.parser')
    >>> fence_texts(soup.div, soup)
    True
    >>> soup.div
    <div><p>Running free</p><p>fenced</p></div>

    Beim erneuten Aufruf gibt es nichts mehr zu tun:

    >>> fence_texts(soup.div, soup)
    False

    Praxisnäheres Beispiel:

    >>> txt = '''<body><div class="attribute-text"><div class="marginalia">Homogenisierung</div>
    ...
    ... Die
    ... <a class="glossar" href="#topic-2">Homogenisierung</a>
    ...  der Zementrohstoffe erfolgt, wie erwähnt (...).
    ...
    ...  <ol><li>
    ...  <strong>Mischbett</strong>: Bla ...
    ...  </ol>
    ...  <br>
    ...  <div class="marginalia"><img alt="" src="/vdz/32px-nuvola_apps_edu_miscellaneous.png">
    ...  <br>Inhalt des Kurses</div>
    ...
    ...  Im Folgenden ...
    ...  </div></body>'''
    >>> soup = BeautifulSoup(txt, 'html.parser')
    >>> print(soup.body)  # doctest: +NORMALIZE_WHITESPACE
    <body><div class="attribute-text"><div class="marginalia">Homogenisierung</div>
    <BLANKLINE>
    Die
    <a class="glossar" href="#topic-2">Homogenisierung</a>
     der Zementrohstoffe erfolgt, wie erwähnt (...).
    <BLANKLINE>
     <ol><li>
    <strong>Mischbett</strong>: Bla ...
     </li></ol>
    <br/>
    <div class="marginalia"><img alt="" src="/vdz/32px-nuvola_apps_edu_miscellaneous.png"/>
    <br/>Inhalt des Kurses</div>
    <BLANKLINE>
     Im Folgenden ...
     </div></body>
    >>> fence_texts(soup.body.div, soup)
    True

    Bis auf ein p, das nur ein br enthält, schon recht schick:

    >>> print(soup.div)
    <div class="attribute-text"><div class="marginalia">Homogenisierung</div><p>
    <BLANKLINE>
    Die
    <a class="glossar" href="#topic-2">Homogenisierung</a>
     der Zementrohstoffe erfolgt, wie erwähnt (...).
    <BLANKLINE>
     </p><ol><li>
    <strong>Mischbett</strong>: Bla ...
     </li></ol><div class="marginalia"><img alt="" src="/vdz/32px-nuvola_apps_edu_miscellaneous.png"/>
    <br/>Inhalt des Kurses</div><p>
    <BLANKLINE>
     Im Folgenden ...
     </p></div>

    Nun mit automatischer Konversion von Marginalien:

    >>> def is_block(elem):
    ...     if elem.name == 'div' and has_class(elem, 'marginalia'):
    ...         elem.name = 'span'
    ...         return False
    ...     return is_block_element(elem)
    >>> soup = BeautifulSoup(txt, 'html.parser')
    >>> fence_texts(soup.body.div, soup, is_block=is_block)
    True
    >>> print(soup.body)
    <body><div class="attribute-text"><p><span class="marginalia">Homogenisierung</span>
    <BLANKLINE>
    Die
    <a class="glossar" href="#topic-2">Homogenisierung</a>
     der Zementrohstoffe erfolgt, wie erwähnt (...).
    <BLANKLINE>
     </p><ol><li>
    <strong>Mischbett</strong>: Bla ...
     </li></ol><p><span class="marginalia"><img alt="" src="/vdz/32px-nuvola_apps_edu_miscellaneous.png"/>
    <br/>Inhalt des Kurses</span>
    <BLANKLINE>
     Im Folgenden ...
     </p></div></body>
    """
    found = False
    buf = []
    sink = soup.new_tag('div')
    this_p = None
    for child in contents_stripped(elem):
        if is_block(child):
            if found:
                this_p = _consume_buffer(buf, soup)
                if this_p is not None:
                    sink.append(this_p)
                sink.append(child.extract())
        else:
            if not found:
                found = True
            buf.append(child.extract())
    if found:
        this_p = _consume_buffer(buf, soup)
        if this_p is not None:
            sink.append(this_p)
        elem.append(sink)
        sink.unwrap()
    return found


def strip_empty_successor(elem):
    r"""
    Z. B. für Blockelemente, denen ein wohlmeinender Online-Editor einen leeren
    Absatz angefügt hat, um die Bearbeitbarkeit sicherzustellen.

    Löscht aus der Suppe, die das übergebene Element enthält:
    - unmittelbar folgenden Leerraum, wenn es sich bei <elem> um ein
      Blockelement handelt
    - danach ggf. ein p- oder div-Element, das nur Leerraum enthält

    >>> txt1 = '''<div>
    ... <h1>Der nichtleere Absatz</h1>
    ... <p> </p>
    ... </div>'''
    >>> soup1 = BeautifulSoup(txt1, 'html.parser')
    >>> strip_empty_successor(soup1.h1)
    True
    >>> print(soup1.div)
    <div>
    <h1>Der nichtleere Absatz</h1>
    </div>

    >>> txt2 = '''<div>
    ... <h1>Der nichtleere Absatz</h1>
    ... <p> &nbsp;</p>
    ... </div>'''
    >>> soup2 = BeautifulSoup(txt2, 'html.parser')
    >>> strip_empty_successor(soup2.h1)
    True
    >>> print(soup2.div)
    <div>
    <h1>Der nichtleere Absatz</h1>
    </div>

    Das letzte Element in seinem Container bleibt unverändert:
    >>> txt3 = '''<div>
    ... <div id="1">
    ... <p>Ein Absatz</p>
    ... </div>
    ... </div>'''
    >>> soup3 = BeautifulSoup(txt3, 'html.parser')
    >>> strip_empty_successor(soup3.p)
    False
    >>> print(soup3.div)  # doctest: +NORMALIZE_WHITESPACE
    <div>
    <div id="1">
    <p>Ein Absatz</p>
    </div>
    </div>

    >>> txt4 = '''<div>
    ... <div id="1">
    ... <p>Ein Absatz</p>
    ... </div>
    ... <p></p>
    ... </div>'''
    >>> soup4 = BeautifulSoup(txt4, 'html.parser')
    >>> strip_empty_successor(soup4.p)
    False
    >>> print(soup4.div)  # doctest: +NORMALIZE_WHITESPACE
    <div>
    <div id="1">
    <p>Ein Absatz</p>
    </div>
    <p></p>
    </div>

    Etwaige Attribute schützen vor Löschung:

    >>> txt5 = '''<div>
    ... <h5>Der nichtleere Absatz</h5>
    ... <p id="5"> </p>
    ... </div>'''
    >>> soup5 = BeautifulSoup(txt5, 'html.parser')
    >>> strip_empty_successor(soup5.h5)
    False
    >>> print(soup5.div)  # doctest: +NORMALIZE_WHITESPACE
    <div>
    <h5>Der nichtleere Absatz</h5>
    <p id="5"> </p>
    </div>
    """
    changed = False
    sibs = list(elem.next_siblings)[:2]
    # print(elem, [sib.string for sib in sibs])
    first = True  # mutmaßlich obsolet
    dellist = []
    for sib in sibs:
        if sib.name is None:
            if not sib.string.strip():
                if first and is_block_element(elem):
                    dellist.append(sib)
            else:
                break
        elif sib.name in ('p', 'div'):
            # from pdb import set_trace; set_trace()
            if is_empty(sib) and not sib.attrs:
                dellist.append(sib)
                changed = True
            break
        else:
            break
    if changed:
        while dellist:
            dellist.pop().extract()
    return changed


def get_strippable_container(elem, include_start=True):
    r"""
    Diese Funktion braucht evtl. einen noch knackigeren Namen ...

    Gib den ersten Container zurück, der zur Löschung infrage kommende
    Nachfolger hat (siehe strip_empty_successor)

    >>> txt1 = '''<div>
    ... <p id="1"><a><img></a>
    ... </p>
    ... <p id="2"></p>
    ... </div>'''
    >>> soup1 = BeautifulSoup(txt1, 'html.parser')
    >>> soup1.img
    <img/>
    >>> print(get_strippable_container(soup1.img)) # doctest: +NORMALIZE_WHITESPACE
    <p id="1"><a><img/></a>
    </p>

    """
    o = None

    if include_start:
        i = 0
        for sib in elem.next_siblings:
            if sib.name is not None:
                return elem
            elif sib.string.strip():
                return elem
            if i > 1:
                return elem
            i += 1
    done = False
    for p in elem.parents:
        if done:
            break
        i = 0
        for sib in p.next_siblings:
            if (i > 1
                or sib.name is not None
                or sib.string.strip()
                ):
                o = p
                done = True
                break
            i += 1
    if o is not None:
        if o.name not in ('html', 'body'):
            return o
    return None


if __name__ == '__main__':
    # Standard library:
    import doctest
    doctest.testmod()

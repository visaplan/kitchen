# -*- coding: utf-8 -*- äöü vim: ts=8 sts=4 sw=4 si et tw=79 cc=+1
"""\
visaplan.kitchen.extract: Make extracts of HTML text

Our primary use for HTML extracts is to get the leading part
which gives an impression of the whole text (e.g. for search results or
carousel items);
after a well-known console script for a similar purpose,
we call this the "head" of the text.

The "head" program extracts the first N lines, which doesn't make much sense
for HTML text; we count characters instead and allow for some "fuzz" to avoid
cutting in the middle of a word.

Because of this main use of our extraction tool, we mostly keep the HTML
elements in the text, but with some exceptions:

- Some attributes don't make much sense in such an extract:
  - "href" is removed, for example, since the link target might be part of the
    cut-off tail of the document; for external links, the full document should
    be viewed.
  - "id" and "name" attributes are removed as well; we remove the href attributes
    which might point to them, and "id" attributes might harm the main document
    to contain the extract.
  - The only attributes we keep by default are "class" and "lang".
- Some elements don't make much sense, either:
  - We'll replace all <h1> ... <h6> elements by <p class="converted-h1"> etc.
    by default, to not destroy the structure of the document.
  - ...

Example usage::

  kw = {'chars': 300,
        'verbose': True}
  for longtext in usable_texts:
      extracted_text, remaining = head(longtext, **kw)
      ...
      (do what needs to be done about the extracted_text)
      ...
      if remaining['done']:
          break
      kw.update(remaining)

"""
# Python compatibility:
from __future__ import absolute_import, print_function

from six import string_types as six_string_types

# Standard library:
from sys import version_info

USE_PARSER_METHOD = version_info < (3, 4)
if USE_PARSER_METHOD:
    # Python compatibility:
    from six.moves.html_parser import HTMLParser as _P
    unescape_entities = _P().unescape
else:
    from html import unescape as unescape_entities

# Standard library:
from collections import defaultdict

# 3rd party:
from lxml.etree import HTMLParser, fromstring, tostring

# visaplan:
from visaplan.tools.dicts import subdict
try:
    # module .html renamed to .htmlohmy in v1.4+:
    from visaplan.tools.htmlohmy import BLOCK_ELEMENT_NAMES
except ImportError:
    from visaplan.tools.html import BLOCK_ELEMENT_NAMES
from visaplan.tools.minifuncs import gimme_None
from visaplan.tools.words import head as text_head

# ------------------------------------------------------- [ data ... [
__all__ = [
        'head',  # this is what you'll use
        # helper function factories:
        'make_tag_converter',  # create a function convert(elem) -> (name, attr)
        'make_attributes_extractor',  # a factory to create e.g.:
        ]

# possible keyword arguments for lxml.etree.HTMLParser
parser_defaults = {  # original defaults
    'recover':           True,   # try hard to parse through broken HTML
    'no_network':        True,   # prevent network access for related files
    'remove_blank_text': False,  # discard empty text nodes that are ignorable
    'remove_comments':   False,  # discard comments
    'remove_pis':        False,  # discard processing instructions
    'strip_cdata':       True,   # replace CDATA sections by normal text content
    'compact':           True,   # save memory for short text content
    'default_doctype':   True,   # add a default doctype if not found in the HTML
    'collect_ids':       True,   # use a hash table of XML IDs for fast access
    'huge_tree':         False,  # disable security restrictions (libxml2 2.7+)
    }
parser_keys = list(parser_defaults.keys())
# we change some defaults for our specific use case:
parser_defaults.update({
    'remove_blank_text': True,
    'remove_comments':   True,
    'remove_pis':        True,   # we don't search the tree for IDs here
    'collect_ids':       False,
    })
allowed_keys = set([
    'chars', 'words', 'fuzz',
    'ellipsis', 'strip',
    'parser',
    'verbose',
    ])
conversion_keys = set([
    'targettags',  # usually a defaultdict; e.g. {'h1': 'p', ...}
    'classmasks',  # dto.; e.g. {'h1': 'converted-%(tag)s', ...}
    'attr_blacklist',   # removed attribute names, e.g. ['href', 'id']
    'attr_whitelist',   # kept attribute names, e.g. ['class', 'lang']
    ])
multival_attributes = set([  # TODO: get exhaustive list
    'class',
    ])
headline_tags = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']
# ------------------------------------------------------- ] ... data ]


def head(s, **kwargs):
    r"""
    Return the HTML text head, containing the first NN visible characters.

    Like the wellknown console program `head`, return the leading part of the
    given HTML text.  Besides the given text, all further arguments must be
    given by name.

    After the string, given positionally as the first argument, we need at
    least one keyword-only option of:

      chars -- the number of characters (approximated)
      words -- the number of words (NOT YET SUPPORTED)

      (In contrast to the ``head`` and ``tail`` commandline tools, we don't
      extract lines here, since those normally depend on the rendering
      context.)

    Other options, for the details:

      fuzz -- with `chars` given, we need some tolerance; otherwise, we'd cut
              off the string in the middle of a word in most cases.
      ellipsis -- the part appended to the result, if something (non-space) is
              cut off at the end; '...' by default.
      verbose -- *(New in release 1.0.5)*
              Instead of returning the extracted
              text (and markup) only, we return a 2-tuple, with the 2nd item
              being a dict (see the usage example in the module's docstring)

    For demonstration purposes, we use a quite small number of characters:
    >>> kw = {"chars": 20}
    >>> txt = (u'<div>'
    ...        u'<h1>Max und Moritz</h1>'
    ...        u'<p>Ach! Was muß man oft von bösen<br/>'
    ...        u'Kindern hören oder lesen,<br/>'
    ...        u'wie zum Beispiel hier von diesen,<br/>'
    ...        u'welche Max und Moritz hießen.</p>'
    ...        u'</div>')
    >>> head(txt, **kw)                        # doctest: +NORMALIZE_WHITESPACE
    '<div><p class="converted-h1">Max und Moritz</p><p>Ach! ...</p></div>'
    >>> len(head(txt, **kw)) > kw['chars']
    True

    As you can see,
    - the resulting string is usually longer than the given chars limit might suggest
      (68 chars, in this case), as we try to regard word borders, and we only
      count visible text, disregarding the HTML markup in this respect
    - we try not to cut the result in the middle of a word (using a default
      fuzz value of 10 percent of the given `chars` length value)
    - we append an ellipsis character
    - we convert headlines to paragraphs
    - we terminate any active HTML element.

    Empty texts have empty heads:
    >>> head('', **kw)
    ''
    >>> head(' \t\v', **kw)
    ''
    >>> head('<!-- comment only -->', **kw)
    ''

    If given non-HTML ("plain") text, we wrap the returned value in a
    paragraph:
    >>> head('just simple plain text', **kw)
    '<p>just simple plain ...</p>'

    Comments and obsolete whitespace are weeded out by the parser
    (unless you specify your own which behaves differently):
    >>> txt = u'''<div> <!-- ein Kommentar. -->
    ...       <h1>\v
    ...       Max \t und  Moritz  </h1>
    ...       <p>Ach! Was muß man oft von bösen<br/>
    ...       Kindern hören oder lesen,<br/>
    ...       wie zum Beispiel hier von diesen,<br/>
    ...       welche Max und Moritz hießen.
    ...       </p>
    ...       </div>
    ...       '''
    >>> kw['chars'] = 25
    >>> head(txt, **kw)                        # doctest: +NORMALIZE_WHITESPACE
    '<div><p class="converted-h1">Max und Moritz</p><p>Ach! Was ...</p></div>'
    >>> len('Max und Moritz'
    ...     'Ach! Was ')
    23

    For short texts, there is no need to inject the ellipsis:
    >>> stub = '<a href="#">just this <strong>fancy</strong> link</a>'
    >>> stub = '<span>just this <strong>fancy</strong> text</span>'
    >>> head(stub, **kw)                        # doctest: +NORMALIZE_WHITESPACE
    '<span>just this <strong>fancy</strong> text</span>'

    By default, we preserve only a little subset of HTML attributes:
    >>> txt2 = '''<div><h1 class="main">
    ... Kid's life
    ... </h1>
    ... <p>My little brat loves to go to her
    ... <span lang="de">Kindergarten</span>,
    ... and she is very proud of her bicycle.
    ... </p>
    ... </div>
    ... '''
    >>> kw['chars'] = 50
    >>> head(txt2, **kw)                       # doctest: +NORMALIZE_WHITESPACE
    '<div><p class="converted-h1 main">Kid\'s life</p><p>My little brat loves
    to go to her\n<span lang="de">Kindergarte...</span></p></div>'
    >>> len("Kid's life"
    ...     'My little brat loves to go to her '
    ...     'Kindergarte...')
    58

    Ooops, what has happened?
    We were a little bit unlucky, since the characters limit was reached in the
    middle of a long word, and the fuzz value was not sufficient to find a word
    border; thus, the cumulated text length equals chars + fuzz +
    len(ellipsis).

    Let's increase the fuzz:
    >>> kw['fuzz'] = 6
    >>> head(txt2, **kw)                       # doctest: +NORMALIZE_WHITESPACE
    '<div><p class="converted-h1 main">Kid\'s life</p><p>My little brat loves
    to go to her\n...</p></div>'

    Parser characteristics:

    By default, only leading whitespace is stripped:
    >>> framedroot = '  <p>  single  root  </p>  '
    >>> tostring(fromstring(framedroot, parser=HTMLParser()))
    '<html><body><p>  single  root  </p>  </body></html>'

    Let's use a little test helper now which uses our preferred parsing
    options:
    >>> def p(s):
    ...  return tostring(fromstring(s,
    ...                  parser=HTMLParser(**parser_defaults)))
    >>> p(framedroot)
    '<html><body><p>  single  root  </p></body></html>'

    That's better.
    Now, what the head function gives you:
    >>> head(framedroot, **kw)
    '<p>single root</p>'

    >>> with_comment = '<p>  some <!-- interrupted -->  text </p>'
    >>> p(with_comment)
    '<html><body><p>  some   text </p></body></html>'
    >>> head(with_comment, **kw)
    '<p>some text</p>'

    There must be a single root element:
    >>> twops = '<p>one  </p><p> two</p>'
    >>> tostring(fromstring(twops), parser=HTMLParser())
    Traceback (most recent call last):
      ...
    XMLSyntaxError: Extra content at the end of the document, line 1, column 13 (line 1)

    With our preferred parsing options, it works:
    >>> p(twops)
    '<html><body><p>one  </p><p> two</p></body></html>'
    >>> head(twops, **kw)
    '<p>one</p><p>two</p>'

    What about character entities?
    >>> p('<p>Außen </p>')
    '<html><body><p>Au&#195;&#159;en </p></body></html>'
    >>> len('&#195;&#159;')
    12

    Ugh. Instead of a single "ß", we'd get (and count!) 12 characters.
    Worse still, we might cut in the middle of them:
    >>> text_head('&#195;&#159;', chars=10, fuzz=1)
    '&#195;&#159...'

    >>> p('<p>Düsen bürsten außen und innen')
    '<html><body><p>D&#195;&#188;sen b&#195;&#188;rsten au&#195;&#159;en und innen</p></body></html>'
    >>> kw['chars'] = 10

    This one doesn't work yet as expected (!):
    >>> head('<p>Außen und innen</p>', **kw)  # doctest: +SKIP
    '<p>Au&#195;&#159; und ...</p>'

    Now, sometimes we have multiple sources of text to use;
    if the first one is too short (e.g. a description), we might want to
    consider the next (e.g. the full text).  For this purpose, we can use the
    "verbose" option, which will inject the "remaining" dict into the result:

    >>> kw['verbose'] = 1
    >>> head('<p>Innen und außen</p>', **kw)
    ('<p>Innen ...</p>', {'chars': 1, 'done': True})

    Hu! One char remaining, but done is True?
    That's why:

    >>> kw['fuzz']
    6

    We could have used one more character to match the expected character
    length, but this is within the specified fuzzyness of 6, so all is fine.
    """
    kw = dict(kwargs)
    _head_kwargs(kw)
    if not s:
        if kw['verbose']:
            return ('', kw['remaining'])
        return ''
    parser = kw.get('parser')
    kw['makeelement'] = makeelement = parser.makeelement
    if 'convert_tag' not in kw:
        kw['convert_tag'] = make_tag_converter(
                **subdict(kw,
                          conversion_keys,
                          do_pop=1,
                          defaults_factory=gimme_None))
    elif not kw['convert_tag']:
        kw['convert_tag'] = convert_fallthrough

    tree = fromstring(s, parser)
    if tree is None:
        s = s.strip()
        if not s or s.startswith('<!--'):
            return ''
        raise ValueError("Couldn't build a tree from %r!" % (
            s[:30] + (kw['ellipsis'] if s[30:]
                      else ''),
            ))
    body = tree.find('body')
    children = body.getchildren()
    if not children:
        return ''
    dest = makeelement('body')
    dest_stack = [dest]
    # dest_stack = [dest.find('body')]
    for child in children:
        if _head(child, dest_stack, kw):
            break
    res = tostring(dest)
    if kw['verbose']:
        return (res[6:-7], kw['remaining'])
    return res[6:-7]


def _head(child, dest_stack, kwargs):
    """
    Internally used (and recursively called) helper for the `head` function.

    Returns None or True
    """
    convert_tag = kwargs['convert_tag']
    makeelement = kwargs['makeelement']

    # a node may have own text, children, and a (textual) tail.
    # We have a node, so we add it to the current tip:
    tagname, attr = convert_tag(child)
    tip = makeelement(tagname, attr)

    dest_stack[-1].append(tip)
    dest_stack.append(tip)

    done, newtext = _done_after_adding(_relevant_text(child), kwargs)
    if newtext:
        tip.text = newtext
    if done:
        return done

    for grandchild in child.getchildren():
        if _head(grandchild, dest_stack, kwargs):
            return True
    dest_stack.pop()

    done, newtext = _done_after_adding(_relevant_tail(child), kwargs)
    if newtext:
        tip.tail = newtext
    if done:
        return done


def _relevant_text(elem, tagname=None):
    """
    Return the relevant text of the element.

    *Note*: the tests for this little helper function are to be understood as
    *illustrative* rather than *normative*!  It may change in all aspects
    without further notice if required by the public interface function.

    It seems the lxml parser doesn't remove whitespace around block element
    tags ...

    >>> from lxml.builder import E
    >>> elem = E.div(' ', E.p('some text'))
    >>> tostring(elem)
    '<div> <p>some text</p></div>'
    >>> elem.text
    ' '

    The <div> element is a block element, so the whitespace in that case is not
    interesting; since we count the text characters, we need to remove it:

    >>> _relevant_text(elem)
    ''

    We have a child (at least one), and the first child is a block element as
    well:

    >>> elem = E.div(' Some prefix ', E.p('some text'))
    >>> tostring(elem)
    '<div> Some prefix <p>some text</p></div>'
    >>> elem.text
    ' Some prefix '
    >>> _relevant_text(elem)
    'Some prefix'

    What if our first child is an inline element?
    >>> elem = E.p(' Some text containing ', E.a('an anchor'))
    >>> tostring(elem)
    '<p> Some text containing <a>an anchor</a></p>'
    >>> elem.text
    ' Some text containing '
    >>> _relevant_text(elem)
    'Some text containing '

    Or if elem is an inline element itself?
    >>> elem = E.a(' Link text containing ', E.em('something important'))
    >>> tostring(elem)
    '<a> Link text containing <em>something important</em></a>'
    >>> elem.text
    ' Link text containing '
    >>> _relevant_text(elem)
    ' Link text containing '

    """
    txt = elem.text
    if not txt:
        return txt
    if tagname is None:
        tagname = elem.tag
    children = elem.getchildren()
    if tagname in BLOCK_ELEMENT_NAMES:
        stripleft = True
        stripright = not children or children[0].tag in BLOCK_ELEMENT_NAMES
    else:
        # in inline elements, we don't strip anything:
        return txt
    assert stripleft
    if stripright:
        return txt.strip()
    return txt.lstrip()


def _relevant_tail(elem, tagname=None):
    """
    Return the relevant tail of the element.
    Like for _relevant_text, this depends on the nature of the element (block
    or inline); but we are not interested in the children.

    First let's have a look at block elements:
    >>> from lxml.builder import E
    >>> p = E.p('some text')
    >>> p.tail = '  the tail '
    >>> tostring(p)
    '<p>some text</p>  the tail '
    >>> _relevant_tail(p)
    'the tail '

    The tails of inline elements are never stripped:
    >>> a = E.a('link text', href='#linked-url')
    >>> a.tail = '  some text behind '
    >>> tostring(a)
    '<a href="#linked-url">link text</a>  some text behind '
    >>> _relevant_tail(a)
    '  some text behind '
    """
    txt = elem.tail
    if not txt:
        return txt
    if tagname is None:
        tagname = elem.tag
    if tagname in BLOCK_ELEMENT_NAMES:
        return txt.lstrip()
    return txt


def _head_kwargs(kw):
    """
    Inspect the keyword arguments for the `head` function.

    Modifies the given dict in-place.

    For our doctest, we'll use a little test helper:
    >>> def _hkw(**dic):
    ...     _head_kwargs(dic)
    ...     return sorted(dic.items())
    >>> _hkw(chars=50)              # doctest: +NORMALIZE_WHITESPACE +ELLIPSIS
    [('chars', 50),
     ('done', False),
     ('ellipsis', '...'), ('fuzz', 5),
     ('parser', <lxml.etree.HTMLParser object at 0x...>),
     ('remaining', {'chars': 50}),
     ('verbose', False),
     ('words', None)]
    >>> _hkw(chars=50, fuzz=2)      # doctest: +NORMALIZE_WHITESPACE +ELLIPSIS
    [('chars', 50),
     ('done', False),
     ('ellipsis', '...'), ('fuzz', 2),
     ('parser', <lxml.etree.HTMLParser object at 0x...>),
     ('remaining', {'chars': 50}),
     ('verbose', False),
     ('words', None)]
    >>> _hkw(chars=50, fuzz=0)      # doctest: +NORMALIZE_WHITESPACE +ELLIPSIS
    [('chars', 50),
     ('done', False),
     ('ellipsis', '...'), ('fuzz', 0),
     ('parser', <lxml.etree.HTMLParser object at 0x...>),
     ('remaining', {'chars': 50}),
     ('verbose', False),
     ('words', None)]
    >>> _hkw(words=10)              # doctest: +NORMALIZE_WHITESPACE +ELLIPSIS
    [('chars', None),
     ('done', False),
     ('ellipsis', '...'), ('fuzz', None),
     ('parser', <lxml.etree.HTMLParser object at 0x...>),
     ('remaining', {'words': 10}),
     ('verbose', False),
     ('words', 10)]

    Further allowed keyword arguments:

    - parser - should be an lxml.etree._BaseParser instance.
               We use an HTMLParser(**parser_defaults) by default.
    - all allowed HTML-specific HTMLParser keyword arguments;
      see the parser_defaults dictionary for our preferences.

    If unsupported arguments are given, we raise a TypeError:

    >>> _hkw(unknown_opt=42, chars=300)
    Traceback (most recent call last):
      ...
    TypeError: Unknown keyword argument(s): unknown_opt

    ... unless strict=False is given:
    >>> _hkw(unknown_opt=42, chars=300, strict=False, parser='DUMMYVALUE')
    ...                                       # doctest: +NORMALIZE_WHITESPACE
    [('chars', 300),
     ('done', False),
     ('ellipsis', '...'), ('fuzz', 30),
     ('parser', 'DUMMYVALUE'),
     ('remaining', {'chars': 300}),
     ('unknown_opt', 42),
     ('verbose', False),
     ('words', None)]

    For further processing we might want to know about about what we have
    consumed already, and whether we should consider more input; that's what we
    use the verbose results option for:
    >>> _hkw(chars=300, parser='DUMMYVALUE',  # doctest: +NORMALIZE_WHITESPACE
    ...      verbose=1)
    [('chars', 300),
     ('done', False),
     ('ellipsis', '...'), ('fuzz', 30),
     ('parser', 'DUMMYVALUE'),
     ('remaining', {'chars': 300}),
     ('verbose', 1),
     ('words', None)]

    """
    for key in ('chars', 'words', 'fuzz'):
        num = kw.setdefault(key, None)
        if num is not None:
            if not isinstance(num, int):
                raise ValueError('%(key)s=%(num)r: integer number expected!'
                                 % locals())
            elif key == 'fuzz':
                if num < 0:
                    raise ValueError('%(key)s=%(num)d: must be >= 0!'
                                     % locals())
            elif num <= 0:
                raise ValueError('%(key)s=%(num)d: must be > 0!'
                                 % locals())
    chars = kw['chars']
    words = kw['words']
    if chars is None and words is None:
        raise TypeError("Neither 'chars' nor 'words' option given!")

    fuzz = kw['fuzz']
    if fuzz is None and chars is not None:
        kw['fuzz'] = fuzz = int(chars * 0.1)

    parser = kw.get('parser')
    if parser is None:
        kw['parser'] = HTMLParser(**subdict(kw, parser_keys, parser_defaults))

    ellipsis = kw.get('ellipsis')
    if ellipsis is None:
        kw['ellipsis'] = '...'
    elif not isinstance(ellipsis, six_string_types):
        raise ValueError('ellipsis=%(ellipsis)r: string expected!' % locals())

    strict = kw.pop('strict', True)
    if strict:
        # the 'required' option is not "allowed" but injected; see below:
        invalid = set(kw.keys()) - allowed_keys
        if invalid:
            raise TypeError('Unknown keyword argument(s): %s'
                            % (', '.join(tuple(sorted(invalid))),
                               ))

    kw.setdefault('verbose', False)
    if 1:  # we'll use this dict during processing:
        kw['remaining'] = remaining = {}
        if chars is not None:
            remaining['chars'] = chars
        if words is not None:
            remaining['words'] = words

    if kw.setdefault('done', False):
        raise ValueError("'done' is expected to be False;"
                         " see the usage example!")


def _done_after_adding(txt, dic):
    """
    Call the text_head function and return a 2-tuple (done, text)

    (Internally used helper for the `_head` function)
    """
    if not txt:
        return (None, None)
    assert 'remaining' in dic
    # As of visaplan.tools v1.3.12, the [text_]head function supports
    # the return_tuple option for chars constraints *only*,
    # and not combinations of chars and words, either: 
    rem = dic['remaining']
    remaining = rem['chars']
    fuzz = dic['fuzz']
    ellipsis = dic['ellipsis']
    if '&' in txt:
        txt = unescape_entities(txt)
    newtext, added = \
            text_head(txt,
                      strip=False,
                      chars=remaining,
                      fuzz=fuzz,
                      ellipsis=ellipsis,
                      detect_entities=1,
                      return_tuple=1)
    remaining -= added
    if remaining < fuzz:
        rem.update({
            'chars': remaining,
            'done':  True,
            })
        if 0:\
        assert newtext.endswith(ellipsis), ('remaining=%(remaining)r, '
            'fuzz=%(fuzz)r; newtext doesn\'t end with %(ellipsis)r:\n'
            '%(newtext)r'
            % locals())
        return True, newtext
    elif remaining > fuzz:
        rem.update({
            'chars': remaining,
            })
        rem['chars'] = remaining
        return False, newtext
    elif newtext.endswith(ellipsis):
        rem.update({
            'chars': remaining,
            'done':  True,
            })
        return True, newtext
    else:
        rem.update({
            'chars': remaining,
            'done':  True,
            })
        newtext += ellipsis
        return True, newtext


def make_tag_converter(targettags=None, classmasks=None, **kwargs):
    """
    Create function to convert tags to .tag(...) input

    Options:

    targettags -- a (default)dict {'originaltag': 'othertag'}
    classmasks -- a (default)dict {'tag': 'classmask-%(tag)s'}
    attr_whitelist -- a list of HTML attributes to keep (throw away all others)
    attr_blacklist -- a list of HTML attributes to remove (keep all others)

    The attr_whitelist and attr_blacklist options are mutually exclusive;
    see as well the make_attributes_extractor doctests.
    For this function we'll use the default of attr_whitelist=['class'].

    When extracting description texts, we usually don't want headline elements
    in the result, because those would disturb our page structure.

    >>> from lxml.builder import E
    >>> convert_tag = make_tag_converter()
    >>> h1 = E.h1('a headline')
    >>> convert_tag(h1)
    ('p', {'class': 'converted-h1'})

    We applied a transformation here, to convert an h1 element (which we don't
    want to see in our extractions) to a paragraph.
    The original element would be produced by the basic convert_fallthrough
    function:
    >>> convert_fallthrough(h1)
    ('h1', {})

    We convert anchor elements as well, but we don't inject a class:
    >>> convert_tag(E.a('a link'))
    ('span', {})

    According to our default whitelist, existing class attributes are retained:
    >>> span = E.span('nothing interesting', {'class': 'bonk'})
    >>> tostring(span)
    '<span class="bonk">nothing interesting</span>'
    >>> convert_tag(span)
    ('span', {'class': 'bonk'})

    What if an element is converted, adding a class, which has a class
    attribute already?

    In such cases we add the class, retaining the others;
    the new class attribute value is sorted:

    >>> h1.attrib['class'] = 'another-class two three four'
    >>> convert_tag(h1)
    ('p', {'class': 'another-class converted-h1 four three two'})
    """
    extract_attributes = make_attributes_extractor(**kwargs)

    if targettags is None:
        targettags = defaultdict(gimme_None)
        targettags.update({
                tag: 'p' for tag in headline_tags
                })
        targettags.update({
            'a': 'span',
            })
    if classmasks is None:
        classmasks = defaultdict(gimme_None)
        classmasks.update({
                tag: 'converted-%(tag)s' for tag in headline_tags
                })
    def convert_tag(elem):
        """
        Return a 2-tuple (tagname, attribute-changes) (string, dict)
        """
        tag = elem.tag
        dic = extract_attributes(elem)
        mask = classmasks[tag]
        if mask:
            curval = set((dic.get('class') or '').split())
            curval.add(mask % locals())
            dic['class'] = ' '.join(sorted(curval))
        newtag = targettags[tag]
        if newtag:
            tag = newtag
        return tag, dic

    return convert_tag


def convert_fallthrough(elem):
    """
    Simply return a 2-tuple (tagname, attributes)

    This is the "converter" used for head(..., convert_tag=0)
    """
    return (elem.tag, elem.attrib)


def make_attributes_extractor(**kwargs):
    """
    Return a simple function to extract the allowed attributes from a given tag

    Either a whitelist or a blacklist of attribute names is expected.

    >>> makeelement = HTMLParser().makeelement
    >>> elem = makeelement('a', {
    ...            'href': '#', 'class': 'one two',
    ...            'name': 'my-name', 'id': 'my-id',
    ...            'data-type': 'cheesecake'})
    >>> tostring(elem)
    '<a class="one two" data-type="cheesecake" href="#" id="my-id" name="my-name"/>'

    With neither white- nor blacklist given, we use a default attr_whitelist which
    only keeps the 'class' attribute:
    >>> func1 = make_attributes_extractor()
    >>> sorted(func1(elem).items())
    [('class', 'one two')]

    We can specify a attr_blacklist instead; here we only remove the 'href'
    attribute:
    >>> func2 = make_attributes_extractor(attr_blacklist=['href'])
    >>> sorted(func2(elem).items())            # doctest: +NORMALIZE_WHITESPACE
    [('class', 'one two'),
     ('data-type', 'cheesecake'),
     ('id', 'my-id'),
     ('name', 'my-name')]
    """
    pop = kwargs.pop
    whitelist = pop('attr_whitelist', None)
    blacklist = pop('attr_blacklist', None)
    if whitelist and blacklist:
        raise TypeError('Both attr_whitelist and attr_blacklist given!')
    if kwargs:
        raise TypeError('Invalid named option(s): %s' %
                        ', '.join(sorted(set(kwargs))))

    use_whitelist = False
    if whitelist is None and blacklist is None:
        whitelist = [
                'class',
                'lang',
                ]
    use_whitelist = bool(whitelist)
    if not use_whitelist and blacklist is None:
        blacklist = ['href',
                     'id', 'name',
                     'onclick',
                     'title',
                     ]

    def include_attributes(tag):
        """
        A helper function for head: Extract the attributes to be kept.

        """
        res = {}
        attrs = tag.attrib
        for key, val in attrs.items():
            if key in whitelist:
                res[key] = val
        return res

    def exclude_attributes(tag):
        res = {}
        attrs = tag.attrib
        for key, val in attrs.items():
            if key not in blacklist:
                res[key] = val
        return res

    if use_whitelist:
        return include_attributes
    else:
        return exclude_attributes


if __name__ == '__main__':
    # Standard library:
    import doctest
    doctest.testmod()

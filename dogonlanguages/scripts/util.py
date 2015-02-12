# coding=utf8
from __future__ import unicode_literals
import re
from hashlib import md5
from io import open
import shutil
from collections import defaultdict
from subprocess import check_output
from urllib import urlretrieve

import requests
from fuzzywuzzy import fuzz
from purl import URL

from clld.lib.imeji import file_urls
from clld.lib.bibtex import Record, Database, unescape


def get_contributors(rec, data):
    for author in re.split('\s+and\s+', unescape(rec['author'])):
        for cid, obj in data['Contributor'].items():
            if fuzz.token_sort_ratio(author, obj.name) >= 92:
                yield cid


class UrlResolver(object):
    def __init__(self, args):
        self.args = args
        self.checksums = {}
        if not args.data_file('docs').exists():
            self.edmond_urls = {}
        else:
            for fname in args.data_file('docs').files():
                self.checksums[fname.basename()] = check_output(
                    'md5sum "%s"' % fname, shell=True).split()[0]
            for fname in args.data_file('docs', 'not_on_edmond').files():
                self.checksums[fname.basename()] = check_output(
                    'md5sum "%s"' % fname, shell=True).split()[0]
            self.edmond_urls = {d['md5']: d for d in file_urls(args.data_file('Edmond.xml'))}

    def __call__(self, url_):
        url = URL(url_)
        if url.host() == 'dogonlanguages.org':
            basename = url.path_segment(-1)
            if basename in self.checksums:
                checksum = self.checksums[basename]
                if checksum in self.edmond_urls:
                    return self.edmond_urls[checksum]
        return url_


def update_species_data(species, d):
    eol = d.get('eol')
    if eol:
        for an in eol.get('ancestors', []):
            if not an.get('taxonRank'):
                continue
            for tr in ['family']:
                if tr == an['taxonRank']:
                    curr = getattr(species, tr)
                    #if curr != an['scientificName']:
                    #print(tr, ':', curr, '-->', an['scientificName'])
                        #setattr(species, tr, an['scientificName'])

        species.update_jsondata(eol_id=eol['identifier'])


def split_words(s):
    """
    split string at , or ; if this is not within brackets.
    """
    s = re.sub('\s+', ' ', s)
    chunk = ''
    in_bracket = False

    for c in s:
        if c in ['(', '[']:
            in_bracket = True
        if c in [')', ']']:
            in_bracket = False
        if c in [',', ';'] and not in_bracket:
            yield chunk
            chunk = ''
        else:
            chunk += c
    if chunk:
        yield chunk


def parse_form(form):
    attrs = {}
    parts = form.split('(', 1)
    if len(parts) == 2:
        attrs['name'] = parts[0].strip()
        if not parts[1].endswith(')'):
            if parts[1].endswith('"'):
                parts[1] += ')'
            else:
                print '---->', parts[1]
                return {'name': form}
        comment = parts[1][:-1].strip()
        if comment.startswith('"') and comment.endswith('"'):
            attrs['description'] = comment[1:-1].strip()
        else:
            attrs['comment'] = comment
    else:
        attrs['name'] = form
    return attrs


def get_thumbnail(args, filename):
    path = args.data_file('repos', 'thumbnails', filename)
    if not path.exists():
        print path
        return
        r = requests.get('http://dogonlanguages.org/thumbnails/' + filename, stream=True)
        if r.status_code == 200:
            with open(path, 'wb') as f:
                r.raw.decode_content = True
                shutil.copyfileobj(r.raw, f)
        else:
            return
    with open(path, 'rb') as f:
        return f.read()


KV_PATTERN = re.compile('(?P<key>[A-Za-z]+)\s*\=\s*\{(?P<value>.*)$', re.MULTILINE)


def fixed(mess):
    id_ = md5('@'.encode('utf8') + mess.encode('utf8'))
    for messyid in ['BibTeX', 'Indiana University']:
        mess = mess.replace(messyid + ',\n', '')
    genre, rem = mess.split('{', 1)
    assert rem.endswith('}')
    rem = rem[:-1].strip()
    kw = {}
    for kv in re.split('},\n', rem):
        kv = kv.strip()
        if kv.endswith('}'):
            kv = kv[:-1]
        m = KV_PATTERN.match(kv)
        if not m:
            #print kv
            continue
        if m.group('value').strip():
            kw[m.group('key').lower()] = m.group('value').strip()
    if kw:
        return Record(genre, id_.hexdigest().decode('ascii'), **kw)


def get_bib(args):
    db = Database.from_file(args.data_file('repos', 'Dogon.bib'), lowercase=True)
    keys = defaultdict(int)
    for rec in db:
        keys[rec.id] += 1
        rec.id = '%sx%s' % (rec.id, keys[rec.id])
        yield rec


CONTRIBUTORS = {
    "Brian Cansler": ("""studies linguistics and African languages at the University of North Carolina at Chapel Hill, focusing on language acquisition and psycholinguistics. His fieldwork in Mali has been on the Dogul Dom language spoken not far from Bandiagara. Past research projects have included emphatic auxiliary verbs in Senegalese Wolof and bidirectional nasal harmony in Toro Tegu (Dogon). Along with Samantha Farquharson, he has worked in the language acquisition lab of Prof. Misha Becker at UNC. He recently spent a month as a visiting scholar at the Max Planck Institute for Psycholinguistics in Nijmegen, Netherlands in May-June 2012. There he worked with Dr. Asifa Majid on a cross-cultural sensory classification project that is already using Brian's Dogulu data, and this collaboration is planned to continue. His fieldwork stint in 2011 working on Dogul Dom went well, and is being followed up by another short trip in summer 2012.""",
        "bcansler (at) brianlcansler (at) gmail.com",
        "http://unc.edu/~bcansler/"),

    "Minkailou Djiguiba": ("""is a native speaker of Jamsay (Dogon), and also speaks French, Fulfulde, and Bambara. After graduating from secretariat school at IFN in Sevare, he joined the project initially as Jamsay informant and assistant for Heath. He has stayed on as a full-time employee to manage our bases and to organize our travels and our visits to Dogon villages. He has filmed some of our feature videos and has done much work in the geography and flora-fauna components of the project. He drives the project vehicle (which he owns).""",
        "minkailoudjiguiba (at) yahoo.fr",
        None),

    "Vadim Dyachkov": ("""is a student of the Moscow State University and studies linguistics focusing on morphology, syntax and their interactions. He joined the project in 2011. He made two short trips to Mali (from June to October 2011 and from February to March 2012) working on the Tomo-Kan language. Initially he began his work with the Djanga-Sagou dialect of Tomo-Kan, but then concentrated on the dialect spoken in Segue collecting texts (esp. fairy tales) and making a corpus. He is now working on a grammar of Tomo-Kan and plans to continue his fieldwork in winter 2012-13.""",
        "hyppocentaurus (at) mail.ru",
        None),

    "Stefan Elders": ("""a Dutch post-doc trained at University of Leiden (Netherlands) and active as a research associate at the University of Bayreuth (Germany), joined the project in September 2006 to work on Bangime in the village of Bounou. His tragic death in Mali due to a sudden illness in February 2007 was a devastating blow to West African linguistics. In his short career he did extensive fieldwork in Cameroon and Burkina Faso, made important contributions to Gur and West Atlantic linguistics, and was in the process of becoming one of the major overall authorities on West African linguistics. This website presents the materials we were able to salvage from his work on Bangime: a handout he prepared for a workshop on Dogon languages in Bamako December 2006, and scans from his notebooks (courtesy of the Elders family). The original notebooks are archived at the University of Leiden library. We are also in possession of two partially recorded cassettes, some flora specimens, and a number of ethnographic photographs that we will process and disseminate. Click on the Bangime tab for more on Elders' work on this language.""",
        None, None),

    "Samantha Farquharson": ("""is an undergraduate studying linguistics, Japanese, and psychology at the University of North Carolina at Chapel Hill. Along with Brian Cansler, she has worked in the language acquisition lab of Prof. Misha Becker at UNC.""",
        "samfarquharson (at) gmail.com",
        None),

    "Abbie Hantgan": ("""a graduate student in Linguistics at Indiana University, specializes in phonology. She was recruited following Elders' death to carry on the study of Bangime. She had previously been a Peace Corps volunteer in Mali for several years, based initially in the village of Koira Beiri (Kindige language area) and then in Mopti-Sevare. She is fluent in Fulfulde, which is invaluable as a lingua franca in the Bangime villages, and has recently learned to speak Bambara/Jula. Abbie did initial fieldwork on Bangime in Bounou June-August 2008, and has returned to the field annually since. She is finishing a reference grammar of Bangime and is continuing her work on Dogon (Kindige, Ibi So).""",
        "ahantgan (at) umail.iu.edu",
        "http://mypage.iu.edu/~ahantgan/"),
    #(includes a grammar and lexicon of Tiefo, a severely endangered Gur language of SW Burkina Faso)
    #Abbie's article in the Returned Peace Corps Volunteer Newsletter [pdf]

    "Jeffrey Heath": ("""Prof. of Linguistics, University of Michigan (Ann Arbor) is a veteran of more than 14 years of on-location fieldwork. He began with Australian Aboriginal languages of eastern Arnhem Land (1970's), then did various topical projects on Jewish and Muslim dialects of Maghrebi Arabic (1980's). Since 1989 he has made annual trips to Mali where he has worked in succession on Hassaniya Arabic, riverine Songhay languages (Koyra Chiini, Koyraboro Senni), montane Songhay languages (Tondi Songway Kiini, Humburi Senni), and Tamashek (Berber family). Since 2005 he has focused on Dogon languages: Jamsay, Ben Tey, Bankan Tey, Bunoge, Najamba, Nanga, Penange, Tebul Ure, Tiranige, and Yanda Dom. During his 2011-12 fieldwork stint he has also been shooting and producing low-budget videos of cultural events and everyday practical activities, some of which can be viewed on the project website. He has also been mapping Dogon villages in collaboration with the LLMAP project at Eastern Michigan University, and has continued to work on local flora-fauna and native terms thereof. He is the author of A Grammar of Jamsay (Mouton, 2008), but his more recent Dogon grammars are currently disseminated on the project website.""",
        "schweinehaxen (at) hotmail.com",
        "http://www-personal.umich.edu/~jheath/"),

    "Laura McPherson": ("""is a fourth-year PhD student in Linguistics at UCLA, where she is supported with a National Science Foundation Graduate Research Fellowship. Her main theoretical interests lie in phonology, tonology, and the phonology-syntax interface. She earned her BA in Linguistics from Scripps College in 2008, working with Africanist Mary Paster on the verbal morphology of Luganda. She proceeded to spend eleven months in Mali, first with the support of our project (summer 2008) and then with a Fulbright fellowship, during which time she made significant progress on the grammar and lexicon of the Tommo So language. She returned for a brief stint in May-June of 2010, then for another stint in January-February of 2012, with the latter trip focused largely on text collection. Laura's grammar of Tommo So grammar will appear soon in the Mouton Grammar Library.""",
        "laura.emcpherson (at) gmail.com",
        "http://www.linguistics.ucla.edu/people/grads/McPherson/Laura_McPhersons_Homepage/Welcome.html"),

    "Steven Moran": ("""a veteran of the Eastern Michigan University Linguist List and E-MELD team. He has completed a Ph.D. in Computational Linguistics at the University of Washington, dissertation title "Phonetics information base and lexicon." He currently has a four-year postdoc researcher position at the University of Munich (Germany), working on the project "Quantitative language comparison" funded by the European Research Council. He is the creator and manager of this website. He undertook initial fieldwork on Toro-So from April to June 2009, from April to June 2013, and plans another trip in 2014. Recent conference presentations were at EuroScipy (Brussels 2012, given "best paper" award), Digital Humanities (Hamburg 2012), International Conference on Historical Linguistics ICHL (Osaka 2011), workshop at Reflex project (Lyons, 2012), Language Resources and Evaluation LREC (Istanbul 2012). He previously did fieldwork in Ghana and published a grammatical sketch of Western Sisaala.""",
        "stiv (at) uw.edu",
        "http://www.spw.uzh.ch/moran.html"),

    "Kirill Prokhorov": ("""is a Russian M.A. graduate and Ph.D. candidate who has been trained by West African specialists and field-oriented typologists in Moscow and St. Petersburg. Since 2008 he has focused on the Mombo (also known as Kolu-So) language with a base in the picturesque village of Songho just west of Bandiagara. In January 2009 he was a visiting scholar for one month at the Max Planck Institute for Evolutionary Anthropology (MPI-EVA) in Leipzig, which also provided him with a stipend to support his 2008 fieldwork. He has made return trips to Dogon country in 2009, 2010 and 2011. He has also studied Ampari, and did short pilot-studies of Bunoge and Penange. Since 2010 he has been based at Humboldt University (Berlin) where he is working on the project "Predicate-centered focus types: A sample-based typological study in African languages", part of the larger project SFB 632 "Information Structure" funded by German Science Association (DFG).""",
        "bolshoypro (at) gmail.com",
        "http://www2.hu-berlin.de/predicate_focus_africa/en/project2.php"),

    "Vu Truong": ("""graduated from Brandeis University with a B.A. in linguistics in 2011. In 2010, he designed and implemented a sociolinguistic survey in Sokone, Senegal on attitudes towards language shift to Wolof. In 2011, he taught English in Kagoshima, Japan as part of the JET Program. He joined the project in August 2012, and after two months of studying Jula for use as a contact language, he is currently conducting fieldwork on Jalkunan (Mande, 500 speakers).""",
        "valiant (at) brandeis.edu",
        None),
    }


class Entry(object):
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


def ff_to_standard(d):
    kw = {}
    for k, v in FIELD_MAP.items():
        if v:
            kw[v] = d.get(k)
    return Entry(**kw)


FIELD_MAP = {
    "code (Eng)": "code_eng",
    "subcode (Eng)": "subcode_eng",
    "code (fr)": "code_fr",
    "sous-code (fr)": "sous_code_fr",
    "code #": "code",
    "subcode #": "subcode",
    "order": "subsubcode",
    "short": "short",
    "court": "court",
    "ref#": "ref",
    "jpg": "jpg",
    "video": "video",
    "date": "date",
    "comment": "comment",
    "English": "English",
    "français": "Francais",
    "core": "core",

    "Toro Tegu (Toupere, JH)": "Toro_Tegu",
    "Ben Tey (Beni, JH)": "Ben_Tey",
    "Bankan-Tey (Walo, JH)": "Bankan_Tey",
    "Nanga (Anda, JH)": "Nanga",
    "Jamsay (alphabet)": "Jamsay_Alphabet",
    "Jamsay (Douentza area, JH)": "Jamsay",
    "Perge Tegu (Pergué, JH)": "Perge_Tegu",
    "Gourou (Kiri, JH)": "Gourou",
    "Jamsay (Mondoro, JH)": "Jamsay_Mondoro",
    "Togo-Kan (Koporo-pen, JH with BT)": "Togo_Kan",
    "Yorno-So (Yendouma, JH and DT)": "Yorno_So",
    "Ibi-So (JH)": "",
    "Donno-So": "",
    "Tomo Kan (Segue)": "Tomo_Kan",
    "Tomo Kan (Diangassagou)": "Tomo_Kan_Diangassagou",
    "Tommo So (Tongo Tongo, combined)": "Tommo_So",
    "Tommo So (Tongo Tongo, JH)": "",

    "Tommo-So (Tongo Tongo, LM)": "",
    "Dogul Dom (Bendiely, BC)": "Dogul_Dom",
    "Tebul Ure (JH)": "Tebul_Ure",
    "Yanda Dom (Yanda, JH)": "Yanda_Dom",
    "Najamba (Kubewel-Adia, JH)": "Najamba",
    "Tiranige (Boui, JH)": "Tiranige",
    "Mombo JH": "Mombo",
    "Mombo (Songho, KP)": "",
    "Ampari (Nando, JH)": "Ampari",
    "Ampari (Nando, KP)": "",
    "Bunoge (Boudou)": "Bunoge",
    "Penange (Pinia)": "Penange",

    "Bangime (Bounou, JH)": "",
    "Bangime (Bounou, AH)": "",

    "HS Songhay": "",
    "TSK Songhay": "",
    "species": "species",
    "family": "family",
}
"""
    book p.,
    synonymy,
    comment,
    domain,
    specimen
"""
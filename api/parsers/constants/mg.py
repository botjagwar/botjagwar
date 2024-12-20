CASES = {
    # very abbreviated forms
    "n": "endriky ny lazaina",
    "g": "mpanamarika ny an'ny tompo",
    "d": "mpanamarika ny tolorana",
    "a": "endrika teny fameno",
    "l": "endrika teny famaritan-toerana",
    "v": "endrika miantso",
    # abbreviated forms
    "cfin": "ebdrika kaozaly-mamarana",
    "ade": "adesiva",
    "nom": "endriky ny lazaina",
    "acc": "endrika teny fameno",
    "loc": "endrika teny famaritan-toerana",
    "dat": "mpanamarika ny tolorana",
    "gen": "mpanamarika ny an'ny tompo",
    "ine": "inesiva",
    "del": "delativa",
    "ela": "elativa",
    "ill": "ilativa",
    "spe": "soperesiva",
    "abl": "ablativa",
    "tran": "translativa",
    "efor": "esiva manaja",
    "ins": "mpanamarika fomba fanaovana",
    "pre": "endrika mampiankina",
    "voc": "endrika miantso",
    "dim": "endrika manamari-pahakelezana",
    # full forms
    "nominative": "endriky ny lazaina",
    "genitive": "mpanamarika ny an'ny tompo",
    "accusative": "endrika teny fameno",
    "partitive": "partitiva",
    "inessive": "inesiva",
    "elative": "elativa",
    "illative": "ilativa",
    "adessive": "adesiva",
    "ablative": "ablativa",
    "allative": "alativa",
    "essive": "esiva",
    "translative": "translativa",
    "instructive": "instroktiva",
    "abessive": "abesiva",
    "comitative": "komitativa",
}

TENSE = {
    "aor": "aorista",
    "aori": "aorista",
    "pres": "ankehitriny",
    "past": "efa lasa",
    "fut": "ho avy",
    "futr": "ho avy",
    "npast": "tsy efa lasa",
    "prog": "prôgresiva",
    "pret": "preterita",
    "perf": "perfekta",
    "plup": "ploperfekta",
    "pluperf": "ploperfekta",
    "impf": "imperfekta",
    "imperf": "imperfekta",
    "semf": "semelaktiva",
    "phis": "efa lasa ara-tantara",
    "pfv": "perfektiva",
    "perfv": "perfektiva",
    "impfv": "imperfektiva",
    # full forms
    "present": "ankehitriny",
    "imperfect": "imperfekta",
    "preterite": "filazam-potoana lasa tsotra",
    "future": "ho avy",
    "conditional": "kôndisiônaly",
}

MOOD = {
    "imp": "filaza mandidy",
    "impr": "filaza mandidy",
    "iter": "filaza mitsingerina",
    "ind": "filaza manoro",
    "indc": "filaza manoro",
    "indic": "filaza manoro",
    "sub": "sobjônktiva",
    "subj": "sobjônktiva",
    "cond": "kôndisiônaly",
    "opta": "ôptativa",
    "opt": "ôptativa",
    "potn": "pôtentsialy",
    "juss": "josiva",
    "coho": "kôhôrtativa",
    "inf": "infinitiva",
    "part": "ova matoanteny",
    "ptcp": "ova matoanteny",
    "poss": "endrika manan-tompony",
    "neg": "endrika mandà",
    "conn": "endrika miara-mandà",
    "conneg": "endrika miara-mandà",
    "sup": "sopinina",
    # full forms
    "gerund": "endrika ara-tambin-teny",
    "participle": "ova matoanteny",
    "past participle": "ova matoanteny efa lasa",
    "present participle": "ova matoanteny",
    "future participle": "ova matoanteny hoavy",
    "conditional": "kôndisiônaly",
    "subjunctive": "sobjônktiva",
    "indicative": "filaza manoro",
    "imperative": "filaza mandidy",
}

NUMBER = {
    "s": "singiolary",
    "sg": "singiolary",
    "p": "ploraly",
    "d": "mamaritra ny roa",
    "t": "mamaritra ny telo",
    "pl": "ploraly",
    "pau": "mamaritra zava-bitsy",
    "sgl": "singiolativa",
    "col": "mamondrona",
    # full forms
    "singular": "singiolary",
    "plural": "ploraly",
}
GENDER = {"m": "andehilahy", "f": "ambehivavy", "n": "tsy miandany"}

VOICE = {
    "act": "fiendrika manano",
    "actv": "fiendrika manano",
    "mid": "fiendrika anelanelana",
    "midl": "fiendrika anelanelana",
    "pass": "fiendrika anoina",
    "pasv": "fiendrika anoina",
    "mp": "fiendrika anelanelana",
    "mpsv": "fiendrika anelanelana",
}

PERSONS = {
    "1": "mpandray anjara voalohany",
    "2": "mpandray anjara faharoa",
    "3": "mpandray anjara fahatelo",
    "4": "mpandray anjara fahaefatra",
    "5": "mpandray anjara fahadimy",
    "impers": "mpandray anjara tsy fantatra",
    # full forms
    "first-person": "mpandray anjara voalohany",
    "second-person": "mpandray anjara faharoa",
    "second-person (tú)": "mpandray anjara faharoa (tú)",
    "second-person (vos)": "mpandray anjara faharoa (vos)",
    "third-person": "mpandray anjara fahatelo",
}

DEFINITENESS = {
    "def": "voafaritra",
    "indef": "tsy voafaritra",
    # full forms
    "definite": "voafaritra",
    "indefinite": "tsy voafaritra",
}

POSSESSIVENESS = {}
for person in PERSONS:
    for number in NUMBER:
        POSSESSIVENESS[person + number] = f"{PERSONS[person]} {NUMBER[number]}"

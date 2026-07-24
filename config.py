"""
Zentrale Konfiguration für den Urlaubs-Agent.

Dies ist die interne Verdrahtung - NICHT hier deine Reisedaten eintragen!
Trag deine Eckdaten in `mein_urlaub.py` ein (siehe SETUP.md), diese Datei
liest sie ein und baut daraus die Strukturen, die agent.py/mailer.py/main.py
erwarten. So bleibt die eigentliche Such-/Bewertungslogik unverändert, egal
was in mein_urlaub.py steht.
"""
import os

import mein_urlaub as nutzer

# ---------------------------------------------------------------------------
# REISE-KRITERIEN (aus mein_urlaub.py zusammengebaut)
# ---------------------------------------------------------------------------
REISE = {
    "start_ort_plz": nutzer.START_PLZ,
    "richtung": nutzer.RICHTUNG,
    "fahrzeit_von_stunden": nutzer.FAHRZEIT_VON_STUNDEN,
    "fahrzeit_bis_stunden": nutzer.FAHRZEIT_BIS_STUNDEN,
    "anreise": nutzer.ANREISE,

    "zeitraum_von": nutzer.ZEITRAUM_VON,
    "zeitraum_bis": nutzer.ZEITRAUM_BIS,
    "flex_tage": nutzer.FLEX_TAGE,

    "min_dauer_tage": nutzer.MIN_DAUER_TAGE,

    "erwachsene": nutzer.ERWACHSENE,
    "kinder_alter": nutzer.KINDER_ALTER,

    "unterkunft": nutzer.UNTERKUNFT,
    # Wird aus MIND_SCHLAFZIMMER generiert, damit dieser Text und das harte
    # K.-o.-Kriterium in GESCHMACK weiter unten NIE auseinanderlaufen können.
    "pflicht": f"MINDESTENS {nutzer.MIND_SCHLAFZIMMER} Schlafzimmer",
    "ausschluss_regionen": nutzer.AUSSCHLUSS_REGIONEN,
}

# Direkt zugänglich (nicht nur eingebettet in REISE["pflicht"]/GESCHMACK
# ["hartes_ko"]), damit mailer.py es referenzieren kann, ohne den Text zu
# parsen.
MIND_SCHLAFZIMMER = nutzer.MIND_SCHLAFZIMMER

# Exakte Enum-Werte, die Claude im JSON-Feld "schlafzimmer" zurückgeben soll
# (agent.py) UND die main.py._ist_ko() für den K.-o.-Filter vergleicht. EINE
# gemeinsame Quelle, damit beide Stellen bei einer anderen MIND_SCHLAFZIMMER-
# Zahl automatisch in Sync bleiben - sonst würde der K.-o.-Filter bei
# abweichendem Wert stillschweigend nie mehr greifen.
SCHLAFZIMMER_VOLL = f"{MIND_SCHLAFZIMMER}+ bestätigt"
SCHLAFZIMMER_NULL = f"weniger als {MIND_SCHLAFZIMMER} bestätigt"

# ---------------------------------------------------------------------------
# ZIELREGIONEN: Startpunkt-Liste, keine abschließende Liste (siehe Prompt in
# agent.py: Claude darf und soll auch andere Regionen im Radius vorschlagen).
# Wird rotierend genutzt (agent._heutige_zielregionen).
# ---------------------------------------------------------------------------
ZIELREGIONEN = nutzer.ZIELREGIONEN

# ---------------------------------------------------------------------------
# PREIS-KLASSEN (statt Fixpreis)
# Gesamtpreis für die ganze Reise, Grenzen aus mein_urlaub.py.
# Claude ordnet jedes Objekt anhand einer Preisindikation in eine Klasse ein.
# ---------------------------------------------------------------------------
PREISKLASSEN = {
    "€":    {"bis": nutzer.BUDGET_GUENSTIG,    "label": "günstig",     "desc": "Camping-Bungalow, einfache FeWo"},
    "€€":   {"bis": nutzer.BUDGET_MITTEL,      "label": "mittel",      "desc": "solide FeWo / Aparthotel"},
    "€€€":  {"bis": nutzer.BUDGET_OBERES_ENDE, "label": "oberes Ende", "desc": "gehobene FeWo / Familienhotel"},
    "€€€€": {"bis": None, "label": "über Budget", "desc": f"über {nutzer.BUDGET_OBERES_ENDE} € - nur zur Info"},
}

# Bewertungs-Schwerpunkte (fließen in Claudes Ranking ein)
BEWERTUNG_FOKUS = nutzer.BEWERTUNG_FOKUS

# ---------------------------------------------------------------------------
# GESCHMACKSPROFIL v2: Match-Score statt Ausschlussfilter (siehe
# docs/konzepte/KONZEPT_geschmacksprofil_v2.md). GENAU EIN K.-o. (bestätigt <
# MIND_SCHLAFZIMMER Schlafzimmer), alles andere fließt gewichtet in einen
# 0-100-Match-Score ein. "Unklar" wird NIE bestraft/ausgeschlossen, sondern
# neutral (halbe Punkte) gewertet.
#
# WICHTIG: Die Schlüsselnamen in "gewichte"/"modifikatoren" sind in
# agent.py (_match_score_berechnen) fest verdrahtet - hier NICHT umbenennen.
# ---------------------------------------------------------------------------
GESCHMACK = {
    "hartes_ko": [
        f"weniger als {nutzer.MIND_SCHLAFZIMMER} Schlafzimmer (NUR bei bestätigtem Verstoß ausschließen, 'unklar' schließt NICHT aus)",
    ],
    "gewichte": {          # Summe sollte 100 = Perfect Match ergeben
        "schlafzimmer": nutzer.GEWICHT_SCHLAFZIMMER,
        "pool": nutzer.GEWICHT_POOL,
        "kueche": nutzer.GEWICHT_KUECHE,
        "groesse_stil": nutzer.GEWICHT_GROESSE_STIL,
        "lage": nutzer.GEWICHT_LAGE,
    },
    "unklar_faktor": nutzer.UNKLAR_FAKTOR,
    "modifikatoren": {
        "preis_€€€": nutzer.MODIFIKATOR_PREIS_OBERES_ENDE,
        "preis_€€€€": nutzer.MODIFIKATOR_PREIS_UEBER_BUDGET,
        "kinder_bonus_max": nutzer.KINDER_BONUS_MAX,
        "stil_bonus_max": nutzer.STIL_BONUS_MAX,
    },
    "bewusst_offen": [
        "Landschaftsart egal (Berg, Meer, See, Hügel/Weinland, Therme, Wald ...) - NICHT auf Berg/Meer fixieren",
        "Verpflegung egal (Selbstversorger oder Hotel)",
        "Trubel-Level egal (lebhaftes Resort oder ruhig)",
        "Anreise-Fahrzeit egal innerhalb des Radius - kürzer ist kein Bonus, länger kein Malus",
        "Aktivitäten egal - Familie ist offen für alles",
        "neue vs. bekannte Region egal - keine Abwertung von Bekanntem",
    ],
    "referenzen": nutzer.REFERENZEN,
    "min_landschaftstypen_pro_lauf": nutzer.MIN_LANDSCHAFTSTYPEN_PRO_LAUF,
}

# Niedrige Schwelle - Nutzer will lieber mehr sehen ("lieber ein paar Nieten
# sehen als Treffer verpassen") als zu scharf herausfiltern.
MIN_MATCH_SCORE_FUER_MAIL = nutzer.MIN_MATCH_SCORE_FUER_MAIL

# ---------------------------------------------------------------------------
# FEEDBACK-SCHLEIFE & SELBSTDIAGNOSE (siehe docs/konzepte/KONZEPT_stufe1_lernen.md)
# Feedback kommt per GitHub-Issue (Label FEEDBACK_LABEL) - GITHUB_TOKEN ist in
# GitHub Actions automatisch vorhanden (kein neues Secret nötig), lokal muss
# es ggf. selbst gesetzt werden (z.B. via `gh auth token`).
# ---------------------------------------------------------------------------
FEEDBACK_AKTIV = True
# GITHUB_REPOSITORY wird von GitHub Actions automatisch gesetzt (Format
# "owner/repo") - dadurch funktionieren Feedback-Issue-Links in JEDEM Fork
# automatisch richtig, ohne dass der Nutzer etwas eintragen muss. Lokal ohne
# Wert - dann sind die Feedback-Links nur lokal nicht klickbar (unkritisch).
GITHUB_REPO = os.environ.get("GITHUB_REPOSITORY", "")
FEEDBACK_LABEL = "feedback"
FEEDBACK_BEISPIELE_IM_PROMPT = nutzer.FEEDBACK_BEISPIELE_IM_PROMPT
FEEDBACK_BONUS_MAX = nutzer.FEEDBACK_BONUS_MAX

DIAGNOSE_AKTIV = True
DIAGNOSE_FENSTER_LAEUFE = nutzer.DIAGNOSE_FENSTER_LAEUFE

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

# ---------------------------------------------------------------------------
# BETRIEB
# ---------------------------------------------------------------------------
MODELL = nutzer.MODELL

MAX_WEBSEARCHES_PRO_LAUF = nutzer.MAX_WEBSEARCHES_PRO_LAUF
MAX_WEBFETCHES_PRO_LAUF = nutzer.MAX_WEBFETCHES_PRO_LAUF
MAX_KANDIDATEN_BEWERTEN = nutzer.MAX_KANDIDATEN_BEWERTEN

# Direktlink-Auflösung (separater, kleiner Claude-Aufruf pro Deal, siehe
# docs/konzepte/KONZEPT_direktlink.md). Eigenes Tool-Kontingent (1 Suche + 1 Fetch pro Deal),
# bewusst GETRENNT von MAX_WEBSEARCHES_PRO_LAUF/MAX_WEBFETCHES_PRO_LAUF, damit
# die Hauptsuche nicht verhungert - Kostendeckel ist stattdessen die Anzahl der
# Deals (nur die Top-N nach Score bekommen eine Auflösung).
MAX_DIREKTLINK_AUFLOESUNG = nutzer.MAX_DIREKTLINK_AUFLOESUNG
DIREKTLINK_MAX_TOKENS = nutzer.DIREKTLINK_MAX_TOKENS

# ---------------------------------------------------------------------------
# PERSISTENZ
# ---------------------------------------------------------------------------
DB_PFAD = "deals.sqlite"

# ---------------------------------------------------------------------------
# MAIL (Werte kommen aus GitHub Secrets / Umgebungsvariablen)
# ---------------------------------------------------------------------------
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
MAIL_AN   = os.environ.get("MAIL_AN", "")

DIGEST_IMMER = True

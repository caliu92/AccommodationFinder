"""
DEINE URLAUBSKONFIGURATION
==========================
Das ist die einzige Datei, die du anfassen musst. Trag oben deine Eckdaten
ein - alles darunter ("Fortgeschritten") hat funktionierende Standardwerte,
du kannst es unverändert lassen.

Tipp: Statt hier von Hand zu tippen, kannst du die Generator-Seite nutzen
(Link steht in SETUP.md) - die erzeugt dir den passenden Inhalt zum
Reinkopieren.
"""

# =============================================================================
# PFLICHT - deine Eckdaten
# =============================================================================

# Postleitzahl deines Startorts (als Text, mit Anführungszeichen) - Beispielwert,
# unbedingt durch deine eigene PLZ ersetzen
START_PLZ = "12345"

# In welche Himmelsrichtung soll gesucht werden? (nur Info für Claude, kein
# harter Filter - z.B. "Süden", "Norden", "egal")
RICHTUNG = "Süden"

# Wie viele Erwachsene reisen mit?
ERWACHSENE = 2

# Alter der Kinder (eine Zahl pro Kind, in eckigen Klammern, mit Kommas
# getrennt). Leere Liste [] bedeutet: keine Kinder.
KINDER_ALTER = [5, 9]

# Reisezeitraum (Format IMMER "JJJJ-MM-TT") - Beispielwerte, durch euren
# eigenen Zeitraum ersetzen
ZEITRAUM_VON = "2027-07-01"
ZEITRAUM_BIS = "2027-07-14"

# Wie viele Tage darf der Zeitraum nach vorne/hinten verschoben werden?
FLEX_TAGE = 2

# Mindestaufenthaltsdauer in Tagen
MIN_DAUER_TAGE = 7

# Wie viele Schlafzimmer braucht ihr MINDESTENS? Das ist das einzige harte
# Ausschlusskriterium - alles andere ist "weiches" Bewertungskriterium.
MIND_SCHLAFZIMMER = 2

# Budget-Grenzen in Euro, GESAMT für die ganze Reise (nicht pro Nacht/Person).
# Drei Preisklassen - Claude ordnet jedes Angebot in eine davon ein.
BUDGET_GUENSTIG = 1500       # bis zu diesem Betrag = "günstig"
BUDGET_MITTEL = 2300         # bis zu diesem Betrag = "mittel"
BUDGET_OBERES_ENDE = 2700    # bis zu diesem Betrag = "oberes Ende"
                             # (alles darüber wird trotzdem angezeigt, nur
                             # als "über Budget" gekennzeichnet)

# Länder/Regionen, die NIE vorgeschlagen werden sollen, auch wenn sie sonst
# passen würden (z.B. wegen früherer schlechter Erfahrung).
AUSSCHLUSS_REGIONEN = ["Schweiz", "Ungarn", "Slowenien", "Kroatien", "Venetien/Jesolo"]


# =============================================================================
# FORTGESCHRITTEN - Standardwerte funktionieren, nur ändern wenn du weißt,
# was du tust
# =============================================================================

# Fahrzeit-Radius in Stunden ab deinem Startort (nur mit dem Auto gerechnet)
FAHRZEIT_VON_STUNDEN = 8
FAHRZEIT_BIS_STUNDEN = 10

# Anreiseart (nur Info für Claude)
ANREISE = "nur mit Auto"

# Art der Unterkunft, die infrage kommt
UNTERKUNFT = "egal (Hotel/FeWo/Camping-Bungalow)"

# Rotierende Startpunkt-Liste für die tägliche Suche (KEINE abschließende
# Liste - Claude darf und soll auch andere Regionen im Fahrzeit-Radius
# vorschlagen). Pro Lauf wird nur ein Ausschnitt daraus genutzt (siehe
# MAX_WEBSEARCHES_PRO_LAUF unten), damit das Such-Budget nicht sofort
# aufgebraucht ist.
ZIELREGIONEN = [
    # Deutschland
    "Bodensee",                                 # ~3h
    "Allgäu",                                   # ~3h
    "Schwarzwald / Titisee-Schluchsee",         # ~2,5h
    "Bayerischer Wald",                         # ~3h
    # Österreich
    "Tirol (Fiss/Serfaus/Ötztal/Zillertal)",    # ~5h
    "Salzkammergut (Wolfgangsee/Attersee)",     # ~5h
    "Kärnten (Wörthersee/Millstätter See)",     # ~6h
    "Steiermark Thermenland",                   # ~6h
    # Italien
    "Südtirol (Meran/Pustertal/Eisacktal)",     # ~5h
    "Trentino (Levico/Caldonazzo)",             # ~6h
    "Gardasee",                                 # ~6h
    "Emilia-Romagna (Rimini/Cesenatico)",       # ~8h
    "Toskana (Maremma/Versilia/Chianti)",       # ~8h
    "Ligurien",                                 # ~8h
    "Umbrien",                                  # ~8,5h
    # Frankreich
    "Elsass / Vogesen",                         # ~3h
    "Jura / Franche-Comté",                     # ~5h
    "Burgund",                                  # ~6h
    "Provence-Nord / Drôme",                    # ~8,5h
    "Ardèche",                                  # ~8,5h
]

# Bewertungs-Schwerpunkte, die in Claudes Ranking einfließen
BEWERTUNG_FOKUS = [
    "kinderfreundliche Umgebung (Spielplatz, Pool, flacher Strand/See)",
    "geeignet für Kleinkind UND Schulkind (passend zu deinen Kindern oben)",
    "gutes Preis-Leistungs-Verhältnis",
]

# Gewichtung der weichen Kriterien im Match-Score (0-100). Die Summe sollte
# 100 ergeben - Schlafzimmer zählt am meisten, Lage am wenigsten.
GEWICHT_SCHLAFZIMMER = 30
GEWICHT_POOL = 25
GEWICHT_KUECHE = 20
GEWICHT_GROESSE_STIL = 15   # klein/modern statt Großkomplex
GEWICHT_LAGE = 10           # naturnah/nicht städtisch

# Wie viele Punkte gibt's, wenn ein Kriterium unklar ist (0.5 = halbe Punkte,
# NIE 0 - "unklar" soll nie wie "nicht erfüllt" behandelt werden)
UNKLAR_FAKTOR = 0.5

# Punktabzug im Match-Score je nach Preisklasse
MODIFIKATOR_PREIS_OBERES_ENDE = -5     # bei "oberes Ende"-Preisklasse
MODIFIKATOR_PREIS_UEBER_BUDGET = -25   # bei "über Budget"-Preisklasse

# Maximale Bonus-Punkte für Kinderfreundlichkeits- bzw. Stil-Signale
KINDER_BONUS_MAX = 5
STIL_BONUS_MAX = 5

# Stil-Anker: Beispiel-Unterkünfte, die euch gefallen haben (oder gefallen
# würden) - zeigen Claude den gewünschten STIL, nicht den Ort. Trag hier
# gerne eure eigenen Beispiele ein.
REFERENZEN = [
    {"name": "Camping Village Mediterraneo (bei Jesolo, IT)",
     "warum": "entspanntes familientaugliches Ferienresort am Wasser mit Pool"},
    {"name": "Nagalu Hotel Garni (Fiss, AT)",
     "warum": "modernes, überschaubares, familiäres Hotel Garni mit alpinem Design"},
    {"name": "Hotel Alpin Chalet am Burgsee (Ladis, AT)",
     "warum": "moderner Chalet-/Boutique-Stil, naturnah am See"},
]

# Wie viele unterschiedliche Landschaftstypen (Berg, Meer, See, Wein, ...)
# soll ein Lauf mindestens abdecken? Verhindert Fixierung auf nur 1-2 Typen.
MIN_LANDSCHAFTSTYPEN_PRO_LAUF = 3

# Ab diesem Match-Score (0-100) wird ein Angebot per Mail geschickt. Niedrig
# angesetzt: lieber ein paar Nieten sehen als einen Treffer verpassen.
MIN_MATCH_SCORE_FUER_MAIL = 40

# Claude-Modell für die Suche/Bewertung (Haiku = günstig, siehe Kosten-
# Hinweis in SETUP.md)
MODELL = "claude-haiku-4-5-20251001"

# Kostendeckel pro Lauf
MAX_WEBSEARCHES_PRO_LAUF = 5
MAX_WEBFETCHES_PRO_LAUF = 6
MAX_KANDIDATEN_BEWERTEN = 8

# Direktlink-Auflösung: für wie viele Top-Deals wird zusätzlich versucht,
# die echte Objektseite (statt nur Portalseite) zu finden?
MAX_DIREKTLINK_AUFLOESUNG = 4
DIREKTLINK_MAX_TOKENS = 1024

# Feedback-Schleife (Daumen hoch/runter per GitHub Issue)
FEEDBACK_BEISPIELE_IM_PROMPT = 20   # letzte N Feedback-Einträge als Beispiel
FEEDBACK_BONUS_MAX = 10             # max. Punkte Auf-/Abwertung durch Feedback

# Selbstdiagnose: nach wie vielen Läufen in Folge ohne Treffer warnen?
DIAGNOSE_FENSTER_LAEUFE = 3

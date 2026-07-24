"""
Der Urlaubs-Agent (v5).

Neu ggü. v4:
- web_fetch (Beta) ergänzt: Claude öffnet die 2-4 besten Treffer wirklich und
  holt den echten Objekt-Detaillink + eine Preisindikation, statt nur die
  Portal-Startseite zu nehmen.
- Quellen gemischt (FeWo-direkt/Vrbo, HomeToGo, Booking, Airbnb, Camping),
  Claude wählt je Region.
- Preis als Klasse (€/€€/€€€) + ungefährer Betrag, kein Fixpreis mehr.
"""
import datetime as dt
import json
import re
import anthropic
import config
import storage

client = anthropic.Anthropic()

MAX_TOKENS = 8000
BETA_HEADER = {"anthropic-beta": "web-fetch-2025-09-10"}


def _preisklassen_text() -> str:
    zeilen = []
    vorherige_grenze = None
    for sym, info in config.PREISKLASSEN.items():
        if info["bis"]:
            grenze = f"bis ~{info['bis']} €"
        else:
            grenze = f"über {vorherige_grenze} €" if vorherige_grenze else "ohne Obergrenze"
        vorherige_grenze = info["bis"] or vorherige_grenze
        zeilen.append(f"  {sym} = {info['label']} ({grenze}): {info['desc']}")
    return "\n".join(zeilen)


def _geschmack_text() -> str:
    g = config.GESCHMACK
    hartes_ko = "\n".join(f"  - {k}" for k in g["hartes_ko"])
    offen = "\n".join(f"  - {o}" for o in g["bewusst_offen"])
    referenzen = "\n".join(f'  - "{r["name"]}": {r["warum"]}' for r in g["referenzen"])
    return f"""GESCHMACKSPROFIL DER FAMILIE ("Perfect Match" - Stil-Anker, NICHT Geografie):
Diese Unterkünfte haben der Familie gefallen und zeigen den gewünschten STIL,
nicht den Ort. Suche neue Unterkünfte mit ähnlichem Charakter in BELIEBIGEN
Regionen/Landschaften - die Namen unten sind nur Referenz, sie müssen NICHT
selbst in den Suchergebnissen auftauchen:
{referenzen}

EINZIGES HARTES K.-o.-KRITERIUM (alles andere ist keine Ausschlussfrage,
sondern fließt gewichtet in einen Match-Score ein, siehe unten):
{hartes_ko}

DAS PERFECT-MATCH-IDEALBILD (wird pro Kriterium einzeln bewertet, siehe
JSON-Felder unten): mindestens 2 getrennte Schlafzimmer, Pool vorhanden
(Anlagenpool geteilt reicht), Küche in der Unterkunft, klein/mittelgroß und
modern (Chalet-/Boutique-/kleines-Resort-Gefühl statt großer anonymer
Hotelkomplex), naturnahe/nicht-städtische/ruhige Lage.

BEWUSST OFFEN (NICHT einschränken, kein Bonus/Malus):
{offen}

WICHTIG - "unklar" ist ein legitimes und ERWÜNSCHTES Ergebnis: Bewerte jedes
der obigen Kriterien ehrlich mit erfüllt / nicht erfüllt / unklar. Rate
NIEMALS. "unklar" führt zu einer neutralen Teilpunktzahl - NIEMALS zu einem
Ausschluss. Ein Angebot mit vielen "unklar"-Kriterien bekommt einen mittleren
Score und wird dem Nutzer trotzdem gezeigt, damit er selbst nachprüfen kann.

WICHTIG - Landschafts-Streuung: Fixiere dich NICHT auf Berg oder Meer, auch
wenn dort die meisten Treffer ranken. Decke pro Lauf mindestens
{g['min_landschaftstypen_pro_lauf']} unterschiedliche Landschaftstypen ab
(z.B. See, Weinregion, Therme, Wald, Hügelland, Berg, Meer), solange das
harte K.-o.-Kriterium nicht bestätigt verletzt ist."""


def _feedback_text() -> str:
    """Baut die Lern-Zusammenfassung aus bisherigem Nutzer-Feedback als
    Few-shot-Beispiele (siehe docs/konzepte/KONZEPT_stufe1_lernen.md §3.2, Variante A).
    Gibt einen leeren String zurück, solange noch kein Feedback vorliegt -
    dann taucht auch kein leerer Abschnitt im Prompt auf."""
    if not config.FEEDBACK_AKTIV:
        return ""
    eintraege = storage.feedback_letzte(config.FEEDBACK_BEISPIELE_IM_PROMPT)
    if not eintraege:
        return ""

    zeilen = []
    for e in eintraege:
        try:
            merkmale = json.loads(e.get("merkmale_json") or "{}")
        except json.JSONDecodeError:
            merkmale = {}
        deskriptoren = ", ".join(v for v in [
            e.get("landschaft"),
            merkmale.get("groesse_stil"),
            "Pool" if merkmale.get("pool") == "bestätigt" else None,
        ] if v)
        emoji_text = "👍 gefiel" if e.get("bewertung") == "daumen_hoch" else "👎 gefiel NICHT"
        klammer = f" ({deskriptoren})" if deskriptoren else ""
        grund = f' – Grund: "{e["grund"]}"' if e.get("grund") else ""
        zeilen.append(f'{emoji_text}: "{e.get("titel","")}"{klammer}{grund}')

    return f"""GELERNT AUS BISHERIGEM FEEDBACK DES NUTZERS:
{chr(10).join(zeilen)}

Berücksichtige diese Vorlieben bei der Bewertung. Objekte, die den
👍-Beispielen ähneln, im Feld "feedback_bonus" positiv bewerten; solche, die
den 👎-Beispielen ähneln, negativ. Vergib feedback_bonus NUR bei klarer
Ähnlichkeit zu einem Beispiel oben, sonst 0 - niemals raten oder erzwingen."""


def _heutige_zielregionen() -> list[str]:
    """Rotierende Auswahl aus config.ZIELREGIONEN für den heutigen Lauf.

    Kostendeckel: pro Lauf werden nur MAX_WEBSEARCHES_PRO_LAUF Regionen
    vorgeschlagen (nicht alle 20) - eine Suche pro Region passt genau ins
    bestehende Websuche-Budget. Deterministisch über den Tag des Jahres
    (kein Rotations-Index in der DB nötig) - das ist die einfachste robuste
    Lösung: kein zusätzlicher State, der zwischen Läufen synchron gehalten
    werden müsste, und trotzdem reproduzierbar. Der Fensterstart wandert pro
    Tag um MAX_WEBSEARCHES_PRO_LAUF Positionen weiter, sodass sich bei 20
    Regionen und 5 Suchen/Lauf ein 4-Tage-Zyklus ergibt, der alle Regionen
    ohne Überschneidung abdeckt (Wraparound am Listenende ist unkritisch)."""
    regionen = config.ZIELREGIONEN
    n = min(config.MAX_WEBSEARCHES_PRO_LAUF, len(regionen))
    tag_des_jahres = dt.date.today().timetuple().tm_yday
    start = (tag_des_jahres * n) % len(regionen)
    return [regionen[(start + i) % len(regionen)] for i in range(n)]


def _kriterien_text() -> str:
    r = config.REISE
    kinder = ", ".join(f"{a} Jahre" for a in r["kinder_alter"])
    fokus = "\n".join(f"  - {f}" for f in config.BEWERTUNG_FOKUS)
    ausschluss_regionen = ", ".join(r["ausschluss_regionen"])
    heutige_regionen = ", ".join(_heutige_zielregionen())
    feedback = _feedback_text()
    feedback_block = f"\n{feedback}\n" if feedback else ""
    gesamt_personen = r['erwachsene'] + len(r['kinder_alter'])
    return f"""REISEKRITERIEN (harte Filter):
- Startort: PLZ {r['start_ort_plz']}, Anreise {r['anreise']}
- Richtung: {r['richtung']}, Fahrzeit-Radius ca. {r['fahrzeit_von_stunden']}-{r['fahrzeit_bis_stunden']} Std
- HEUTIGE REGIONS-AUSWAHL (rotiert täglich, Kostendeckel): {heutige_regionen}
  Diese Regionen sind Beispiele für den Radius, KEINE abschließende Liste. Du
  darfst und sollst auch andere Regionen im ~{r['fahrzeit_bis_stunden']}h-Autoradius
  ab PLZ {r['start_ort_plz']} vorschlagen, wenn sie zum Geschmacksprofil passen.
- AUSGESCHLOSSEN: {ausschluss_regionen} - dort keine Unterkünfte vorschlagen,
  auch wenn sie sonst im Radius liegen und passen würden.
- Reisezeitraum: {r['zeitraum_von']} bis {r['zeitraum_bis']} (jeweils +/- {r['flex_tage']} Tage)
- Mindestdauer: {r['min_dauer_tage']} Tage
- Reisegruppe: {r['erwachsene']} Erwachsene + {len(r['kinder_alter'])} Kinder ({kinder})
- Unterkunft: {r['unterkunft']}
- PFLICHT: {r['pflicht']}

PREIS: kein Fixpreis. Ordne jedes Objekt in eine Preisklasse ein (Gesamt ca. {r['min_dauer_tage']} Nächte, {gesamt_personen} Pers.):
{_preisklassen_text()}

BEWERTUNGS-SCHWERPUNKTE:
{fokus}

{_geschmack_text()}
{feedback_block}
SUCH- UND FETCH-STRATEGIE:
1. Führe bis zu {config.MAX_WEBSEARCHES_PRO_LAUF} Websuchen durch - orientiere
   dich an der HEUTIGEN REGIONS-AUSWAHL oben (grob eine Suche pro Region),
   tausche aber gerne 1-2 davon gegen eine andere Region im Radius, wenn dir
   eine besser zum Geschmacksprofil passende einfällt. Wähle je Region
   passende Quellen aus dem gesamten Spektrum: FeWo-direkt/Vrbo, HomeToGo,
   Booking.com, Airbnb, Camping-Portale (PiNCAMP, Roan, Vacanceselect),
   Familienhotel-Seiten. Ziel: konkrete EINZELNE Unterkünfte, nicht nur Übersichten.
2. Öffne dann mit web_fetch die {config.MAX_WEBFETCHES_PRO_LAUF} vielversprechendsten
   Trefferseiten, um den DIREKTEN Objekt-Link (Detailseite der konkreten Unterkunft)
   und eine ungefähre Preisangabe herauszulesen.
3. Gib als "url" immer den tiefsten verfügbaren Objekt-Link an, den du tatsächlich
   gesehen hast - NICHT die Portal-Startseite. Wenn du nur eine Portal-/
   Übersichtsseite hast, sage das ehrlich im Feld "link_typ" ("nur Portalseite").
4. Kontakt-E-Mail: Handelt es sich um die eigene Website des Anbieters (nicht
   Booking.com/Airbnb/HomeToGo/Vrbo o.ä.), suche auf der bereits gefetchten
   Objektseite nach einem sichtbaren Link zu "Impressum" oder "Kontakt" und
   öffne diesen zusätzlich per web_fetch (in DACH-Ländern ist ein Impressum
   mit E-Mail-Pflicht üblich). Übernimm die E-Mail nur, wenn sie dort
   tatsächlich steht - niemals raten. Bei großen Buchungsportalen gibt es
   i.d.R. keine Kontakt-Mail zu finden - dann bleibt das Feld leer, das ist
   normal."""


SYSTEM = """Du bist ein sorgfältiger Reise-Deal-Scout für eine Familie.
Du suchst aktiv mit web_search und öffnest die besten Treffer mit web_fetch,
um echte Objekt-Detaillinks und Preisindikationen zu bekommen.
Erfinde niemals Angebote, Preise oder URLs. Gib nur URLs an, die tatsächlich in
den Such- oder Fetch-Ergebnissen vorkamen. Wenn du unsicher bei Schlafzimmern
oder Preis bist, kennzeichne das ehrlich statt zu raten.
Halte Begründungen kurz (max 1 Satz)."""


TOOLS = [
    {"type": "web_search_20250305", "name": "web_search",
     "max_uses": config.MAX_WEBSEARCHES_PRO_LAUF},
    {"type": "web_fetch_20250910", "name": "web_fetch",
     "max_uses": config.MAX_WEBFETCHES_PRO_LAUF,
     "max_content_tokens": 6000},
]


def _ausgabe_anweisung() -> str:
    return f"""
Gib jetzt AUSSCHLIESSLICH ein kompaktes JSON-Objekt aus - kein Fließtext, keine
Backticks. Maximal {config.MAX_KANDIDATEN_BEWERTEN} Objekte, beste zuerst. Format:
{{"deals": [{{
  "titel": "Name der konkreten Unterkunft",
  "region": "z.B. Gardasee / Toskana",
  "preisklasse": "€ | €€ | €€€ | €€€€",
  "preis_indikation": "ca. 1800-2000 € / 8 Nächte  (oder: unbekannt)",
  "zeitraum": "16.-24.08.2026 falls bekannt, sonst: Zeitraum prüfen",
  "schlafzimmer": "{config.SCHLAFZIMMER_VOLL} | {config.SCHLAFZIMMER_NULL} | unklar",
  "pool": "bestätigt | kein Pool bestätigt | unklar",
  "kueche": "bestätigt | keine Küche bestätigt | unklar",
  "groesse_stil": "klein/modern | mittel | großer Komplex | unklar - nur Textsignale (Baujahr/renoviert/Design/Chalet/Boutique), niemals raten",
  "lage": "naturnah/ruhig | städtisch | unklar",
  "landschaft": "z.B. See / Weinregion / Therme / Berg / Meer / Wald / Hügelland",
  "kinder_bonus_signal": 0,
  "stil_bonus_signal": 0,
  "feedback_bonus": 0,
  "feedback_begruendung": "",
  "url": "https://direkter-objekt-link",
  "link_typ": "Objektseite | nur Portalseite",
  "kontakt_email": "E-Mail-Adresse der Unterkunft, NUR falls auf der Seite tatsächlich sichtbar (z.B. Impressum/Kontakt) - sonst leerer String, niemals raten",
  "begruendung": "1 kurzer Satz: was macht diese Unterkunft aus, v.a. Stil und Kinderfreundlichkeit"
}}]}}
"kinder_bonus_signal" (0-5): wie viele explizite Kinderfreundlichkeits-Merkmale
(Spielplatz, flacher Einstieg/Kinderbecken, Babybett) tatsächlich erwähnt
werden - 0, wenn nichts davon erwähnt wird, niemals raten.
"stil_bonus_signal" (0-5): wie stark die Beschreibung an die Referenzen oben
erinnert (Chalet/Boutique/modernes Design) - 0, wenn keine solchen Signale da sind.
"feedback_bonus" (-10 bis +10): NUR ungleich 0, wenn oben eine
Feedback-Zusammenfassung steht UND dieses Objekt einem 👍/👎-Beispiel klar
ähnelt (siehe Abschnitt "GELERNT AUS BISHERIGEM FEEDBACK"); sonst 0.
"feedback_begruendung": kurzer Satz, WELCHEM Beispiel es ähnelt und warum
(z.B. "ähnelt Chalet del Gelso, das dir gefiel") - leer lassen, wenn
feedback_bonus 0 ist.
Den Gesamt-Score (match_score) berechnet NICHT du, sondern der Code aus diesen
Feldern - du musst ihn nicht ausgeben.
Nur wenn die Suche wirklich nichts hergab: {{"deals": []}}
"""


# ---------------------------------------------------------------------------
# MATCH-SCORE-BERECHNUNG (siehe docs/konzepte/KONZEPT_geschmacksprofil_v2.md §4)
# Bewusst NICHT von Claude selbst addieren lassen: die Gewichtung muss exakt
# stimmen (siehe die Referenz-Rechnungen im Konzept, z.B. "alles unklar" MUSS
# exakt 50 ergeben), und LLMs rechnen unzuverlässig. Claude liefert nur die
# qualitativen Einzelurteile (erfüllt/nicht erfüllt/unklar je Kriterium plus
# zwei kleine Bonus-Signale), der Code addiert deterministisch zusammen.
# ---------------------------------------------------------------------------
_UNKLAR_LABEL = {
    "schlafzimmer": "Schlafzimmer",
    "pool": "Pool",
    "kueche": "Küche",
    "groesse_stil": "Größe/Stil",
    "lage": "Lage",
}

# (Feldname, Wert bei vollen Punkten, Wert bei 0 Punkten)
_KRITERIEN = [
    ("schlafzimmer", config.SCHLAFZIMMER_VOLL, config.SCHLAFZIMMER_NULL),
    ("pool", "bestätigt", "kein Pool bestätigt"),
    ("kueche", "bestätigt", "keine Küche bestätigt"),
    ("groesse_stil", "klein/modern", "großer Komplex"),
    ("lage", "naturnah/ruhig", "städtisch"),
]


def _match_score_berechnen(deal: dict) -> None:
    """Berechnet match_score (0-100) deterministisch aus Claudes qualitativen
    Einzelurteilen und schreibt match_score/score_details/unklar_punkte in
    den Deal zurück. "Unklar" (und jeder unbekannte/fehlende Wert, z.B.
    "mittel" bei groesse_stil) bekommt IMMER den neutralen Faktor - nie 0."""
    g = config.GESCHMACK
    gewichte = g["gewichte"]
    unklar_faktor = g["unklar_faktor"]

    score_details = {}
    unklar_punkte = []
    basis_summe = 0.0

    for feld, voll_wert, null_wert in _KRITERIEN:
        wert = deal.get(feld)
        if wert == voll_wert:
            faktor = 1.0
        elif wert == null_wert:
            faktor = 0.0
        else:
            faktor = unklar_faktor
            unklar_punkte.append(_UNKLAR_LABEL[feld])
        punkte = gewichte[feld] * faktor
        score_details[feld] = round(punkte)
        basis_summe += punkte

    preisklasse = deal.get("preisklasse", "")
    preis_key = {"€€€": "preis_€€€", "€€€€": "preis_€€€€"}.get(preisklasse)
    preis_mod = g["modifikatoren"].get(preis_key, 0) if preis_key else 0
    score_details["preis_modifikator"] = preis_mod

    def _bonus(feld: str, max_key: str) -> float:
        wert = deal.get(feld)
        maximum = g["modifikatoren"][max_key]
        if not isinstance(wert, (int, float)):
            return 0.0
        return max(0.0, min(float(maximum), float(wert)))

    kinder_bonus = _bonus("kinder_bonus_signal", "kinder_bonus_max")
    stil_bonus = _bonus("stil_bonus_signal", "stil_bonus_max")
    score_details["kinder_bonus"] = round(kinder_bonus)
    score_details["stil_bonus"] = round(stil_bonus)

    # Feedback-Bonus (siehe docs/konzepte/KONZEPT_stufe1_lernen.md §3.3): gedeckelt auf
    # +/- FEEDBACK_BONUS_MAX, verschiebt nur den Score, filtert NIE aus.
    feedback_bonus_wert = deal.get("feedback_bonus")
    feedback_bonus = feedback_bonus_wert if isinstance(feedback_bonus_wert, (int, float)) else 0.0
    feedback_bonus = max(-float(config.FEEDBACK_BONUS_MAX),
                          min(float(config.FEEDBACK_BONUS_MAX), float(feedback_bonus)))
    score_details["feedback_bonus"] = round(feedback_bonus)

    gesamt = basis_summe + preis_mod + kinder_bonus + stil_bonus + feedback_bonus
    gesamt = max(0.0, min(100.0, gesamt))

    deal["match_score"] = round(gesamt)
    deal["score_details"] = score_details
    deal["unklar_punkte"] = unklar_punkte


def _match_scores_berechnen(deals: list[dict]) -> None:
    for deal in deals:
        _match_score_berechnen(deal)


def _call(messages):
    return client.messages.create(
        model=config.MODELL, max_tokens=MAX_TOKENS, system=SYSTEM,
        tools=TOOLS, messages=messages, extra_headers=BETA_HEADER,
    )


# ---------------------------------------------------------------------------
# DIREKTLINK-AUFLÖSUNG (siehe docs/konzepte/KONZEPT_direktlink.md)
# Eigener, fokussierter Mini-Aufruf pro Deal mit EIGENEM kleinen Tool-Budget
# (1 Suche + 1 Fetch) statt aus dem Hauptbudget (MAX_WEBSEARCHES_PRO_LAUF/
# MAX_WEBFETCHES_PRO_LAUF) - so verhungert die Hauptsuche nicht, und der
# Kostendeckel ist stattdessen schlicht die Anzahl der Deals, die eine
# Auflösung bekommen (MAX_DIREKTLINK_AUFLOESUNG, Top-N nach Score).
# ---------------------------------------------------------------------------
DIREKTLINK_SYSTEM = """Du verifizierst die offizielle Direktseite EINER konkreten
Unterkunft. Suche gezielt nach Name + Region, öffne mit web_fetch das
vielversprechendste Ergebnis und prüfe, ob Name und Ort wirklich zur
gesuchten Unterkunft passen - nimm NIEMALS blind das erste Suchergebnis
ungeprüft. Gib niemals eine URL zurück, die du nicht tatsächlich geöffnet
und geprüft hast; erfinde keine URLs.
Antworte knapp. Die LETZTE Zeile deiner Antwort enthält AUSSCHLIESSLICH die
verifizierte URL, oder das Wort "keine", falls keine eindeutige Direktseite
existiert (z.B. weil die Unterkunft nur auf einem Buchungsportal existiert
oder die Seite technisch nicht lesbar war)."""

DIREKTLINK_TOOLS = [
    {"type": "web_search_20250305", "name": "web_search", "max_uses": 1},
    {"type": "web_fetch_20250910", "name": "web_fetch",
     "max_uses": 1, "max_content_tokens": 4000},
]


def _direktlink_call(messages):
    return client.messages.create(
        model=config.MODELL, max_tokens=config.DIREKTLINK_MAX_TOKENS,
        system=DIREKTLINK_SYSTEM, tools=DIREKTLINK_TOOLS,
        messages=messages, extra_headers=BETA_HEADER,
    )


def _direktlink_aufloesen(deal: dict) -> None:
    """Versucht für EINEN Deal ohne bestätigte Objektseite die echte
    Direktseite zu finden und schreibt bei Erfolg url/link_typ direkt in den
    Deal zurück. Robust: jeder Fehler landet bei link_typ='nur Portalseite',
    die bestehende (Portal-)URL bleibt unangetastet."""
    titel = deal.get("titel", "")
    region = deal.get("region", "")
    frage = (f'Finde und verifiziere die offizielle Direktseite dieser '
             f'Unterkunft:\n"{titel}" ({region})')
    messages = [{"role": "user", "content": frage}]

    resp = None
    try:
        for _ in range(6):
            resp = _direktlink_call(messages)
            if resp.stop_reason == "pause_turn":
                messages.append({"role": "assistant", "content": resp.content})
                continue
            break
    except Exception as e:
        print(f"  [diag] Direktlink-Auflösung fehlgeschlagen für '{titel}': "
              f"{type(e).__name__}: {e}")
        deal["link_typ"] = "nur Portalseite"
        return

    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    zeilen = [z.strip() for z in text.splitlines() if z.strip()]
    letzte_zeile = zeilen[-1] if zeilen else ""

    if letzte_zeile.lower().startswith("http"):
        deal["url"] = letzte_zeile
        deal["link_typ"] = "Direktseite"
        print(f"  [diag] Direktlink gefunden für '{titel}': {letzte_zeile}")
    else:
        deal["link_typ"] = "nur Portalseite"
        print(f"  [diag] Keine Direktseite verifizierbar für '{titel}'.")


def _direktlinks_aufloesen(deals: list[dict]) -> None:
    """Löst für die Top-N Deals (nach match_score) ohne bestätigte Objektseite
    den echten Direktlink auf - Kostendeckel: MAX_DIREKTLINK_AUFLOESUNG Deals."""
    kandidaten = [d for d in deals if d.get("link_typ") != "Objektseite"]
    kandidaten.sort(
        key=lambda d: d.get("match_score") if isinstance(d.get("match_score"), int) else 0,
        reverse=True,
    )
    top_n = kandidaten[: config.MAX_DIREKTLINK_AUFLOESUNG]
    print(f"  [diag] Direktlink-Auflösung für {len(top_n)} von "
          f"{len(kandidaten)} Kandidaten (Kostendeckel={config.MAX_DIREKTLINK_AUFLOESUNG}).")
    for deal in top_n:
        _direktlink_aufloesen(deal)


def finde_deals() -> list[dict]:
    print(f"  [diag] Modell={config.MODELL}, search={config.MAX_WEBSEARCHES_PRO_LAUF}, fetch={config.MAX_WEBFETCHES_PRO_LAUF}")
    messages = [{"role": "user", "content": _kriterien_text()}]

    resp = None
    try:
        for i in range(16):
            resp = _call(messages)
            print(f"  [diag] Runde {i+1}: stop_reason={resp.stop_reason}")
            if resp.stop_reason == "pause_turn":
                messages.append({"role": "assistant", "content": resp.content})
                continue
            break
    except Exception as e:
        print(f"  [diag] FEHLER beim API-Aufruf: {type(e).__name__}: {e}")
        return []

    text = "".join(b.text for b in resp.content if b.type == "text").strip()

    if not _sieht_nach_json_aus(text):
        messages.append({"role": "assistant", "content": resp.content})
        messages.append({"role": "user", "content": _ausgabe_anweisung()})
        try:
            final = _call(messages)
            while final.stop_reason == "pause_turn":
                messages.append({"role": "assistant", "content": final.content})
                final = _call(messages)
            print(f"  [diag] JSON-Turn stop_reason={final.stop_reason}")
            text = "".join(b.text for b in final.content if b.type == "text").strip()
        except Exception as e:
            print(f"  [diag] FEHLER bei JSON-Anforderung: {type(e).__name__}: {e}")
            return []

    deals = _parse_json(text)
    print(f"  [diag] {len(deals)} Deals aus JSON extrahiert.")

    _match_scores_berechnen(deals)
    verteilung = sorted((d["match_score"] for d in deals), reverse=True)
    print(f"  [diag] Match-Score-Verteilung: {verteilung}")

    _direktlinks_aufloesen(deals)

    return deals


def _sieht_nach_json_aus(text: str) -> bool:
    t = text.replace("```json", "").replace("```", "").strip()
    return t.startswith("{") and '"deals"' in t


def _parse_json(text: str) -> list[dict]:
    cleaned = text.replace("```json", "").replace("```", "").strip()
    if "{" in cleaned:
        cleaned = cleaned[cleaned.index("{"):]
    if "}" in cleaned:
        cleaned = cleaned[:cleaned.rindex("}") + 1]
    try:
        data = json.loads(cleaned)
        deals = data.get("deals", [])
        return [d for d in deals if d.get("titel") and d.get("url")]
    except json.JSONDecodeError:
        pass
    print("  [diag] JSON unvollständig -> Einzel-Rettung.")
    deals = []
    for match in re.finditer(r"\{[^{}]*\}", cleaned):
        try:
            d = json.loads(match.group(0))
            if d.get("titel") and d.get("url"):
                deals.append(d)
        except json.JSONDecodeError:
            continue
    print(f"  [diag] Rettung ergab {len(deals)} Deals.")
    return deals

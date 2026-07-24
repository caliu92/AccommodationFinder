# Konzept v2: Geschmacksprofil als Match-Score (statt Ausschlussfilter)

> **Input für Claude Code.** Ersetzt die bisherige Geschmacksprofil-Umsetzung im
> **Such-Agenten** (`agent.py`, `config.py`, `main.py`, `mailer.py`).
> Lies zuerst `CLAUDE.md` und die bestehenden Module.
>
> **WICHTIG — Warum diese Neufassung:** Die erste Umsetzung nutzte das
> Geschmacksprofil als **harten Filter** (Pool = Pflicht, `passt_zum_geschmack`
> = K.-o.). Folge: Der Agent fand über Tage **nichts mehr** — weil sich Pool,
> „klein/modern" etc. über eine Websuche kaum hart bestätigen lassen und alles
> Unklare weggefiltert wurde. Diese Fassung dreht das Prinzip um:
> **Das Geschmacksprofil ist ein Ziel-/Idealbild („Perfect Match"), gegen das
> jedes Angebot per Score gemessen wird. Abweichungen sind erlaubt und
> erwünscht — sie senken nur den Score, sie schließen nicht aus.**

---

## 1. Grundprinzip

- Es gibt **genau EIN hartes K.-o.-Kriterium**: weniger als 2 Schlafzimmer —
  und auch das **nur bei bestätigtem Verstoß** (siehe §3).
- Alles andere (Pool, Küche, Größe/Stil, Lage, Preis) fließt **gewichtet** in
  einen **Match-Score 0–100** ein: „Wie nah ist dieses Angebot am Perfect Match?"
- **„Unklar" wird NIE bestraft** und führt NIE zum Ausschluss. Es wird neutral
  behandelt und für den Nutzer sichtbar markiert. Grundsatz des Nutzers:
  *„lieber ein paar Nieten sehen als Treffer verpassen."*
- Der Nutzer entscheidet selbst anhand der **transparenten Aufschlüsselung**,
  ob ein Angebot trotz Abweichung interessant ist.

---

## 2. Der „Perfect Match" (Idealbild = 100 Punkte)

Eine Unterkunft, die ALLES erfüllt:
- mindestens 2 getrennte Schlafzimmer
- Pool vorhanden (Anlagenpool geteilt reicht)
- Küche in der Unterkunft
- klein/mittelgroß und modern (Chalet-/Boutique-/kleines-Resort-Gefühl),
  KEIN großer anonymer Hotelkomplex
- naturnahe, nicht-städtische, ruhige Lage
- Preisklasse € oder €€ (€€€ noch ok, aber schwächer)
- kinderfreundlich für 5- und 9-Jährige (Beispiel - eigene Kinderalter in mein_urlaub.py)
- im Zeitraum 01.–14.07.2027 (±2, Beispiel), mind. 7 Tage, 2 Erw. + 2 Kinder
- Anreise mit Auto aus PLZ 12345 (Beispiel) innerhalb ~9h

**Referenz-Unterkünfte (Stil-Anker, Few-shot — NICHT als Suchziel!):**
Diese definieren den **STIL**, ausdrücklich **NICHT die Geografie**:
1. **Camping Village Mediterraneo (bei Jesolo, IT)** — entspanntes,
   familientaugliches Ferienresort am Wasser mit Pool.
2. **Nagalu Hotel Garni (Fiss, AT)** — modernes, überschaubares, familiäres
   Hotel Garni mit alpinem Design.
3. **Hotel Alpin Chalet am Burgsee (Ladis, AT)** — moderner Chalet-/Boutique-Stil,
   naturnah am See.

**Abgeleitete DNA:** klein bis mittelgroß · modern/renoviert · Pool ·
familienfreundlich · naturnah, nicht-städtisch · gepflegt · Chalet-/Boutique-/
Resort-Gefühl statt anonymer Großkomplex.

**Landschaftsart ist bewusst OFFEN** — Berg, Meer, See, Weinregion, Therme,
Wald, Hügelland: alles willkommen. Der Agent darf sich NICHT auf Berg/Meer
fixieren (siehe §6).

---

## 3. Das einzige harte K.-o.-Kriterium

**Weniger als 2 Schlafzimmer → ausschließen.**

Aber ausschließlich bei **bestätigtem** Verstoß:
- `schlafzimmer == "weniger als 2 bestätigt"` → **raus**
- `schlafzimmer == "2+ bestätigt"` → volle Punkte
- `schlafzimmer == "unklar"` → **NICHT ausschließen**, neutral werten,
  sichtbar markieren

> Merksatz für die Implementierung: Nur *bestätigte* Verstöße filtern.
> „Unklar" fliegt niemals raus — das war der Fehler der ersten Fassung.

---

## 4. Score-Modell (0–100)

### Gewichtung (Reihenfolge vom Nutzer vorgegeben: wichtig → unwichtig)

| Kriterium | Gewicht | Volle Punkte wenn | Neutral (unklar) | 0 Punkte wenn |
|---|---|---|---|---|
| **2 Schlafzimmer** | 30 | „2+ bestätigt" | 15 (unklar) | (bestätigter Verstoß → K.-o., taucht gar nicht auf) |
| **Pool** | 25 | Pool bestätigt | 12 (unklar) | kein Pool bestätigt |
| **Küche** | 20 | Küche bestätigt | 10 (unklar) | keine Küche bestätigt |
| **Kein Großkomplex / klein & modern** | 15 | klein/modern | 7 (unklar) | großer Komplex bestätigt |
| **Lage naturnah, nicht städtisch** | 10 | naturnah/ruhig | 5 (unklar) | reine Innenstadtlage |

Summe = **100** bei Perfect Match.

### Zusätzliche Modifikatoren (nach der Basissumme)
- **Preisklasse:** € → +0 · €€ → +0 · €€€ → **−5** · €€€€ (über Budget) → **−25**
  (kein Ausschluss! Nur Abzug — der Nutzer will es sehen und selbst entscheiden.
  Der Abzug ist bewusst deutlich, damit „über Budget" nicht die echten Treffer
  verdrängt, aber sichtbar bleibt.)
- **Kinderfreundlichkeit** (Spielplatz, flacher Einstieg, Kinderbecken, Babybett):
  bis zu **+5** Bonus, wenn explizit erwähnt. Kein Abzug, wenn nicht erwähnt.
- **Stil-Ähnlichkeit zu den Referenzen** (Chalet/Boutique/modern-Signale):
  bis zu **+5** Bonus. Kein Abzug, wenn unklar.

Score wird am Ende auf **0–100 geklemmt** und **gerundet**.

### Referenz-Rechnungen (zur Verifikation der Implementierung)

Diese Werte müssen nach dem Umbau herauskommen — als Test verwenden:

| Fall | Erwarteter Score |
|---|---|
| Perfect Match (alles bestätigt, €€, Boni) | **100** |
| **ALLES unklar** (der kritische Fall!) | **50** → kommt durch ✅ |
| 2 SZ bestätigt, Rest unklar (Normalfall) | **65** → kommt durch ✅ |
| Gut, aber kein Pool bestätigt | **75** |
| Gut, aber Großkomplex + €€€ | **80** |
| Kein Pool, keine Küche, Großkomplex | **35** → fällt raus (< 40) |
| Über Budget €€€€, sonst perfekt | **75** |

> **Der wichtigste Test:** „Alles unklar" = 50 Punkte und wird GEZEIGT.
> Wenn dieser Fall wieder rausfliegt, ist die Implementierung falsch.

### Wichtige Regel für Claude im Prompt
> „Bewerte jedes Kriterium ehrlich mit erfüllt / nicht erfüllt / unklar.
> Rate NICHT. ‚Unklar' ist ein legitimes und erwünschtes Ergebnis und führt zu
> neutraler Teilpunktzahl — niemals zu einem Ausschluss.
> Ein Angebot mit vielen ‚unklar' bekommt einen mittleren Score und wird dem
> Nutzer trotzdem gezeigt."

---

## 5. Erweitertes JSON-Schema

Pro Deal zusätzlich zu den bestehenden Feldern:

```
"schlafzimmer":   "2+ bestätigt | weniger als 2 bestätigt | unklar",
"pool":           "bestätigt | kein Pool bestätigt | unklar",
"kueche":         "bestätigt | keine Küche bestätigt | unklar",
"groesse_stil":   "klein/modern | mittel | großer Komplex | unklar",
"lage":           "naturnah/ruhig | städtisch | unklar",
"landschaft":     "z.B. See / Weinregion / Therme / Berg / Meer / Hügelland",
"match_score":    0-100,
"score_details": {
    "schlafzimmer": 30, "pool": 12, "kueche": 20,
    "groesse_stil": 15, "lage": 5,
    "preis_modifikator": -5, "kinder_bonus": 3, "stil_bonus": 5
},
"unklar_punkte":  ["Pool nicht eindeutig belegt", "Küche unklar"],
"begruendung":    "1 kurzer Satz: warum dieser Score"
```

- `score_details` macht den Score **transparent nachvollziehbar** (Nutzerwunsch).
- `unklar_punkte` listet, was der Nutzer selbst nachprüfen sollte.

---

## 6. Anti-Fixierung & Streuung (unverändert wichtig)

Explizit im Prompt:
> „Fixiere dich NICHT auf Berg oder Meer. Die Referenzen zeigen den STIL, nicht
> die Region. Schlage bewusst auch andere Landschaften vor (Seen, Weinregionen,
> Thermengebiete, Wald, Hügelland). Decke pro Lauf mindestens 3 verschiedene
> Landschaftstypen ab."

Begründung: Ohne diesen Zwang tendiert die Suche zu Berg/Meer, weil dort die
meisten Familienpools ranken.

Referenzen **nie als Suchziel** verwenden — nie „suche das Nagalu Hotel Garni",
nur als Stil-Anker. Ihre Namen müssen in den Ergebnissen nicht vorkommen.

---

## 7. Umsetzung in `config.py`

```python
# Perfect-Match-Profil: Zielbild, gegen das gescort wird (KEIN Filter!)
GESCHMACK = {
    "hartes_ko": [
        "weniger als 2 Schlafzimmer (NUR bei bestätigtem Verstoß ausschließen)",
    ],
    "gewichte": {          # Summe 100 = Perfect Match
        "schlafzimmer": 30,
        "pool": 25,
        "kueche": 20,
        "groesse_stil": 15,   # klein/modern statt Großkomplex
        "lage": 10,           # naturnah/nicht städtisch
    },
    "unklar_faktor": 0.5,     # "unklar" => halbe Punkte, NIE Ausschluss
    "modifikatoren": {
        "preis_€€€": -5, "preis_€€€€": -25,
        "kinder_bonus_max": 5, "stil_bonus_max": 5,
    },
    "bewusst_offen": [
        "Landschaftsart egal - NICHT auf Berg/Meer fixieren",
        "Verpflegung egal (Selbstversorger oder Hotel)",
        "Trubel-Level egal (Resort oder ruhig)",
        "Aktivitäten egal - offen für alles",
        "neue vs. bekannte Region egal",
        "Anreisedauer innerhalb ~9h: kürzer kein Bonus, länger kein Malus",
    ],
    "referenzen": [
        {"name": "Camping Village Mediterraneo (bei Jesolo, IT)",
         "warum": "entspanntes familientaugliches Ferienresort am Wasser mit Pool"},
        {"name": "Nagalu Hotel Garni (Fiss, AT)",
         "warum": "modernes, überschaubares, familiäres Hotel Garni mit alpinem Design"},
        {"name": "Hotel Alpin Chalet am Burgsee (Ladis, AT)",
         "warum": "moderner Chalet-/Boutique-Stil, naturnah am See"},
    ],
}

# Niedrige Schwelle - Nutzer will lieber mehr sehen ("lieber ein paar Nieten")
MIN_MATCH_SCORE_FUER_MAIL = 40
```

**Hinweis für Claude Code:** Die alte Konstante `MIN_SCORE_FUER_MAIL` (1–10) und
die Felder `passt_zum_geschmack` / `score` durch das neue Score-Modell ersetzen
bzw. sauber migrieren. Keine Altlasten stehen lassen, die weiterhin hart filtern.

---

## 8. Umsetzung in `main.py` (Filter — bewusst minimal!)

Nur noch **zwei** Filter:
1. **K.-o.:** `schlafzimmer == "weniger als 2 bestätigt"` → raus.
2. **Score-Schwelle:** `match_score < MIN_MATCH_SCORE_FUER_MAIL` (40) → raus.

**Alles andere bleibt drin** — auch €€€€, auch „kein Pool bestätigt", auch
viele „unklar". Der Nutzer will sie sehen und selbst entscheiden.

Sortierung: `match_score` absteigend.

> **Explizit NICHT mehr filtern:** kein `passt_zum_geschmack`-Filter, kein
> Pool-Pflichtfilter, kein Preisklassen-Ausschluss. Das war die Ursache für
> „findet nichts mehr".

---

## 9. Umsetzung in `mailer.py` (Transparenz — Nutzerwunsch)

Pro Deal sichtbar machen:
- **Match-Score prominent**, z.B. `82/100` mit Farbbalken
  (≥80 grün · 60–79 blau · 40–59 gelb).
- **Kriterien-Zeile mit Symbolen**, damit der Nutzer sofort sieht, was fehlt:
  `🛏 2 SZ ✓ · 🏊 Pool ? · 🍳 Küche ✓ · 🏡 klein/modern ✓ · 🌲 naturnah ✓`
  (✓ = bestätigt, ✗ = nicht erfüllt, ? = unklar)
- **`unklar_punkte`** als kleiner grauer Hinweis: „Selbst prüfen: Pool, Küche".
- **Landschaftstyp** anzeigen (macht die Streuung sichtbar).
- Preisklasse + Preisindikation wie bisher.

Optional (nice-to-have): zwei Rubriken
- **„Nah am Perfect Match"** (Score ≥ 70)
- **„Interessant, mit Abstrichen"** (Score 40–69)
Damit sieht der Nutzer sofort die Top-Kandidaten, verliert aber die
Grenzfälle nicht.

---

## 10. Duplikate — unverändert

Der Nutzer will jede Unterkunft **nur EINMAL gemeldet** bekommen.
→ Bestehende Duplikaterkennung (`storage.py`, Fingerprint) **unverändert lassen**.
Keine Wiedervorlage, keine erneute Meldung bei Score-Änderung.

**Hinweis:** Wenn nach dem Umbau mehrere Läufe „nichts Neues" liefern, sind das
höchstwahrscheinlich Duplikate früherer Läufe — nicht der Filter. Zur
Verifikation die `[diag]`-Zeilen prüfen (siehe §11).

---

## 11. Diagnose-Logging (zur Fehlersuche behalten/erweitern)

`[diag]`-Zeilen sollen unterscheidbar machen, WO Treffer verloren gehen:
```
[diag] X Kandidaten von Claude erhalten
[diag] Y nach K.-o.-Filter (bestätigt <2 Schlafzimmer)
[diag] Z nach Score-Schwelle (>= 40)
[diag] N davon sind NEU (Rest = Duplikate)
[diag] Score-Verteilung: z.B. [82, 71, 64, 55, 41]
```
Die **Score-Verteilung** ist wichtig: Sie zeigt, ob die Schwelle 40 sinnvoll ist
oder ob systematisch zu niedrig gescort wird.

---

## 12. Ehrliche Grenzen

- **„Modern"/„klein" ist über Websuche schwer messbar** — Annäherung über
  Textsignale (renoviert, Design, Chalet, Boutique, Zimmeranzahl). Bei
  Unsicherheit `"unklar"` setzen, NICHT raten. Das kostet nur Teilpunkte.
- **Pool/Küche** sind oft nicht eindeutig belegt → `"unklar"` ist der Normalfall,
  kein Fehler. Deshalb darf „unklar" niemals ausschließen.
- Ein Angebot mit lauter „unklar" landet bei ~50 Punkten → wird gezeigt,
  mit klarem „Selbst prüfen"-Hinweis. Genau so gewollt.

---

## 13. Definition of Done

- [ ] `GESCHMACK` in config.py als **Score-Modell** (nicht als Filter).
- [ ] `MIN_MATCH_SCORE_FUER_MAIL = 40`; alte `MIN_SCORE_FUER_MAIL`/
      `passt_zum_geschmack`-Logik entfernt.
- [ ] agent.py-Prompt: Perfect Match + Referenzen als Few-shot +
      Anti-Berg/Meer-Fixierung + „unklar ist erlaubt und wird nicht bestraft".
- [ ] JSON mit `match_score`, `score_details`, `unklar_punkte` und den
      Einzelkriterien (schlafzimmer/pool/kueche/groesse_stil/lage/landschaft).
- [ ] main.py filtert NUR: bestätigt <2 SZ, und Score < 40. Sonst nichts.
- [ ] mailer.py zeigt Score, Kriterien-Symbolzeile (✓/✗/?), unklar_punkte,
      Landschaft; sortiert nach Score.
- [ ] `[diag]`-Logging inkl. Score-Verteilung.
- [ ] Duplikatlogik unverändert (nur einmal melden).
- [ ] **Testlauf zeigt wieder Treffer** (das war das Kernproblem) — und zwar
      auch solche mit „unklar"-Kriterien.
- [ ] CLAUDE.md aktualisiert (Score-Modell statt Filter dokumentieren).

---

## 14. Erster Prompt-Vorschlag für Claude Code

> „Lies CLAUDE.md und die Module. Setze KONZEPT_geschmacksprofil_v2.md um: Das
> Geschmacksprofil wird von einem harten Filter zu einem Match-Score (0–100)
> umgebaut. WICHTIG: Der Agent findet aktuell nichts mehr, weil ‚unklar'
> weggefiltert wird — das muss weg. Nur noch EIN K.-o. (bestätigt weniger als 2
> Schlafzimmer) und die Score-Schwelle 40. Baue zuerst config.py und agent.py um,
> mach dann einen Testlauf und zeig mir die Score-Verteilung sowie 5 Beispiel-
> Treffer mit score_details, bevor du mailer.py anpasst. Ich will sehen, dass
> wieder Treffer durchkommen und dass die Gewichtung sinnvoll greift.“

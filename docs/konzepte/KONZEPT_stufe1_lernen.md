# Konzept: Stufe 1 — Gedächtnis & Lernen (Feedback-Schleife + Selbstdiagnose)

> **Input für Claude Code.** Erweitert den bestehenden **Such-Agenten**
> (`agent.py`, `config.py`, `main.py`, `mailer.py`, `storage.py`).
> Lies zuerst `CLAUDE.md` und die Module.
>
> **Voraussetzung:** `KONZEPT_geschmacksprofil_v2.md` (Match-Score 0–100) ist
> umgesetzt. Dieses Konzept baut darauf auf und nutzt `match_score`,
> `score_details` und die Einzelkriterien.
>
> **Ziel:** Der Agent lernt aus den Reaktionen des Nutzers, statt bei jedem Lauf
> bei null zu starten. Zusätzlich erkennt er selbst, wenn er nichts mehr findet,
> und meldet das aktiv.

---

## 1. Ausgangslage & Ziel

**Heute:** Jeder Lauf startet ohne Gedächtnis. Der Nutzer muss seinen Geschmack
mühsam in Kriterien übersetzen (Gewichte in `config.py`). Wenn der Agent nichts
mehr findet, merkt er es nicht — der Nutzer muss selbst ins Log schauen
(genau das ist bereits passiert: mehrere Läufe „nichts Neues", Ursache waren zu
strenge Filter).

**Ziel dieses Bausteins:**
1. **Feedback-Schleife:** Der Nutzer gibt per Klick 👍/👎 (+ optional Grund) zu
   einzelnen Vorschlägen. Der Agent liest das beim nächsten Lauf und passt seine
   Bewertung an.
2. **Selbstdiagnose:** Der Agent führt Statistik über sich selbst und meldet
   aktiv, wenn er über mehrere Läufe nichts findet — inkl. Vermutung, woran es
   liegt.

**Nicht Teil dieses Konzepts:** Der Agent handelt weiterhin NICHT (verschickt
keine Anfragen, bucht nichts). Er informiert nur — jetzt aber lernend.

---

## 2. Feedback-Kanal: GitHub Issues (kein Server nötig)

**Warum Issues:** Der Agent läuft nur kurz in GitHub Actions und hat keinen
Server, der Klicks entgegennehmen könnte. GitHub Issues lösen das: Ein Link in
der Mail öffnet ein **vorausgefülltes Issue**, der Nutzer tippt einmal auf
„Submit" (geht am Handy mit der GitHub-App), und der Agent liest die Issues beim
nächsten Lauf per API.

### Mechanik
- In der Digest-Mail bekommt **jeder Treffer zwei Links**:
  - 👍 „Gefällt mir"
  - 👎 „Gefällt mir nicht"
- Beide sind **GitHub-Issue-Prefill-URLs** nach diesem Muster:
  ```
  https://github.com/caliu92/UrlausAgent/issues/new
     ?title=<URL-kodiert: FEEDBACK: 👍 {titel}>
     &labels=feedback
     &body=<URL-kodiert: strukturierter Body, siehe unten>
  ```
- Der Nutzer klickt, GitHub öffnet das fertige Issue, er kann optional noch einen
  **Grund** ergänzen und drückt „Submit new issue". Fertig.

### Issue-Body-Vorlage (vom Agent vorausgefüllt)
```
fingerprint: a1b2c3d4e5f6g7h8
titel: Chalet del Gelso
region: Tremosine sul Garda, Gardasee
bewertung: daumen_hoch        <-- bzw. daumen_runter
match_score: 82

grund: <!-- optional: kurz ergänzen, z.B. "zu groß", "Lage top" -->
```

- `fingerprint` = der bestehende Fingerprint aus `storage.py` → eindeutige
  Zuordnung zum Deal, auch wenn der Titel abweicht.
- `grund` ist ein **optionales Freitextfeld** — der Nutzer kann, muss aber nicht.
- Label `feedback` macht das Auslesen einfach und trennt es von echten Bugs.

### Verifizierte Beispiel-URL (getestet, funktioniert mit Umlauten/Emojis)
```python
from urllib.parse import quote
url = (f"https://github.com/{GITHUB_REPO}/issues/new"
       f"?title={quote('FEEDBACK: 👍 ' + titel)}"
       f"&labels=feedback"
       f"&body={quote(body)}")
```
Ergibt z.B. (gekürzt):
```
https://github.com/caliu92/UrlausAgent/issues/new?title=FEEDBACK%3A%20%F0%9F%91%8D%20Chalet%20del%20Gelso...&labels=feedback&body=fingerprint%3A%20a1b2...
```
Typische Länge ~380 Zeichen — unkritisch (GitHub verträgt ~8000).
**Wichtig:** `quote()` auf Titel UND Body anwenden, sonst brechen Umlaute,
Kommas und Zeilenumbrüche die URL.

### Auslesen durch den Agent
- Beim Lauf: GitHub-API abfragen nach Issues mit Label `feedback` und
  Status `open`.
- Auth: das in Actions ohnehin vorhandene `GITHUB_TOKEN`
  (`${{ secrets.GITHUB_TOKEN }}`) reicht für das eigene Repo — **kein neues
  Secret nötig**. Benötigte Permission im Workflow: `issues: write`.
- Jedes Issue parsen (Key-Value-Zeilen aus dem Body), in die DB schreiben,
  danach das Issue **schließen** (und ggf. mit Label `verarbeitet` versehen),
  damit es nicht doppelt gelesen wird.
- Robust: Wenn ein Issue nicht dem Format entspricht (Nutzer hat frei getippt),
  überspringen und im Log vermerken — nicht abstürzen.

---

## 3. Was der Agent aus dem Feedback lernt

### 3.1 Speichern
Neue Tabelle in der bestehenden DB (`deals.sqlite`):

```
Tabelle feedback:
  fingerprint   TEXT PRIMARY KEY    -- Zuordnung zum Deal
  titel         TEXT
  region        TEXT
  landschaft    TEXT                -- aus dem Deal übernommen
  bewertung     TEXT                -- 'daumen_hoch' | 'daumen_runter'
  grund         TEXT                -- optionaler Freitext
  match_score   INTEGER             -- was der Agent damals vergab
  merkmale_json TEXT                -- Snapshot: pool/kueche/groesse_stil/lage/preisklasse
  erfasst_am    TEXT
  issue_nummer  INTEGER
```

- `merkmale_json` ist entscheidend: Es speichert, **welche Eigenschaften** das
  bewertete Objekt hatte. Nur so kann der Agent Muster erkennen
  („3× 👍 bei landschaft=See", „2× 👎 bei groesse_stil=großer Komplex").

### 3.2 Auswerten (Muster erkennen)
Vor der Suche liest der Agent das gesammelte Feedback und erzeugt eine
**kompakte Lern-Zusammenfassung** für den Prompt. Zwei Wege — Claude Code soll
den einfacheren zuerst umsetzen:

**Variante A (bevorzugt, simpel & robust):**
Die letzten ~20 Feedback-Einträge werden als **Few-shot-Beispiele** direkt in den
Prompt gegeben:
```
GELERNT AUS BISHERIGEM FEEDBACK DES NUTZERS:
👍 gefiel: "Chalet del Gelso" (See, klein/modern, Pool) – Grund: "Lage top"
👍 gefiel: "Residence Sonnenhof" (Weinregion, klein/modern, Pool)
👎 gefiel NICHT: "Hotel Riva Grande" (Meer, großer Komplex) – Grund: "zu groß"
👎 gefiel NICHT: "Camping Bella" (See, mittel) – Grund: "zu einfach"

Berücksichtige diese Vorlieben bei der Bewertung. Objekte, die den 👍-Beispielen
ähneln, höher bewerten; solche, die den 👎-Beispielen ähneln, niedriger.
```
Das nutzt genau das, was LLMs gut können: Muster aus Beispielen ziehen.

**Variante B (später, optional):**
Statistische Auswertung → automatische Anpassung der Gewichte in `config.py`
(z.B. „bei 5× 👎 wegen ‚zu groß' → Gewicht `groesse_stil` von 15 auf 25
anheben"). **Bewusst NICHT in V1** — zu viel Automatik, schwer nachvollziehbar,
Risiko von Aufschaukeln bei wenigen Datenpunkten.

### 3.3 Anwenden im Score
- Der Agent erhält die Lern-Zusammenfassung im Prompt (siehe 3.2 Variante A).
- Neues optionales Score-Element: **`feedback_bonus`** von **−10 bis +10**,
  das Claude vergibt, wenn ein Objekt stark den 👍- bzw. 👎-Beispielen ähnelt.
- Wird in `score_details` transparent ausgewiesen (Nutzer sieht, dass gelernt
  wurde) und im Feld `feedback_begruendung` kurz erklärt, z.B.:
  „ähnelt Chalet del Gelso, das dir gefiel".
- **Wichtig:** Der Bonus verändert nur den Score, er filtert NIE aus. Das
  Grundprinzip aus v2 (nichts ausschließen bei Unsicherheit) gilt weiter.

---

## 4. Selbstdiagnose

### 4.1 Lauf-Statistik speichern
Neue Tabelle:
```
Tabelle laeufe:
  lauf_id        INTEGER PRIMARY KEY AUTOINCREMENT
  gelaufen_am    TEXT
  kandidaten     INTEGER      -- von Claude erhalten
  nach_ko        INTEGER      -- nach K.-o.-Filter (<2 Schlafzimmer)
  nach_score     INTEGER      -- nach Score-Schwelle
  neu_gemeldet   INTEGER      -- tatsächlich in die Mail
  score_max      INTEGER
  score_median   INTEGER
  fehler         TEXT         -- falls ein Fehler auftrat
```

### 4.2 Diagnose-Regeln (bei jedem Lauf prüfen)
Der Agent wertet die letzten Läufe aus und erkennt Muster:

| Bedingung | Diagnose | Vorschlag in der Mail |
|---|---|---|
| 3 Läufe in Folge `neu_gemeldet == 0` **und** `nach_score > 0` | „Ich finde Treffer, aber alles sind Duplikate" | „Die Suche liefert immer dieselben Objekte. Soll ich neue Regionen/Quellen probieren?" |
| 3 Läufe in Folge `nach_score == 0` **und** `kandidaten > 0` | „Meine Score-Schwelle ist zu hoch" | „Alle Kandidaten lagen unter {MIN_MATCH_SCORE}. Höchster Score war {score_max}. Schwelle senken?" |
| 3 Läufe in Folge `kandidaten == 0` | „Die Suche selbst liefert nichts" | „Die Websuche findet keine Kandidaten — evtl. Suchstrategie/Regionen anpassen." |
| 3 Läufe in Folge `nach_ko == 0` | „Der K.-o.-Filter schneidet alles weg" | „Alle Objekte hatten bestätigt <2 Schlafzimmer — ungewöhnlich, bitte prüfen." |
| `fehler` in letztem Lauf gesetzt | „Technischer Fehler" | Fehlermeldung kurz zeigen. |

### 4.3 Ausgabe der Diagnose
- Wenn eine Regel greift: ein **auffälliger Hinweiskasten oben in der Digest-Mail**
  (gelber/oranger Kasten), z.B.:
  > ⚠️ **Selbstdiagnose:** Ich habe an 3 Tagen in Folge nichts Neues gemeldet.
  > Ich finde zwar Kandidaten (Ø 8/Lauf), aber alle waren Duplikate früherer
  > Läufe. Vorschlag: neue Regionen oder Quellen einbeziehen.
- Zusätzlich im Log als `[diag]`-Zeile.
- **Der Agent ändert NICHTS selbstständig** — er meldet nur und schlägt vor.
  Die Entscheidung bleibt beim Nutzer. (Bewusste Grenze: keine
  Selbstumkonfiguration in V1.)

---

## 5. Umsetzung im Detail

### config.py
```python
# Feedback-Schleife
FEEDBACK_AKTIV = True
GITHUB_REPO = "caliu92/UrlausAgent"          # für Issue-Links
FEEDBACK_LABEL = "feedback"
FEEDBACK_BEISPIELE_IM_PROMPT = 20            # letzte N Einträge als Few-shot
FEEDBACK_BONUS_MAX = 10                      # +/- Punkte im Score

# Selbstdiagnose
DIAGNOSE_AKTIV = True
DIAGNOSE_FENSTER_LAEUFE = 3                  # ab wie vielen Läufen in Folge warnen
```

### storage.py
- Tabellen `feedback` und `laeufe` anlegen (siehe §3.1 und §4.1).
- Funktionen: `feedback_speichern(...)`, `feedback_letzte(n)`,
  `lauf_speichern(...)`, `laeufe_letzte(n)`.
- **Achtung Schema-Migration:** Es gibt bereits eine bestehende `deals.sqlite`.
  Neue Tabellen mit `CREATE TABLE IF NOT EXISTS` anlegen — die bestehende
  `deals`-Tabelle NICHT anfassen, damit die Duplikat-Historie erhalten bleibt.
  (Lektion aus dem Projekt: Schemaänderungen an bestehenden Tabellen erforderten
  bisher ein Löschen der DB — das soll hier vermieden werden.)

### feedback_reader.py (neu)
- Liest offene Issues mit Label `feedback` über die GitHub-API.
- Parst den Body (Key-Value-Zeilen), validiert, schreibt in DB.
- Schließt verarbeitete Issues (Kommentar optional: „✅ verarbeitet").
- Nutzt `GITHUB_TOKEN` aus der Umgebung; keine externen Abhängigkeiten nötig
  (Standard-`urllib` oder `requests`, falls schon vorhanden).

### agent.py
- Vor der Suche: `feedback_letzte(FEEDBACK_BEISPIELE_IM_PROMPT)` holen und als
  Lern-Zusammenfassung in den Prompt einbauen (§3.2 Variante A).
- JSON-Schema um `feedback_bonus` (int, −10..+10) und `feedback_begruendung`
  (kurzer Text) erweitern; in `score_details` aufnehmen.
- Prompt-Zusatz: „Berücksichtige die Vorlieben aus dem Feedback. Vergib
  feedback_bonus nur, wenn eine klare Ähnlichkeit zu einem 👍/👎-Beispiel
  besteht — sonst 0."

### main.py
- Ablauf neu: **Feedback lesen** → Suche → Bewertung → Filter → Speichern →
  **Lauf-Statistik schreiben** → **Diagnose prüfen** → Mail (inkl. evtl.
  Diagnose-Kasten).
- Diagnose-Ergebnis an `mailer.py` durchreichen.

### mailer.py
- Pro Deal die zwei Feedback-Links (👍/👎) rendern, korrekt **URL-kodiert**
  (`urllib.parse.quote`) — wichtig bei Umlauten/Leerzeichen in Titeln.
- Diagnose-Hinweiskasten oben, wenn vorhanden.
- Wenn `feedback_bonus != 0`: kleinen Hinweis anzeigen, z.B.
  „🧠 +7 – ähnelt einem Objekt, das dir gefiel".

### .github/workflows/daily.yml
- `permissions:` um `issues: write` erweitern (zum Lesen und Schließen).
- `GITHUB_TOKEN` als env an den Python-Schritt durchreichen.

---

## 6. Ehrliche Grenzen & Risiken

- **Feedback braucht Zeit.** Mit 2–3 Bewertungen lernt der Agent praktisch
  nichts. Sinnvoll wird es ab ca. 10–15 Rückmeldungen. Erwartung entsprechend
  setzen — nicht nach 2 Tagen enttäuscht sein.
- **Kein Aufschaukeln zulassen.** Deshalb in V1 **keine automatische
  Gewichtsanpassung** (Variante B), sondern nur Few-shot im Prompt. Der Agent
  soll sich nicht selbst in eine Ecke optimieren.
- **`feedback_bonus` ist gedeckelt** (±10 von 100). Er soll nachjustieren, nicht
  dominieren. Die harten Kriterien (2 Schlafzimmer) und die Gewichtung aus v2
  bleiben führend.
- **Issue-Links sind ein Klick + ein Tap.** Etwas mehr Reibung als ein echter
  1-Klick-Link, aber die einzige serverlose Lösung. Erwartung: der Nutzer
  bewertet nicht jeden Treffer, sondern die Ausreißer (sehr gut / sehr schlecht)
  — das reicht völlig.
- **Selbstdiagnose ist regelbasiert**, kein Zauber. Sie erkennt die Muster aus
  §4.2 — nicht jede denkbare Ursache. Bewusst simpel gehalten, damit sie
  verlässlich ist.
- **Privates Repo:** Issues sind nicht öffentlich sichtbar. Trotzdem: keine
  sensiblen Daten in Issue-Bodies (nur Titel/Region/Score — unkritisch).

---

## 7. Definition of Done

- [ ] Tabellen `feedback` und `laeufe` in `storage.py` (via
      `CREATE TABLE IF NOT EXISTS`, bestehende `deals`-Tabelle unangetastet).
- [ ] `feedback_reader.py` liest Issues mit Label `feedback`, parst, speichert,
      schließt sie; robust bei Formatabweichungen.
- [ ] Workflow hat `issues: write` und reicht `GITHUB_TOKEN` durch.
- [ ] `mailer.py` rendert pro Deal 👍/👎-Issue-Links, korrekt URL-kodiert.
- [ ] `agent.py` bekommt die letzten N Feedback-Einträge als Few-shot in den
      Prompt und vergibt `feedback_bonus` (−10..+10), sichtbar in `score_details`.
- [ ] `main.py` schreibt Lauf-Statistik und prüft die Diagnose-Regeln.
- [ ] Diagnose-Kasten erscheint in der Mail, wenn eine Regel greift.
- [ ] Agent ändert nichts selbstständig — er meldet und schlägt nur vor.
- [ ] Testlauf: Ein manuell angelegtes Feedback-Issue wird gelesen, gespeichert,
      geschlossen — und taucht beim nächsten Lauf im Prompt auf.
- [ ] `CLAUDE.md` um Feedback-Schleife und Selbstdiagnose ergänzt.

---

## 8. Erster Prompt-Vorschlag für Claude Code

> „Lies CLAUDE.md und die Module. Setze KONZEPT_stufe1_lernen.md um.
> Baue in dieser Reihenfolge, damit ich zwischendurch prüfen kann:
> 1) storage.py: neue Tabellen feedback + laeufe (CREATE TABLE IF NOT EXISTS,
>    bestehende deals-Tabelle NICHT anfassen).
> 2) mailer.py: 👍/👎-Issue-Links pro Deal, korrekt URL-kodiert — zeig mir eine
>    Beispiel-URL, damit ich sie einmal manuell durchklicken kann.
> 3) feedback_reader.py + Workflow-Permission issues: write. Dann Testlauf:
>    Ich lege ein Feedback-Issue an, du liest es aus und zeigst mir den
>    DB-Inhalt.
> 4) agent.py: Feedback als Few-shot in den Prompt + feedback_bonus im Score.
> 5) main.py + Diagnose-Regeln + Diagnose-Kasten in der Mail.
> Wichtig: feedback_bonus darf nur den Score verschieben, niemals ausschließen.
> Keine automatische Gewichtsanpassung — der Agent meldet und schlägt vor,
> ändert aber nichts selbst.“

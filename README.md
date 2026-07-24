# Urlaubs-Agent

Autonomer Agent, der **täglich** nach passenden Familien-Urlaubsangeboten sucht,
sie mit Claude bewertet und dir einen **Mail-Digest** schickt.

**Neu hier und willst deine eigene Instanz einrichten?** → [SETUP.md](SETUP.md)
führt dich in 5 Schritten durch, ganz ohne Terminal.

## Scope (deine Eckdaten, in `mein_urlaub.py`)
Alles unten ist bei einer eigenen Instanz frei konfigurierbar — das sind nur
die mitgelieferten Standardwerte:
- Ab PLZ 12345 (Beispiel), **nur mit Auto**, Richtung Süden, bis ~9 Std Fahrt
- Zeitraum **01.–14.07.2027 (±2 Tage)** (Beispiel), mindestens 7 Tage
- **2 Erwachsene + 2 Kinder** (5 & 9 J., Beispiel)
- **Zwingend mind. 2 Schlafzimmer**
- Bis **2700 €** gesamt
- Bewertung nach **Kinderfreundlichkeit** u. Preis-Leistung
- Läuft **1× täglich**, Mail-Digest immer (auch "nichts Neues")

## Architektur
```
main.py         -> Orchestrierung
agent.py        -> Claude API + Websuche + Bewertung (JSON)
storage.py      -> SQLite, Duplikaterkennung (kein Deal doppelt)
mailer.py       -> HTML-Mail-Digest
mein_urlaub.py  -> DEINE Reisedaten - hier anpassen, siehe SETUP.md
config.py       -> interne Verdrahtung, i.d.R. nicht anfassen
docs/index.html -> Generator-Seite, erzeugt den Inhalt für mein_urlaub.py
.github/workflows/daily.yml -> täglicher Cron
```

## Einrichtung (einmalig)

Ausführliche, geführte Anleitung für Ersteinrichtung: [SETUP.md](SETUP.md).
Kurzfassung:

1. Repo per "Use this template" übernehmen.
2. Anthropic API-Key + SMTP-Zugang (z.B. Gmail-App-Passwort) besorgen.
3. Als GitHub Secrets eintragen (Settings -> Secrets and variables -> Actions):

| Name | Wert |
|---|---|
| `ANTHROPIC_API_KEY` | dein Key |
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_PORT` | `587` |
| `SMTP_USER` | deine.mail@gmail.com |
| `SMTP_PASS` | 16-stelliges App-Passwort |
| `MAIL_AN` | wohin der Digest soll |

4. `mein_urlaub.py` mit deinen Eckdaten füllen (per Generator-Seite oder
   direkt im GitHub-Web-Editor).
5. Actions-Tab -> "Urlaubs-Agent (täglich)" -> **Run workflow** zum Testen.
   Danach läuft er automatisch jeden Morgen.

## Lokal testen
```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...
export SMTP_HOST=smtp.gmail.com SMTP_PORT=587
export SMTP_USER=... SMTP_PASS=... MAIL_AN=...
python main.py
```

## Kosten
- Modell: Haiku (günstig)
- Websearch: max. 5 Suchen/Lauf (~$10/1000 -> ~1,5 €/Monat)
- Gesamt realistisch **< 5 €/Monat**. Hartes Limit im API-Dashboard setzen.

## Ehrliche Grenzen
- Es gibt keine kostenlose Universal-API für Reisedeals. Der Agent nutzt
  **Websuche** -> Treffer sind unstrukturiert, Claude interpretiert sie.
  Preise/Verfügbarkeit/Schlafzimmer **immer selbst gegenprüfen** vor Buchung.
- Qualität steigt, wenn du später konkrete Quellen/Portale ergänzt.

## Erweitern
- Konkrete Portale in `agent.py` (SYSTEM-Prompt) als bevorzugte Quellen nennen.
- Telegram-Push zusätzlich: kleines `notify_telegram.py`, in `main.py` einhängen.
- Bewertung mit Opus statt Haiku, wenn Budget erhöht wird (`MODELL` in `mein_urlaub.py`).

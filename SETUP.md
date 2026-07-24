# Setup — eigene Urlaubs-Agent-Instanz in 5 Schritten

Kein Terminal nötig, alles läuft über die GitHub-Weboberfläche. Rechne mit
15-20 Minuten, der größte Teil davon für Schritt 2 (externe Zugangsdaten).

## 1. Repo übernehmen

Oben auf dieser Seite auf **"Use this template" → "Create a new repository"**
klicken, eigenen Namen vergeben. Du bekommst eine komplett unabhängige Kopie
— kein Fork, keine Verbindung zum Original.

## 2. Zugangsdaten besorgen

Zwei Dinge brauchst du, die nichts mit GitHub zu tun haben:

**Anthropic API-Key** (für die KI-Bewertung der Angebote)
- Auf [console.anthropic.com](https://console.anthropic.com) registrieren.
- API-Key erstellen.
- **Wichtig:** unter Settings → Limits ein monatliches Ausgabenlimit setzen,
  z.B. 5 €. Der Agent nutzt bewusst ein günstiges Modell, damit die
  Kosten realistisch unter 5 €/Monat bleiben (siehe Abschnitt "Kosten" in
  README.md) — das Limit ist trotzdem eine sinnvolle Absicherung.

**SMTP-Zugang zum Mailversand** (Beispiel Gmail)
- Google-Konto → Sicherheit → 2-Faktor-Authentifizierung aktivieren
  (Voraussetzung für den nächsten Schritt).
- Google-Konto → Sicherheit → "App-Passwörter" → neues Passwort erzeugen.
- Das erzeugte 16-stellige Passwort ist **nicht** dein normales
  Google-Passwort — das trägst du gleich als `SMTP_PASS` ein.
- Andere Mail-Anbieter funktionieren auch, brauchen aber andere
  `SMTP_HOST`/`SMTP_PORT`-Werte (beim Anbieter nachschauen, Suchbegriff
  "SMTP-Zugangsdaten").

## 3. GitHub Secrets eintragen

In deiner neuen Repo-Kopie: **Settings → Secrets and variables → Actions →
New repository secret**, für jede Zeile einen Eintrag:

| Name | Wert |
|---|---|
| `ANTHROPIC_API_KEY` | dein Anthropic-Key aus Schritt 2 |
| `SMTP_HOST` | `smtp.gmail.com` (bei Gmail) |
| `SMTP_PORT` | `587` (bei Gmail) |
| `SMTP_USER` | deine.mail@gmail.com |
| `SMTP_PASS` | das 16-stellige App-Passwort aus Schritt 2 |
| `MAIL_AN` | die Mailadresse, an die der Digest gehen soll |

`GITHUB_TOKEN` musst du **nicht** anlegen — GitHub stellt das automatisch
bereit.

## 4. Deine Reisedaten eintragen

Öffne die **Generator-Seite**: https://caliu92.github.io/AccommodationFinder/

Dort füllst du ein einfaches Formular aus (Startort, Familie, Zeitraum,
Budget, Ausschlussregionen) und bekommst am Ende einen fertigen Textblock.

Dann in deiner Repo-Kopie:
1. Datei `mein_urlaub.py` öffnen.
2. Stift-Symbol ("Edit this file") klicken — öffnet einen Editor direkt im
   Browser, kein Download nötig.
3. Inhalt durch den generierten Textblock ersetzen (oder nur die Werte im
   Abschnitt "PFLICHT" anpassen, wenn du lieber direkt im Editor tippst —
   der Rest der Datei hat funktionierende Standardwerte).
4. Unten "Commit changes..." → "Commit directly to the main branch".

## 5. Testen

**Actions-Tab → "Urlaubs-Agent (täglich)" → "Run workflow"** (grüner Button,
manueller Start). Nach ein paar Minuten sollte die erste Mail ankommen — so
siehst du sofort, ob alles funktioniert, statt bis zum nächsten
automatischen Lauf zu warten.

Ab jetzt läuft der Agent täglich automatisch, kein weiteres Zutun nötig.

## Wenn etwas nicht klappt

- **Keine Mail, Actions-Lauf ist rot:** Actions-Tab → den fehlgeschlagenen
  Lauf öffnen → Logs lesen. Am häufigsten: ein Secret aus Schritt 3 fehlt
  oder ist falsch eingetippt — der Agent bricht dann mit einer klaren
  Meldung ab ("FEHLER: folgende Secrets fehlen..."), nicht mit einem
  kryptischen Fehler.
- **Mail kommt, aber leer/wenig Treffer:** normal in den ersten Tagen, siehe
  Selbstdiagnose-Hinweis in der Mail (falls vorhanden) sowie Abschnitt
  "Ehrliche Grenzen" in README.md.

# Konzept: Direktlink-Auflösung (Agent findet die Unterkunfts-Website selbst)

> **Input für Claude Code.** Kleine, eigenständige Erweiterung des bestehenden
> **Such-Agenten** (`agent.py`, `mailer.py`). Ziel: Der Nutzer soll NICHT selbst
> googeln müssen — der Agent soll für jeden Treffer aktiv versuchen, den echten
> Direktlink zur Unterkunfts-Website (oder zur konkreten Objekt-Detailseite)
> zu finden und zurückzugeben, statt nur auf eine Portal-Übersichtsseite zu
> verlinken.
> Lies zuerst `CLAUDE.md` und die bestehenden Module; nutze das bereits
> integrierte `web_fetch` und den vorhandenen pause_turn-Loop.

---

## 1. Problem

Der Agent kennt oft den **Namen** einer Unterkunft (aus dem Suchsnippet), hat
aber nur die **Portal-Übersichts-URL** (z.B. ferienwohnungen.de) statt der
konkreten Objektseite. In der Mail landet dann ein Portal-Link, auf dem der
Nutzer die Unterkunft gar nicht direkt sieht.

## 2. Ziel

Der Agent übernimmt das „Nachschlagen" selbst:
- Er sucht/verifiziert die konkrete Unterkunfts-Seite (eigene Website ODER
  konkrete Objekt-Detailseite auf einem Portal).
- Er gibt in der Mail einen **fertigen Direktlink** zurück — der Nutzer muss
  nicht selbst googeln.
- Wo es partout keinen Direktlink gibt (z.B. FeWo existiert nur auf dem Portal,
  oder Seite nicht lesbar), bleibt der Portal-Link mit **ehrlichem Vermerk**.

---

## 3. Ablauf (pro Treffer, budgetgedeckelt)

Für die besten Treffer eines Laufs (NICHT für alle — Kostendeckel!):

1. Agent hat: `titel` (Unterkunftsname), `region`, bisherige `url` (oft Portal).
2. Wenn die bisherige `url` bereits eine **konkrete Objektseite** ist
   (`link_typ == "Objektseite"`) → nichts tun, Direktlink steht schon.
3. Sonst: Agent führt eine gezielte Websuche nach `titel + region` durch
   (z.B. `"Chalet del Gelso" Tremosine Gardasee`).
4. Agent öffnet mit `web_fetch` das vielversprechendste Ergebnis und
   **verifiziert**, dass Name/Ort zur gesuchten Unterkunft passen
   (nicht blind das erste Ergebnis nehmen).
5. Wenn verifiziert → diese URL als `url` setzen, `link_typ = "Direktseite"`.
6. Wenn nicht eindeutig verifizierbar → bisherige (Portal-)`url` behalten,
   `link_typ = "nur Portalseite"`, ehrlich kennzeichnen.

---

## 4. Budget-Deckelung (wichtig, 5-€-Ziel)

- Direktlink-Auflösung nur für die **Top-N Treffer** nach Score (Vorschlag:
  `MAX_DIREKTLINK_AUFLOESUNG = 4` in `config.py`). Nicht für jeden Treffer.
- Jede Auflösung = 1 zusätzliche Suche + 1 web_fetch. Deshalb hart begrenzen.
- Die bestehenden `MAX_WEBSEARCHES_PRO_LAUF` / `MAX_WEBFETCHES_PRO_LAUF` ggf.
  leicht anheben ODER ein separates Kontingent für die Auflösung reservieren,
  damit die Haupt-Suche nicht verhungert. Claude Code soll hier die sinnvollste
  Aufteilung wählen und im Code kommentieren.

---

## 5. Umsetzung

### agent.py
- Nach der Haupt-Bewertung (JSON mit Deals liegt vor): für die Top-N Deals mit
  `link_typ != "Objektseite"` je einen Auflösungs-Schritt anstoßen.
- Kann als zweite, kompakte Claude-Runde je Deal umgesetzt werden ODER gebündelt.
  Empfehlung: pro Deal ein kleiner, fokussierter Aufruf mit web_search+web_fetch,
  System-Prompt: „Finde die offizielle Direktseite dieser konkreten Unterkunft.
  Verifiziere Name und Ort. Gib nur eine URL zurück, die du tatsächlich geöffnet
  und geprüft hast. Wenn keine eindeutige Direktseite existiert, gib 'keine'
  zurück."
- Ergebnis in den Deal zurückschreiben (`url`, `link_typ`).
- pause_turn-Loop und robustes Parsing wie gehabt.

### JSON-Feld
- Bestehendes `link_typ` erweitern um Wert `"Direktseite"`:
  `"Objektseite" | "Direktseite" | "nur Portalseite"`.

### mailer.py
- Link-Label je nach `link_typ`:
  - `Direktseite` / `Objektseite` → „Zur Unterkunft →" (ohne Warnhinweis)
  - `nur Portalseite` → „Zum Portal →" + kleiner grauer Vermerk
    „(keine Direktseite gefunden)".
- Optional zusätzlich (Fallback, kostenlos): einen Google-Such-Link aus
  `titel + region` generieren und als sekundären Link „🔍 Name suchen"
  anzeigen — für die Fälle, wo nur Portalseite gefunden wurde. (URL:
  `https://www.google.com/search?q=` + URL-kodierter `titel + " " + region`.)
  Das kostet nichts und gibt dem Nutzer immer einen zweiten Weg.

---

## 6. Ehrliche Grenzen (im Code/Prompt berücksichtigen)

- Manche FeWos haben **keine eigene Website** und existieren nur auf dem Portal
  → dann IST der Portal-Link korrekt; kein Direktlink erfinden.
- `web_fetch` kann **JavaScript-lastige** Buchungsseiten teils nicht lesen →
  Fallback auf Portalseite.
- Verifizierung ist eine Annäherung; bei mehrdeutigen Namen lieber ehrlich
  „nur Portalseite" als einen falschen Direktlink.
- Niemals eine URL zurückgeben, die nicht tatsächlich in Suche/Fetch vorkam
  (kein Raten/Konstruieren von URLs).

---

## 7. Definition of Done

- [ ] `MAX_DIREKTLINK_AUFLOESUNG` in config.py, Kostendeckel greift.
- [ ] agent.py löst für Top-N Deals den Direktlink auf, verifiziert Name/Ort.
- [ ] `link_typ` unterstützt "Direktseite" / "Objektseite" / "nur Portalseite".
- [ ] mailer.py zeigt passendes Link-Label + ehrlichen Vermerk bei Portalseite.
- [ ] Optionaler Google-Such-Fallback-Link bei "nur Portalseite".
- [ ] Kein URL-Raten; bei Unsicherheit Portalseite behalten.
- [ ] Testlauf zeigt für mehrere Treffer echte Direktseiten statt Portallinks.

---

## 8. Erster Prompt-Vorschlag für Claude Code

> „Lies CLAUDE.md und die Module. Setze KONZEPT_direktlink.md um: Der Agent soll
> für die Top-N Treffer selbst die Direktseite der Unterkunft finden und
> verifizieren (web_search + web_fetch), mit hartem Kostendeckel
> (MAX_DIREKTLINK_AUFLOESUNG). Erweitere link_typ und passe die Link-Anzeige in
> mailer.py an, inkl. ehrlichem Vermerk und optionalem Google-Fallback-Link.
> Mach danach einen Testlauf und zeig mir für 5 Treffer, welchen link_typ und
> welche URL herauskam.“

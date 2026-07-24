"""
Liest Nutzer-Feedback aus GitHub-Issues (Label config.FEEDBACK_LABEL), speichert
valide Einträge in der DB und schließt die Issues danach - siehe
docs/konzepte/KONZEPT_stufe1_lernen.md. Nutzt nur die Standardbibliothek (urllib), kein
neuer Dependency nötig.

Der Nutzer klickt in der Digest-Mail auf einen 👍/👎-Link (siehe mailer.py),
der ein vorausgefülltes GitHub-Issue öffnet. Dieses Modul liest solche Issues
beim nächsten Lauf, bevor main.py die neue Suche startet.
"""
import json
import urllib.error
import urllib.request

import config
import storage

_API_BASIS = "https://api.github.com"


def _api_request(pfad: str, methode: str = "GET", daten: dict | None = None):
    url = f"{_API_BASIS}{pfad}"
    body = json.dumps(daten).encode("utf-8") if daten is not None else None
    req = urllib.request.Request(url, data=body, method=methode)
    req.add_header("Authorization", f"Bearer {config.GITHUB_TOKEN}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "urlaubs-agent")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _offene_feedback_issues() -> list[dict]:
    pfad = (f"/repos/{config.GITHUB_REPO}/issues"
            f"?labels={config.FEEDBACK_LABEL}&state=open&per_page=50")
    return _api_request(pfad)


def _body_parsen(body: str) -> dict:
    """Parst die Key:Value-Zeilen aus dem Issue-Body. Unausgefüllte
    HTML-Kommentar-Platzhalter (z.B. beim optionalen "grund"-Feld) zählen als
    leer. Gibt ein leeres Dict zurück (statt zu werfen), wenn nichts
    Brauchbares gefunden wird - der Aufrufer entscheidet, ob das reicht."""
    werte = {}
    for zeile in (body or "").splitlines():
        zeile = zeile.strip()
        if not zeile or ":" not in zeile:
            continue
        schluessel, _, wert = zeile.partition(":")
        schluessel = schluessel.strip().lower()
        wert = wert.strip()
        if wert.startswith("<!--"):
            wert = ""
        if schluessel and wert:
            werte[schluessel] = wert
    return werte


def _issue_schliessen(nummer: int) -> None:
    try:
        _api_request(f"/repos/{config.GITHUB_REPO}/issues/{nummer}",
                      methode="PATCH", daten={"state": "closed"})
        _api_request(f"/repos/{config.GITHUB_REPO}/issues/{nummer}/comments",
                      methode="POST", daten={"body": "✅ verarbeitet"})
    except Exception as e:
        print(f"  [diag] Konnte Feedback-Issue #{nummer} nicht schließen: "
              f"{type(e).__name__}: {e}")


_MERKMAL_FELDER = ("pool", "kueche", "groesse_stil", "lage", "preisklasse")


def feedback_einlesen() -> int:
    """Liest offene Feedback-Issues, speichert valide Einträge in der DB und
    schließt sie. Gibt die Anzahl erfolgreich verarbeiteter Issues zurück.
    Robust: ein fehlerhaftes/leeres Issue überspringt nur dieses, kein
    Abbruch des gesamten Laufs."""
    if not config.FEEDBACK_AKTIV:
        return 0
    if not config.GITHUB_TOKEN:
        print("  [diag] Kein GITHUB_TOKEN gesetzt - Feedback-Einlesen übersprungen.")
        return 0

    try:
        issues = _offene_feedback_issues()
    except Exception as e:
        print(f"  [diag] FEHLER beim Abrufen der Feedback-Issues: {type(e).__name__}: {e}")
        return 0

    print(f"  [diag] {len(issues)} offene Feedback-Issue(s) gefunden.")
    verarbeitet = 0
    for issue in issues:
        nummer = issue.get("number")
        try:
            werte = _body_parsen(issue.get("body", ""))
            fingerprint = werte.get("fingerprint")
            bewertung = werte.get("bewertung")
            if not fingerprint or bewertung not in ("daumen_hoch", "daumen_runter"):
                print(f"  [diag] Issue #{nummer} hat kein gültiges Feedback-Format "
                      f"- übersprungen.")
                continue

            match_score = None
            if (werte.get("match_score") or "").isdigit():
                match_score = int(werte["match_score"])

            merkmale = {k: werte[k] for k in _MERKMAL_FELDER if k in werte}

            storage.feedback_speichern({
                "fingerprint": fingerprint,
                "titel": werte.get("titel"),
                "region": werte.get("region"),
                "landschaft": werte.get("landschaft"),
                "bewertung": bewertung,
                "grund": werte.get("grund"),
                "match_score": match_score,
                "merkmale": merkmale,
                "issue_nummer": nummer,
            })
            _issue_schliessen(nummer)
            verarbeitet += 1
        except Exception as e:
            print(f"  [diag] FEHLER bei Feedback-Issue #{nummer}: {type(e).__name__}: {e}")
            continue

    print(f"  [diag] {verarbeitet} Feedback-Issue(s) verarbeitet.")
    return verarbeitet

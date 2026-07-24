"""
Einstiegspunkt des Urlaubs-Agenten.
Wird täglich von GitHub Actions aufgerufen.

  Feedback lesen -> Suche+Fetch (Claude) -> Match-Score-Bewertung
  -> K.-o.-/Score-Filter -> Duplikatfilter -> Speichern
  -> Lauf-Statistik -> Selbstdiagnose -> Mail-Digest

Geschmacksprofil v2 (siehe docs/konzepte/KONZEPT_geschmacksprofil_v2.md): bewusst NUR zwei
Filter. Alles andere (Pool, Küche, Stil, Lage, Preis) ist keine Ausschlussfrage
mehr, sondern fließt in den Match-Score ein - Deals mit vielen "unklar" oder
sogar über Budget werden weiterhin gezeigt, nicht mehr hart rausgefiltert.

Stufe 1 - Lernen (siehe docs/konzepte/KONZEPT_stufe1_lernen.md): Der Agent liest vor der
Suche offene Feedback-Issues, merkt sich nach dem Lauf seine eigene Statistik
und erkennt per Selbstdiagnose, wenn er über mehrere Läufe hinweg nichts
Neues findet. Er ändert dabei NICHTS selbstständig - nur melden, nie handeln.
"""
import datetime as dt
import os
import statistics
import sys

import config
import storage
import agent
import feedback_reader
import mailer


def _secrets_pruefen() -> None:
    """Bricht mit einer klaren deutschen Meldung ab, wenn Pflicht-Secrets
    fehlen, statt tief in smtplib/Anthropic-SDK mit einem rohen Traceback
    abzustürzen - wichtig für Nutzer, die das Setup selbst zusammenklicken
    (siehe SETUP.md) und im Actions-Log sonst nur eine kryptische Exception
    sähen."""
    fehlend = []
    if not os.environ.get("ANTHROPIC_API_KEY"):
        fehlend.append("ANTHROPIC_API_KEY")
    if not config.SMTP_USER:
        fehlend.append("SMTP_USER")
    if not config.SMTP_PASS:
        fehlend.append("SMTP_PASS")
    if not config.MAIL_AN:
        fehlend.append("MAIL_AN")
    if fehlend:
        print("FEHLER: folgende Secrets fehlen oder sind leer: "
              f"{', '.join(fehlend)}")
        print("-> Repo-Settings -> Secrets and variables -> Actions, "
              "siehe SETUP.md Schritt 3.")
        sys.exit(1)


def _schon_heute_gelaufen() -> bool:
    """True, wenn heute bereits ein Lauf verzeichnet ist. Grund: daily.yml hat
    zwei Cron-Einträge (Winter-/Sommerzeit für 7 Uhr deutscher Zeit), UND
    GitHub Actions verzögert geplante Läufe teils um mehrere Stunden
    (dokumentiertes Verhalten, keine Garantie auf pünktliche Ausführung) - in
    der Praxis können dadurch an einem Tag beide Cron-Einträge feuern, oft
    Stunden nach der Zielzeit. Diese Prüfung verhindert dann einen doppelten
    Lauf/doppelte Mail, OHNE (wie zuvor) auf eine exakte Uhrzeit zu bestehen,
    die durch die Verzögerung ohnehin nie mehr getroffen wird. Gilt NUR für
    automatische Cron-Läufe - ein manueller Start (workflow_dispatch) läuft
    immer, egal was heute schon passiert ist (bewusster Fallback/Test-Weg)."""
    if os.environ.get("GITHUB_EVENT_NAME") != "schedule":
        return False
    letzte = storage.laeufe_letzte(1)
    if not letzte:
        return False
    gelaufen_am = letzte[0].get("gelaufen_am") or ""
    return gelaufen_am[:10] == dt.date.today().isoformat()


def _ist_ko(deal: dict) -> bool:
    """Das EINZIGE harte K.-o.-Kriterium: bestätigt weniger als MIND_SCHLAFZIMMER
    Schlafzimmer (config.SCHLAFZIMMER_NULL). "unklar" schließt NIEMALS aus (das
    war der Fehler der ersten Fassung - der Agent fand tagelang nichts, weil
    "unklar" weggefiltert wurde)."""
    return deal.get("schlafzimmer") == config.SCHLAFZIMMER_NULL


def _diagnose_pruefen(laeufe: list[dict]) -> str | None:
    """Prüft die letzten Läufe auf die Muster aus docs/konzepte/KONZEPT_stufe1_lernen.md §4.2.
    Gibt einen Diagnosetext zurück oder None, wenn nichts auffällt. Der Agent
    schlägt hier nur etwas vor - er ändert nie selbstständig etwas."""
    if not config.DIAGNOSE_AKTIV or not laeufe:
        return None

    letzter = laeufe[0]
    if letzter.get("fehler"):
        return f"Technischer Fehler im letzten Lauf: {letzter['fehler']}"

    fenster = config.DIAGNOSE_FENSTER_LAEUFE
    if len(laeufe) < fenster:
        return None
    letzte_n = laeufe[:fenster]

    if all((l.get("kandidaten") or 0) == 0 for l in letzte_n):
        return (f"Ich habe an {fenster} Läufen in Folge gar keine Kandidaten "
                f"gefunden. Die Websuche liefert nichts - evtl. Suchstrategie "
                f"oder Regionen anpassen?")

    if all((l.get("nach_ko") or 0) == 0 for l in letzte_n):
        return (f"An {fenster} Läufen in Folge hatten ALLE Objekte bestätigt "
                f"weniger als {config.MIND_SCHLAFZIMMER} Schlafzimmer - das ist "
                f"ungewöhnlich, bitte den K.-o.-Filter bzw. die Suchquellen prüfen.")

    if all((l.get("nach_score") or 0) == 0 and (l.get("kandidaten") or 0) > 0
           for l in letzte_n):
        max_score = max((l.get("score_max") or 0) for l in letzte_n)
        return (f"An {fenster} Läufen in Folge lagen alle Kandidaten unter der "
                f"Score-Schwelle ({config.MIN_MATCH_SCORE_FUER_MAIL}). Höchster "
                f"erreichter Score war {max_score}. Schwelle senken?")

    if all((l.get("neu_gemeldet") or 0) == 0 and (l.get("nach_score") or 0) > 0
           for l in letzte_n):
        return (f"An {fenster} Läufen in Folge waren alle Treffer über der "
                f"Score-Schwelle bereits bekannt (Duplikate). Die Suche liefert "
                f"immer dieselben Objekte - soll ich neue Regionen/Quellen "
                f"einbeziehen?")

    return None


def main():
    _secrets_pruefen()
    storage.init()

    if _schon_heute_gelaufen():
        print("Heute bereits gelaufen (zweiter, verspäteter Cron-Treffer durch "
              "Winter-/Sommerzeit-Dopplung oder GitHub-Verzögerung) - überspringe.")
        return

    print("Lese Feedback-Issues ...")
    feedback_reader.feedback_einlesen()

    fehler_text = None
    deals = []
    try:
        print("Suche Deals ...")
        deals = agent.finde_deals()
    except Exception as e:
        fehler_text = f"{type(e).__name__}: {e}"
        print(f"  [diag] FEHLER im Hauptlauf: {fehler_text}")

    print(f"{len(deals)} Kandidaten von Claude erhalten.")

    # Filter 1 (einziges K.-o.): bestätigt weniger als MIND_SCHLAFZIMMER Schlafzimmer
    relevante = [d for d in deals if not _ist_ko(d)]
    nach_ko = len(relevante)
    print(f"  [diag] {nach_ko} nach K.-o.-Filter "
          f"(bestätigt <{config.MIND_SCHLAFZIMMER} Schlafzimmer).")

    # Filter 2: Match-Score-Schwelle - niedrig angesetzt, der Nutzer sieht
    # lieber ein paar Nieten als einen echten Treffer zu verpassen.
    relevante = [d for d in relevante
                 if isinstance(d.get("match_score"), int)
                 and d["match_score"] >= config.MIN_MATCH_SCORE_FUER_MAIL]
    nach_score = len(relevante)
    print(f"{nach_score} nach K.-o.- und Score-Schwelle-Filter "
          f"(>= {config.MIN_MATCH_SCORE_FUER_MAIL}).")

    # Bester Match-Score zuerst
    relevante.sort(key=lambda d: d.get("match_score", 0), reverse=True)

    # Neue herausfiltern + speichern (Duplikaterkennung, unverändert)
    neue = []
    for d in relevante:
        if storage.speichern(d):
            neue.append(d)
    print(f"{len(neue)} davon sind NEU.")

    # Lauf-Statistik für die Selbstdiagnose speichern
    scores = [d["match_score"] for d in deals if isinstance(d.get("match_score"), int)]
    storage.lauf_speichern(
        kandidaten=len(deals),
        nach_ko=nach_ko,
        nach_score=nach_score,
        neu_gemeldet=len(neue),
        score_max=max(scores) if scores else None,
        score_median=round(statistics.median(scores)) if scores else None,
        fehler=fehler_text,
    )

    diagnose = _diagnose_pruefen(storage.laeufe_letzte(config.DIAGNOSE_FENSTER_LAEUFE))
    if diagnose:
        print(f"  [diag] Selbstdiagnose: {diagnose}")

    # Digest immer senden (auch wenn nichts Neues)
    if config.DIGEST_IMMER or neue:
        mailer.sende_digest(neue, anzahl_geprueft=len(deals), diagnose=diagnose)
    else:
        print("Nichts Neues und DIGEST_IMMER=False -> keine Mail.")


if __name__ == "__main__":
    main()

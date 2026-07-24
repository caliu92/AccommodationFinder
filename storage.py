"""
SQLite-Speicher. Merkt sich gesehene Unterkünfte, damit der Agent nicht jeden
Tag dieselben erneut meldet. Fingerprint = grobe Signatur (URL + Titel).

Zusätzlich (siehe docs/konzepte/KONZEPT_stufe1_lernen.md): Tabellen `feedback` (Nutzer-
Rückmeldungen aus GitHub-Issues) und `laeufe` (Lauf-Statistik für die
Selbstdiagnose). Neue Tabellen via CREATE TABLE IF NOT EXISTS - die
bestehende `deals`-Tabelle bleibt bewusst unangetastet.
"""
import sqlite3
import hashlib
import json
import datetime as dt
import config


def _conn():
    c = sqlite3.connect(config.DB_PFAD)
    c.row_factory = sqlite3.Row
    return c


def init():
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS deals (
                fingerprint TEXT PRIMARY KEY,
                titel        TEXT,
                region       TEXT,
                preisklasse  TEXT,
                preis_indikation TEXT,
                zeitraum     TEXT,
                url          TEXT,
                link_typ     TEXT,
                kontakt_email TEXT,
                match_score  INTEGER,
                begruendung  TEXT,
                schlafzimmer TEXT,
                zuerst_gesehen TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                fingerprint   TEXT PRIMARY KEY,
                titel         TEXT,
                region        TEXT,
                landschaft    TEXT,
                bewertung     TEXT,
                grund         TEXT,
                match_score   INTEGER,
                merkmale_json TEXT,
                erfasst_am    TEXT,
                issue_nummer  INTEGER
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS laeufe (
                lauf_id      INTEGER PRIMARY KEY AUTOINCREMENT,
                gelaufen_am  TEXT,
                kandidaten   INTEGER,
                nach_ko      INTEGER,
                nach_score   INTEGER,
                neu_gemeldet INTEGER,
                score_max    INTEGER,
                score_median INTEGER,
                fehler       TEXT
            )
        """)


def fingerprint(url: str, titel: str) -> str:
    basis = (url or "").strip().lower() + "|" + (titel or "").strip().lower()[:60]
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]


def ist_neu(fp: str) -> bool:
    with _conn() as c:
        row = c.execute("SELECT 1 FROM deals WHERE fingerprint = ?", (fp,)).fetchone()
        return row is None


def speichern(deal: dict) -> bool:
    """Speichert eine bewertete Unterkunft. True, wenn sie NEU war."""
    fp = fingerprint(deal.get("url", ""), deal.get("titel", ""))
    if not ist_neu(fp):
        return False
    with _conn() as c:
        c.execute("""
            INSERT OR IGNORE INTO deals
            (fingerprint, titel, region, preisklasse, preis_indikation, zeitraum,
             url, link_typ, kontakt_email, match_score, begruendung, schlafzimmer, zuerst_gesehen)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            fp,
            deal.get("titel"),
            deal.get("region"),
            deal.get("preisklasse"),
            deal.get("preis_indikation"),
            deal.get("zeitraum"),
            deal.get("url"),
            deal.get("link_typ"),
            deal.get("kontakt_email"),
            deal.get("match_score"),
            deal.get("begruendung"),
            deal.get("schlafzimmer"),
            dt.datetime.now().isoformat(timespec="seconds"),
        ))
    return True


def feedback_speichern(eintrag: dict) -> None:
    """Speichert/aktualisiert ein Feedback-Issue (INSERT OR REPLACE, damit ein
    erneutes Feedback zum selben Fingerprint die alte Bewertung ersetzt)."""
    with _conn() as c:
        c.execute("""
            INSERT OR REPLACE INTO feedback
            (fingerprint, titel, region, landschaft, bewertung, grund,
             match_score, merkmale_json, erfasst_am, issue_nummer)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (
            eintrag.get("fingerprint"),
            eintrag.get("titel"),
            eintrag.get("region"),
            eintrag.get("landschaft"),
            eintrag.get("bewertung"),
            eintrag.get("grund"),
            eintrag.get("match_score"),
            json.dumps(eintrag.get("merkmale") or {}, ensure_ascii=False),
            dt.datetime.now().isoformat(timespec="seconds"),
            eintrag.get("issue_nummer"),
        ))


def feedback_letzte(n: int) -> list[dict]:
    """Die letzten n Feedback-Einträge, neueste zuerst."""
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM feedback ORDER BY erfasst_am DESC LIMIT ?", (n,)
        ).fetchall()
        return [dict(r) for r in rows]


def lauf_speichern(kandidaten: int, nach_ko: int, nach_score: int,
                    neu_gemeldet: int, score_max: int | None,
                    score_median: int | None, fehler: str | None) -> None:
    """Schreibt die Statistik eines Laufs (Selbstdiagnose, siehe main.py)."""
    with _conn() as c:
        c.execute("""
            INSERT INTO laeufe
            (gelaufen_am, kandidaten, nach_ko, nach_score, neu_gemeldet,
             score_max, score_median, fehler)
            VALUES (?,?,?,?,?,?,?,?)
        """, (
            dt.datetime.now().isoformat(timespec="seconds"),
            kandidaten, nach_ko, nach_score, neu_gemeldet,
            score_max, score_median, fehler,
        ))


def laeufe_letzte(n: int) -> list[dict]:
    """Die letzten n Läufe, neuester zuerst (für die Selbstdiagnose)."""
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM laeufe ORDER BY lauf_id DESC LIMIT ?", (n,)
        ).fetchall()
        return [dict(r) for r in rows]

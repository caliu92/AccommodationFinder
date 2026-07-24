"""
Mail-Versand. HTML-Digest mit Preisklasse, Preisindikation und Direktlink.
"""
import smtplib
import datetime as dt
import urllib.parse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import config
import storage


def _klasse_farbe(sym: str) -> str:
    return {"€": "#16a34a", "€€": "#0891b2", "€€€": "#ca8a04", "€€€€": "#dc2626"}.get(sym, "#6b7280")


def _match_farbe(score) -> str:
    if not isinstance(score, int):
        return "#6b7280"
    if score >= 80:
        return "#16a34a"
    if score >= 60:
        return "#0891b2"
    if score >= 40:
        return "#ca8a04"
    return "#6b7280"


# (Feldname, Emoji, Label, Wert bei "voll", Wert bei "null") - für die
# Kriterien-Symbolzeile (✓/✗/?). Muss zu den Werten passen, die agent.py im
# JSON zurückgibt (siehe docs/konzepte/KONZEPT_geschmacksprofil_v2.md §5).
_KRITERIEN_ANZEIGE = [
    ("schlafzimmer", "🛏", f"{config.MIND_SCHLAFZIMMER} SZ", config.SCHLAFZIMMER_VOLL, config.SCHLAFZIMMER_NULL),
    ("pool", "🏊", "Pool", "bestätigt", "kein Pool bestätigt"),
    ("kueche", "🍳", "Küche", "bestätigt", "keine Küche bestätigt"),
    ("groesse_stil", "🏡", "klein/modern", "klein/modern", "großer Komplex"),
    ("lage", "🌲", "naturnah", "naturnah/ruhig", "städtisch"),
]

_DETAILS_LABEL = {
    "schlafzimmer": "SZ", "pool": "Pool", "kueche": "Küche",
    "groesse_stil": "Stil", "lage": "Lage", "preis_modifikator": "Preis",
    "kinder_bonus": "Kinder-Bonus", "stil_bonus": "Stil-Bonus",
}


def _kriterien_zeile(d: dict) -> str:
    teile = []
    for feld, emoji, label, voll, null in _KRITERIEN_ANZEIGE:
        wert = d.get(feld)
        symbol = "✓" if wert == voll else "✗" if wert == null else "?"
        teile.append(f"{emoji} {label} {symbol}")
    return " &nbsp;·&nbsp; ".join(teile)


def _details_zeile(d: dict) -> str:
    details = d.get("score_details") or {}
    teile = []
    for schluessel, wert in details.items():
        if not isinstance(wert, (int, float)) or wert == 0:
            continue
        name = _DETAILS_LABEL.get(schluessel, schluessel)
        vorzeichen = "+" if wert > 0 else ""
        teile.append(f"{name} {vorzeichen}{wert}")
    return " · ".join(teile)


def _zeitraum_basis(d: dict) -> str:
    r = config.REISE
    z = (d.get("zeitraum") or "").strip()
    ist_platzhalter = not z or "prüfen" in z.lower() or not any(c.isdigit() for c in z)
    return z if not ist_platzhalter else f"{r['zeitraum_von']} bis {r['zeitraum_bis']}"


def _anfrage_mailto(d: dict) -> str:
    r = config.REISE
    titel = d.get("titel", "die Unterkunft")
    region = d.get("region", "")
    zeitraum_basis = _zeitraum_basis(d)
    kinder = " und ".join(str(a) for a in r["kinder_alter"])
    ort = f' ({region})' if region else ""

    betreff = f"Anfrage: {titel} - Verfügbarkeit {zeitraum_basis}"
    body = (
        "Sehr geehrte Damen und Herren,\r\n\r\n"
        f'wir interessieren uns für "{titel}"{ort} und möchten gerne anfragen:\r\n\r\n'
        f"- Zeitraum: {zeitraum_basis} (wir sind zeitlich +/- {r['flex_tage']} Tage flexibel)\r\n"
        f"- Mindestaufenthalt: {r['min_dauer_tage']} Nächte\r\n"
        f"- Personen: {r['erwachsene']} Erwachsene + {len(r['kinder_alter'])} Kinder ({kinder} Jahre)\r\n"
        f"- Benötigt: mindestens {config.MIND_SCHLAFZIMMER} Schlafzimmer\r\n\r\n"
        "Ist die Unterkunft in diesem Zeitraum für uns verfügbar, und wie hoch wäre "
        "der Gesamtpreis? Falls der genannte Zeitraum nicht passt, freuen wir uns "
        "auch über einen Vorschlag für einen alternativen Zeitraum in der Nähe "
        "des genannten Zeitraums.\r\n\r\n"
        "Vielen Dank und freundliche Grüße"
    )

    email = (d.get("kontakt_email") or "").strip()
    query = f"subject={urllib.parse.quote(betreff, safe='')}&body={urllib.parse.quote(body, safe='')}"
    return f"mailto:{urllib.parse.quote(email, safe='')}?{query}"


def _feedback_issue_url(d: dict, positiv: bool) -> str:
    """GitHub-Issue-Prefill-URL für 👍/👎-Feedback (siehe
    docs/konzepte/KONZEPT_stufe1_lernen.md §2). fingerprint ist derselbe wie in storage.py,
    damit feedback_reader.py das Feedback eindeutig zuordnen kann. Alle
    Merkmale werden mit in den Body geschrieben, damit merkmale_json beim
    Einlesen befüllt werden kann (Grundlage für die Few-shot-Muster in
    agent._feedback_text)."""
    fp = storage.fingerprint(d.get("url", ""), d.get("titel", ""))
    emoji = "👍" if positiv else "👎"
    bewertung = "daumen_hoch" if positiv else "daumen_runter"
    titel = d.get("titel", "")

    body = (
        f"fingerprint: {fp}\r\n"
        f"titel: {titel}\r\n"
        f"region: {d.get('region','')}\r\n"
        f"landschaft: {d.get('landschaft','')}\r\n"
        f"bewertung: {bewertung}\r\n"
        f"match_score: {d.get('match_score','')}\r\n"
        f"pool: {d.get('pool','')}\r\n"
        f"kueche: {d.get('kueche','')}\r\n"
        f"groesse_stil: {d.get('groesse_stil','')}\r\n"
        f"lage: {d.get('lage','')}\r\n"
        f"preisklasse: {d.get('preisklasse','')}\r\n"
        f"\r\n"
        f'grund: <!-- optional: kurz ergänzen, z.B. "zu groß", "Lage top" -->'
    )
    titel_kodiert = urllib.parse.quote(f"FEEDBACK: {emoji} {titel}")
    body_kodiert = urllib.parse.quote(body)
    return (f"https://github.com/{config.GITHUB_REPO}/issues/new"
            f"?title={titel_kodiert}&labels={config.FEEDBACK_LABEL}&body={body_kodiert}")


def _deal_html(d: dict) -> str:
    match_score = d.get("match_score", "?")
    s_farbe = _match_farbe(match_score)
    klasse = d.get("preisklasse", "?")
    k_farbe = _klasse_farbe(klasse)
    link_typ = d.get("link_typ", "")
    nur_portal = link_typ == "nur Portalseite"
    link_label = "Zum Portal →" if nur_portal else "Zur Unterkunft →"
    link_hinweis = ' <span style="color:#9ca3af;font-size:12px;">' \
                   '(keine Direktseite gefunden)</span>' if nur_portal else ""

    google_fallback = ""
    if nur_portal:
        suchbegriff = urllib.parse.quote(f"{d.get('titel','')} {d.get('region','')}".strip())
        google_fallback = (
            f' <a href="https://www.google.com/search?q={suchbegriff}" '
            'style="display:inline-block;margin-top:8px;margin-left:12px;'
            'color:#6b7280;font-size:13px;">🔍 Name suchen</a>'
        )

    unklar_punkte = d.get("unklar_punkte") or []
    unklar_zeile = (
        f'<div style="color:#9ca3af;font-size:12px;margin-top:4px;">'
        f'Selbst prüfen: {", ".join(unklar_punkte)}</div>'
    ) if unklar_punkte else ""

    details_text = _details_zeile(d)
    details_zeile = (
        f'<div style="color:#9ca3af;font-size:11px;margin-top:4px;">'
        f'Details: {details_text}</div>'
    ) if details_text else ""

    feedback_bonus = (d.get("score_details") or {}).get("feedback_bonus", 0)
    feedback_zeile = ""
    if feedback_bonus:
        vorzeichen = "+" if feedback_bonus > 0 else ""
        begruendung = d.get("feedback_begruendung", "")
        zusatz = f" – {begruendung}" if begruendung else ""
        feedback_zeile = (
            f'<div style="color:#7c3aed;font-size:12px;margin-top:4px;">'
            f'🧠 {vorzeichen}{feedback_bonus}{zusatz}</div>'
        )

    feedback_links = ""
    if config.FEEDBACK_AKTIV:
        like_url = _feedback_issue_url(d, True)
        dislike_url = _feedback_issue_url(d, False)
        feedback_links = (
            f'<div style="margin-top:8px;">'
            f'<a href="{like_url}" style="color:#16a34a;font-size:13px;'
            f'text-decoration:none;">👍 Gefällt mir</a>&nbsp;&nbsp;'
            f'<a href="{dislike_url}" style="color:#dc2626;font-size:13px;'
            f'text-decoration:none;">👎 Gefällt mir nicht</a>'
            f'</div>'
        )

    return f"""
    <div style="border:1px solid #e5e7eb;border-radius:10px;padding:14px;margin:10px 0;">
      <div style="display:flex;justify-content:space-between;align-items:baseline;">
        <strong style="font-size:16px;">{d.get('titel','')}</strong>
        <span style="background:{s_farbe};color:#fff;border-radius:12px;padding:2px 10px;
                     font-size:13px;">{match_score}/100</span>
      </div>
      <div style="color:#374151;font-size:14px;margin-top:6px;">
        📍 {d.get('region','')} &nbsp;·&nbsp;
        <span style="color:{k_farbe};font-weight:600;">{klasse}</span>
        {d.get('preis_indikation','')}
      </div>
      <div style="color:#374151;font-size:13px;margin-top:4px;">{_kriterien_zeile(d)}</div>
      <div style="color:#6b7280;font-size:13px;margin-top:4px;">
        🏞️ {d.get('landschaft','unklar')} &nbsp;·&nbsp; 🗓 {d.get('zeitraum','')}
      </div>
      <div style="color:#4b5563;font-size:14px;margin-top:6px;">{d.get('begruendung','')}</div>
      {unklar_zeile}
      {details_zeile}
      {feedback_zeile}
      <a href="{d.get('url','#')}" style="display:inline-block;margin-top:8px;
         color:#2563eb;font-size:14px;">{link_label}</a>{link_hinweis}{google_fallback}
      <a href="{_anfrage_mailto(d)}" style="display:inline-block;margin-top:8px;margin-left:12px;
         background:#2563eb;color:#fff;border-radius:6px;padding:4px 12px;
         font-size:13px;text-decoration:none;">✉️ Anfrage senden</a>
      {'' if d.get('kontakt_email') else ' <span style="color:#9ca3af;font-size:12px;">(Adresse bitte manuell eintragen)</span>'}
      {feedback_links}
    </div>
    """


def _scope_zeile() -> str:
    r = config.REISE
    von = dt.date.fromisoformat(r["zeitraum_von"]).strftime("%d.%m.")
    bis = dt.date.fromisoformat(r["zeitraum_bis"]).strftime("%d.%m.")
    kinder_teil = f" + {len(r['kinder_alter'])} Kinder" if r["kinder_alter"] else ""
    return (f"{r['richtung']} · {r['anreise']} · {von}–{bis} (±{r['flex_tage']}) · "
            f"{r['erwachsene']} Erw.{kinder_teil} · {config.MIND_SCHLAFZIMMER} Schlafzimmer")


def sende_digest(neue_deals: list[dict], anzahl_geprueft: int, diagnose: str | None = None):
    heute = dt.date.today().strftime("%d.%m.%Y")

    diagnose_box = ""
    if diagnose:
        diagnose_box = (
            '<div style="background:#fef3c7;border:1px solid #f59e0b;border-radius:8px;'
            'padding:12px;margin-bottom:16px;color:#92400e;font-size:13px;">'
            f'⚠️ <strong>Selbstdiagnose:</strong> {diagnose}</div>'
        )

    if neue_deals:
        betreff = f"🏖 Urlaubs-Agent: {len(neue_deals)} neue Unterkünfte ({heute})"

        # Zwei Rubriken (siehe docs/konzepte/KONZEPT_geschmacksprofil_v2.md §9): Top-Kandidaten
        # zuerst sichtbar, Grenzfälle (40-69) gehen aber nicht verloren.
        nah = [d for d in neue_deals
               if isinstance(d.get("match_score"), int) and d["match_score"] >= 70]
        interessant = [d for d in neue_deals
                       if not (isinstance(d.get("match_score"), int) and d["match_score"] >= 70)]

        body = ""
        if nah:
            body += (f'<h3 style="margin:18px 0 4px;font-size:15px;">'
                     f'🎯 Nah am Perfect Match ({len(nah)})</h3>')
            body += "".join(_deal_html(d) for d in nah)
        if interessant:
            body += (f'<h3 style="margin:18px 0 4px;font-size:15px;">'
                     f'💡 Interessant, mit Abstrichen ({len(interessant)})</h3>')
            body += "".join(_deal_html(d) for d in interessant)

        intro = f"<p>Der Agent hat heute <strong>{len(neue_deals)} neue passende " \
                f"Unterkünfte</strong> gefunden (von {anzahl_geprueft} geprüften):</p>"
    else:
        betreff = f"🏖 Urlaubs-Agent: heute nichts Neues ({heute})"
        body = ""
        intro = f"<p>Heute keine neuen passenden Unterkünfte gefunden " \
                f"({anzahl_geprueft} geprüft). Der Agent sucht morgen wieder.</p>"

    html = f"""
    <div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;
                max-width:640px;margin:0 auto;color:#111827;">
      <h2 style="margin-bottom:4px;">Urlaubs-Unterkunfts-Digest</h2>
      <p style="color:#6b7280;font-size:13px;margin-top:0;">
        {_scope_zeile()}
      </p>
      <p style="color:#6b7280;font-size:12px;margin-top:0;">
        Match-Score: <span style="color:#16a34a;">≥80</span> Top-Treffer ·
        <span style="color:#0891b2;">60–79</span> gut ·
        <span style="color:#ca8a04;">40–59</span> mit Abstrichen
        &nbsp;·&nbsp; Preisklassen: <span style="color:#16a34a;">€</span> günstig ·
        <span style="color:#0891b2;">€€</span> mittel ·
        <span style="color:#ca8a04;">€€€</span> oberes Ende
      </p>
      {diagnose_box}
      {intro}
      {body}
      <hr style="border:none;border-top:1px solid #e5e7eb;margin:20px 0;">
      <p style="color:#9ca3af;font-size:12px;">
        Preise sind Indikationen, Verfügbarkeit im Zeitraum ist NICHT geprüft.
        "?"-Kriterien sind unklar (nicht bestätigt, aber auch nicht ausgeschlossen) -
        bitte selbst auf der Unterkunftsseite prüfen. Die KI kann sich irren.
      </p>
    </div>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = betreff
    msg["From"] = config.SMTP_USER
    msg["To"] = config.MAIL_AN
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as s:
        s.starttls()
        s.login(config.SMTP_USER, config.SMTP_PASS)
        s.sendmail(config.SMTP_USER, [config.MAIL_AN], msg.as_string())

    print(f"Mail gesendet an {config.MAIL_AN}: {betreff}")

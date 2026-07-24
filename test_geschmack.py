"""
Testskript für das Geschmacksprofil v2 (siehe docs/konzepte/KONZEPT_geschmacksprofil_v2.md).

Ruft agent.finde_deals() mit einem echten API-Call auf und zeigt die ersten
5 Treffer mit Match-Score und Score-Details - speichert NICHTS in
deals.sqlite und verschickt KEINE Mail.

Aufruf: python test_geschmack.py
(ANTHROPIC_API_KEY muss gesetzt sein, z.B. über eine lokale .env.)
"""
import agent


def main():
    deals = agent.finde_deals()
    print(f"\n{len(deals)} Deals insgesamt von Claude erhalten.")

    verteilung = sorted((d.get("match_score") for d in deals), reverse=True)
    print(f"Match-Score-Verteilung: {verteilung}\n")

    for i, d in enumerate(deals[:5], 1):
        print(f"=== Treffer {i}: {d.get('titel', '?')} - "
              f"Match-Score {d.get('match_score')}/100 ===")
        print(f"Region:              {d.get('region')}")
        print(f"Landschaft:          {d.get('landschaft')}")
        print(f"Preisklasse:         {d.get('preisklasse')}  ({d.get('preis_indikation')})")
        print(f"Zeitraum:            {d.get('zeitraum')}")
        print(f"Schlafzimmer:        {d.get('schlafzimmer')}")
        print(f"Pool:                {d.get('pool')}")
        print(f"Küche:               {d.get('kueche')}")
        print(f"Größe/Stil:          {d.get('groesse_stil')}")
        print(f"Lage:                {d.get('lage')}")
        print(f"Score-Details:       {d.get('score_details')}")
        print(f"Unklar-Punkte:       {d.get('unklar_punkte')}")
        print(f"Begründung:          {d.get('begruendung')}")
        print(f"URL:                 {d.get('url')}  ({d.get('link_typ')})")
        print(f"Kontakt-E-Mail:      {d.get('kontakt_email') or '(keine gefunden)'}")
        print()

    if len(deals) > 5:
        print(f"... ({len(deals) - 5} weitere Treffer nicht angezeigt)")


if __name__ == "__main__":
    main()

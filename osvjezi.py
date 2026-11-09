"""Osvjezavanje vijesti za sve klijente. Pokrece ga GitHub Actions dvaput dnevno.

Rucno pokretanje: GitHub -> Actions -> Osvjezavanje vijesti -> Run workflow.
"""
import sys

from core import (
    CLIENTS, krug_institucije, obradi_klijenta, razdoblje, rss_stavke,
    sb_log, sb_ocisti, sb_spremi_vijesti,
)


def main():
    start, today = razdoblje()
    print(f"Razdoblje: {start} – {today}")

    try:
        inst_sirove, inst_urls, inst_n = krug_institucije(start, today)
        print(f"Institucije: {len(inst_sirove)} stavki, {inst_n} pretraga")
        inst_greske = []
    except Exception as e:
        inst_sirove, inst_urls, inst_n = [], set(), 0
        inst_greske = [f"institucije: {e}"]
        print(f"Institucije GREŠKA: {e}")

    svi_rss, rss_greske = rss_stavke(start, today)
    print(f"RSS: {len(svi_rss)} stavki")

    neuspjeli = 0
    ukupno_pretraga = inst_n
    ukupno_gresaka = len(inst_greske)
    for i, key in enumerate(CLIENTS):
        try:
            stavke, stats, greske = obradi_klijenta(key, start, today, inst_sirove, inst_urls, svi_rss)
            if i == 0:  # pretrage institucija pribrajamo prvom klijentu da se vide u ukupnom broju
                stats["pretrage"] += inst_n
                greske = inst_greske + rss_greske + greske
            ukupno_pretraga += stats["pretrage"] - (inst_n if i == 0 else 0)
            ukupno_gresaka += len(greske)
            sb_spremi_vijesti(key, stavke)
            sb_log(key, stats, greske)
            print(f"{key}: pronađeno {stats['pronadeno']}, spremljeno {stats['spremljeno']}, "
                  f"pretraga {stats['pretrage']}, grešaka {len(greske)}")
            for g in greske:
                print(f"   - {g}")
        except Exception as e:
            neuspjeli += 1
            print(f"{key} GREŠKA: {e}")
            try:
                sb_log(key, {}, [str(e)])
            except Exception:
                pass

    try:
        sb_ocisti()
    except Exception as e:
        print(f"Čišćenje starih vijesti nije uspjelo: {e}")

    print(f"Ukupno pretraga: {ukupno_pretraga}")
    if neuspjeli == len(CLIENTS):
        sys.exit(1)
    if ukupno_pretraga == 0 and ukupno_gresaka:
        print("GREŠKA: nijedna web pretraga nije uspjela, provjerite greške iznad.")
        sys.exit(1)


if __name__ == "__main__":
    main()

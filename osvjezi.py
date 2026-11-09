"""Osvjezavanje vijesti za sve klijente. Pokrece ga GitHub Actions dvaput dnevno.

Rucno pokretanje: GitHub -> Actions -> Osvjezavanje vijesti -> Run workflow.
"""
import sys

from core import (
    CLIENTS, obradi_klijenta, razdoblje, sazetak_potrosnje, sb_log, sb_ocisti,
    sb_spremi_vijesti, zajednicki_izvori,
)


def main():
    start, today = razdoblje()
    print(f"Razdoblje: {start} – {today}")

    zajednicki, napomene = zajednicki_izvori(start, today)
    for n in napomene:
        print(n)

    neuspjeli, ukupno_kandidata = 0, 0
    for key in CLIENTS:
        try:
            stavke, stats, greske = obradi_klijenta(key, start, today, zajednicki)
            ukupno_kandidata += stats["pronadeno"]
            sb_spremi_vijesti(key, stavke)
            sb_log(key, stats, greske)
            print(f"{key}: kandidata {stats['pronadeno']}, spremljeno {stats['spremljeno']}, grešaka {len(greske)}")
            print(f"   {stats['koraci']}")
            for o in stats["odbaceno"][:15]:
                print(f"   odbačeno ({o})")
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

    for red in sazetak_potrosnje():
        print(red)

    if neuspjeli == len(CLIENTS):
        sys.exit(1)
    if ukupno_kandidata == 0:
        print("GREŠKA: nijedan izvor nije vratio kandidate, provjerite greške iznad.")
        sys.exit(1)


if __name__ == "__main__":
    main()

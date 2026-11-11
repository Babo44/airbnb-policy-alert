"""Osvjezavanje vijesti za sve klijente. Pokrece ga GitHub Actions dvaput dnevno.

Rucno pokretanje: GitHub -> Actions -> Osvjezavanje vijesti -> Run workflow.
"""
import sys

from core import (
    CLIENTS, obradi_klijenta, razdoblje, sazetak_potrosnje, sb_log, sb_ocisti,
    sb_oznaci_videno, sb_spremi_vijesti, zajednicki_izvori,
)


def main():
    start, today = razdoblje()
    print(f"Razdoblje: {start} – {today}")

    zajednicki, napomene = zajednicki_izvori(start, today)
    for n in napomene:
        print(n)

    neuspjeli, greske_urednika, ukupno_izvora = 0, 0, len(zajednicki)
    for key in CLIENTS:
        try:
            stavke, stats, greske = obradi_klijenta(key, start, today, zajednicki)
            greske = stats["napomene"] + greske
            sb_spremi_vijesti(key, stavke)
            # Kandidati se pamte kao ocijenjeni tek nakon sto su vijesti spremljene.
            if stats["videno_kljucevi"]:
                try:
                    sb_oznaci_videno(key, stats["videno_kljucevi"])
                except Exception as e:
                    greske.append(f"ocijenjeni kandidati nisu zapamćeni: {str(e)[:100]}")
            sb_log(key, stats, greske)
            print(f"{key}: novih kandidata {stats['pronadeno']}, novih vijesti {stats['spremljeno']}, "
                  f"grešaka {len(greske)}")
            print(f"   {stats['koraci']}")
            for o in stats["odbaceno"][:15]:
                print(f"   odbačeno ({o})")
            for o in stats["ispod_praga"][:15]:
                print(f"   ispod praga nakon čitanja (ocjena | izvor | naslov): {o}")
            for g in greske:
                print(f"   - {g}")
            greske_urednika += bool(stats["urednik_greska"])
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
        print(f"Čišćenje starih zapisa nije uspjelo: {e}")

    for red in sazetak_potrosnje():
        print(red)

    if neuspjeli == len(CLIENTS):
        sys.exit(1)
    if greske_urednika == len(CLIENTS):
        print("GREŠKA: urednik (Claude) nije uspio ni za jednog klijenta, provjerite greške iznad.")
        sys.exit(1)
    if ukupno_izvora == 0:
        print("GREŠKA: nijedan zajednički izvor (RSS, e-Savjetovanja, nabave) nije vratio stavke, provjerite greške iznad.")
        sys.exit(1)


if __name__ == "__main__":
    main()

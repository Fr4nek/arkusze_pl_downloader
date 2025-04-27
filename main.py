import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from tqdm import tqdm
import sys
import time

# Konfiguracja
script_dir = os.path.dirname(os.path.abspath(__file__))
download_folder = os.path.join(script_dir, "matura_arkusze")
os.makedirs(download_folder, exist_ok=True)

class Kolory:
    INFO = '\033[94m'
    SUKCES = '\033[92m'
    BŁĄD = '\033[91m'
    RESET = '\033[0m'

PRZEDMIOTY = {
    'matematyka': 'matematyka',
    'język polski': 'jezyk-polski',
    'język angielski': 'jezyk-angielski',
    'język niemiecki': 'jezyk-niemiecki',
    'języki obce': 'jezyki-obce',
    'geografia': 'geografia',
    'biologia': 'biologia',
    'chemia': 'chemia',
    'fizyka': 'fizyka',
    'informatyka': 'informatyka',
    'historia': 'historia',
    'wos': 'wos'
}

POZIOMY = {
    'podstawowy': 'podstawowy',
    'rozszerzony': 'rozszerzony',
    'oba poziomy': 'oba'
}

def log(typ, wiadomość, pbar=None):
    kolory = {
        'info': Kolory.INFO,
        'sukces': Kolory.SUKCES,
        'błąd': Kolory.BŁĄD
    }
    msg = f"{kolory.get(typ, '')}[{typ.upper()}]{Kolory.RESET} {wiadomość}"
    if pbar:
        tqdm.write(msg, file=sys.stdout)
    else:
        print(msg)

def wybierz_opcje(opcje, nazwa):
    print(f"\nDostępne {nazwa}:")
    for i, (key, val) in enumerate(opcje.items(), 1):
        print(f"{i}. {key.capitalize()}")
    
    while True:
        try:
            wybor = input(f"\nWybierz {nazwa} (liczba): ")
            if wybor.lower() == 'q':
                sys.exit(0)
            wybor = int(wybor)
            if 1 <= wybor <= len(opcje):
                return list(opcje.values())[wybor-1]
            log('błąd', f"Nieprawidłowy wybór. Wpisz liczbę 1-{len(opcje)} lub 'q' aby wyjść.")
        except ValueError:
            log('błąd', "To nie jest liczba. Spróbuj ponownie.")

def pobierz_arkusze_dla_przedmiotu(przedmiot, poziom, rok, pbar):
    if poziom == 'oba':
        return (pobierz_arkusze_dla_przedmiotu(przedmiot, 'podstawowy', rok, pbar) +
                pobierz_arkusze_dla_przedmiotu(przedmiot, 'rozszerzony', rok, pbar))
    
    base_url = f"https://arkusze.pl/{przedmiot}-matura-poziom-{poziom}/"
    
    try:
        log('info', f"\nPrzetwarzam: {przedmiot} {poziom}", pbar)
        response = requests.get(base_url, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Znajdź wszystkie dostępne lata
        wszystkie_lata = sorted({row.find_all('td')[0].text.strip()[-4:] 
                               for row in soup.select('tr') 
                               if len(row.find_all('td')) >= 4}, reverse=True)
        
        if rok and rok not in wszystkie_lata:
            log('błąd', f"Brak danych dla roku {rok} w {przedmiot} {poziom}", pbar)
            return 0
        
        # Przygotuj listę arkuszy
        arkusze = []
        for row in soup.select('tr'):
            cols = row.find_all('td')
            if len(cols) >= 4:
                data = cols[0].text.strip()
                if not rok or rok in data:
                    arkusz = {
                        'data': data,
                        'typ': cols[1].text.strip(),
                        'organizator': cols[2].text.strip(),
                        'url': urljoin(base_url, cols[3].find('a')['href']) if cols[3].find('a') else None
                    }
                    if arkusz['url']:
                        arkusze.append(arkusz)
        
        if not arkusze:
            log('info', "Brak arkuszy do pobrania", pbar)
            return 0
        
        # Pobieranie
        liczba_pobranych = 0
        for arkusz in arkusze:
            folder_arkusza = os.path.join(
                download_folder,
                f"{przedmiot}-{poziom}",
                arkusz['data'][-4:],
                f"{arkusz['data']} {arkusz['typ']} {arkusz['organizator']}"
            )
            os.makedirs(folder_arkusza, exist_ok=True)
            
            log('info', f"  Przetwarzam: {arkusz['data']} {arkusz['typ']}", pbar)
            if pobierz_pdf_z_podstrony(arkusz['url'], folder_arkusza, pbar):
                liczba_pobranych += 1
            
            pbar.update(1)
            time.sleep(0.3)  # Ograniczenie zapytań
        
        return liczba_pobranych
        
    except Exception as e:
        log('błąd', f"Błąd przy {przedmiot} {poziom}: {str(e)}", pbar)
        return 0

def pobierz_pdf_z_podstrony(url, folder, pbar):
    try:
        response = requests.get(url, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        pdf_links = [
            (urljoin(url, a['href']), a.text.strip() or os.path.basename(a['href']))
            for a in soup.find_all('a', href=lambda x: x and x.lower().endswith('.pdf'))
        ]
        
        for pdf_url, pdf_name in pdf_links:
            sciezka_pdf = os.path.join(folder, f"{pdf_name}.pdf")
            
            log('info', f"    Pobieram: {pdf_name[:50]}...", pbar)
            with requests.get(pdf_url, stream=True, timeout=20) as r:
                r.raise_for_status()
                with open(sciezka_pdf, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            
            log('sukces', f"    Zapisano: {os.path.basename(sciezka_pdf)}", pbar)
            return True
            
    except Exception as e:
        log('błąd', f"    Błąd przy {url}: {str(e)}", pbar)
        return False

def główny_proces():
    try:
        # Wybór opcji
        print("\n=== WYBÓR ZAKRESU POBRANIA ===")
        przedmiot = wybierz_opcje({**PRZEDMIOTY, 'wszystkie przedmioty': 'wszystkie'}, "przedmioty")
        poziom = wybierz_opcje(POZIOMY, "poziomy")
        
        # Pobierz przykładową listę lat (dla pojedynczego przedmiotu)
        if przedmiot != 'wszystkie':
            url_przyklad = f"https://arkusze.pl/{list(PRZEDMIOTY.values())[0]}-matura-poziom-{list(POZIOMY.values())[0]}/"
            response = requests.get(url_przyklad)
            soup = BeautifulSoup(response.text, 'html.parser')
            wszystkie_lata = sorted({row.find_all('td')[0].text.strip()[-4:] 
                                   for row in soup.select('tr') 
                                   if len(row.find_all('td')) >= 4}, reverse=True)
            rok = wybierz_opcje({**{k: k for k in wszystkie_lata}, 'wszystkie lata': None}, "lata")
        else:
            rok = None
        
        # Przygotuj listę do pobrania
        przedmioty_do_pobrania = PRZEDMIOTY.values() if przedmiot == 'wszystkie' else [przedmiot]
        poziomy_do_pobrania = ['podstawowy', 'rozszerzony'] if poziom == 'oba' else [poziom]
        
        # Oblicz całkowitą liczbę arkuszy
        total_arkuszy = 0
        log('info', "Przygotowywanie listy pobierania...")
        for p in przedmioty_do_pobrania:
            for lvl in poziomy_do_pobrania:
                url = f"https://arkusze.pl/{p}-matura-poziom-{lvl}/"
                try:
                    response = requests.get(url, timeout=10)
                    soup = BeautifulSoup(response.text, 'html.parser')
                    for row in soup.select('tr'):
                        cols = row.find_all('td')
                        if len(cols) >= 4:
                            data = cols[0].text.strip()
                            if not rok or rok in data:
                                if cols[3].find('a'):
                                    total_arkuszy += 1
                except:
                    continue
        
        # Główna pętla pobierania
        with tqdm(total=total_arkuszy, desc="Postęp ogólny", position=1, leave=True) as pbar:
            liczba_pobranych = 0
            for p in przedmioty_do_pobrania:
                for lvl in poziomy_do_pobrania:
                    liczba_pobranych += pobierz_arkusze_dla_przedmiotu(p, lvl, rok, pbar)
            
            log('sukces', f"\nPobrano łącznie {liczba_pobranych}/{total_arkuszy} arkuszy", pbar)
            
    except Exception as e:
        log('błąd', f"Krytyczny błąd: {str(e)}")
    finally:
        log('sukces', f"\nZakończono! Pobrane arkusze znajdują się w:\n{os.path.abspath(download_folder)}")

if __name__ == "__main__":
    print("\n=== MATURALNY POBERACZ ARKUSZY ===")
    print("=== Wersja pełna - wszystkie przedmioty i poziomy ===\n")
    
    try:
        from tqdm import tqdm
    except ImportError:
        print("Instalowanie wymaganego pakietu 'tqdm'...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "tqdm"])
        from tqdm import tqdm
    
    główny_proces()

# Acceptatietest (handmatig)

Kopie van het testplan uit het project. Ongeveer 15 minuten op Windows; alles wat het dashboard doet is dan een keer gezien.

## Voorbereiding

1. Open een terminal in `timelimit-ui\rootfs\usr\bin\dashboard` van de repo (branch `claudeEnhancedVersion`, eerst `git pull`).
2. Start het dashboard met `py -3 app.py`.
3. Open http://127.0.0.1:8100/. Zonder gekoppelde server stuurt het dashboard je naar de instellingen.
4. Heb je een testserver, houd dan het adres en je mailadres bij de hand. Het wachtwoord wordt nergens opgeslagen.

## Windows-controle

| # | Wat je doet | Wat je hoort te zien |
| --- | --- | --- |
| 1 | Instellingen openen, server kiezen, koppelen (of testserver-modus aanzetten met "This is a test server") | Status gaat naar gekoppeld; bij apiLevel 8 verschijnt een versiewaarschuwing (normaal) |
| 2 | Menu: er verschijnt een testsectie zodra de schakelaar aan staat; zet hem uit | Menu-item komt en gaat meteen, zonder herladen |
| 3 | Testsectie: kind of ouder toevoegen | Formulier toont "wachten op server" en daarna de nieuwe gebruiker |
| 4 | Kinderenoverzicht openen | Kaart per kind met gebruikte tijd en status |
| 5 | Op een kaart "Extra tijd / blokkeren" kiezen | Dialoog met categorie-keuze; extra tijd of tijdelijk blokkeren werkt (vereist de volledige versie op de server) |
| 6 | Kinddetail: "Alle limieten uit" en daarna "Limieten weer aan" | Tekstregel onder de kop volgt de status mee |
| 7 | Tab Regels: regel toevoegen, wijzigen, "Uit voor vandaag", verwijderen | Rij gemarkeerd tot de server bevestigt; verwijderen vraagt bevestiging |
| 8 | Tab Categorieen: toevoegen, verplaatsen, apps toewijzen, een app verwijderen | App verwijderen vraagt om bevestiging |
| 9 | Tab Gebruik | Tabel met voortgangsbalken en grafiek over 7 of 30 dagen |
| 10 | Tab Wijzigingen | Elke zojuist gedane wijziging staat erin, zonder wachtwoorden |
| 11 | Instellingen, sectie Ouders: wachtwoord wijzigen | Huidig wachtwoord wordt gecontroleerd; fout geeft een melding bij het veld |
| 12 | Server uitzetten of netwerk weghalen en terugzetten | Waarschuwingsbalk, wijzigknoppen uit; daarna alles vanzelf weer aan |

## Later in Home Assistant

Pas na de image-build; build en add-on-start zijn nog niet geprobeerd.

1. Laat de CI-workflow draaien (handmatig in GitHub, of een push naar main die `config.yaml` raakt) en controleer de aarch64-smoketest.
2. Installeer de add-on, zet `log_level` op `info` en start hem.
3. Open hem via de zijbalk (ingress): de pagina moet volledig laden, met stijl, menu en taal.
4. Doorloop alle schermen uit de tabel; links en live-updates blijven binnen het ingress-pad.
5. Ververs op een subpagina (bijvoorbeeld een kinddetail): die moet terugkomen.
6. Herstart de add-on: koppeling en instellingen blijven behouden (`/data`).

## Wat te melden

Per afwijking: stapnummer, verwachting en wat je zag. Voeg bij een foutmelding de debug-export toe (instellingen); die bevat geen wachtwoorden of sleutels. Bij een crash is de terminaltekst genoeg.

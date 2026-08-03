# The Cure — Archive des concerts

Site statique GitHub Pages basé sur la base V3, avec synchronisation automatique des concerts/setlists récents via l'API officielle setlist.fm.

## Fonctionnement

Le dépôt conserve **ta base historique V3** dans `site-template/index.html`. À chaque déploiement, GitHub Actions :

1. exécute les tests ;
2. contacte l'API officielle setlist.fm si le secret `SETLISTFM_API_KEY` est configuré ;
3. récupère les setlists de The Cure pour l'année courante et l'année précédente ;
4. fusionne temporairement ces données avec la V3 ;
5. génère `dist/index.html` ;
6. publie `dist/` sur GitHub Pages.

Les données reçues de l'API ne sont **pas commitées dans Git**. Le dossier `dist/` est ignoré par `.gitignore`.

## Pourquoi cette architecture ?

setlist.fm demande que les données API soient attribuées et n'autorise pas la conservation durable de copies, hors cache court. Le site généré contient donc une attribution et les données API ne sont pas enregistrées dans l'historique du dépôt.

## Synchronisation

- automatique : chaque jour à **04:17 UTC** ;
- manuelle : onglet **Actions** → workflow **Synchroniser setlist.fm et publier GitHub Pages** → **Run workflow** ;
- à chaque `push` sur `main`.

La limite de ton compte (2 requêtes/s, 1 440/jour) est largement suffisante. Le script impose environ 0,60 s entre les requêtes et ne recharge que deux années.

## Mise à jour des données

La fusion préserve les champs locaux que setlist.fm ne fournit pas (affluence, capacité, adresse, horaires locaux, etc.). Les setlists venant de l'API sont ordonnées explicitement :

`Mainset → Encore 1 → Encore 2 → Encore 3...`

Une setlist locale existante n'est remplacée que si l'API fournit réellement des morceaux.

## Arborescence

```text
.github/workflows/pages.yml      Workflow automatique GitHub Pages
site-template/index.html        Site V3 de référence
scripts/build_site.py           Synchronisation + fusion + construction
source/cure_concerts_V3_complete.xlsx  Base Excel V3 source
source/theCure.png              Visuel source
 tests/                         Tests sans accès réseau
.gitignore
README.md
INSTALLATION.md
```

## Sécurité

Ne mets jamais la clé API dans le HTML, le README ou un fichier du dépôt. Elle doit être enregistrée uniquement dans **GitHub Secrets** sous le nom exact :

`SETLISTFM_API_KEY`

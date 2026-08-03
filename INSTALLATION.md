# Installation pas à pas sur GitHub

Ce fichier contient toute la procédure. Tu peux aussi suivre les étapes avec ChatGPT une par une.

## Étape 1 — Créer le dépôt GitHub

1. Connecte-toi à GitHub.
2. Clique sur **New repository**.
3. Nom conseillé : `the-cure-tours`.
4. Choisis **Public** si tu veux utiliser GitHub Pages simplement et rendre le site public.
5. Ne coche pas l'ajout automatique d'un README : il est déjà fourni.
6. Clique sur **Create repository**.

## Étape 2 — Envoyer les fichiers

Le plus simple sans ligne de commande :

1. dans le nouveau dépôt, clique sur **uploading an existing file** / **Add file → Upload files** ;
2. décompresse le ZIP fourni ;
3. envoie **le contenu du dossier**, y compris `.github` ;
4. vérifie que `.github/workflows/pages.yml` existe bien ;
5. valide avec **Commit changes** sur `main`.

> Sur macOS/Windows, les dossiers commençant par un point peuvent être masqués. Vérifie bien que `.github` est envoyé.

## Étape 3 — Ajouter la clé API setlist.fm

Dans le dépôt :

1. **Settings** ;
2. **Secrets and variables** ;
3. **Actions** ;
4. **New repository secret** ;
5. Name : `SETLISTFM_API_KEY` ;
6. Secret : colle ta clé API ;
7. **Add secret**.

La clé ne doit jamais être publiée dans le code.

## Étape 4 — Activer GitHub Pages avec Actions

1. **Settings → Pages** ;
2. dans **Build and deployment**, choisis **Source: GitHub Actions**.

## Étape 5 — Lancer la première synchronisation

1. ouvre l'onglet **Actions** ;
2. sélectionne **Synchroniser setlist.fm et publier GitHub Pages** ;
3. **Run workflow → Run workflow** ;
4. attends que `build` puis `deploy` soient verts.

L'URL du site apparaît dans le job `deploy` et dans **Settings → Pages**.

## Étape 6 — Vérifier le site

Teste notamment :

- Vue d'ensemble ;
- Concerts et filtres ;
- Tous les titres ;
- Classements ;
- Explorateur de chansons ;
- Comparateur ;
- Carte ;
- ouverture d'un concert ;
- ordre `Mainset → Encore 1 → Encore 2` ;
- affichage iPhone.

## Ensuite

Le workflow se relance automatiquement chaque jour à 04:17 UTC. Les dépôts publics sans activité peuvent voir leurs workflows planifiés désactivés après une longue période d'inactivité ; un lancement manuel les réactive normalement.

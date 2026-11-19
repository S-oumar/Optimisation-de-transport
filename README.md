# Planification des arrivées de véhicules sur quais de déchargement

Modèle d'optimisation par **programmation par contraintes** (Google OR-Tools, solveur CP-SAT). Pour chaque camion, il calcule l'heure d'arrivée et l'heure de début de déchargement à un entrepôt qui a un nombre limité de quais et une file d'attente limitée, puis en déduit l'heure de départ.

Le projet comporte six versions successives du modèle. Chacune ajoute ou modifie une règle par rapport à la précédente. Le détail du modèle (pseudo-code, différences entre versions, explications) est dans [`ALGORITHME.md`](ALGORITHME.md).

## Installation

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
```

La seule dépendance est `ortools`. La version testée est 9.15.6755, avec Python 3.13.

## Le modèle en bref

Toutes les heures sont en minutes depuis minuit (`480` = 08:00). Pour chaque camion :

- `a` : heure d'arrivée ;
- `s` : heure de début de déchargement, avec `s ≥ a` ;
- `w = s − a` : temps d'attente dans la file.

Contraintes, à partir de la version 2 :

- **Capacité des quais** : au plus `Q` déchargements en même temps (`add_cumulative`) ;
- **Taille de la file** : au plus 2 camions en attente en même temps (`add_cumulative`).

Objectif : minimiser l'attente totale `Σ w`. La version 6 minimise d'abord le retard.

L'heure de départ est calculée après la résolution : `départ = a − trajet`.

## Les six versions

| Version | Fichier | Données | Ce qui change |
|---|---|---|---|
| 1 | `planning.py` | 15 véhicules (V1…V15) | Modèle de base, sans quais ni file. Arrivée dans `[T − 30, T]`. |
| 2 | `planning_contraintes.py` | 15 véhicules | Ajoute la capacité des quais `Q` et la file d'attente (`file_max = 2`). |
| 3 | `entrepot.py` | 19 points réels (p1…p19) | Données réelles : rendez-vous `HRDV`, distance `km`, trajet calculé à 30 km/h. Même modèle que la version 2. |
| 4 | `entrepot_avec_formalite.py` | 19 points | Le quai reste occupé pendant `delta + formalite`. Variante non reprise ensuite. |
| 5 | `version5.py` | 19 points | Repart de la version 3. Pas de déchargement avant `HRDV`, pas d'arrivée avant l'ouverture (06:00). |
| 6 | `version6.py` | 19 points | Arrivée après `HRDV` autorisée. Le retard `r = s − HRDV` est pénalisé : objectif `1000 × Σr + Σw`. |

## Utilisation

Chaque script se lance directement :

```bash
python planning.py                  # version 1, écrit resultat.json
python planning_contraintes.py      # version 2, écrit resultat_Q{Q}.json
python entrepot.py                  # version 3, affiche un tableau
python entrepot_avec_formalite.py   # version 4, affiche un tableau
python version5.py                  # version 5, affiche un tableau
python version6.py                  # version 6, affiche le tableau, le retard total et le nombre de camions en retard
```

Le nombre de quais se règle en modifiant la ligne `Q = …` du script. Valeurs actuelles : `Q = 2` dans `planning_contraintes.py` et `version6.py`, `Q = 1` dans `entrepot.py`, `entrepot_avec_formalite.py` et `version5.py`.

> **Attention :** seul `planning_contraintes.py` vérifie le statut du solveur avant de lire la solution. Les versions 3 à 6 affichent le tableau dans tous les cas. Si la première ligne affichée est `INFEASIBLE`, il n'existe aucune solution et les valeurs du tableau n'ont aucun sens.

## Résultats

Résultats obtenus pour Q = 1, 2 et 3 quais, avec une file limitée à 2 camions. Les chiffres sont des attentes totales en minutes. Pour la version 6, `r` est le retard total et `w` l'attente totale.

| Version | Q = 1 | Q = 2 | Q = 3 |
|---|---|---|---|
| 1 — `planning.py` | 0 (pas de quais dans le modèle) | 0 | 0 |
| 2 — `planning_contraintes.py` | INFEASIBLE | 5 | 0 |
| 3 — `entrepot.py` | 70 | 0 | 0 |
| 4 — `entrepot_avec_formalite.py` | INFEASIBLE | 76 | 8 |
| 5 — `version5.py` | INFEASIBLE | 50 | 20 |
| 6 — `version6.py` | r = 230 (5 camions), w = 0 | r = 50 (3 camions), w = 0 | r = 20 (1 camion), w = 0 |

Les versions 1–2 et 3–6 n'utilisent pas les mêmes données : on ne compare les chiffres qu'à l'intérieur de chaque groupe.

Ce qu'on en retient :

- **Données de test (versions 1–2).** Un seul quai ne suffit pas : 15 déchargements de 20 minutes ne tiennent pas dans les fenêtres d'arrivée avec une file de 2. Avec 2 quais, il reste 5 minutes d'attente (V15). Avec 3 quais, il n'y en a plus.
- **Données réelles (versions 3–6).** Quatre camions ont rendez-vous à 09:30 (p10, p12, p13, p15), et c'est ce pic qui fixe le besoin en quais. Si la formalité occupe le quai (version 4) ou si l'on interdit de décharger avant le rendez-vous (version 5), un quai ne suffit plus. La version 6 trouve toujours une solution, au prix d'un retard d'autant plus faible qu'il y a de quais.

Les plannings détaillés des versions 1 et 2 sont dans les fichiers JSON ci-dessous. L'analyse de chaque cas, y compris les raisons des infaisabilités, est dans [`ALGORITHME.md`](ALGORITHME.md).

## Format de sortie JSON (versions 1 et 2)

```json
{
  "quais": 2,
  "file_max": 2,
  "statut": "OPTIMAL",
  "attente_totale": 5,
  "planning": [
    {
      "vehicule": "V1",
      "T": "08:00",
      "depart": "06:45",
      "arrivee": "07:30",
      "dechargement": "07:30",
      "attente": 0
    }
  ]
}
```

Les champs `quais` et `file_max` n'existent qu'en version 2. Si aucune solution n'existe (statut `INFEASIBLE`), `attente_totale` vaut `null` et `planning` est vide.

## Structure du projet

```
.
├── planning.py                  # V1 : modèle sans contraintes de capacité
├── planning_contraintes.py      # V2 : quais (Q) et file d'attente
├── entrepot.py                  # V3 : données réelles de l'entrepôt
├── entrepot_avec_formalite.py   # V4 : formalité comptée dans l'occupation du quai
├── version5.py                  # V5 : déchargement au plus tôt à HRDV, ouverture 06:00
├── version6.py                  # V6 : retard autorisé, pénalisé dans l'objectif
├── resultat.json                # V1
├── resultat_Q1.json             # V2, Q = 1 (infaisable)
├── resultat_Q2.json             # V2, Q = 2
├── resultat_Q3.json             # V2, Q = 3
├── ALGORITHME.md                # description détaillée du modèle et des versions
├── requirements.txt
└── README.md
```
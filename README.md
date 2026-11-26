# Planification des arrivées de véhicules sur quais de déchargement

Modèle d'optimisation par **programmation par contraintes** (Google OR-Tools, solveur CP-SAT).  
Le programme calcule les horaires optimaux d'arrivée et de déchargement de camions dans un entrepôt à quais limités, en minimisant le temps d'attente total.

Le détail complet du modèle, le pseudo-code, les explications techniques et les correspondances OR-Tools sont dans [`ALGORITHME.md`](ALGORITHME.md).

---

## Le problème

Un entrepôt reçoit des camions tout au long de la journée pour des opérations de déchargement. Le problème est le suivant :

- Chaque camion a un **rendez-vous** (noté `HRDV` ou `T` selon la version), exprimé en minutes depuis minuit (`480` = 08:00, `570` = 09:30, etc.).
- L'entrepôt dispose d'un nombre limité de **quais de déchargement** (`Q`). Un quai est occupé pendant toute la durée du déchargement (`delta = 20 min`).
- Si tous les quais sont occupés à l'arrivée d'un camion, ce camion attend dans une **file d'attente** dont la capacité est limitée (`file_attente = 2` : au plus 2 camions en attente simultanément).
- Un camion peut arriver au plus 30 minutes avant son rendez-vous (`avance_max = 30`).

Le programme détermine, pour chaque camion :
- **quand il arrive** à l'entrepôt (heure d'arrivée `a`) ;
- **quand il commence à décharger** (heure de début `s`) ;
- **son temps d'attente** dans la file (`w = s − a`).

L'heure de départ du dépôt est calculée après coup : `départ = a − durée_de_trajet`.

**Objectif :** minimiser la somme des temps d'attente de tous les camions.

### Pourquoi ce problème est difficile

Le cas concret illustre bien la difficulté : avec les données réelles de l'entrepôt (versions 3 à 6), quatre camions — p10, p12, p13 et p15 — ont **tous rendez-vous à 09:30**. Avec un seul quai et 20 minutes de déchargement, ces quatre camions ne peuvent pas décharger en même temps. L'un d'eux doit attendre que le précédent ait terminé. Et si plusieurs attendent en même temps, la file (limitée à 2 places) peut déborder.

Le solveur CP-SAT explore intelligemment toutes les ordonnances possibles pour trouver celle qui minimise l'attente totale — ou déclare le problème infaisable si aucune ne respecte toutes les contraintes.

---

## Approche : six versions progressives

Le modèle a été développé en **six versions**. Chaque version part de la précédente et ajoute ou modifie une contrainte pour coller à une réalité de plus en plus précise. Cette progression permet de comprendre l'impact de chaque contrainte sur la faisabilité et les temps d'attente.

Certaines versions sont **INFEASIBLE** (aucune solution n'existe) pour un seul quai (`Q = 1`) : cela montre que la contrainte ajoutée est trop restrictive pour être satisfaite avec une seule ressource. Pour les rendre faisables, on a allégé une contrainte (borne d'arrivée ou borne de déchargement). La **version 5** fait exception : elle reste délibérément INFEASIBLE à Q = 1, car c'est son comportement intentionnel — il illustre ce qui se passe quand on exige que le déchargement ne commence jamais avant le rendez-vous.

---

## Installation

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
```

Dépendance unique : `ortools` (testé en version 9.15.6755 avec Python 3.13).

---

## Les six versions

### Version 1 — `planning.py` : modèle de base, sans contrainte de capacité

**Données :** 15 véhicules (V1 à V15), rendez-vous de 08:00 à 09:45 (espacés d'environ 8 min), durée de trajet fournie directement.

Ce premier modèle ne représente aucune contrainte de capacité : il n'y a ni quai ni file d'attente. Chaque camion peut arriver entre `T − 30` et `T`, et décharge dès son arrivée. Sans aucun conflit de ressource, l'optimum est trivial : tous les camions arrivent exactement à leur rendez-vous et attendent 0 minute.

**Résultat :** attente totale = **0 min** (quel que soit Q, puisque le modèle l'ignore).

**But :** valider les briques de base du modèle — variables `a`, `s`, `w`, contrainte `s ≥ a`, objectif `min Σw` — avant d'ajouter la complexité des quais.

---

### Version 2 — `planning_contraintes.py` : ajout des quais et de la file d'attente

**Données :** mêmes 15 véhicules.

Cette version introduit les deux contraintes de capacité clés du modèle :
- **Capacité des quais :** au plus `Q` camions déchargent en même temps (`add_cumulative` sur les intervalles de déchargement).
- **Taille de la file :** au plus 2 camions attendent en même temps (`add_cumulative` sur les intervalles d'attente).

La borne supérieure de l'arrivée a été élargie à 1440 (toute la journée, au lieu de `T`) pour que le problème reste faisable à Q = 1 : avec seulement 15 camions et des rendez-vous étalés sur 1 h 45, un seul quai ne peut pas les traiter tous dans la fenêtre `[T−30, T]`.

**Résultats :**

| Q | Statut | Attente totale |
|---|---|---|
| 1 | OPTIMAL | 0 min |
| 2 | OPTIMAL | 0 min |
| 3 | OPTIMAL | 0 min |

**Ce qu'on observe :** quel que soit le nombre de quais (1, 2 ou 3), personne n'attend : la borne d'arrivée élargie à 1440 permet au solveur d'étaler les arrivées sur toute la journée, éliminant tout conflit.

---

### Version 3 — `entrepot.py` : données réelles de l'entrepôt

**Données :** 19 points réels (p1 à p19), rendez-vous de 08:00 (480 min) à 17:30 (1050 min), distance en km. La durée de trajet est calculée à vitesse constante de 30 km/h.

Même modèle que la version 2. Seules changent les données : plus de camions, rendez-vous étalés sur toute la journée. Le champ `formalite` est présent dans les données mais n'est pas encore utilisé.

**Point critique :** quatre camions — p10, p12, p13, p15 — ont tous `HRDV = 570` (09:30). Ce pic crée la situation la plus tendue avec un seul quai.

**Résultats :**

| Q | Statut | Attente totale |
|---|---|---|
| 1 | OPTIMAL | 130 min (p13 : 70 min, p14 : 30 min, p16 : 20 min, p10 : 10 min) |
| 2 | OPTIMAL | 0 min |
| 3 | OPTIMAL | 0 min |

**Ce qu'on observe :** avec Q = 1, le solveur fait décharger certains camions en avance (p12 arrive à 09:00 pour un rendez-vous à 09:30, et décharge immédiatement). Mais le pic de 09:30 crée quand même un encombrement : p13 attend 70 min, p14 30 min, p16 20 min, p10 10 min. Avec 2 quais, tout le monde est servi sans attendre.

---

### Version 4 — `entrepot_avec_formalite.py` : formalité administrative au quai

**Données :** mêmes 19 points.

La formalité administrative (entre 0 et 45 min selon le camion) est ajoutée au temps d'occupation du quai. Chaque camion occupe le quai pendant `delta + formalite` minutes au lieu de `delta = 20` min seules. Par exemple, p5 avec `formalite = 45` min occupe le quai pendant 65 min.

Conséquence : les camions occupent le quai **beaucoup plus longtemps**, ce qui crée davantage de conflits. La borne supérieure de l'arrivée a également été élargie à 1440 pour que le problème reste faisable à Q = 1.

**Résultats :**

| Q | Statut | Attente totale |
|---|---|---|
| 1 | OPTIMAL | 0 min |
| 2 | OPTIMAL | 0 min |
| 3 | OPTIMAL | 0 min |

**Ce qu'on observe :** malgré des occupations de quai jusqu'à 65 min (delta + formalite), la borne d'arrivée élargie à 1440 permet au solveur d'étaler les arrivées sur toute la journée : 0 min d'attente pour tous les Q.

Cette variante n'est pas reprise dans les versions 5 et 6, qui repartent de la version 3.

---

### Version 5 — `version5.py` : déchargement interdit avant le rendez-vous

**Données :** mêmes 19 points. Repart de la version 3 (sans formalité).

Une nouvelle contrainte est ajoutée : le déchargement **ne peut pas commencer avant l'heure de rendez-vous** (`s[p] ≥ HRDV`). Dans les versions précédentes, le solveur pouvait faire décharger un camion jusqu'à 30 minutes en avance (arriver à 09:00, décharger à 09:00 pour un rendez-vous à 09:30). Cette version l'interdit : un camion arrivé en avance doit attendre son heure.

De plus, l'arrivée ne peut pas avoir lieu avant l'ouverture du site (`ouverture = 06:00`).

**À Q = 1, cette version est INFEASIBLE.** Voir ci-dessous.

**Résultats :**

| Q | Statut | Attente totale |
|---|---|---|
| 1 | **INFEASIBLE** | — |
| 2 | OPTIMAL | 60 min |
| 3 | OPTIMAL | 20 min |

#### Pourquoi Q = 1 est infaisable ici ?

Les quatre camions p10, p12, p13 et p15 ont tous `HRDV = 570` (09:30). La contrainte `s[p] ≥ HRDV = 570` les oblige à commencer leur déchargement **au plus tôt à 09:30**.

Avec un seul quai et 20 minutes par camion, la seule façon de les décharger tous est de les séquencer :

```
09:30 → 09:50 : 1er camion sur le quai
09:50 → 10:10 : 2e camion
10:10 → 10:30 : 3e camion
10:30 → 10:50 : 4e camion
```

Pendant ce temps, les trois camions qui attendent leur tour sont dans la file. Or la contrainte `a[p] ≤ HRDV = 570` oblige les quatre camions à arriver au plus tard à 09:30 — ils sont tous là avant même que le premier ait fini de décharger. Dès que le 3e camion arrive (au plus tard à 09:30), la file contient 3 camions simultanément, ce qui dépasse la capacité de 2 : **la file déborde**.

Le solveur ne peut pas contourner ce problème :
- Il ne peut pas faire arriver les camions plus tard : `a[p] ≤ HRDV` est une contrainte dure.
- Il ne peut pas les faire décharger en avance : `s[p] ≥ HRDV` l'en empêche.
- Il ne peut pas décharger deux camions en parallèle : Q = 1.

**Avec Q = 2**, deux camions déchargent en parallèle de 09:30 à 09:50, puis deux autres de 09:50 à 10:10. La file ne contient jamais plus de 2 camions → faisable, avec 60 min d'attente au total. **Avec Q = 3**, trois camions déchargent ensemble de 09:30 à 09:50, le 4e attend 20 min → 20 min d'attente.

---

### Version 6 — `version6.py` : retard autorisé, fortement pénalisé

**Données :** mêmes 19 points.

Cette version résout le problème d'infaisabilité de la version 5 en supprimant les deux bornes restrictives :
- La borne supérieure de `a[p]` passe de `HRDV` à `1440` : un camion peut arriver **après** son rendez-vous.
- La borne inférieure de `s[p]` passe de `HRDV` à `0` : un camion peut décharger avant son rendez-vous.

À la place, un **retard** `r[p] = s[p] − HRDV` est introduit et **fortement pénalisé** dans l'objectif :

```
minimiser  1000 × Σr + Σw
```

Le poids 1000 fait qu'une minute de retard coûte autant que 1000 minutes d'attente. Le solveur préfère donc systématiquement retarder l'arrivée d'un camion (retard 0 mais arrivée tardive) plutôt que de le laisser dans la file (attente positive).

**Résultats** (objectif = 1000 × retard total + attente totale) :

| Q | Statut | Retard total | Camions en retard | Attente totale |
|---|---|---|---|---|
| 1 | OPTIMAL | 350 min | 8 | 0 min |
| 2 | OPTIMAL | 60 min | 4 | 0 min |
| 3 | OPTIMAL | 20 min | 1 | 0 min |

**Ce qu'on observe :** l'attente est toujours nulle — le solveur préfère systématiquement retarder l'arrivée d'un camion plutôt que de le laisser patienter dans la file. Avec Q = 1, 8 camions arrivent après leur rendez-vous pour un retard total de 350 min. Plus on ajoute de quais, moins il faut de retard.

---

## Récapitulatif des résultats

| Version | Fichier | Q = 1 | Q = 2 | Q = 3 |
|---|---|---|---|---|
| 1 — Modèle de base | `planning.py` | 0 (sans quais) | 0 | 0 |
| 2 — Quais + file | `planning_contraintes.py` | w = 0 min | w = 0 min | w = 0 |
| 3 — Données réelles | `entrepot.py` | w = 130 min | w = 0 | w = 0 |
| 4 — Formalité au quai | `entrepot_avec_formalite.py` | w = 0 min | w = 0 min | w = 0 min |
| 5 — Pas de déchargement avant HRDV | `version5.py` | **INFEASIBLE** | w = 60 min | w = 20 min |
| 6 — Retard pénalisé | `version6.py` | r = 350 min (8 camions), w = 0 | r = 60 min (4 camions), w = 0 | r = 20 min (1 camion), w = 0 |

> Les versions 1–2 et 3–6 n'utilisent pas les mêmes données (15 vs 19 camions) : les chiffres ne se comparent qu'à l'intérieur de chaque groupe.

---

## Utilisation

Chaque script se lance directement :

```bash
python planning.py                  # version 1, affiche un tableau
python planning_contraintes.py      # version 2, affiche un tableau
python entrepot.py                  # version 3, affiche un tableau
python entrepot_avec_formalite.py   # version 4, affiche un tableau
python version5.py                  # version 5, INFEASIBLE à Q = 1 (affiche quand même un tableau sans sens)
python version6.py                  # version 6, affiche tableau + retard total + nombre de camions en retard
```

Le nombre de quais se règle en modifiant la ligne `Q = …` dans le script. Valeurs actuelles : `Q = 1` dans tous les scripts.

> **Attention :** `planning.py` et `planning_contraintes.py` vérifient le statut du solveur avant d'afficher les valeurs. Pour les versions 3 à 6, si la première ligne affichée est `INFEASIBLE`, les valeurs du tableau n'ont aucun sens. C'est notamment le cas de `version5.py` avec `Q = 1` : le tableau affiché contient des nombres arbitraires.

---

## Structure du projet

```
.
├── planning.py                  # V1 : modèle sans contraintes de capacité
├── planning_contraintes.py      # V2 : quais (Q) et file d'attente
├── entrepot.py                  # V3 : données réelles de l'entrepôt
├── entrepot_avec_formalite.py   # V4 : formalité comptée dans l'occupation du quai
├── version5.py                  # V5 : déchargement au plus tôt à HRDV (infaisable à Q = 1)
├── version6.py                  # V6 : retard autorisé, fortement pénalisé
├── ALGORITHME.md                # description détaillée du modèle et des versions
├── requirements.txt
└── README.md
```
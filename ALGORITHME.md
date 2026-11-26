# Algorithme de planification des déchargements

Ce document décrit le modèle d'optimisation CP-SAT du projet et ses six versions successives. Le pseudo-code reprend les noms exacts des variables du code Python, pour qu'on puisse retrouver chaque ligne dans les scripts.

---

## 1. Installation et dépendances

Le projet tourne sous Python 3 (testé avec Python 3.13). Sa seule dépendance est **ortools**, qui fournit le solveur CP-SAT (`from ortools.sat.python import cp_model`). Les scripts utilisent l'API en *snake_case* (`new_int_var`, `add_cumulative`…). La version testée est la 9.15.6755.

`requirements.txt` :

```
ortools==9.15.6755
```

Installation :

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # Linux / macOS
pip install -r requirements.txt
```

Chaque script se lance directement (`python version6.py`). Il n'y a pas d'argument en ligne de commande : pour changer le nombre de quais, il faut modifier la ligne `Q = …` du script.

---

## 2. Le problème

Des camions doivent venir décharger dans un entrepôt qui dispose de `Q` quais. Chaque camion a une heure de rendez-vous. Il peut arriver un peu en avance, mais il ne peut pas décharger si tous les quais sont occupés. Dans ce cas, il attend dans une file dont la taille est limitée. Le modèle choisit l'heure d'arrivée et l'heure de début de déchargement de chaque camion. L'objectif est de minimiser l'attente totale, puis, dans la dernière version, le retard d'abord.

Toutes les heures sont des entiers en **minutes depuis minuit** (`480` = 08:00). L'horizon est d'une journée (`1440`).

### Déroulé d'un camion

```
 départ               arrivée            début déchargement        fin
   |------ trajet ------|---- attente w ----|------ delta ------|
 a - trajet            a                    s                 s + delta
                        \___ dans la file __/\___ sur un quai __/
```

1. Le camion part à `a - trajet`. Cette heure est calculée **après** la résolution : elle n'est pas une variable du modèle.
2. Il arrive à `a`, dans une fenêtre autour de son rendez-vous.
3. Si aucun quai n'est libre, il attend dans la file pendant `w = s - a` minutes.
4. Il occupe un quai de `s` à `s + delta`. Dans une variante, il l'occupe aussi pendant la formalité.

---

## 3. Socle commun

Les six versions partagent les éléments suivants. Ils sont décrits ici une fois pour toutes, et les sections suivantes ne donnent que les différences.

### Données et noms

Le nom des indices et des données change à partir de la version 3. Le rôle reste le même :

| Rôle | Versions 1–2 (`planning*.py`) | Versions 3–6 |
|---|---|---|
| ensemble des camions | `VEHICULES` (V1…V15, 15 camions) | `POINTS` (p1…p19, 19 camions) |
| indice de boucle | `C` | `p` |
| heure de rendez-vous | `v["T"]` | `v["HRDV"]` |
| durée de trajet (min) | `v["trajet"]` (donnée) | `trajet(v["km"])` (calculée) |
| durée de déchargement | `v["Delta"]` = 20 | `delta` = 20 |
| taille max de la file | `file_max` = 2 | `file_attente` = 2 |
| intervalles de quai | `dechargements` (`dech_…`) | `quais` (`quai_…`) |

Paramètre commun à toutes les versions : `avance_max = 30`, c'est-à-dire qu'un camion peut arriver au plus 30 minutes avant son rendez-vous.

### Variables et contraintes communes

```
m ← CpModel()
a, s, w ← {}, {}, {}

pour chaque camion C (ou p) de données v :
    a[C] ∈ [borne_basse, borne_haute]      # heure d'arrivée (bornes : voir chaque version)
    s[C] ∈ [0, 1440]                       # heure de début de déchargement
    w[C] ∈ [0, 1440]                       # temps d'attente
    contrainte  s[C] ≥ a[C]                # on ne décharge pas avant d'être arrivé
    contrainte  w[C] = s[C] − a[C]         # l'attente est le temps passé entre arrivée et quai
```

### Résolution et lecture

```
solveur ← CpSolver()
statut  ← solveur.solve(m)
afficher status_name(statut)
pour chaque camion : lire value(a), value(s), value(w) ; départ = a − trajet
```

### Pourquoi la simultanéité passe par des intervalles et `add_cumulative`

À partir de la version 2, les contraintes portent sur ce qui se passe **au même moment** : « au plus `Q` camions sur les quais » et « au plus `file_attente` camions dans la file ». Une contrainte linéaire classique ne peut pas exprimer ce comptage, parce que le temps n'est pas découpé en cases. Il existe deux autres façons de l'écrire :

- créer une variable booléenne par camion et par minute (19 × 1440 variables), puis sommer chaque minute. C'est très lourd et le solveur raisonne mal sur ces variables ;
- écrire une disjonction « i avant j ou j avant i » pour chaque paire de camions. Le nombre de booléens croît en n², et cela ne marche que pour un seul quai.

CP-SAT propose un objet adapté à ce cas : la **variable d'intervalle**. Elle relie un début, une durée et une fin, sous la contrainte `début + durée = fin`, et représente la période `[début, fin)`. Un camion produit deux intervalles :

- `attentes` : `[a, s)`, de durée `w`, pendant lequel il est dans la file ;
- `quais` (ou `dechargements`) : `[s, s + delta)`, de durée fixe, pendant lequel il occupe un quai.

`add_cumulative(intervalles, demandes, capacité)` impose qu'à chaque instant, la somme des demandes des intervalles actifs ne dépasse pas la capacité. Ici, chaque camion demande 1, donc la contrainte compte les camions présents. Il s'agit d'une **contrainte globale** : le solveur dispose de raisonnements spécialisés pour elle (profils d'occupation, raisonnement énergétique) qui éliminent très tôt les plannings impossibles.

Deux conséquences pratiques :

- les intervalles sont semi-ouverts. Un camion qui libère le quai à 10:00 et un autre qui le prend à 10:00 ne sont pas en conflit ;
- un camion qui n'attend pas (`w = 0`) a un intervalle d'attente vide, donc il **n'occupe pas** la file.

À noter : `new_interval_var(a, w, s)` impose déjà `a + w = s`. La ligne `m.add(w == s − a)` est donc redondante dès qu'on crée l'intervalle d'attente. Comme `w ≥ 0` par son domaine, `m.add(s ≥ a)` l'est aussi. Ces lignes ne gênent pas le solveur et rendent le modèle plus lisible.

### Pourquoi il faut tester le statut avant de lire les valeurs

`solveur.solve(m)` renvoie un statut : `OPTIMAL`, `FEASIBLE` (solution trouvée sans preuve d'optimalité), `INFEASIBLE` (aucune solution n'existe) ou `MODEL_INVALID`/`UNKNOWN`. **Les valeurs `solveur.value(...)` n'ont de sens que pour `OPTIMAL` ou `FEASIBLE`.** Dans les autres cas, l'appel ne lève pas d'erreur : il renvoie des nombres arbitraires.

Les exécutions faites pour ce document le montrent. `version5.py` avec `Q = 1` est infaisable, mais le script, qui ne teste pas le statut, affiche quand même un tableau :

```
INFEASIBLE
p8      09:0076381059768266777:2076381059768266777:29 ...
attente totale : -23120926979352832824 min
```

`planning_contraintes.py` teste bien le statut avant d'écrire le JSON. En revanche, il affiche `attente totale : 0.0 minutes` avant ce test, y compris quand le problème est `INFEASIBLE`. Ce 0.0 n'est pas un résultat. Le bon schéma est le suivant :

```
si statut ∈ {OPTIMAL, FEASIBLE} :
    lire et afficher les valeurs
sinon :
    signaler l'absence de solution, ne rien lire
```

Seul `planning_contraintes.py` applique ce schéma. `entrepot.py`, `entrepot_avec_formalite.py`, `version5.py` et `version6.py` lisent les valeurs sans condition.

---

## 4. Les versions

L'ordre suit le contenu du code : chaque version reprend la précédente et y ajoute quelque chose. Il est confirmé par l'historique git et les dates de modification. Le code de `version5.py` part de `entrepot.py` (version 3) et non de la variante avec formalité (version 4). Ses changements sont donc décrits par rapport à la version 3.

Les résultats viennent des fichiers `resultat*.json` quand ils existent. Sinon, ils ont été obtenus en exécutant une copie du script où seule la ligne `Q = …` change (ortools 9.15.6755). Quand plusieurs plannings sont également optimaux, les horaires de certains camions peuvent varier d'une exécution à l'autre. Les totaux, eux, ne changent pas.

### Version 1 — modèle sans capacité

**Fichier :** `planning.py`

**Ce qu'elle fait** (point de départ, en plus du socle) :

```
VEHICULES : 15 camions, T de 480 (08:00) à 585 (09:45), trajet donné, Delta = 20
avance_max = 30

pour chaque C :
    a[C] ∈ [v["T"] − avance_max, v["T"]]   # arriver entre T−30 et T

minimiser  sum(w.values())
```

Il n'y a ni quai ni file : aucun intervalle, aucune contrainte cumulative. Le script écrit `resultat.json`.

**Pourquoi :** poser les variables et l'objectif sur un cas où l'optimum est évident, pour vérifier le modèle de base. C'est un premier essai naïf : on vérifie que le solveur tourne correctement avant d'ajouter les contraintes de capacité.

**Résultat :** `Q` n'existe pas dans cette version, et le résultat est le même quel que soit le nombre de quais. Statut **OPTIMAL**, attente totale **0 min** : chaque camion décharge dès son arrivée.

### Version 2 — quais et file d'attente

**Fichier :** `planning_contraintes.py`

**Ce qui change par rapport à la version 1 :**

```
Q = 2            # nombre de quais (le fichier contient actuellement 2)
file_max = 2     # camions en attente simultanément

pour chaque C :
    attentes.append( new_interval_var(a[C], w[C], s[C]) )               # [a, s)
    dechargements.append( new_fixed_size_interval_var(s[C], v["Delta"]) ) # [s, s+Delta)

add_cumulative(dechargements, [1]*n, Q)
add_cumulative(attentes,      [1]*n, file_max)

si statut ∈ {OPTIMAL, FEASIBLE} : construire le planning
sinon : attente_totale = None, planning = []
écrire resultat_Q{Q}.json
```

**Pourquoi :** la version 1 ne représente pas la ressource limitée. Cette version ajoute la capacité des quais et la taille maximale de la file, et fait du nombre de quais `Q` le paramètre étudié.

**Résultats** (concordent avec `resultat_Q1/2/3.json`) :

| Q | Statut | Attente totale |
|---|---|---|
| 1 | OPTIMAL | 100 min |
| 2 | OPTIMAL | 5 min (seul V15 attend) |
| 3 | OPTIMAL | 0 min |

**Pourquoi c'était INFEASIBLE avant (avec `a[C] ∈ [T−30, T]`) :**
Tous les camions devaient arriver au plus tard à leur heure T. Or avec 15 camions dont les rendez-vous s'étalent de 08:00 à 09:45 (soit 105 min), un seul quai de 20 min ne peut traiter que 105 / 20 ≈ 5 camions dans cette fenêtre. Les 10 autres ne peuvent pas accéder au quai à temps : il y a un conflit impossible à résoudre.

**Ce qui a changé :** la borne supérieure de `a[C]` est passée de `v["T"]` à `1440`. Cela autorise un camion à arriver plus tard que son rendez-vous, ce qui permet au solveur d'étaler les arrivées sur toute la journée. L'`avance_max` reste inchangé (30 min).

### Version 3 — données réelles de l'entrepôt

**Fichier :** `entrepot.py`

**Ce qui change par rapport à la version 2 :**

```
POINTS : 19 camions (p1…p19), HRDV de 480 (08:00) à 1050 (17:30),
         avec km et formalite (en minutes)
delta = 20 ; vitesse = 30 (km/h) ; Q = 1 ; file_attente = 2

trajet(km) = round(km / vitesse × 60)      # utilisé seulement pour afficher le départ

pour chaque p :
    a[p] ∈ [v["HRDV"] − avance_max, v["HRDV"]]
    quais.append( new_fixed_size_interval_var(s[p], delta) )

# la formalité est présente dans les données mais n'est pas utilisée
# plus de test du statut, plus d'écriture JSON : affichage d'un tableau seulement
```

Le modèle mathématique est identique à celui de la version 2. Seuls changent les données, les noms et la durée de trajet, désormais déduite de la distance.

**Pourquoi :** passer du jeu d'essai à des données réelles (commit « nouvelle résolution avec des données réelles »). Les rendez-vous s'étalent sur la journée, avec quatre camions à 09:30 (p10, p12, p13, p15).

**Résultats :**

| Q | Statut | Attente totale |
|---|---|---|
| 1 | OPTIMAL | 70 min (p12 : 50, p10 : 10, p14 : 10) |
| 2 | OPTIMAL | 0 min |
| 3 | OPTIMAL | 0 min |

### Version 4 — formalité au quai (variante)

**Fichier :** `entrepot_avec_formalite.py`

**Ce qui change par rapport à la version 3 :**

```
formalite_au_quai = True

pour chaque p :
    occupation = delta + (v["formalite"] si formalite_au_quai sinon 0)
    quais.append( new_fixed_size_interval_var(s[p], occupation) )   # [s, s+occupation)
```

**Pourquoi :** tenir compte du temps administratif (la formalité, de 0 à 45 min). Ce temps immobilise le quai en plus du déchargement. L'interrupteur `formalite_au_quai` permet de revenir à la version 3.

**Résultats :**

| Q | Statut | Attente totale |
|---|---|---|
| 1 | OPTIMAL | 192 min |
| 2 | OPTIMAL | 76 min |
| 3 | OPTIMAL | 8 min |

**Pourquoi c'était INFEASIBLE avant (avec `a[p] ∈ [HRDV−30, HRDV]`) :**
p10, p12, p13 et p15 ont tous rendez-vous à 09:30. Avec `formalite_au_quai = True`, chaque camion occupe le quai pendant `delta + formalite` (entre 38 et 65 min). Ces quatre camions doivent tous passer par le quai unique, mais leurs fenêtres d'arrivée se chevauchent totalement. Le solveur ne peut pas les intercaler : il manque du temps.

**Ce qui a changé :** la borne supérieure de `a[p]` est passée de `v["HRDV"]` à `1440`. Le solveur peut maintenant repousser l'arrivée de certains camions après leur rendez-vous pour libérer le quai. L'`avance_max` reste inchangé (30 min).

Cette variante n'est pas reprise par les versions 5 et 6.

### Version 5 — pas de déchargement avant le rendez-vous

**Fichier :** `version5.py`

**Ce qui change par rapport à la version 3** (et non la 4, voir plus haut) :

```
ouverture = 360   # 06:00

pour chaque p :
    a[p] ∈ [max(ouverture, v["HRDV"] − avance_max), v["HRDV"]]   # pas d'arrivée avant l'ouverture
    s[p] ∈ [v["HRDV"], 1440]                                     # pas de déchargement avant HRDV
```

**Pourquoi :** dans les versions précédentes, l'optimiseur fait décharger les camions jusqu'à 30 min avant leur rendez-vous, ce qui n'est sans doute pas acceptable pour l'entrepôt. La version 5 interdit de commencer avant `HRDV` et interdit d'arriver avant l'ouverture du site.

Conséquences visibles dans le code et les résultats :

- avec ces données, `ouverture` ne joue aucun rôle, car le premier rendez-vous est à 08:00 et `HRDV − 30` vaut toujours plus de 06:00 ;
- comme `a ≤ HRDV ≤ s`, arriver en avance ne fait qu'allonger l'attente. Le solveur fait donc arriver tout le monde exactement à `HRDV`, et `avance_max` ne sert plus à rien.

**Résultats :**

| Q | Statut | Attente totale |
|---|---|---|
| 1 | **INFEASIBLE** | — |
| 2 | OPTIMAL | 50 min |
| 3 | OPTIMAL | 20 min |

**Pourquoi Q = 1 est INFEASIBLE :**

La contrainte `s[p] ≥ HRDV` force chaque camion à attendre son rendez-vous avant de décharger. Quatre camions (p10, p12, p13, p15) ont tous rendez-vous à 09:30 (`HRDV = 570`). Avec un seul quai et 20 min de déchargement, ils se déchargent obligatoirement l'un après l'autre :

```
09:30 → 09:50 : 1er camion sur le quai
09:50 → 10:10 : 2e camion
10:10 → 10:30 : 3e camion
10:30 → 10:50 : 4e camion
```

Chacun doit arriver entre `max(360, 570 − 30) = 540` (06:00 ou 09:00) et `570` (09:30). Dès qu'un troisième camion de ce groupe arrive (au plus tard à 09:30), deux autres sont déjà dans la file — la capacité de 2 est atteinte. Le 4e ne peut plus y entrer : la file déborde.

Le solveur ne peut pas contourner ce blocage :
- `a[p] ≤ HRDV = 570` oblige les quatre camions à arriver au plus tard à 09:30 ;
- `s[p] ≥ HRDV = 570` leur interdit de décharger avant 09:30 ;
- avec Q = 1, le déchargement est séquentiel : trois des quatre camions attendent nécessairement ;
- `file_attente = 2` signifie qu'au plus 2 camions peuvent attendre en même temps.

Trois camions simultanément en attente alors que la file est limitée à 2 → le problème n'a pas de solution.

Avec Q = 2, les quatre camions peuvent se décharger par paires (09:30–09:50 × 2, puis 09:50–10:10 × 2) et la file reste à 1. Avec Q = 3, le retard se réduit encore davantage.

### Version 6 — retard autorisé mais pénalisé

**Fichier :** `version6.py`

**Ce qui change par rapport à la version 5 :**

```
Q = 1
r = {}

pour chaque p :
    a[p] ∈ [max(ouverture, v["HRDV"] − avance_max), 1440]   # on peut arriver après HRDV
    s[p] ∈ [0, 1440]                                          # pas de borne inf HRDV sur s
    r[p] ∈ [0, 1440]
    contrainte  r[p] = s[p] − v["HRDV"]                       # retard du début de déchargement

minimiser  1000 × sum(r.values()) + sum(w.values())

afficher  retard_total, en_retard (nombre de camions avec r > 0)
```

**Pourquoi :** la version 5 était infaisable avec un seul quai, parce que `s[p] ≥ HRDV` forçait tous les camions à attendre leur rendez-vous. La version 6 enlève cette contrainte et introduit un retard pénalisé : un camion peut décharger avant ou après son rendez-vous, mais s'il dépasse `HRDV`, le retard est fortement pénalisé (poids 1000). L'attente ne sert qu'à départager les solutions de même retard.

**Ce qui a changé par rapport à l'état initial :** `Q` est passé de 2 à 1, et la borne inférieure de `s[p]` est passée de `v["HRDV"]` à `0` (même raison que version 5 : avec Q=1 et `s[p] ≥ HRDV`, le problème était infaisable).

**Résultats** (objectif = 1000 × retard + attente) :

| Q | Statut | Retard total | Camions en retard | Attente totale | Objectif |
|---|---|---|---|---|---|
| 1 | OPTIMAL | 230 min | 5 | 0 min | 230 000 |
| 2 | OPTIMAL | 50 min | 3 | 0 min | 50 000 |
| 3 | OPTIMAL | 20 min | 1 | 0 min | 20 000 |

L'attente devient nulle : plutôt que de faire patienter un camion dans la file, le modèle le fait partir plus tard. Par exemple, avec Q = 1, p12 part à 10:34 pour un rendez-vous à 09:30.

---

## 5. Récapitulatif

| Version | Fichier | Camions | Borne d'arrivée `a` | Contrainte sur le déchargement `s` | Occupation du quai | Objectif | Q = 1 | Q = 2 | Q = 3 |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `planning.py` | 15 V | `[T−30, T]` | `s ≥ a`, aucune limite de quais | — | min Σw | 0 (sans Q) | 0 (sans Q) | 0 (sans Q) |
| 2 | `planning_contraintes.py` | 15 V | `[T−30, 1440]` ¹ | `s ≥ a`, ≤ Q quais, file ≤ 2 | `Delta` = 20 | min Σw | w = 100 | w = 5 | w = 0 |
| 3 | `entrepot.py` | 19 p | `[HRDV−30, HRDV]` | idem | `delta` = 20 | min Σw | w = 70 | w = 0 | w = 0 |
| 4 | `entrepot_avec_formalite.py` | 19 p | `[HRDV−30, 1440]` ¹ | idem | `delta + formalite` | min Σw | w = 192 | w = 76 | w = 8 |
| 5 | `version5.py` | 19 p | `[max(360, HRDV−30), HRDV]` | `s ≥ HRDV`, idem | `delta` = 20 | min Σw | INFEASIBLE | w = 50 | w = 20 |
| 6 | `version6.py` | 19 p | `[max(360, HRDV−30), 1440]` | `s ≥ 0` ¹, `r = s − HRDV`, idem | `delta` = 20 | min 1000·Σr + Σw | r = 230, w = 0 | r = 50, w = 0 | r = 20, w = 0 |

¹ Contrainte allégée pour rendre le problème faisable à Q = 1 (voir la section de chaque version pour le détail). La version 5 n'a pas d'allègement : elle reste INFEASIBLE à Q = 1 par conception.

Les résultats sont donnés en minutes. Les versions 1–2 et 3–6 n'utilisent pas les mêmes données : on ne peut comparer les chiffres qu'à l'intérieur de chaque groupe.

---

## 6. Correspondance pseudo-code / OR-Tools

| Pseudo-code | Appel OR-Tools (Python) |
|---|---|
| créer un modèle | `m = cp_model.CpModel()` |
| `x ∈ [lb, ub]` (entier) | `m.new_int_var(lb, ub, "nom")` |
| contrainte linéaire (`s ≥ a`, `w = s − a`, `r = s − HRDV`) | `m.add(s[p] >= a[p])`, `m.add(w[p] == s[p] - a[p])` |
| intervalle `[début, fin)` de durée variable | `m.new_interval_var(début, durée, fin, "nom")` |
| intervalle de durée fixe | `m.new_fixed_size_interval_var(début, durée, "nom")` |
| « au plus K intervalles actifs à la fois » | `m.add_cumulative(intervalles, [1] * n, K)` |
| minimiser une expression | `m.minimize(expr)` |
| résoudre | `solveur = cp_model.CpSolver()` puis `statut = solveur.solve(m)` |
| tester le statut | `statut in (cp_model.OPTIMAL, cp_model.FEASIBLE)` |
| nom lisible du statut | `solveur.status_name(statut)` |
| lire une valeur | `solveur.value(x)` |
| valeur de l'objectif | `solveur.objective_value` |

---

## 7. Hypothèses et questions ouvertes

### Hypothèses retenues dans le code

- Le temps est discret, à la minute, sur une seule journée (`0` à `1440`).
- La durée de trajet est fixe. Elle est donnée en version 1–2 et vaut `round(km / 30 × 60)` à partir de la version 3, avec une vitesse moyenne constante de 30 km/h. L'heure de départ n'est pas une variable du modèle : elle est calculée après coup.
- Les `Q` quais sont identiques et interchangeables. Le modèle ne dit pas *quel* quai reçoit quel camion, seulement combien sont occupés.
- La file ne compte que les camions **en attente**. Un camion au quai n'y figure pas, et un camion qui n'attend pas ne l'occupe jamais.
- La durée de déchargement est la même pour tous (20 min). La formalité ne compte que dans la version 4.
- Le sens de `HRDV` évolue : heure d'arrivée au plus tard (v3–v4), heure de déchargement au plus tôt (v5), puis heure cible avec pénalité de retard (v6).
- Le poids 1000 de la version 6 est censé faire passer le retard avant l'attente.

### Questions ouvertes

1. **Formalité** : elle est prise en compte dans la version 4, puis abandonnée dans les versions 5 et 6. A-t-elle lieu au quai, avant le quai, ou en dehors de l'entrepôt ?
2. **Poids 1000** : il ne garantit l'ordre retard puis attente que si l'attente totale ne peut pas dépasser 1000 minutes en échange d'une minute de retard en moins. Le domaine de `w` (jusqu'à 1440 par camion) ne l'interdit pas. Pour une garantie stricte, on peut résoudre en deux temps : minimiser `sum(r)`, fixer cette valeur, puis minimiser `sum(w)`.
3. **Retard** : `r` mesure le retard du *début de déchargement*, pas de l'arrivée. Est-ce bien la mesure voulue ?
4. **Ouverture et fermeture** : `ouverture = 360` n'a aucun effet avec ces données, et aucune heure de fermeture n'est imposée. En version 6, un camion pourrait être repoussé jusqu'en fin de journée.
5. **Test du statut** : les versions 3 à 6 n'en ont pas, et affichent des valeurs fausses quand le problème est infaisable (§ 3). Faut-il le rétablir ?
6. **Temps de calcul** : aucune limite de temps n'est fixée (`max_time_in_seconds`). C'est sans conséquence pour 19 camions, mais à prévoir sur des jeux plus grands.
8. **Test du statut dans version5.py** : quand Q = 1, le script affiche un tableau de valeurs sans sens (voir § 3). Un test `if statut in {OPTIMAL, FEASIBLE}` avant la lecture éviterait cela.
from ortools.sat.python import cp_model

m = cp_model.CpModel()

a, s, w = {}, {}, {}

VEHICULES = {
    "V1":  {"T": 480, "trajet": 45, "Delta": 20},
    "V2":  {"T": 488, "trajet": 35, "Delta": 20},
    "V3":  {"T": 495, "trajet": 50, "Delta": 20},
    "V4":  {"T": 503, "trajet": 30, "Delta": 20},
    "V5":  {"T": 510, "trajet": 40, "Delta": 20},
    "V6":  {"T": 518, "trajet": 25, "Delta": 20},
    "V7":  {"T": 525, "trajet": 55, "Delta": 20},
    "V8":  {"T": 533, "trajet": 42, "Delta": 20},
    "V9":  {"T": 540, "trajet": 33, "Delta": 20},
    "V10": {"T": 548, "trajet": 48, "Delta": 20},
    "V11": {"T": 555, "trajet": 37, "Delta": 20},
    "V12": {"T": 563, "trajet": 60, "Delta": 20},
    "V13": {"T": 570, "trajet": 28, "Delta": 20},
    "V14": {"T": 578, "trajet": 52, "Delta": 20},
    "V15": {"T": 585, "trajet": 43, "Delta": 20},
}

avance_max = 30
Q = 1        # 1 seul quai de déchargement
file_max = 2  # au plus 2 camions en attente en même temps

attentes, dechargements = [], []



def hhmm(minutes):
    return f"{minutes // 60:02d}:{minutes % 60:02d}" 


for C, v in VEHICULES.items():
    a[C] = m.new_int_var(v["T"] - avance_max, 1440, f"a_{C}")  # borne sup à 1440 : on autorise les arrivées tardives pour que Q=1 reste faisable
    s[C] = m.new_int_var(0, 1440, f"s_{C}")
    w[C] = m.new_int_var(0, 1440, f"w_{C}")
    m.add(s[C] >= a[C]) 
    m.add(w[C] == s[C] - a[C])
    attentes.append(
        m.new_interval_var(a[C], w[C], s[C], f"att_{C}"))
    dechargements.append(
        m.new_fixed_size_interval_var(s[C], v["Delta"], f"dech_{C}"))

n = len(VEHICULES)

m.add_cumulative(dechargements, [1] * n, Q) #blocs demande capacite 
m.add_cumulative(attentes, [1] * n, file_max)


m.minimize(sum(w.values())) 

solveur = cp_model.CpSolver()
statut = solveur.solve(m) 

print(solveur.status_name(statut))

if statut in (cp_model.OPTIMAL, cp_model.FEASIBLE):
    total = 0
    print(f"{'véh':<6}{'T':>7}{'départ':>9}{'arrivée':>9}{'décharg.':>10}{'attente':>9}")
    for C, v in VEHICULES.items():
        arrivee = solveur.value(a[C])
        attente = solveur.value(w[C])
        total += attente
        print(f"{C:<6}{hhmm(v['T']):>7}"
              f"{hhmm(arrivee - v['trajet']):>9}"
              f"{hhmm(arrivee):>9}"
              f"{hhmm(solveur.value(s[C])):>10}"
              f"{attente:>9}")
    print(f"\nattente totale : {total} min")
else:
    print("aucune solution")








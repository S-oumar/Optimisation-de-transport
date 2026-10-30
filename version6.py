import json 
from ortools.sat.python import cp_model
m = cp_model.CpModel()

POINTS = {
    "p1":  {"HRDV": 780,  "km": 3.2,  "formalite": 0},
    "p2":  {"HRDV": 600,  "km": 9.8,  "formalite": 40},
    "p3":  {"HRDV": 810,  "km": 17.2, "formalite": 26},
    "p4":  {"HRDV": 1020, "km": 7.3,  "formalite": 20},
    "p5":  {"HRDV": 960,  "km": 11.0, "formalite": 45},
    "p6":  {"HRDV": 1050, "km": 4.5,  "formalite": 20},
    "p7":  {"HRDV": 870,  "km": 6.6,  "formalite": 20},
    "p8":  {"HRDV": 540,  "km": 4.6,  "formalite": 30},
    "p9":  {"HRDV": 480,  "km": 4.3,  "formalite": 20},
    "p10": {"HRDV": 570,  "km": 6.9,  "formalite": 30},
    "p11": {"HRDV": 810,  "km": 11.7, "formalite": 15},
    "p12": {"HRDV": 570,  "km": 18.2, "formalite": 20},
    "p13": {"HRDV": 570,  "km": 7.4,  "formalite": 18},
    "p14": {"HRDV": 630,  "km": 22.8, "formalite": 45},
    "p15": {"HRDV": 570,  "km": 4.0,  "formalite": 20},
    "p18": {"HRDV": 720,  "km": 10.5, "formalite": 0},
}

delta = 20
avance_max=30
vitesse = 30 
Q=2
file_attente = 2 

def hhmm(minutes):
    return f"{minutes//60:02d}:{minutes%60:02d}"

def trajet(km):
    return round(km/vitesse*60) 


a, s, w, r = {}, {}, {}, {} 
attentes, quais = [], [] 
ouverture = 360

for p, v in POINTS.items():

    a[p] = m.new_int_var(max(ouverture,v["HRDV"] - avance_max), 1440, f"a_{p}")
    s[p] = m.new_int_var(v["HRDV"], 1440, f"s_{p}")
    w[p] = m.new_int_var(0, 1440, f"w_{p}")  
    r[p] = m.new_int_var(0, 1440, f"r_{p}")

    m.add(r[p] == s[p] - v["HRDV"])
    m.add(s[p] >= a[p])
    m.add(w[p] == s[p] - a[p])  

    attentes.append(m.new_interval_var(a[p], w[p], s[p], f"att_{p}"))
    quais.append(m.new_fixed_size_interval_var(s[p], delta, f"quai_{p}"))

n = len(POINTS)

m.add_cumulative(quais, [1] * n, Q)
m.add_cumulative(attentes, [1] * n, file_attente) 

m.minimize(1000 * sum(r.values()) + sum(w.values())) 
solveur = cp_model.CpSolver()
statut = solveur.solve(m)

print(solveur.status_name(statut))

total = 0
print(f"{'pt':<6}{'HRDV':>7}{'départ':>9}{'arrivée':>9}{'quai':>9}{'attente':>9}")
for p, v in POINTS.items():
    
    arrivee = solveur.value(a[p])
    attente = solveur.value(w[p])

    total += attente
    print(f"{p:<6}{hhmm(v['HRDV']):>7}"
          f"{hhmm(arrivee - trajet(v['km'])):>9}"
          f"{hhmm(arrivee):>9}"
          f"{hhmm(solveur.value(s[p])):>9}"
          f"{attente:>9}")
print(f"\nattente totale : {total} min")

retard_total = sum(solveur.value(r[p]) for p in POINTS)
en_retard = sum(1 for p in POINTS if solveur.value(r[p]) > 0)
print(f"retard total : {retard_total} min sur {en_retard} camions") 
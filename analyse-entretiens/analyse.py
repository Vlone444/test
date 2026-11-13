#!/usr/bin/env python3
"""Analyse lexicale d'entretiens : base de données + diagrammes des mots récurrents.

Usage :
    python analyse.py DOSSIER_DES_ENTRETIENS

Le script :
  1. lit tous les entretiens du dossier (.txt, .docx, .pdf), sous-dossiers compris ;
  2. compte les mots de chaque entretien et les range dans une base SQLite ;
  3. produit, pour tout le corpus et pour chaque patient, un diagramme avec le mot
     le plus récurrent au centre et les suivants autour, ainsi que des tableaux CSV.

Identification du patient :
  - si les entretiens sont rangés dans un sous-dossier par patient, le nom du
    sous-dossier sert d'identifiant ;
  - sinon, c'est le début du nom de fichier, jusqu'au premier « _ »
    (« P001_entretien2.txt » -> patient « P001 »).
"""

import argparse
import csv
import math
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

ICI = Path(__file__).resolve().parent
EXTENSIONS = {".txt", ".docx", ".pdf"}
LETTRES = r"[a-zàâäéèêëîïôöùûüçœæ]+"
MOT = re.compile(rf"{LETTRES}(?:-{LETTRES})*")     # garde les mots composés : rendez-vous
PARTIE = re.compile(LETTRES)


# --------------------------------------------------------------------------- lecture

def lire_texte(fichier: Path) -> str:
    ext = fichier.suffix.lower()
    if ext == ".txt":
        donnees = fichier.read_bytes()
        for encodage in ("utf-8-sig", "cp1252"):
            try:
                return donnees.decode(encodage)
            except UnicodeDecodeError:
                continue
        return donnees.decode("latin-1")
    if ext == ".docx":
        try:
            import docx
        except ImportError:
            sys.exit("Fichiers Word détectés : installez d'abord  pip install python-docx")
        return "\n".join(p.text for p in docx.Document(str(fichier)).paragraphs)
    if ext == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError:
            sys.exit("Fichiers PDF détectés : installez d'abord  pip install pypdf")
        return "\n".join(page.extract_text() or "" for page in PdfReader(str(fichier)).pages)
    raise ValueError(f"format non géré : {fichier}")


def charger_mots_vides(fichier: Path) -> set:
    mots = set()
    for ligne in fichier.read_text(encoding="utf-8").splitlines():
        ligne = ligne.split("#", 1)[0]
        mots.update(PARTIE.findall(ligne.lower()))
    return mots


def identifiant_patient(fichier: Path, racine: Path) -> str:
    relatif = fichier.relative_to(racine)
    if len(relatif.parts) > 1:
        return relatif.parts[0]
    return fichier.stem.split("_")[0]


def compter(texte: str, mots_vides: set, prefixes_ignores: list) -> Counter:
    if prefixes_ignores:
        lignes = [l for l in texte.splitlines()
                  if not l.strip().lower().startswith(tuple(prefixes_ignores))]
        texte = "\n".join(lignes)
    compte = Counter()
    for mot in MOT.findall(texte.lower()):
        # un mot composé est ignoré si toutes ses parties sont des mots vides (est-ce, peut-être)
        if any(len(p) > 2 and p not in mots_vides for p in mot.split("-")):
            compte[mot] += 1
    return compte


# ------------------------------------------------------------------------------ base

SCHEMA = """
CREATE TABLE entretiens (
    id         INTEGER PRIMARY KEY,
    patient_id TEXT NOT NULL,
    fichier    TEXT NOT NULL UNIQUE,
    nb_mots    INTEGER NOT NULL
);
CREATE TABLE frequences (
    entretien_id INTEGER NOT NULL REFERENCES entretiens(id),
    mot          TEXT NOT NULL,
    occurrences  INTEGER NOT NULL,
    PRIMARY KEY (entretien_id, mot)
);
CREATE INDEX idx_frequences_mot ON frequences(mot);
CREATE INDEX idx_entretiens_patient ON entretiens(patient_id);
"""


def construire_base(dossier: Path, base: Path, mots_vides: set, prefixes: list):
    fichiers = sorted(f for f in dossier.rglob("*")
                      if f.is_file() and f.suffix.lower() in EXTENSIONS)
    if not fichiers:
        sys.exit(f"Aucun entretien (.txt, .docx, .pdf) trouvé dans {dossier}")

    if base.exists():
        base.unlink()          # la base est reconstruite à chaque lancement
    con = sqlite3.connect(base)
    con.executescript(SCHEMA)

    vides = []
    for fichier in fichiers:
        try:
            compte = compter(lire_texte(fichier), mots_vides, prefixes)
        except Exception as erreur:                       # fichier illisible
            print(f"  ! ignoré ({erreur}) : {fichier}")
            continue
        if not compte:
            vides.append(fichier)
        cur = con.execute(
            "INSERT INTO entretiens (patient_id, fichier, nb_mots) VALUES (?, ?, ?)",
            (identifiant_patient(fichier, dossier), str(fichier.relative_to(dossier)),
             sum(compte.values())))
        con.executemany("INSERT INTO frequences VALUES (?, ?, ?)",
                        [(cur.lastrowid, mot, n) for mot, n in compte.items()])
    con.commit()
    for fichier in vides:
        print(f"  ! aucun mot extrait (PDF scanné ? fichier vide ?) : {fichier}")
    return con


def top_mots(con, patient=None, limite=25):
    """[(mot, occurrences, nb d'entretiens)] du plus au moins fréquent."""
    filtre, params = ("WHERE e.patient_id = ?", (patient, limite)) if patient else ("", (limite,))
    return con.execute(f"""
        SELECT f.mot, SUM(f.occurrences) AS n, COUNT(*) AS nb_entretiens
        FROM frequences f JOIN entretiens e ON e.id = f.entretien_id
        {filtre}
        GROUP BY f.mot ORDER BY n DESC, f.mot LIMIT ?""", params).fetchall()


# ------------------------------------------------------------------------- diagramme

COULEURS = ["#b3261e", "#1f4e79", "#5f6b7a"]     # centre, 1er anneau, 2e anneau


def diagramme(mots, titre, sous_titre, fichier: Path):
    """Mot le plus récurrent au centre ; rangs 2-9 sur un anneau, 10-25 sur le suivant."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if not mots:
        return
    fig, ax = plt.subplots(figsize=(14, 11))
    ax.set_xlim(-1.9, 1.9)
    ax.set_ylim(-1.5, 1.5)
    ax.axis("off")

    mot, n_max, _ = mots[0]
    taille_centre = max(24, min(48, 340 / max(len(mot), 1)))
    ax.text(0, 0.03, mot, ha="center", va="center", fontsize=taille_centre,
            weight="bold", color=COULEURS[0])
    ax.text(0, -0.13, f"{n_max} occurrences", ha="center", va="center",
            fontsize=13, color=COULEURS[0])

    # anneaux elliptiques (plus larges que hauts) : les mots s'étalent à l'horizontale
    anneaux = [(mots[1:9], 1.02, 0.62, 13, 24), (mots[9:25], 1.62, 1.18, 10, 15)]
    for i, (anneau, rx, ry, taille_min, taille_max) in enumerate(anneaux):
        for k, (mot, n, _) in enumerate(anneau):
            angle = math.pi / 2 - 2 * math.pi * k / len(anneau)   # sens horaire depuis le haut
            decal = 0.09 if k % 2 else -0.09                      # quinconce : évite les chevauchements
            taille = taille_min + (taille_max - taille_min) * math.sqrt(n / n_max)
            x, y = (rx + decal) * math.cos(angle), (ry + decal) * math.sin(angle)
            ax.text(x, y, mot, ha="center", va="center", fontsize=taille,
                    color=COULEURS[i + 1], weight="bold" if i == 0 else "normal")
            ax.text(x, y - 0.035 - taille / 400, str(n), ha="center", va="top",
                    fontsize=8, color="#8a8f98")

    fig.suptitle(titre, fontsize=20, weight="bold", y=0.97)
    fig.text(0.5, 0.925, sous_titre, ha="center", fontsize=12, color="#5f6b7a")
    fig.savefig(fichier, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def nom_de_fichier(texte: str) -> str:
    return re.sub(r"[^\w.-]+", "_", texte).strip("_") or "patient"


# ------------------------------------------------------------------------------ main

def main():
    p = argparse.ArgumentParser(description="Mots les plus récurrents dans des entretiens.")
    p.add_argument("dossier", type=Path, help="dossier contenant les entretiens")
    p.add_argument("--sortie", type=Path, default=Path("resultats"),
                   help="dossier où écrire la base, les CSV et les diagrammes (défaut : resultats)")
    p.add_argument("--top", type=int, default=25, help="nombre de mots par diagramme (max 25)")
    p.add_argument("--mots-vides", type=Path, default=ICI / "mots_vides.txt",
                   help="fichier listant les mots à ignorer")
    p.add_argument("--ignorer-lignes", nargs="*", default=[], metavar="PREFIXE",
                   help="ignorer les lignes commençant par ces préfixes, "
                        "ex. --ignorer-lignes \"Intervieweur :\" \"Q :\"")
    p.add_argument("--sans-diagrammes-patients", action="store_true",
                   help="ne produire que le diagramme global")
    args = p.parse_args()

    if not args.dossier.is_dir():
        sys.exit(f"Dossier introuvable : {args.dossier}")
    args.sortie.mkdir(parents=True, exist_ok=True)
    dossier_diag = args.sortie / "diagrammes"
    dossier_diag.mkdir(exist_ok=True)
    top = max(1, min(args.top, 25))

    mots_vides = charger_mots_vides(args.mots_vides)
    prefixes = [x.strip().lower() for x in args.ignorer_lignes if x.strip()]

    print("Lecture des entretiens…")
    con = construire_base(args.dossier, args.sortie / "entretiens.db", mots_vides, prefixes)
    nb_entretiens, nb_patients = con.execute(
        "SELECT COUNT(*), COUNT(DISTINCT patient_id) FROM entretiens").fetchone()
    print(f"  {nb_entretiens} entretiens, {nb_patients} patients")

    # Tableau global
    with open(args.sortie / "frequences_corpus.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["rang", "mot", "occurrences", "nb_entretiens"])
        for rang, ligne in enumerate(top_mots(con, limite=1_000_000), 1):
            w.writerow([rang, *ligne])

    # Tableau par patient (les `top` premiers mots de chacun)
    patients = [r[0] for r in con.execute(
        "SELECT DISTINCT patient_id FROM entretiens ORDER BY patient_id")]
    with open(args.sortie / "frequences_par_patient.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["patient", "rang", "mot", "occurrences", "nb_entretiens"])
        for patient in patients:
            for rang, ligne in enumerate(top_mots(con, patient, top), 1):
                w.writerow([patient, rang, *ligne])

    print("Diagrammes…")
    diagramme(top_mots(con, limite=top), "Mots les plus récurrents",
              f"{nb_entretiens} entretiens · {nb_patients} patients",
              dossier_diag / "_corpus.png")
    if not args.sans_diagrammes_patients:
        for patient in patients:
            n = con.execute("SELECT COUNT(*) FROM entretiens WHERE patient_id = ?",
                            (patient,)).fetchone()[0]
            diagramme(top_mots(con, patient, top), f"Patient {patient}",
                      f"{n} entretien{'s' if n > 1 else ''}",
                      dossier_diag / f"{nom_de_fichier(patient)}.png")

    print("\nLes 10 mots les plus récurrents du corpus :")
    for mot, n, nb in top_mots(con, limite=10):
        print(f"  {mot:18} {n:7} occurrences, dans {nb} entretiens")
    print(f"\nRésultats dans : {args.sortie.resolve()}")


if __name__ == "__main__":
    main()

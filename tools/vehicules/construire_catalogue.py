"""Construit le catalogue des véhicules électriques de l'intégration à partir d'OpenEV Data.

Source : https://github.com/open-ev-data/open-ev-data-dataset (licence CDLA-Permissive-2.0).
Le jeu est rédigé en couches (base du modèle, année, variante) : on les fusionne selon les règles
du jeu (objets fusionnés par clé, valeurs et listes remplacées par la couche la plus haute), puis on
ne garde que ce dont l'intégration a besoin pour la recharge.

Usage : python tools/vehicules/construire_catalogue.py <dossier du jeu cloné>
Écrit custom_components/ucaness/donnees/vehicules.json (trié, reproductible).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

SORTIE = Path(__file__).resolve().parents[2] / "custom_components" / "ucaness" / "donnees" / "vehicules.json"
ANNEE_MINI = 2018


def fusion(bas: dict, haut: dict) -> dict:
    out = dict(bas)
    for cle, val in haut.items():
        if isinstance(val, dict) and isinstance(out.get(cle), dict):
            out[cle] = fusion(out[cle], val)
        else:
            out[cle] = val
    return out


def gabarit(rec: dict) -> str:
    """Forme du dessin : citadine, berline, suv ou utilitaire."""
    style = ((rec.get("body") or {}).get("style") or "").lower()
    type_ = (rec.get("vehicle_type") or "").lower()
    longueur = (rec.get("dimensions") or {}).get("length_mm") or 0
    if type_ in ("van", "pickup") or style in ("van", "pickup", "minivan", "mpv"):
        return "utilitaire"
    if type_ == "suv" or "suv" in style or style == "crossover":
        return "suv"
    if style in ("hatchback", "quadricycle") and (not longueur or longueur < 4200):
        return "citadine"
    if longueur and longueur < 4000:
        return "citadine"
    return "berline"


def resume(rec: dict) -> dict | None:
    batterie = rec.get("battery") or {}
    capa = batterie.get("pack_capacity_kwh_net") or batterie.get("pack_capacity_kwh_gross")
    ac = (rec.get("charging") or {}).get("ac") or {}
    if not capa or not ac.get("max_power_kw"):
        return None
    wltp = next((r.get("range_km") for r in (rec.get("range") or {}).get("rated") or [] if r.get("cycle") == "wltp"), None)
    trim = (rec.get("trim") or {}).get("name") or ""
    variante = (rec.get("variant") or {}).get("name") or ""
    trim = "" if trim.lower() == "base" else trim
    # La variante répète souvent la finition (« M50 M50 ») : on ne garde alors que la variante.
    version = variante if trim and variante.lower().startswith(trim.lower()) else " ".join(x for x in (trim, variante) if x)
    ident = ":".join(x for x in (rec["make"]["slug"], rec["model"]["slug"], str(rec["year"]),
                                  (rec.get("trim") or {}).get("slug", "base"), (rec.get("variant") or {}).get("slug", "")) if x)
    return {
        "id": ident,
        "marque": rec["make"]["name"],
        "modele": rec["model"]["name"],
        "annee": rec["year"],
        "version": version,
        "gabarit": gabarit(rec),
        "capacite_kwh": round(float(capa), 1),
        "ac_kw": round(float(ac["max_power_kw"]), 1),
        "phases": int(ac.get("phases") or 1),
        # Consommation estimée d'après l'autonomie WLTP (kWh/100 km), faute de mieux.
        "conso_kwh_100km": round(float(capa) / wltp * 100, 1) if wltp else None,
    }


def construire(racine: Path) -> list[dict]:
    sortie = []
    for base in sorted((racine / "src").glob("*/*/base.json")):
        modele = json.loads(base.read_text(encoding="utf-8"))
        for dossier in sorted(p for p in base.parent.iterdir() if p.is_dir() and p.name.isdigit()):
            if int(dossier.name) < ANNEE_MINI:
                continue
            fichiers = {f.stem: json.loads(f.read_text(encoding="utf-8")) for f in dossier.glob("*.json")}
            racines = {k: v for k, v in fichiers.items() if "variant" not in v}
            for nom, annee in racines.items():
                rec = fusion(modele, annee)
                rec.setdefault("year", int(dossier.name))
                for r in (rec, *(fusion(rec, v) for k, v in fichiers.items()
                                 if "variant" in v and k.startswith(nom + "_"))):
                    res = resume(r)
                    if res:
                        sortie.append(res)
    vus, propre = set(), []
    for v in sorted(sortie, key=lambda x: (x["marque"], x["modele"], -x["annee"], x["version"], x["id"])):
        # Même identifiant, ou même version affichée avec les mêmes valeurs : une seule fiche.
        cle = (v["marque"], v["modele"], v["annee"], v["version"], v["capacite_kwh"], v["ac_kw"], v["phases"])
        if v["id"] not in vus and cle not in vus:
            vus |= {v["id"], cle}
            propre.append(v)
    return propre


def main() -> None:
    racine = Path(sys.argv[1])
    version = json.loads((racine / "package.json").read_text(encoding="utf-8")).get("version")
    vehicules = construire(racine)
    SORTIE.write_text(json.dumps({
        "source": "OpenEV Data (https://github.com/open-ev-data/open-ev-data-dataset)",
        "licence": "CDLA-Permissive-2.0 (https://cdla.dev/permissive-2-0/)",
        "version_source": version,
        "vehicules": vehicules,
    }, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"{len(vehicules)} véhicules -> {SORTIE}")


if __name__ == "__main__":
    main()

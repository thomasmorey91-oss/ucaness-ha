"""Test rapide, depuis votre PC, de la lecture UCANESS (avant installation dans Home Assistant).

Usage (Python 3.11+ et aiohttp : `pip install aiohttp`) :
    python tools/ucaness_probe.py

Le script demande l'e-mail, le mot de passe (saisie masquée) et l'ID EMS,
puis affiche les principales mesures. Il ne lit que des données : aucun réglage n'est modifié.
Le mot de passe n'est ni affiché ni enregistré.
"""
import asyncio
import getpass
import importlib.util
import pathlib
import sys

import aiohttp

PKG = pathlib.Path(__file__).resolve().parents[1] / "custom_components" / "ucaness"


def _load(name):
    spec = importlib.util.spec_from_file_location(f"ucaness_{name}", PKG / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


api = _load("api")
parser = _load("parser")


async def main() -> None:
    email = input("E-mail UCANESS : ").strip()
    password = getpass.getpass("Mot de passe UCANESS (masqué) : ")
    code = input("ID EMS (encadré « Détails » du portail) : ").strip()
    async with aiohttp.ClientSession() as session:
        client = api.UcanessClient(session, email, api.hash_password(password))
        detail = await client.get_detail(code)
        config = await client.get_config(code)
        events = await client.get_events(code)
    values = parser.extract({"detail": detail, "config": config, "events": events})
    width = max(len(m.name) for m in parser.MEASURES)
    for m in parser.MEASURES:
        v = values.get(m.key)
        print(f"{m.name:<{width}}  {'' if v is None else v} {m.unit or ''}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except api.UcanessAuthError:
        print("Identifiants refusés par UCANESS.")
    except api.UcanessError as err:
        print(f"Erreur : {err}")

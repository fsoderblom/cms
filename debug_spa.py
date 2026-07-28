#!/usr/bin/env python3
"""Standalone script to compare /spas/{id} vs /spas list freshness.

Usage:
    CMS_EMAIL=you@example.com CMS_PASSWORD=secret python3 debug_spa.py [--watch] [--json]

If CMS_EMAIL/CMS_PASSWORD are not set, you'll be prompted (password hidden).
--watch polls every 10s so you can compare against the physical panel live.
--json prints each sample as a JSON object instead of the human-readable summary.
"""
import os
import sys
import time
import json
import getpass
import requests

LOGIN_URL = "https://iot.controlmyspa.com/auth/login"
SPAS_URL = "https://iot.controlmyspa.com/spas"

def login(session, email, password):
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://controlmyspa.com",
        "Referer": "https://controlmyspa.com/",
        "User-Agent": "Mozilla/5.0",
    }
    r = session.post(LOGIN_URL, json={"email": email, "password": password}, headers=headers)
    r.raise_for_status()
    token = r.json()["data"]["accessToken"]
    return token

def fetch(session, token):
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "Mozilla/5.0",
    }
    spas_resp = session.get(SPAS_URL, headers=headers)
    spas_resp.raise_for_status()
    spas = spas_resp.json().get("data", {}).get("spas", [])
    if not spas:
        raise SystemExit("No spas found")
    spa = spas[0]
    spa_id = spa["_id"]
    listed = spa.get("currentState", {})

    single_resp = session.get(f"{SPAS_URL}/{spa_id}", headers=headers)
    single_resp.raise_for_status()
    single = single_resp.json().get("currentState", {})

    return spa_id, listed, single, spa.get("lastMqttMessages"), spa.get("c8zCurrentState")

def summarize(label, cs):
    keys = ["currentTemp", "desiredTemp", "errorCode", "updatedAt", "uplinkTimestamp", "staleTimestamp"]
    parts = [f"{k}={cs.get(k)}" for k in keys]
    print(f"  {label}: " + " ".join(parts))
    if "components" in cs:
        comps = cs["components"]
        on = [f"{c.get('name')}({c.get('port')})={c.get('value')}" for c in comps]
        print(f"    components: {on}")
    else:
        print("    components: <missing>")

def main():
    email = os.environ.get("CMS_EMAIL") or input("Email: ")
    password = os.environ.get("CMS_PASSWORD") or getpass.getpass("Password: ")
    watch = "--watch" in sys.argv
    as_json = "--json" in sys.argv

    session = requests.Session()
    token = login(session, email, password)
    if not as_json:
        print(f"Logged in OK.\n")

    while True:
        spa_id, listed, single, last_mqtt, c8z = fetch(session, token)
        if as_json:
            record = {
                "spaId": spa_id,
                "sampledAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "list": listed,
                "single": single,
                "c8zCurrentState": c8z,
                "lastMqttMessages": last_mqtt,
            }
            print(json.dumps(record, indent=2))
        else:
            print(f"--- spa_id={spa_id} @ {time.strftime('%H:%M:%S')} ---")
            summarize("/spas list  ", listed)
            summarize("/spas/{id}  ", single)
            print(f"  c8zCurrentState: {c8z}")
            print(f"  lastMqttMessages: {last_mqtt}")
            print()
        if not watch:
            break
        time.sleep(10)

if __name__ == "__main__":
    main()

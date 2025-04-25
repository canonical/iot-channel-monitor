"""This module provide Test Observer API"""

import json
import requests


# pylint: disable=R0913, R0914, R0917
def start_exec(
    name="",
    version="",
    arch="",
    env="",
    ci_link="https://example.com",
    test_plan="",
    status="IN_PROGRESS",
    family="",
    revision=0,
    track="",
    store="",
    branch="",
    stage="",
):
    """API for create Test Observer execution and return ID"""

    url = "https://test-observer-api-staging.canonical.com/v1/test-executions/start-test"
    headers = {
        "accept": "application/json",
        "Content-Type": "application/json",
    }

    payload = {
        "name": name,
        "version": version,
        "arch": arch,
        "environment": env,
        "ci_link": ci_link,
        "test_plan": test_plan,
        "initial_status": status,
        "family": family,
        "revision": revision,
        "track": track,
        "store": store,
        "branch": branch,
        "execution_stage": stage,
    }
    response = requests.put(url, json=payload, headers=headers, timeout=10)

    if response.status_code == 200:
        data = response.json()
        return data["id"]

    print(f"STATUS = {response.status_code}")
    return -1


def patch_exec(eid="", c3_link=None, ci_link=None, status=""):
    """patch execution"""

    url = f"https://test-observer-api-staging.canonical.com/v1/test-executions/{eid}"
    headers = {
        "accept": "application/json",
        "Content-Type": "application/json",
    }

    payload = {"c3_link": c3_link, "ci_link": ci_link, "status": status}
    response = requests.patch(url, json=payload, headers=headers, timeout=10)

    if response.status_code == 200:
        return 0

    print(f"STATUS = {response.status_code}")
    return -1


def get_exec_results(aid):
    """get execution result"""
    if not isinstance(aid, (str, int)):
        return []

    url = f"https://test-observer-api-staging.canonical.com/v1/artefacts/{aid}/builds"
    headers = {
        "accept": "application/json",
        "Content-Type": "application/json",
    }

    response = requests.get(url, headers=headers, timeout=10)
    if response.status_code != 200:
        raise ConnectionError("Failed to connect to the server")

    return json.loads(response.text)


def get_artefact_status(name="", version="", family=""):
    """get artefact status"""
    url = f"https://test-observer-api-staging.canonical.com/v1/artefacts?family={family}"
    headers = {
        "accept": "application/json",
        "Content-Type": "application/json",
    }

    response = requests.get(url, headers=headers, timeout=10)
    if response.status_code != 200:
        raise ConnectionError("Failed to connect to the server")

    result = None
    artefacts_datas = json.loads(response.text)
    for artefact in artefacts_datas:
        if artefact["name"] == name and artefact["version"] == version:
            result = {}
            result["id"] = artefact["id"]
            result["status"] = artefact["status"]
            break

    return result

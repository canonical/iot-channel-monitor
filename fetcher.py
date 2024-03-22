import yaml
import requests
import sys


def dump_sanp_data():
    """Fetch snap information from SNAP store

    Returns:
        dict: the SNAP information for specific snaps
    """
    with open("snaps.yaml") as f:
        snap_data = yaml.safe_load(f)
        SNAPS = [(k, snap_data[k]["store"]) for k in snap_data.keys()]

    mysnapdict = dict()
    for snap, store in SNAPS:
        url = ("https://api.snapcraft.io/v2/snaps/info/"
               "{}?fields=version,revision,snap-yaml".format(snap))
        headers = {"Snap-Device-Series": "16",
                   "Snap-Device-Store": store}
        a = requests.get(url, headers=headers)
        j = a.json()
        if not hasattr(mysnapdict, snap):
            mysnapdict[snap] = dict()
        if "channel-map" not in j:
            print("WARNING: BAD ITEM: ", file=sys.stderr)
            print(j, file=sys.stderr)
            continue
        for x in j.get("channel-map"):
            track = x["channel"]["track"]
            version = x["version"]
            revision = x["revision"]
            snap_yaml = x.get("snap-yaml")
            if snap_yaml:
                snap_dict = yaml.safe_load(snap_yaml)
                grade = snap_dict.get("grade")
            else:
                grade = "unknown"
            # Special case: We only want to test mir-kiosk for grade: stable
            if snap == "mir-kiosk" and grade == "devel":
                continue
            if track not in mysnapdict[snap]:
                mysnapdict[snap][track] = dict()
            risk = x["channel"]["risk"]
            if risk not in mysnapdict[snap][track]:
                mysnapdict[snap][track][risk] = dict()
            architecture = x["channel"]["architecture"]
            if architecture not in mysnapdict[snap][track][risk]:
                mysnapdict[snap][track][risk][architecture] = dict()
            mysnapdict[snap][track][risk][architecture]["version"] = version
            mysnapdict[snap][track][risk][architecture]["revision"] = revision
            mysnapdict[snap][track][risk][architecture]["grade"] = grade

    return mysnapdict


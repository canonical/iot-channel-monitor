"""Channel Monitor main module"""

import time
import threading
from typing import TypedDict
import jenkins
import requests
from fetcher import dump_sanp_data
from testob_api import (
    get_exec_results,
    get_artefact_status,
)


class JenkinsServerInfo(TypedDict):
    """
    The JenkinsServerInfo data type
    """

    server: str
    username: str
    password: str


class Monitor:
    """
    The module to monitor snap changes
    """

    # pylint: disable=E1101
    def __init__(self, jenkins_server: JenkinsServerInfo, test_job_data: dict):
        self.mutex = threading.Lock()
        self.jenkins_server = jenkins.Jenkins(
            jenkins_server["server"],
            username=jenkins_server["username"],
            password=jenkins_server["password"],
        )
        self.jenkins_link = jenkins_server["server"]

        self._data = test_job_data
        self._snap_data = dump_sanp_data()
        self._review = True

    def snap_version(self, name, track, channel, arch):
        """
        Get revision of snap

        Args:
            name (str): snap name
            track (str): snap track
            channel (str): snap channel
            arch (str): snap architecture

        Returns:
            str: the revision of SNAP
        """
        try:
            return self._snap_data[name][track][channel][arch]["version"]
        except KeyError:
            return -1

    def snap_rev(self, name, track, channel, arch):
        """
        Get revision of snap

        Args:
            name (str): snap name
            track (str): snap track
            channel (str): snap channel
            arch (str): snap architecture

        Returns:
            str: the revision of SNAP
        """
        try:
            return self._snap_data[name][track][channel][arch]["revision"]
        except KeyError:
            return -1

    # pylint: disable=R0913, R0917, E1121
    def run_remote_job(self, job, job_token, timeout, extra_snap, under_test):
        """
        Trigger a testing job in Jenkins

        Args:
            job (str): job name
            eid: TO execution ID
            cilink: execution CI link
        """
        build_info = None
        parameters = {
            "d_grade": "true",
            "EXTRA_SNAPS": extra_snap,
            "under_test": under_test,
        }

        try:
            job_info = self.jenkins_server.get_job_info(job)
            self.jenkins_server.build_job(
                job, parameters=parameters, token=job_token
            )
        except (jenkins.JenkinsException, requests.exceptions.HTTPError):
            print("Failed to trigger {job}.")
            return

        next_build_number = job_info["nextBuildNumber"]

        while True:
            try:
                # try fetch job status
                # it could be not created yet and cause exception
                build_info = self.jenkins_server.get_build_info(
                    job, next_build_number
                )
                break

            except (jenkins.JenkinsException, requests.exceptions.HTTPError):
                time.sleep(3)

        started = time.time()
        while not build_info["result"] and time.time() - started < timeout:
            time.sleep(10)
            build_info = self.jenkins_server.get_build_info(
                job, next_build_number
            )

        if not build_info or not build_info["result"]:
            print(f"Test job {job} was Failed")

        elif build_info["result"] not in ["SUCCESS", "UNSTABLE"]:
            print(f'Test job {job} was {build_info["result"]}')

    # pylint: disable=R0912
    def start(self):
        """
        Start to monitor snap changes
        """
        threads = []
        # Handle snaps in yaml
        for data in self._data:
            snap_item = list(data.values())[0]
            rev = self.snap_rev(
                snap_item["name"],
                snap_item["track"],
                snap_item["channel"],
                snap_item["arch"],
            )

            version = self.snap_version(
                snap_item["name"],
                snap_item["track"],
                snap_item["channel"],
                snap_item["arch"],
            )

            if rev == -1 or version == -1:
                print(f'No snap: {snap_item["name"]} info from store')
                continue

            artefact = get_artefact_status(snap_item["name"], version, "snap")
            if artefact["status"] == "EMPTY":
                print("Artefact is not found, create new one")
                results = []
            elif artefact["status"] == "ERROR":
                continue

            else:
                print(
                    f'Artefact {artefact["id"]} status is {artefact["status"]}'
                )
                if artefact["status"] != "UNDECIDED":
                    print("Do Nothing")
                    continue

                results = get_exec_results(artefact["id"])

            print(
                f'snap: {snap_item["name"]}, '
                f'channel: {snap_item["channel"]}, '
                f"version: {version}, "
                f"revision: {rev}"
            )

            # handle projects under snap
            for proj in snap_item["projects"]:
                env_data = None
                if results:
                    for env in (next(iter(results)))["test_executions"]:
                        if proj["name"] == env["environment"]["name"]:
                            env_data = env
                            break

                if env_data:
                    if env_data["status"] in [
                        "COMPLETED",
                        "PASSED",
                        "ENDED_PREMATURELY",
                    ]:
                        print(f'The {proj["name"]} sanity task has been done')
                        continue

                # run platform sanity job
                under_test = ":".join(
                    [
                        "snap",
                        snap_item["name"],
                        snap_item["track"],
                        snap_item["channel"],
                        version,
                        rev,
                    ]
                )
                task = threading.Thread(
                    target=self.run_remote_job,
                    args=(
                        proj["job"],
                        proj["job_token"],
                        proj.get("timeout", 7200),
                        f'--snap={snap_item["name"]}={snap_item["track"]}/{snap_item["channel"]}',
                        under_test,
                    ),
                )
                task.start()
                threads.append(task)

            for x in threads:
                x.join()

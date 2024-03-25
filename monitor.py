#!/usr/bin/env python3
import yaml
import jenkins
import time
import threading
import re
import json

from typing import TypedDict
from jira import JIRA
from fetcher import dump_sanp_data


class JenkinsServerInfo(TypedDict):
    """
    The JenkinsServerInfo data type
    """
    server: str
    username: str
    password: str


class JiraServerInfo(TypedDict):
    """
    The JiraServerInfo data type
    """
    server: str
    username: str
    password: str


class Monitor:
    """
    The module to monitor snap changes
    """
    def __init__(self,
                 jenkins_server: JenkinsServerInfo,
                 jira_server: JiraServerInfo,
                 test_job_data: dict):
        self.mutex = threading.Lock()
        self.jenkins_server = jenkins.Jenkins(
            jenkins_server["server"],
            username=jenkins_server["username"],
            password=jenkins_server["password"])

        self.auth_jira = JIRA(
            server=jira_server["server"],
            basic_auth=(jira_server["username"], jira_server["password"]))

        self._data = test_job_data
        self._snap_data = dump_sanp_data()

    def sync_yaml(self):
        """
        Update monitor.yaml file
        """
        with open("monitor.yaml", 'w') as file:
            yaml.dump(self._data, file)

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
        return self._snap_data[name][track][channel][arch]["revision"]

    def run_remote_job(self, job, job_token, issue, assignee, timeout):
        """
        Trigger a testing job in Jenkins

        Args:
            job (str): job name
            issue (str): jira issue
            assignee (str): an Jira user for assignee
        """
        parameters = {"": ""}
        job_info = self.jenkins_server.get_job_info(job)
        next_build_number = job_info['nextBuildNumber']

        try:
            self.jenkins_server.build_job(job, parameters=parameters,
                                          token=job_token)
        except Exception:
            print(f'Failed to trigger test job {job}')
            return

        while True:
            try:
                # try fetch job status
                # it could be not created yet and cause exception
                build_info = self.jenkins_server.get_build_info(
                                                job, next_build_number)
                break

            except Exception:
                time.sleep(3)

        started = time.time()
        while not build_info["result"] and time.time() - started < timeout:
            time.sleep(10)
            build_info = self.jenkins_server.get_build_info(job,
                                                            next_build_number)

        if build_info["result"] in ["SUCCESS", "UNSTABLE"]:
            print(f'Test job {job} was {build_info["result"]}')
            log = self.jenkins_server.get_build_console_output(
                                                job, next_build_number)
            try:
                report = re.search(
                    r"(?P<url>https?://certification.canonical.com[^\s]+)",
                    log).group("url")
                self.auth_jira.add_comment(issue, report)
            except Exception:
                self.auth_jira.add_comment(issue, "Test Failed")

        self.auth_jira.assign_issue(issue, assignee)

    def start(self):
        """
        Start to monitor snap changes
        """
        threads = []
        # Handle snaps in yaml
        for data in self._data:
            snap_item = list(data.values())[0]
            snap = snap_item["name"]
            track = snap_item["track"]
            channel = snap_item["channel"]
            arch = snap_item["arch"]
            jira_id = snap_item["jira_id"]
            rev = self.snap_rev(snap, track, channel, arch)

            print(f"snap: {snap} channel: {channel} revision: {rev} ")

            # if revision not exist on jira under snap epic
            jira_issues = json.dumps(self.auth_jira.search_issues(
                "project=OST", startAt=0, json_result=True))
            if re.search(f"{snap}-rev{rev}", jira_issues) is None:
                new_revision = self.auth_jira.create_issue(
                    project="OST",
                    summary=f"{snap}-rev{rev}",
                    description='kernel monitor',
                    issuetype={'name': 'Task'},
                    parent={'key': jira_id})

                rev_key = (
                    new_revision.raw['fields']['votes']['self']
                ).split("/")[7]

                # handle projects under snap
                for proj in snap_item["projects"]:
                    new_platform = self.auth_jira.create_issue(
                        project="OST",
                        summary=proj["name"],
                        description='kernel monitor',
                        issuetype={'name': 'Sub-task'},
                        parent={'key': rev_key})
                    task = threading.Thread(
                        target=self.run_remote_job,
                        args=(proj["job"], proj["job_token"],
                              new_platform, proj["assignee"],
                              proj.get("timeout", 7200))
                    )
                    task.start()
                    threads.append(task)

        for x in threads:
            x.join()

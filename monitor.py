#!/usr/bin/env python3
import yaml
import jenkins
import time
import threading
import re
import json
from io import StringIO

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
        self._review = True

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
        try:
            return self._snap_data[name][track][channel][arch]["revision"]
        except KeyError:
            return -1

    def run_remote_job(self, job, job_token, issue, assignee, timeout, extra_snap):
        """
        Trigger a testing job in Jenkins

        Args:
            job (str): job name
            issue (str): jira issue
            assignee (str): an Jira user for assignee
        """
        parameters = {"d_grade": "true", "EXTRA_SNAPS": extra_snap}
        job_info = self.jenkins_server.get_job_info(job)
        next_build_number = job_info['nextBuildNumber']

        try:
            self.auth_jira.transition_issue(issue, "In Progress")
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

        log = self.jenkins_server.get_build_console_output(
                                                job, next_build_number)
        attachment = StringIO()
        attachment.write(log)
        self.auth_jira.add_attachment(issue=issue, attachment=attachment, filename=f'{next_build_number}_log.txt')

        if build_info["result"] in ["SUCCESS", "UNSTABLE"]:
            print(f'Test job {job} was {build_info["result"]}')
            try:
                report = re.search(
                    r"(?P<url>https?://certification.canonical.com[^\s]+)",
                    log).group("url")
                self.auth_jira.add_comment(issue, f"{next_build_number} Passe {report}")
                self.auth_jira.transition_issue(issue, "In Review")
            except Exception:
                print(f'Test job {job} was success, but report not found')
                self._review = False
                self.auth_jira.add_comment(issue, f"{next_build_number} build Successfully, but report not found")
        elif not build_info["result"]:
            print(f'Test job {job} was Timeout')
            self._review = False
            self.auth_jira.add_comment(issue, f"{next_build_number} Test timeout")
        else:
            print(f'Test job {job} was Failed')
            self._review = False
            self.auth_jira.add_comment(issue, f"{next_build_number} Test Failed")

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

            if rev == -1:
                print(f"No snap: {snap} info from store")
                continue

            print(f"snap: {snap} channel: {channel} revision: {rev} ")

            # if revision not exist on jira under snap epic
            jira_resp = self.auth_jira.search_issues(
                f"project=OST and summary ~ {snap}-rev{rev}",
                startAt=0,
                json_result=True
            )
            jira_issues = jira_resp["issues"]

            if not jira_issues:
                new_revision = self.auth_jira.create_issue(
                    project="OST",
                    summary=f"{snap}-rev{rev}",
                    description='kernel monitor',
                    issuetype={'name': 'Task'},
                    parent={'key': jira_id})

                self.auth_jira.transition_issue(new_revision, "In Progress")
                rev_key = new_revision.key
            else:
                rev_key = jira_issues[0]["key"]
                issue_status = jira_issues[0]["fields"]["status"]["name"]

                if issue_status.lower() in [
                    "done", "to be deployed", "in review", "rejected"
                ]:
                    print(f"The {rev_key} sanity task has been done")
                    continue



            # handle projects under snap
            for proj in snap_item["projects"]:
                # create platform jira card
                jira_resp = self.auth_jira.search_issues(
                    f'project=OST and summary ~ {proj["name"]}-rev{rev}',
                    startAt=0, json_result=True
                )
                jira_issues = jira_resp["issues"]
                if not jira_issues:
                    platform = self.auth_jira.create_issue(
                        project="OST",
                        summary=f'{proj["name"]}-rev{rev}',
                        description='kernel monitor',
                        issuetype={'name': 'Sub-task'},
                        parent={'key': rev_key})

                    issue_status = platform.fields.status.name
                else:
                    platform = jira_issues[0]["key"]
                    issue_status = jira_issues[0]["fields"]["status"]["name"]

                    if issue_status.lower() in [
                        "done", "in review", "rejected", "untriaged"
                    ]:
                        print(f"The {platform} sanity task has been done")
                        continue

                # run platform sanity job
                task = threading.Thread(
                    target=self.run_remote_job,
                    args=(proj["job"], proj["job_token"],
                          platform, proj["assignee"],
                          proj.get("timeout", 7200),
                          f"--snap={snap}={track}/{channel}")
                )
                task.start()
                threads.append(task)

            for x in threads:
                x.join()
            if self._review:
                self.auth_jira.transition_issue(rev_key, "In Review")

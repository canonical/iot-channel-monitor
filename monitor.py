#!/usr/bin/env python3

import yaml
import requests
import sys
import yaml
import jenkins
import time
import threading
import re
import json
import os
from parser import DataParser

from jira import JIRA
from fetcher import dump_sanp_data

class monitor:

    def __init__(self):
        self.mutex = threading.Lock()
        self.jenkins_server = jenkins.Jenkins(os.getenv('JENKINS_SERVER'), username = os.getenv('JENKINS_USERNAME'), password = os.getenv('JENKINS_TOKEN'))
        self.auth_jira = JIRA(server = os.getenv('JIRA_SERVER'), basic_auth=( os.getenv('JIRA_ACCOUNT'), os.getenv('JIRA_TOKEN')))

        self._snap_data = dump_sanp_data()
        data_parser = DataParser("monitor.yaml")
        self._data = data_parser.data

    def sync_yaml(self):
        with open("monitor.yaml", 'w') as file:
            yaml.dump(self._data, file)

    def snap_rev(self, name, track, channel, arch):
        return  self._snap_data[name][track][channel][arch]["revision"]

    def run_remote_job(self, job, issue, assignee):
        parameters={"":""}
        next_build_number = self.jenkins_server.get_job_info(job)['nextBuildNumber']

        try:
            self.jenkins_server.build_job(job, parameters=parameters, token=os.getenv('JOB_TOKEN'))
        except Exception as e:
            print(f'Failed to trigger test job {job}')
            return

        while True:
            try:
                # try fetch job status, it could be not created yet and cause exception
                build_info = self.jenkins_server.get_build_info(job, next_build_number)
                break

            except Exception:
                time.sleep(3)

        started = time.time()
        while not build_info["result"]  and time.time() - started < 3600:
            time.sleep(10)
            build_info = self.jenkins_server.get_build_info(job, next_build_number)

        if build_info["result"] == "SUCCESS" or build_info["result"] == "UNSTABLE":
            print(f'Test job {job} was {build_info["result"]}')
            log = self.jenkins_server.get_build_console_output(job, next_build_number)
            try:
                report = re.search("(?P<url>https?://certification.canonical.com[^\s]+)", log).group("url")
                self.auth_jira.add_comment(issue, report)
            except Exception as e:
                self.auth_jira.add_comment(issue, "Test Failed")

        self.auth_jira.assign_issue(issue, assignee)

    def start(self):
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
            # if revision not exist on jira under snap epic
            jira_issues = json.dumps(self.auth_jira.search_issues(
                "project=OST", startAt = 0, json_result=True))
            if re.search(f"{snap}-rev{rev}", jira_issues) is None:
                new_revision = self.auth_jira.create_issue(
                    project="OST" , 
                    summary=f"{snap}-rev{rev}",
                    description='kernel monitor', 
                    issuetype={'name': 'Task'}, 
                    parent={'key': jira_id})

                rev_key = (new_revision.raw['fields']['votes']['self']).split("/")[7]

                # handle projects under snap
                for proj in snap_item["projects"]:
                    new_platform = self.auth_jira.create_issue(
                        project="OST", 
                        summary=proj["name"],
                        description='kernel monitor', 
                        issuetype={'name': 'Sub-task'}, 
                        parent={'key': rev_key})
                    task = threading.Thread(target=self.run_remote_job, args=(
                        proj["job"],
                        new_platform,
                        proj["assignee"]))
                    task.start()
                    threads.append(task)

        for x in threads:
            x.join()


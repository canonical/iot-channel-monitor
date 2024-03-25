import os
from monitor import Monitor, JenkinsServerInfo, JiraServerInfo
from job_parser import DataParser


def main():
    """
    Main function to start channel monitor
    """
    jenkins_info = JenkinsServerInfo(
        server=os.getenv('JENKINS_SERVER'),
        username=os.getenv('JENKINS_USERNAME'),
        password=os.getenv('JENKINS_TOKEN')
    )
    jira_info = JiraServerInfo(
        server=os.getenv('JIRA_SERVER'),
        username=os.getenv('JIRA_ACCOUNT'),
        password=os.getenv('JIRA_TOKEN')
    )
    data_parser = DataParser("monitor.yaml")

    mon = Monitor(jenkins_info, jira_info, data_parser.data)
    mon.start()


if __name__ == "__main__":
    main()

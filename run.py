""" Channel Monitor entry point"""
import os
from monitor import Monitor, JenkinsServerInfo
from job_parser import DataParser


def main():
    """
    Main function to start channel monitor
    """
    jenkins_info = JenkinsServerInfo(
        server=os.getenv("JENKINS_SERVER"),
        username=os.getenv("JENKINS_USERNAME"),
        password=os.getenv("JENKINS_TOKEN"),
    )
    data_parser = DataParser("monitor.yaml")

    mon = Monitor(jenkins_info, data_parser.data)
    mon.start()


if __name__ == "__main__":
    main()
